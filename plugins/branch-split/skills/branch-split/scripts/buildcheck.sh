#!/bin/bash
# usage: buildcheck.sh <spec.json>
# Checks out every branch state in the scratch clone (never the user's repo) and:
#  - runs $BUILD_CMD if set, otherwise a Metro release bundle for Android and iOS (React Native);
#  - lints the JS/TS files the branch touched with eslint no-undef / react/jsx-no-undef.
# Logs go to <out>/build/. Exit 1 if anything failed, 3 if node_modules is missing.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SPEC=${1:?usage: buildcheck.sh <spec.json>}
INFO=$(python3 -I "$HERE/split.py" buildinfo "$SPEC") || exit $?
REPO=$(sed -n 1p <<<"$INFO"); C=$(sed -n 2p <<<"$INFO"); BASE_TREE=$(sed -n 3p <<<"$INFO")
OUT=$(dirname "$C")/build
rm -rf "$OUT"; mkdir -p "$OUT"

if [ ! -d "$C/node_modules" ]; then
  [ -d "$REPO/node_modules" ] || { echo "No node_modules in $REPO. Run the install there first, or skip the build check."; exit 3; }
  echo "Copying node_modules into the scratch clone (APFS clone where possible)..."
  cp -cR "$REPO/node_modules" "$C/node_modules" 2>/dev/null || cp -R "$REPO/node_modules" "$C/node_modules"
fi

FAILED=0
while read -r label tree; do
  git -C "$C" read-tree -u --reset "$tree"
  git -C "$C" clean -fdq -e node_modules
  if [ -n "${BUILD_CMD:-}" ]; then
    (cd "$C" && bash -c "$BUILD_CMD") > "$OUT/$label-build.log" 2>&1 \
      && echo "OK   $label build" || { echo "FAIL $label build"; tail -15 "$OUT/$label-build.log"; FAILED=1; }
  elif [ -d "$C/node_modules/react-native" ]; then
    entry=index.js; [ -f "$C/index.ts" ] && entry=index.ts
    for plat in android ios; do
      (cd "$C" && npx react-native bundle --platform $plat --dev false --entry-file $entry \
        --bundle-output "$OUT/$label-$plat.js" --assets-dest "$OUT/assets-$label-$plat" --reset-cache) \
        > "$OUT/$label-$plat.log" 2>&1 \
        && echo "OK   $label $plat" || { echo "FAIL $label $plat"; tail -15 "$OUT/$label-$plat.log"; FAILED=1; }
    done
  else
    echo "SKIP $label build (not React Native; set BUILD_CMD to run a build)"
  fi
  files=()
  while IFS= read -r f; do [ -n "$f" ] && files+=("$f"); done < <(git -C "$C" diff --name-only --diff-filter=AMR "$BASE_TREE" "$tree" -- '*.js' '*.jsx' '*.ts' '*.tsx')
  if [ "${#files[@]}" -gt 0 ] && [ -x "$C/node_modules/.bin/eslint" ]; then
    (cd "$C" && ESLINT_USE_FLAT_CONFIG=false npx eslint --no-eslintrc --parser @typescript-eslint/parser \
      --parser-options ecmaVersion:2022,sourceType:module,ecmaFeatures:{jsx:true} --env es2022,node,browser \
      --plugin react --rule 'no-undef:error' --rule 'react/jsx-no-undef:error' --global __DEV__,JSX,React "${files[@]}") \
      > "$OUT/$label-lint.log" 2>&1 \
      && echo "LINT OK     $label" || { echo "LINT ISSUES $label (may predate this change; compare with the base)"; grep -E "error" "$OUT/$label-lint.log" | head -10; }
  fi
done < <(sed -n '4,$p' <<<"$INFO")
echo "Logs: $OUT"
exit $FAILED

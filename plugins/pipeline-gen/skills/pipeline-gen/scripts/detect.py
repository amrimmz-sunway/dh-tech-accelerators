#!/usr/bin/env python3
"""Detect a repo's stack and build commands. Read-only. Prints one JSON object.

Usage: python3 -I detect.py <repo> [--path SUBDIR]

Exit codes: 0 ok, 2 usage / ambiguous (pass --path), 3 not a directory.
Stdlib only. Shared copy: keep plugins/*/scripts/detect.py identical.
"""
import json
import os
import re
import sys

SKIP_DIRS = {"node_modules", ".git", "bin", "obj", "dist", "build", "Pods", "vendor", ".angular", "www", "platforms", "plugins"}
NPM_PLACEHOLDER_TEST = re.compile(r"no test specified", re.I)


def die(code, msg):
    print(msg, file=sys.stderr)
    sys.exit(code)


def walk(root, max_depth):
    root_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.count(os.sep) - root_depth
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        if depth >= max_depth:
            dirnames[:] = []
        yield dirpath, filenames


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def deps_all(pkg):
    deps = {}
    deps.update(pkg.get("dependencies") or {})
    deps.update(pkg.get("devDependencies") or {})
    return deps


def node_stack(pkg):
    deps = deps_all(pkg)
    if "react-native" in deps:
        return "react-native", deps.get("react-native")
    if "@ionic/angular" in deps:
        return "ionic-angular", deps.get("@angular/core")
    if "@angular/core" in deps:
        return "angular", deps.get("@angular/core")
    for fw in ("express", "fastify", "koa", "@nestjs/core", "restify", "@hapi/hapi"):
        if fw in deps:
            return "node-express", deps.get(fw)
    if "start" in (pkg.get("scripts") or {}) or pkg.get("main"):
        return "node-express", None
    return "unknown", None


def node_version_hint(proj, pkg):
    for name in (".nvmrc", ".node-version"):
        txt = read_text(os.path.join(proj, name)).strip()
        if txt:
            return txt.lstrip("v"), name
    eng = ((pkg.get("engines") or {}).get("node") or "").strip()
    if eng:
        m = re.search(r"(\d+)(?:\.\d+)?(?:\.\d+)?", eng)
        if m:
            return m.group(1), "package.json engines (" + eng + ")"
    # Fall back to the image production builds from: FROM [registry/]node:<version>
    for root in (proj, repo_root(proj)):
        for dirpath, files in walk(root, 3):
            for f in files:
                if not f.startswith("Dockerfile"):
                    continue
                m = re.search(r"^FROM\s+\S*?node:(\d+(?:\.\d+){0,2})", read_text(os.path.join(dirpath, f)), re.M)
                if m:
                    return m.group(1), os.path.relpath(os.path.join(dirpath, f), root) + " (FROM node:" + m.group(1) + ")"
    return None, None


def repo_root(path):
    cur = path
    while cur != os.path.dirname(cur):
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        cur = os.path.dirname(cur)
    return path


def package_manager(proj):
    if os.path.exists(os.path.join(proj, "pnpm-lock.yaml")):
        return "pnpm", "pnpm-lock.yaml"
    if os.path.exists(os.path.join(proj, "yarn.lock")):
        berry = os.path.exists(os.path.join(proj, ".yarnrc.yml"))
        return ("yarn-berry" if berry else "yarn"), "yarn.lock"
    if os.path.exists(os.path.join(proj, "package-lock.json")):
        return "npm", "package-lock.json"
    if os.path.exists(os.path.join(proj, "npm-shrinkwrap.json")):
        return "npm", "npm-shrinkwrap.json"
    return "npm", None


def detect_node(repo, proj, pkg):
    stack, fw_version = node_stack(pkg)
    scripts = pkg.get("scripts") or {}
    test = scripts.get("test")
    if test and NPM_PLACEHOLDER_TEST.search(test):
        test = None
    pm, lockfile = package_manager(proj)
    nv, nv_source = node_version_hint(proj, pkg)
    rel = os.path.relpath(proj, repo)
    out = {
        "stack": stack,
        "framework_version": fw_version,
        "project_dir": "." if rel == "." else rel,
        "package_manager": pm,
        "lockfile": lockfile,
        "node_version": nv,
        "node_version_source": nv_source,
        "scripts": {
            "test": "test" if test else None,
            "lint": "lint" if scripts.get("lint") else None,
            "build": "build" if scripts.get("build") else None,
        },
        # The actual commands, so callers can see e.g. whether "test" lists files explicitly.
        "script_commands": {k: scripts.get(k) for k in ("test", "lint", "build") if scripts.get(k)},
        "typescript": os.path.exists(os.path.join(proj, "tsconfig.json")),
        "karma": os.path.exists(os.path.join(proj, "karma.conf.js")) or "karma" in deps_all(pkg),
        "warnings": [],
    }
    if stack == "react-native":
        android = os.path.join(proj, "android")
        ios = os.path.join(proj, "ios")
        out["android_dir"] = os.path.relpath(android, repo) if os.path.exists(os.path.join(android, "gradlew")) else None
        ws = sorted(f for f in os.listdir(ios) if f.endswith(".xcworkspace")) if os.path.isdir(ios) else []
        out["ios_workspace"] = os.path.relpath(os.path.join(ios, ws[0]), repo) if ws else None
        out["ios_scheme"] = ws[0][: -len(".xcworkspace")] if ws else None
        out["gemfile"] = os.path.exists(os.path.join(proj, "Gemfile"))
        app_gradle = read_text(os.path.join(android, "app", "build.gradle"))
        if "google-services" in app_gradle and not os.path.exists(os.path.join(android, "app", "google-services.json")):
            out["warnings"].append(
                "android/app applies google-services but google-services.json is not in the repo: "
                "the Android build job will fail until CI is given that file"
            )
        if not out["android_dir"]:
            out["warnings"].append("no android/gradlew found: Android build job will be skipped")
    if nv is None:
        out["warnings"].append("no Node version in .nvmrc/.node-version/engines: ask which version production runs")
    return out


def detect_dotnet(repo, sln):
    proj_dir = os.path.dirname(sln)
    frameworks = set()
    test_projects = []
    sdk_style = False
    for dirpath, files in walk(proj_dir, 3):
        for f in files:
            if not f.endswith(".csproj"):
                continue
            txt = read_text(os.path.join(dirpath, f))
            frameworks.update(re.findall(r"<TargetFrameworkVersion>\s*([^<\s]+)", txt))
            for m in re.findall(r"<TargetFrameworks?>\s*([^<]+)", txt):
                sdk_style = True
                frameworks.update(x.strip() for x in m.split(";") if x.strip())
            if re.search(r"tests?\.csproj$", f, re.I):
                test_projects.append(os.path.relpath(os.path.join(dirpath, f), repo))
    legacy = any(fw.startswith("v4") or fw.startswith("v3") for fw in frameworks)
    warnings = []
    old = sorted(fw for fw in frameworks if re.match(r"v(3\.|4\.[0-5](\.|$)|4\.6(\.[01])?$)", fw))
    if old:
        warnings.append(
            "projects target " + ", ".join(old) + ": GitHub's windows runners only ship .NET Framework 4.6.2+ "
            "targeting packs, so msbuild will fail on those projects until they are retargeted or reference "
            "the Microsoft.NETFramework.ReferenceAssemblies NuGet package"
        )
    if not test_projects:
        warnings.append("no *Tests.csproj found: the pipeline will build only")
    return {
        "stack": "dotnet-framework" if legacy or not sdk_style else "dotnet-sdk",
        "project_dir": "." if os.path.relpath(proj_dir, repo) == "." else os.path.relpath(proj_dir, repo),
        "solution": os.path.relpath(sln, repo),
        "target_frameworks": sorted(frameworks),
        "test_projects": sorted(test_projects),
        "packages_config": any(
            "packages.config" in files for _, files in walk(proj_dir, 3)
        ),
        "warnings": warnings,
    }


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        die(2, __doc__.strip())
    repo = os.path.abspath(argv[0])
    sub = None
    if len(argv) >= 3 and argv[1] == "--path":
        sub = argv[2]
    elif len(argv) != 1:
        die(2, "usage: detect.py <repo> [--path SUBDIR]")
    if not os.path.isdir(repo):
        die(3, "not a directory: " + repo)
    base = os.path.abspath(os.path.join(repo, sub)) if sub else repo
    if not base.startswith(repo):
        die(2, "--path must stay inside the repo")

    pkgs, slns = [], []
    for dirpath, files in walk(base, 3):
        if "package.json" in files:
            pkgs.append(os.path.join(dirpath, "package.json"))
        slns.extend(os.path.join(dirpath, f) for f in files if f.endswith(".sln"))

    # Prefer a manifest at the chosen root; otherwise require exactly one candidate.
    root_pkg = os.path.join(base, "package.json")
    if os.path.exists(root_pkg) and read_json(root_pkg) is not None:
        chosen = ("node", root_pkg)
    elif slns and len(slns) == 1:
        chosen = ("dotnet", slns[0])
    elif len(pkgs) == 1 and not slns:
        chosen = ("node", pkgs[0])
    elif not pkgs and not slns:
        print(json.dumps({"stack": "unknown", "reason": "no package.json or .sln within 3 levels"}, indent=2))
        return 0
    else:
        cands = [os.path.relpath(os.path.dirname(p), repo) for p in pkgs + slns]
        print(json.dumps({"stack": "ambiguous", "candidates": sorted(set(cands))}, indent=2))
        die(2, "several projects found; re-run with --path <one of the candidates>")

    existing = []
    wf = os.path.join(repo, ".github", "workflows")
    if os.path.isdir(wf):
        existing = sorted(f for f in os.listdir(wf) if f.endswith((".yml", ".yaml")))

    if chosen[0] == "node":
        pkg = read_json(chosen[1]) or {}
        out = detect_node(repo, os.path.dirname(chosen[1]), pkg)
    else:
        out = detect_dotnet(repo, chosen[1])
    out["existing_workflows"] = existing
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

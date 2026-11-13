#!/usr/bin/env python3
"""Find existing units to copy patterns from, plus the files where new units get registered.
Read-only. Prints one JSON object.

Usage: python3 -I find-exemplars.py <repo> --detect DETECT.json [--like STEM] [--max 5]

A "unit" is one feature spread over several roles, for example
routes/user.js + controllers/userController.js + services/userService.js.
The exemplar is the feature stem present in the most roles (ties: medium-sized files).

Exit codes: 0 ok, 2 usage / unsupported stack / --like not found, 3 missing file.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

SKIP_DIRS = {"node_modules", ".git", "bin", "obj", "dist", "build", "Pods", "vendor", ".angular", "www",
             "platforms", "plugins", "android", "ios", "coverage", "packages", "e2e", "assets", "Content", "Scripts", "fonts"}

# (role, regex on the path relative to the project dir). First match wins.
RULES = {
    "node-express": [
        ("test", r"(^|/)(tests?|__tests__|spec)/.*\.(js|ts)$|\.(test|spec)\.(js|ts)$"),
        ("route", r"(^|/)(routes?|routers?)/.*\.(js|ts)$|\.routes?\.(js|ts)$"),
        ("controller", r"(^|/)controllers?/.*\.(js|ts)$|[Cc]ontroller\.(js|ts)$"),
        ("service", r"(^|/)services?/.*\.(js|ts)$|[Ss]ervice\.(js|ts)$"),
        ("model", r"(^|/)(models?|entities|schemas?)/.*\.(js|ts)$"),
        ("validation", r"(^|/)(validations?|validators?|schemas?)/.*\.(js|ts)$"),
        ("repository", r"(^|/)(repositor(y|ies)|dao|db|queries)/.*\.(js|ts)$"),
    ],
    "react-native": [
        ("test", r"(^|/)__tests__/.*\.(js|jsx|ts|tsx)$|\.(test|spec)\.(js|jsx|ts|tsx)$"),
        ("screen", r"(^|/)(screens?|Screens?|pages?|Pages?|views?|Views?|containers?)/.*\.(js|jsx|ts|tsx)$|Screen\.(js|jsx|ts|tsx)$"),
        ("screen", r"(^|/)(app|features?|modules?)/[^/]+/.*\.(js|jsx|ts|tsx)$"),
        ("api", r"(^|/)(api|API|services?|Services?)/.*\.(js|ts)$"),
        ("state", r"(^|/)(redux|store|slices?|reducers?|actions|context|hooks)/.*\.(js|ts|tsx)$"),
        ("component", r"(^|/)(components?|Components?)/.*\.(js|jsx|ts|tsx)$"),
    ],
    "angular": [
        ("test", r"\.spec\.ts$"),
        ("routing", r"-routing\.module\.ts$|\.routes\.ts$"),
        ("page", r"\.page\.ts$"),
        ("component", r"\.component\.ts$"),
        ("service", r"\.service\.ts$"),
        ("module", r"\.module\.ts$"),
        ("model", r"\.(model|interface|types?)\.ts$|(^|/)models?/.*\.ts$"),
    ],
    "dotnet-framework": [
        ("test", r"(^|/)[^/]*\.Tests?/.*\.cs$|(^|/)Tests?/.*\.cs$|Tests?\.cs$"),
        ("controller", r"Controller\.cs$"),
        ("service", r"(^|/)Services?/.*\.cs$|Service\.cs$"),
        ("repository", r"(^|/)Repositor(y|ies)/.*\.cs$|Repository\.cs$"),
        ("model", r"(^|/)(Models?|ViewModels?|Entities|DTOs?)/.*\.cs$"),
        ("view", r"Views/.*\.cshtml$"),
    ],
}
RULES["ionic-angular"] = RULES["angular"]

ROLE_WORDS = re.compile(
    r"(controller|service|services|routes?|router|screen|page|component|module|routing|model|"
    r"repository|repo|validation|validator|schema|api|slice|reducer|spec|test|viewmodel|dto|entity|index)$", re.I)

PRIMARY = {
    "node-express": {"route", "controller"},
    "react-native": {"screen"},
    "angular": {"component", "page"},
    "ionic-angular": {"page", "component"},
    "dotnet-framework": {"controller"},
}
FEATURE_DIR = {
    "react-native": re.compile(r"(?:^|/)(?:app|features?|modules?|screens?|Screens?|pages?|Pages?)/([^/]+)/"),
    "node-express": re.compile(r"(?:^|/)(?:features?|modules?|components)/([^/]+)/"),
}
GENERIC_DIRS = {"screens", "components", "services", "api", "utils", "navigation", "navigator", "redux", "store",
                "hooks", "context", "assets", "theme", "types", "lib", "layouts", "common", "shared", "helpers",
                "config", "constants", "styles", "images", "models", "routes", "controllers", "pages", "modules",
                "controller", "service", "model", "route", "router", "screen", "component", "page", "module",
                "validator", "validators", "repository", "repositories", "middleware", "middlewares", "init"}

# Stems that name shared plumbing, not a feature; never offered as exemplars.
STEM_STOP = {"api", "apis", "service", "services", "config", "utils", "util", "helpers", "helper", "index", "app",
             "main", "navigation", "navigator", "navigationref", "theme", "colors", "constants", "types", "styles",
             "store", "root", "rest", "error", "errors", "logging", "logger", "cache", "base", "common", "shared"}
# A file "uses the API" if it imports the HTTP layer: api/services modules, axios, HttpClient, HttpClient-like.
USES_API = re.compile(
    r"""(from\s+['"][^'"]*(/api|/API|/services?/|/Services?/|api['"]|Api['"])|require\(\s*['"][^'"]*(api|service)[^'"]*['"]"""
    r"""|\baxios\b|\bHttpClient\b|\bfetch\(|HttpClient\(|\.(Query|Execute)(Async)?\(|DbContext|SqlCommand|MySqlCommand)""",
    re.I)

REGISTRATION = {
    "node-express": [r"\bapp\.use\(\s*['\"`/]"],
    "react-native": [r"create(Native)?StackNavigator|createBottomTabNavigator|createDrawerNavigator|<Stack\.Screen|<Tab\.Screen"],
    "angular": [r"\bRoutes\s*=\s*\[|RouterModule\.for(Root|Child)|provideRouter\("],
    "dotnet-framework": [r"routes\.MapRoute|MapHttpRoute|RegisterType<|\.RegisterType\(|Bind<|builder\.Register|services\.Add(Scoped|Transient|Singleton)"],
}
REGISTRATION["ionic-angular"] = REGISTRATION["angular"]
EXTS = {
    "node-express": (".js", ".ts", ".mjs", ".cjs"),
    "react-native": (".js", ".jsx", ".ts", ".tsx"),
    "angular": (".ts",),
    "ionic-angular": (".ts",),
    "dotnet-framework": (".cs", ".cshtml"),
}


def die(code, msg):
    print(msg, file=sys.stderr)
    sys.exit(code)


def stem_of(path, stack):
    base = os.path.basename(path)
    if stack == "dotnet-framework" and base.endswith(".cshtml"):
        return os.path.basename(os.path.dirname(path)).lower()  # Views/<Feature>/Index.cshtml
    if stack in FEATURE_DIR:
        # Feature folders: src/app/<feature>/main.tsx -> <feature>
        for m in FEATURE_DIR[stack].finditer(path):
            if m.group(1).lower() not in GENERIC_DIRS:
                return re.sub(r"[-_ ]", "", m.group(1)).lower()
    name = base.split(".")[0]
    if name.lower() == "index":
        name = os.path.basename(os.path.dirname(path))
    name = re.sub(r"[-_ ]", "", name)
    prev = None
    while prev != name:
        prev = name
        name = ROLE_WORDS.sub("", name) or name
    return name.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--detect", required=True)
    ap.add_argument("--like")
    ap.add_argument("--max", type=int, default=5)
    a = ap.parse_args()

    repo = os.path.realpath(a.repo)
    try:
        d = json.load(open(a.detect, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        die(3, "cannot read detect JSON: %s" % exc)
    stack = d.get("stack")
    if stack not in RULES:
        die(2, "unsupported stack %r. Supported: %s" % (stack, ", ".join(sorted(RULES))))
    proj = os.path.realpath(os.path.join(repo, d.get("project_dir") or "."))
    rules = [(r, re.compile(rx)) for r, rx in RULES[stack]]
    reg_rx = [re.compile(rx) for rx in REGISTRATION[stack]]

    by_stem = defaultdict(lambda: defaultdict(list))
    registration = []
    shared = []
    migrations = set()
    tests_seen = False
    csproj = []
    for dirpath, dirnames, filenames in os.walk(proj):
        dirnames[:] = sorted(x for x in dirnames if x not in SKIP_DIRS and not x.startswith("."))
        for f in filenames:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, proj).replace(os.sep, "/")
            if f.endswith(".csproj"):
                csproj.append(rel)
            if f.endswith(".sql") or re.search(r"(^|/)migrations?/", rel):
                migrations.add(os.path.dirname(rel) or ".")
            if not f.endswith(EXTS[stack]) or f.endswith((".d.ts", ".min.js")):
                continue
            role = next((r for r, rx in rules if rx.search(rel)), None)
            try:
                size = os.path.getsize(full)
                text = open(full, encoding="utf-8", errors="replace").read(200000) if size < 400000 else ""
            except OSError:
                continue
            uses_api = bool(USES_API.search(text))
            if any(rx.search(text) for rx in reg_rx):
                registration.append(rel)
            if role is None:
                continue
            if role == "test":
                tests_seen = True
            if role in ("api", "service") and stack == "react-native":
                shared.append(rel)
            stem = stem_of(rel, stack)
            if len(stem) < 2 or stem in STEM_STOP:
                continue
            by_stem[stem][role].append({"path": rel, "bytes": size, "uses_api": uses_api})

    def score(item):
        stem, roles = item
        non_test = [r for r in roles if r != "test"]
        sizes = sorted(x["bytes"] for r in roles.values() for x in r)
        median = sizes[len(sizes) // 2] if sizes else 0
        # has a primary role (screen/controller/...) first; then more roles; then has-test;
        # then medium size (closest to 4 KB)
        primary = int(bool(PRIMARY[stack] & set(roles)))
        fetches = int(any(x["uses_api"] for r in roles.values() for x in r))
        return (-primary, -len(non_test), -fetches, -int("test" in roles), abs(median - 4000))

    ranked = sorted(by_stem.items(), key=score)
    if a.like:
        match = [x for x in ranked if x[0] == a.like.lower().replace("-", "").replace("_", "")]
        if not match:
            die(2, "no unit named %r found; candidates: %s" % (a.like, ", ".join(s for s, _ in ranked[:15])))
        ranked = match + [x for x in ranked if x not in match]

    def pack(stem, roles):
        files = []
        for role in dict.fromkeys(r for r, _ in RULES[stack]):
            for x in sorted(roles.get(role, []), key=lambda y: (len(y["path"]), y["path"]))[:2]:
                files.append({"role": role, "path": x["path"], "bytes": x["bytes"], "uses_api": x["uses_api"]})
        return {"stem": stem, "roles": sorted(roles),
                "fetches_data": any(f["uses_api"] for f in files), "files": files}

    out = {
        "stack": stack,
        "project_dir": d.get("project_dir") or ".",
        "exemplar": pack(*ranked[0]) if ranked else None,
        "other_candidates": [pack(s, r) for s, r in ranked[1 : a.max + 1]],
        "shared_modules": sorted(set(shared))[:8],
        "registration_files": sorted(set(registration))[:15],
        "migration_dirs": sorted(migrations)[:5],
        "has_tests": tests_seen,
        "test_script": (d.get("scripts") or {}).get("test"),
    }
    if stack == "dotnet-framework":
        out["csproj_files"] = sorted(csproj)
    if not ranked:
        out["note"] = "no multi-role units found; ask the user to point at one existing feature to copy (--like)"
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

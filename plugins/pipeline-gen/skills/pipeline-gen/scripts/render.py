#!/usr/bin/env python3
"""Render a CI workflow from detect.py output. Deterministic; no network.

Usage:
  python3 -I render.py --repo REPO --detect DETECT.json
                       [--node-version X] [--java-version 17]
                       [--branches main,develop] [--sonar] [--ios] [--no-android]
                       [--typecheck] [--no-audit]
                       [--out .github/workflows/ci.yml] [--force] [--stdout]

Exit codes: 0 written, 2 usage/guardrail (missing input, unsupported stack,
target exists without --force, path outside repo), 3 missing file.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
TEMPLATES = os.path.join(SKILL, "templates")
PLUGIN_JSON = os.path.join(SKILL, "..", "..", ".claude-plugin", "plugin.json")
TOKEN = re.compile(r"\[\[([^\[\]]+)\]\]")
NODE_STACKS = {"node-express", "angular", "ionic-angular", "react-native"}
TEMPLATE_FOR = {
    "node-express": "node-express.yml",
    "angular": "angular.yml",
    "ionic-angular": "angular.yml",
    "react-native": "react-native.yml",
    "dotnet-framework": "dotnet-framework.yml",
}


def die(code, msg):
    print(msg, file=sys.stderr)
    sys.exit(code)


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        die(3, "cannot read %s: %s" % (path, exc))


def expand_includes(text):
    out = []
    for line in text.splitlines():
        m = re.fullmatch(r"\s*\[\[INCLUDE:([\w.-]+)\]\]\s*", line)
        out.append(load(os.path.join(TEMPLATES, m.group(1))).rstrip("\n") if m else line)
    return "\n".join(out) + "\n"


def apply_conditionals(text, flags):
    out, stack = [], []  # stack of (this_branch_active, parent_active)
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("#@if "):
            parent = all(a for a, _ in stack)
            stack.append((parent and bool(flags.get(s[5:].strip())), parent))
        elif s == "#@else":
            if not stack:
                die(2, "template error: #@else without #@if (line %d)" % n)
            active, parent = stack.pop()
            stack.append((parent and not active, parent))
        elif s == "#@endif":
            if not stack:
                die(2, "template error: #@endif without #@if (line %d)" % n)
            stack.pop()
        elif all(a for a, _ in stack):
            out.append(line)
    if stack:
        die(2, "template error: unclosed #@if")
    return "\n".join(out) + "\n"


def substitute(text, values, pins):
    def repl(m):
        key = m.group(1)
        if key.startswith("PIN:"):
            name = key[4:]
            if name not in pins:
                die(2, "template uses an unpinned action: " + name)
            return "%s # %s" % (pins[name]["sha"], pins[name]["tag"])
        if key not in values or values[key] is None:
            die(2, "template needs a value for " + key)
        return str(values[key])

    return TOKEN.sub(repl, text)


def pm_commands(pm, lockfile):
    if pm == "pnpm":
        return {"install": "pnpm install --frozen-lockfile", "run": "pnpm", "argsep": "", "cache": "pnpm", "corepack": True, "audit": "pnpm audit --prod --audit-level high"}
    if pm == "yarn-berry":
        return {"install": "yarn install --immutable", "run": "yarn", "argsep": "", "cache": "yarn", "corepack": True, "audit": None}
    if pm == "yarn":
        return {"install": "yarn install --frozen-lockfile", "run": "yarn", "argsep": "", "cache": "yarn", "corepack": False, "audit": "yarn audit --groups dependencies --level high"}
    return {
        "install": "npm ci" if lockfile else "npm install --no-audit --no-fund",
        "run": "npm run",
        "argsep": "-- ",
        "cache": "npm",
        "corepack": False,
        "audit": "npm audit --omit=dev --audit-level=high",
    }


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--detect", required=True)
    ap.add_argument("--node-version")
    ap.add_argument("--java-version", default="17")
    ap.add_argument("--branches", default="main,develop")
    ap.add_argument("--sonar", action="store_true")
    ap.add_argument("--ios", action="store_true")
    ap.add_argument("--no-android", action="store_true")
    ap.add_argument("--typecheck", action="store_true")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--out", default=".github/workflows/ci.yml")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()

    repo = os.path.realpath(a.repo)
    d = json.loads(load(a.detect))
    stack = d.get("stack")
    if stack not in TEMPLATE_FOR:
        die(2, "unsupported stack %r. Supported: %s" % (stack, ", ".join(sorted(TEMPLATE_FOR))))

    branches = [b.strip() for b in a.branches.split(",") if b.strip()]
    if not branches or any(not re.fullmatch(r"[\w./*-]+", b) for b in branches):
        die(2, "--branches must be a comma list of branch names")

    pins = json.loads(load(os.path.join(HERE, "pins.json")))
    plugin = json.loads(load(PLUGIN_JSON))
    project_dir = d.get("project_dir") or "."
    values = {
        "PLUGIN_VERSION": plugin["version"],
        "BRANCHES": ", ".join(branches),
        "PROJECT_DIR": project_dir,
    }
    flags = {}

    if stack in NODE_STACKS:
        node = a.node_version or d.get("node_version")
        if not node:
            die(2, "no Node version detected: pass --node-version (ask the user which version production runs)")
        if not re.fullmatch(r"\d+(\.\d+){0,2}(\.x)?|lts/\*", node):
            die(2, "--node-version must look like 20, 22.11 or 22.11.0")
        pm = pm_commands(d.get("package_manager", "npm"), d.get("lockfile"))
        scripts = d.get("scripts") or {}
        lock = d.get("lockfile")
        values.update({
            "NODE_VERSION": node,
            "INSTALL_CMD": pm["install"],
            "RUN": pm["run"],
            "ARGSEP": pm["argsep"],
            "CACHE": pm["cache"],
            "LOCKFILE_PATH": lock if project_dir == "." else project_dir + "/" + (lock or ""),
            "AUDIT_CMD": pm["audit"],
            "JAVA_VERSION": a.java_version,
        })
        flags.update({
            "COREPACK": pm["corepack"],
            "LOCKFILE": bool(lock),
            "LINT": bool(scripts.get("lint")),
            "TEST": bool(scripts.get("test")),
            "BUILD": bool(scripts.get("build")),
            "KARMA": bool(d.get("karma")),
            "AUDIT": bool(pm["audit"]) and not a.no_audit,
            "TYPECHECK": a.typecheck and bool(d.get("typescript")),
        })
        if stack == "react-native":
            android = d.get("android_dir")
            flags["ANDROID"] = bool(android) and not a.no_android
            values["ANDROID_DIR"] = android
            if a.ios:
                if not d.get("ios_workspace"):
                    die(2, "--ios given but no ios/*.xcworkspace was detected")
                values.update({
                    "IOS_WORKSPACE": os.path.relpath(os.path.join(repo, d["ios_workspace"]), os.path.join(repo, project_dir)),
                    "IOS_SCHEME": d["ios_scheme"],
                    "IOS_DIR": os.path.dirname(d["ios_workspace"]),
                })
            flags["IOS"] = a.ios
            flags["GEMFILE"] = bool(d.get("gemfile"))
    else:  # dotnet-framework
        values["SOLUTION"] = d["solution"].replace("/", "\\")
        values["TEST_PROJECTS"] = ", ".join(d.get("test_projects") or [])
        flags["TESTS"] = bool(d.get("test_projects"))

    body = expand_includes(load(os.path.join(TEMPLATES, TEMPLATE_FOR[stack])))
    text = load(os.path.join(TEMPLATES, "_header.yml")) + body
    if a.sonar:
        text += load(os.path.join(TEMPLATES, "sonarcloud.snippet.yml"))
    text = substitute(apply_conditionals(text, flags), values, pins)
    text = re.sub(r"\n{3,}", "\n\n", text)

    if a.stdout:
        sys.stdout.write(text)
        return 0

    out = os.path.realpath(os.path.join(repo, a.out))
    wf_dir = os.path.join(repo, ".github", "workflows")
    if os.path.dirname(out) != wf_dir or not out.endswith((".yml", ".yaml")):
        die(2, "--out must be a .yml file directly inside .github/workflows/")
    if os.path.exists(out) and not a.force:
        die(2, "%s already exists; show the user a diff and re-run with --force only if they agree" % os.path.relpath(out, repo))
    os.makedirs(wf_dir, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("WROTE=" + os.path.relpath(out, repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())

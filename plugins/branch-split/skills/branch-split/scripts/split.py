#!/usr/bin/env python3
"""branch-split: turn one change set into per-ticket branches as patch files.

Every command is read-only towards the user's repo, except that git may read its
objects. All building happens in a scratch clone under the spec's "out" folder.
Nothing here ever commits, pushes, or changes the user's branches or index.

Commands (run with `python3 -I split.py <cmd> ...`):
  scan      --repo R --base-ref B [--source S]   inventory: changed files, version bumps,
                                                 DEV/staging leftovers, signing material, EOL-only
  listhunks (--spec F | --repo R --base-ref B [--source S]) PATH... [--show]
  names     SPEC     fail if any target branch already exists locally or on origin
  build     SPEC     build each branch's tree in the scratch clone and write NN-*.patch
  verify    SPEC     replay patches, check completeness vs source, cross-check shared files
  render    SPEC     write apply.sh and manifest.md
  pushed    SPEC     after the user ran apply.sh: check branches on origin, print PR order

Exit codes: 0 ok, 1 check failed, 2 bad usage/spec, 3 git error.
"""
import argparse
import itertools
import json
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GITCFG = ['-c', 'diff.noprefix=false', '-c', 'diff.mnemonicPrefix=false',
          '-c', 'core.quotePath=false', '-c', 'color.ui=false']
DIFFOPTS = ['--no-color', '--no-ext-diff', '--src-prefix=a/', '--dst-prefix=b/']
ENV = dict(os.environ, GIT_LITERAL_PATHSPECS='1', LC_ALL='C')


class Fail(Exception):
    def __init__(self, msg, code=1):
        super().__init__(msg)
        self.code = code


def run(args, cwd=None, input=None, env=None, check=True):
    p = subprocess.run(args, cwd=cwd, input=input, capture_output=True, env=env or ENV)
    if check and p.returncode:
        raise Fail(f"$ {' '.join(args)}\n{p.stderr.decode(errors='replace').strip()}", 3)
    return p


def git(repo, *a, input=None, env=None, check=True):
    return run(['git', *GITCFG, '-C', repo, *a], input=input, env=env, check=check).stdout


def gtext(repo, *a, **kw):
    return git(repo, *a, **kw).decode(errors='replace')


# ---------------------------------------------------------------- spec

def load(path):
    try:
        s = json.load(open(path))
    except (OSError, ValueError) as e:
        raise Fail(f'cannot read spec {path}: {e}', 2)
    for k in ('repo', 'app', 'base', 'branches'):
        if k not in s:
            raise Fail(f'spec is missing "{k}"', 2)
    s['repo'] = os.path.abspath(os.path.expanduser(s['repo']))
    s.setdefault('pr_target', s['base'])
    s.setdefault('base_ref', 'origin/' + s['base'])
    s.setdefault('source', 'index')
    s.setdefault('version_files', [])
    s.setdefault('exclude', {})
    s.setdefault('forbid', [])
    s.setdefault('notes', [])
    s['out'] = os.path.abspath(os.path.expanduser(s.get('out') or os.path.dirname(os.path.abspath(path))))
    s['_spec'] = os.path.abspath(path)
    seen = []
    for b in s['branches']:
        n = b.get('name', '')
        if not re.fullmatch(r'[A-Za-z0-9._/-]+', n) or '..' in n or n.endswith(('/', '.lock')) or n.startswith('-'):
            raise Fail(f'bad branch name: {n!r}', 2)
        if n in seen:
            raise Fail(f'duplicate branch: {n}', 2)
        p = b.get('parent') or 'base'
        if p != 'base' and p not in seen:
            raise Fail(f'{n}: parent {p} must be an earlier branch in the list (or "base")', 2)
        b['parent'] = p
        for k in ('files', 'edits', 'notes'):
            b.setdefault(k, [])
        b.setdefault('hunks', {})
        dup = set(b['files']) & set(b['hunks'])
        if dup:
            raise Fail(f'{n}: {sorted(dup)} listed under both files and hunks', 2)
        seen.append(n)
    return s


def state_path(s):
    return os.path.join(s['out'], 'state.json')


def load_state(s):
    try:
        return json.load(open(state_path(s)))
    except OSError:
        raise Fail('no state.json: run "build" first', 2)


def patch_name(i, name):
    return f'{i:02d}-{name.replace("/", "-")}.patch'


# ---------------------------------------------------------------- source side

def resolve(repo, ref):
    return gtext(repo, 'rev-parse', '--verify', '-q', ref + '^{commit}').strip()


def src_entry(repo, source, path):
    """(mode, sha) of path in the source (index or a commit), or None if absent."""
    if source == 'index':
        out = gtext(repo, 'ls-files', '-s', '--', path)
        for line in out.splitlines():
            meta, p = line.split('\t', 1)
            if p == path:
                mode, sha, _ = meta.split()
                return mode, sha
        return None
    out = gtext(repo, 'ls-tree', source, '--', path)
    for line in out.splitlines():
        meta, p = line.split('\t', 1)
        if p == path:
            mode, _, sha = meta.split()
            return mode, sha
    return None


def src_diff_args(source, base):
    return ['--cached', base] if source == 'index' else [base, source]


def src_changed(repo, source, base):
    out = gtext(repo, 'diff', '--name-only', '--no-renames', *src_diff_args(source, base))
    return [p for p in out.splitlines() if p]


def src_path_diff(repo, source, base, path):
    return git(repo, 'diff', *DIFFOPTS, '-U3', *src_diff_args(source, base), '--', path)


def split_diff(diff):
    header, hunks, cur = [], [], None
    for line in diff.splitlines(keepends=True):
        if line.startswith(b'@@'):
            cur = [line]
            hunks.append(cur)
        elif cur is None:
            header.append(line)
        else:
            cur.append(line)
    return header, hunks


# ---------------------------------------------------------------- scratch clone

def clone_dir(s):
    c = os.path.join(s['out'], 'clone')
    if not os.path.isdir(os.path.join(c, '.git')):
        os.makedirs(s['out'], exist_ok=True)
        run(['git', 'clone', '-q', '--shared', '--no-checkout', s['repo'], c])
    return c


def ix_env(idx):
    return dict(ENV, GIT_INDEX_FILE=idx)


def ls_entry(c, tree, path):
    out = gtext(c, 'ls-tree', tree, '--', path)
    for line in out.splitlines():
        meta, p = line.split('\t', 1)
        if p == path:
            mode, _, sha = meta.split()
            return mode, sha
    return None


def tree_changed(c, a, b):
    return [p for p in gtext(c, 'diff', '--name-only', '--no-renames', a, b).splitlines() if p]


# ---------------------------------------------------------------- commands

def cmd_scan(a):
    repo = os.path.abspath(a.repo)
    base = resolve(repo, a.base_ref)
    if not base:
        raise Fail(f'cannot resolve {a.base_ref}', 2)
    src = a.source
    dargs = src_diff_args(src, base)
    print(f'repo {repo}\nbase {a.base_ref} = {base[:12]}   source {src}\n')

    print('== Changed (source vs base)')
    print(gtext(repo, 'diff', '--name-status', '-M', *dargs).rstrip() or '(none)')
    if src == 'index':
        uns = gtext(repo, 'diff', '--name-only').splitlines()
        unt = gtext(repo, 'ls-files', '--others', '--exclude-standard').splitlines()
        print('\n== Unstaged (not in the source; kept out unless you stage them)')
        print('\n'.join(uns) or '(none)')
        print('\n== Untracked')
        print('\n'.join(unt) or '(none)')

    plain = set(gtext(repo, 'diff', '--name-only', '--no-renames', *dargs).splitlines())
    noeol = set(gtext(repo, 'diff', '--name-only', '--no-renames', '--ignore-cr-at-eol', *dargs).splitlines())
    eol_only = sorted(plain - noeol)
    print('\n== Line-ending-only changes (usually drop these)')
    print('\n'.join(eol_only) or '(none)')

    patt = {
        'version': re.compile(r'versionCode|versionName|MARKETING_VERSION|CURRENT_PROJECT_VERSION|"version"\s*:|CFBundle(Short)?Version'),
        'dev': re.compile(r'''DEV['"]|[.\-_]dev\b|(?i:staging|\buat\b|\bsit\b|localhost|127\.0\.0\.1)|\b10\.\d+\.\d+\.\d+|\b192\.168\.|(?i:debug\w*\s*[:=]\s*true)'''),
        'secret': re.compile(r'(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|client[_-]?secret)\w*\s*[:=]'),
    }
    hits = {k: [] for k in patt}
    diffs = [('', dargs)] + ([(' (unstaged)', [])] if src == 'index' else [])
    for tag, args in diffs:
        diff = gtext(repo, 'diff', *DIFFOPTS, '-U0', '--no-renames', *args)
        path, ln = None, 0
        for line in diff.splitlines():
            if line.startswith('+++ '):
                path = line[6:] if line.startswith('+++ b/') else None
            elif line.startswith('@@'):
                m = re.search(r'\+(\d+)', line)
                ln = int(m.group(1)) if m else 0
            elif line.startswith('+') and path:
                body = line[1:]
                for k, rx in patt.items():
                    if rx.search(body):
                        shown = '' if k == 'secret' else '  ' + body.strip()[:120]
                        hits[k].append(f'{path}:{ln}{tag}{shown}')
                ln += 1
    labels = {'version': 'Version bumps (keep out of ticket branches)',
              'dev': 'Possible DEV/staging leftovers (check each before it ships)',
              'secret': 'Possible credentials (values not shown; never commit them)'}
    for k in patt:
        print(f'\n== {labels[k]}')
        print('\n'.join(hits[k]) or '(none)')

    signing = re.compile(r'(?i)\.(p12|p8|pfx|jks|keystore|pem|key|mobileprovision|cer)$')
    tracked = [p for p in gtext(repo, 'ls-files').splitlines() if signing.search(p)]
    print('\n== Signing material tracked in git')
    print('\n'.join(tracked) or '(none)')
    return 0


def cmd_listhunks(a):
    if a.spec:
        s = load(a.spec)
        repo, base_ref, src = s['repo'], s['base_ref'], s['source']
    else:
        if not (a.repo and a.base_ref):
            raise Fail('listhunks needs --spec or --repo and --base-ref', 2)
        repo, base_ref, src = os.path.abspath(a.repo), a.base_ref, a.source
    base = resolve(repo, base_ref)
    for path in a.paths:
        header, hunks = split_diff(src_path_diff(repo, src, base, path))
        print(f'== {path}: {len(hunks)} hunk(s)')
        if any(l.startswith(b'Binary files') or l.startswith(b'GIT binary') for l in header):
            print('   binary: use "files", not "hunks"')
        for i, h in enumerate(hunks, 1):
            add = sum(l.startswith(b'+') for l in h[1:])
            rem = sum(l.startswith(b'-') for l in h[1:])
            print(f'{i:>3} {h[0].decode(errors="replace").strip()}  (+{add} -{rem})')
            if a.show:
                for l in h[1:]:
                    print('      ' + l.decode(errors='replace').rstrip('\r\n'))
    return 0


def remote_heads(repo):
    out = gtext(repo, 'ls-remote', '--heads', 'origin')
    return {l.split('\t')[1][len('refs/heads/'):]: l.split('\t')[0] for l in out.splitlines() if '\t' in l}


def cmd_names(a):
    s = load(a.spec)
    remote = remote_heads(s['repo'])
    bad = 0
    for b in s['branches']:
        n = b['name']
        local = git(s['repo'], 'rev-parse', '-q', '--verify', 'refs/heads/' + n, check=False).strip()
        where = [w for w, hit in (('local', local), ('origin', n in remote)) if hit]
        if where:
            bad = 1
            print(f'EXISTS ({", ".join(where)}): {n}')
    if not bad:
        print(f'OK: none of the {len(s["branches"])} branch names exist locally or on origin')
    return bad


def cmd_build(a):
    s = load(a.spec)
    repo, src = s['repo'], s['source']
    base = resolve(repo, s['base_ref'])
    if not base:
        raise Fail(f'cannot resolve {s["base_ref"]} in {repo}', 2)
    if src != 'index' and not resolve(repo, src):
        raise Fail(f'cannot resolve source {src}', 2)
    c = clone_dir(s)
    base_tree = gtext(c, 'rev-parse', base + '^{tree}').strip()
    idx = os.path.join(s['out'], 'build.index')
    env = ix_env(idx)
    changed = src_changed(repo, src, base)
    for f in os.listdir(s['out']):
        if re.fullmatch(r'\d\d-.*\.patch', f):
            os.remove(os.path.join(s['out'], f))

    trees, state = {'base': base_tree}, {'base_sha': base, 'base_tree': base_tree, 'branches': {}}
    for i, b in enumerate(s['branches'], 1):
        n, ptree = b['name'], trees[b['parent']]
        git(c, 'read-tree', ptree, env=env)
        for p in b['files']:
            paths = [q for q in changed if q.startswith(p)] if p.endswith('/') else [p]
            if not paths:
                raise Fail(f'{n}: "{p}" matches no changed path', 2)
            for q in paths:
                e = src_entry(repo, src, q)
                if e:
                    git(c, 'update-index', '--add', '--cacheinfo', f'{e[0]},{e[1]},{q}', env=env)
                else:
                    git(c, 'update-index', '--force-remove', '--', q, env=env)
        for p, picks in b['hunks'].items():
            header, hunks = split_diff(src_path_diff(repo, src, base, p))
            if any(l.startswith((b'Binary files', b'GIT binary')) for l in header):
                raise Fail(f'{n}: {p} is binary; put it under "files"', 2)
            try:
                chosen = [hunks[int(k) - 1] for k in picks]
            except (IndexError, ValueError):
                raise Fail(f'{n}: {p} has {len(hunks)} hunk(s); asked for {picks}', 2)
            patch = b''.join(header) + b''.join(b''.join(h) for h in chosen)
            r = run(['git', *GITCFG, '-C', c, 'apply', '--cached', '--recount', '-'], input=patch, env=env, check=False)
            if r.returncode:
                raise Fail(f'{n}: hunks {picks} of {p} do not apply on the parent tree '
                           f'(use "files" or "edits" instead):\n{r.stderr.decode(errors="replace")}')
        for e in b['edits']:
            p = e['path']
            meta = gtext(c, 'ls-files', '-s', '--', p, env=env).split()
            if not meta:
                raise Fail(f'{n}: edit target {p} is not in the tree at this point', 2)
            data = git(c, 'cat-file', 'blob', ':' + p, env=env)
            for old, new in e['replace']:
                o, w = old.encode(), new.encode()
                k = data.count(o)
                if k != 1:
                    raise Fail(f'{n}: edit in {p} expected exactly 1 match, found {k}:\n{old!r}', 2)
                data = data.replace(o, w)
            for bad in e.get('assert_absent', []):
                if bad.encode() in data:
                    raise Fail(f'{n}: {p} still contains {bad!r} after edits', 1)
            sha = gtext(c, 'hash-object', '-w', '--no-filters', '--stdin', input=data).strip()
            git(c, 'update-index', '--cacheinfo', f'{meta[0]},{sha},{p}', env=env)
        tree = gtext(c, 'write-tree', env=env).strip()
        if tree == ptree:
            raise Fail(f'{n}: no changes compared with its parent', 2)
        trees[n] = tree
        pf = patch_name(i, n)
        diff = git(c, 'diff', *DIFFOPTS, '--binary', '-M', ptree, tree)
        open(os.path.join(s['out'], pf), 'wb').write(diff)
        stat = gtext(c, 'diff', '--shortstat', '-M', ptree, tree).strip()
        state['branches'][n] = {'tree': tree, 'parent_tree': ptree, 'patch': pf}
        print(f'{pf:<70} {stat}')
    json.dump(state, open(state_path(s), 'w'), indent=1)
    print(f'\nstate: {state_path(s)}')
    return 0


def apply_on(c, tree, patches, idx):
    env = ix_env(idx)
    git(c, 'read-tree', tree, env=env)
    for p in patches:
        r = run(['git', *GITCFG, '-C', c, 'apply', '--cached', p], env=env, check=False)
        if r.returncode:
            return None, f'{os.path.basename(p)}: {r.stderr.decode(errors="replace").strip()}'
    return gtext(c, 'write-tree', env=env).strip(), None


def cmd_verify(a):
    s = load(a.spec)
    st = load_state(s)
    c, repo, src = clone_dir(s), s['repo'], s['source']
    idx = os.path.join(s['out'], 'verify.index')
    P = lambda n: os.path.join(s['out'], st['branches'][n]['patch'])
    problems = 0

    print('== Each patch on its parent')
    for b in s['branches']:
        n, info = b['name'], st['branches'][b['name']]
        t, err = apply_on(c, info['parent_tree'], [P(n)], idx)
        ok = t == info['tree']
        problems += not ok
        print(f'{"OK  " if ok else "FAIL"} {info["patch"]}' + (f'  {err}' if err else ''))

    print('\n== All patches in order on the base, compared with the source')
    final, err = apply_on(c, st['base_tree'], [P(b['name']) for b in s['branches']], idx)
    if err:
        print(f'FAIL {err}')
        return 1
    paths = sorted(set(src_changed(repo, src, st['base_sha'])) | set(tree_changed(c, st['base_tree'], final)))
    for p in paths:
        want, got = src_entry(repo, src, p), ls_entry(c, final, p)
        if want == got:
            continue
        if p in s['exclude']:
            print(f'EXCLUDED (expected) {p}: {s["exclude"][p]}')
            if want and got:
                print('   ' + gtext(c, 'diff', *DIFFOPTS, '-U0', got[1], want[1]).replace('\n', '\n   ').rstrip())
        elif p in s['version_files']:
            print(f'VERSION (kept out)  {p}')
        else:
            problems += 1
            kind = 'MISSING' if got is None and want else 'STILL PRESENT' if want is None else 'DIFF'
            print(f'{kind:<19} {p}')
    print(f'checked {len(paths)} path(s)')

    print('\n== Branches with the same parent that share a file (both orders)')
    shared = 0
    by_parent = {}
    for b in s['branches']:
        by_parent.setdefault(b['parent'], []).append(b['name'])
    files = {n: set(tree_changed(c, i['parent_tree'], i['tree'])) for n, i in st['branches'].items()}
    for sibs in by_parent.values():
        for x, y in itertools.combinations(sibs, 2):
            common = files[x] & files[y]
            if not common:
                continue
            shared += 1
            pt = st['branches'][x]['parent_tree']
            t1, e1 = apply_on(c, pt, [P(x), P(y)], idx)
            t2, e2 = apply_on(c, pt, [P(y), P(x)], idx)
            ok = t1 and t1 == t2
            problems += not ok
            print(f'{"OK  " if ok else "FAIL"} {x} + {y}: {", ".join(sorted(common))}' + (f'  {e1 or e2}' if not ok else ''))
    if not shared:
        print('(none)')

    if s['forbid']:
        print('\n== Forbidden strings in added lines')
        found = 0
        for b in s['branches']:
            for line in open(P(b['name']), 'rb').read().decode(errors='replace').splitlines():
                if line.startswith('+') and not line.startswith('+++'):
                    for f in s['forbid']:
                        if f in line:
                            found += 1
                            print(f'FAIL {b["name"]}: contains {f!r}')
        problems += found
        if not found:
            print(f'OK: none of {len(s["forbid"])} string(s) appear')

    print(f'\n{"VERIFIED" if not problems else f"{problems} PROBLEM(S)"}')
    return 1 if problems else 0


def _numbering(s):
    return {b['name']: i for i, b in enumerate(s['branches'], 1)}


def _children(s):
    kids = {}
    for b in s['branches']:
        if b['parent'] != 'base':
            kids.setdefault(b['parent'], []).append(b['name'])
    return kids


def merge_rules(s, shared_notes):
    num, kids = _numbering(s), _children(s)
    roots = [num[b['name']] for b in s['branches'] if b['parent'] == 'base']
    out = [f'- **{_ranges(roots)}:** any order.' + (f' {shared_notes}' if shared_notes else '')]
    for b in s['branches']:
        if b['parent'] != 'base':
            p = num[b['parent']]
            out.append(f'- **#{num[b["name"]]}:** only after #{p}. Retarget it to `{s["pr_target"]}` once #{p} merges '
                       f'(or delete #{p}\'s branch on merge and GitHub retargets it).')
    stacked = sorted({num[p] for p in kids} | {num[k] for v in kids.values() for k in v})
    if stacked:
        out.append(f'- **Merge method:** use "Create a merge commit" (not squash) for '
                   f'{", ".join("#%d" % n for n in stacked)}; a squash forces the stacked PR to be rebased.')
    return out


def _ranges(nums):
    nums, parts = sorted(nums), []
    for _, g in itertools.groupby(enumerate(nums), lambda t: t[1] - t[0]):
        g = [x for _, x in g]
        parts.append(f'#{g[0]}' if len(g) == 1 else f'#{g[0]}–#{g[-1]}')
    return ', '.join(parts)


def cmd_render(a):
    s = load(a.spec)
    st = load_state(s)
    c = clone_dir(s)
    num = _numbering(s)
    tmpl = open(os.path.join(HERE, 'apply.sh.tmpl')).read()
    lines = []
    for b in s['branches']:
        parent = s['base'] if b['parent'] == 'base' else b['parent']
        lines.append(f'  {shlex.quote(b["name"] + "|" + parent + "|" + st["branches"][b["name"]]["patch"])}')
    rep = {
        '@@APP@@': s['app'], '@@REPO@@': shlex.quote(s['repo']), '@@OUT@@': shlex.quote(s['out']),
        '@@BASE@@': shlex.quote(s['base']), '@@BASE_SHA@@': st['base_sha'],
        '@@BACKUP@@': shlex.quote(s['app'].lower() + '-split-backup'),
        '@@VERSION_FILES@@': ' '.join(shlex.quote(v) for v in s['version_files']),
        '@@BRANCHES@@': '\n'.join(lines), '@@COUNT@@': str(len(s['branches'])),
        '@@TARGET@@': s['pr_target'],
    }
    for k, v in rep.items():
        tmpl = tmpl.replace(k, v)
    ap = os.path.join(s['out'], 'apply.sh')
    open(ap, 'w').write(tmpl)
    os.chmod(ap, 0o755)

    files = {n: gtext(c, 'diff', '--name-status', '-M', i['parent_tree'], i['tree']).splitlines()
             for n, i in st['branches'].items()}
    paths = {n: {l.split('\t')[-1] for l in v} for n, v in files.items()}
    roots = [b['name'] for b in s['branches'] if b['parent'] == 'base']
    shares = [f'#{num[x]}/#{num[y]} share `{p}`' for x, y in itertools.combinations(roots, 2)
              for p in sorted(paths[x] & paths[y])]
    shared_note = (('; '.join(shares) + ', but each touches separate parts (verified in both orders).') if shares else '')

    md = [f'# {os.path.basename(s["repo"])}: ticket branches', '',
          f'Cut from `{s["base"]}`; every PR ends up in **`{s["pr_target"]}`**.', '',
          '| # | Branch | Cut from | PR base | Ticket | Files |', '|---|---|---|---|---|---|']
    for b in s['branches']:
        n = b['name']
        cut = s['base'] if b['parent'] == 'base' else f'#{num[b["parent"]]}'
        prb = s['pr_target'] if b['parent'] == 'base' else f'#{num[b["parent"]]}, then {s["pr_target"]}'
        md.append(f'| {num[n]} | `{n}` | {cut} | {prb} | {b.get("ticket", "")} | {len(files[n])} |')
    md += ['', '**Merge order:**', *merge_rules(s, shared_note), '']
    for b in s['branches']:
        n = b['name']
        md.append(f'## {num[n]}. {n}' + (f' (stacked on #{num[b["parent"]]})' if b['parent'] != 'base' else ''))
        if b.get('summary'):
            md += ['**Changes:**', *[f'- {x}' for x in b['summary']]]
        md += ['', '**Files:**', *[f'- `{l.split(chr(9))[0][0]}` {l.split(chr(9))[-1]}' for l in files[n]], '']
        md.append(f'**Commit:** `{b.get("commit") or (b.get("ticket", "") + ": " + b.get("title", n)).strip(": ")}`')
        md += [f'- {x}' for x in b['notes']]
        md.append('')
    extra = ([f'- **Version bump:** {", ".join("`%s`" % v for v in s["version_files"])}. `apply.sh` restores these on `{s["base"]}`, unstaged.']
             if s['version_files'] else [])
    extra += [f'- **`{p}` (left out on purpose):** {why}' for p, why in s['exclude'].items()]
    extra += [f'- {x}' for x in s['notes']]
    if extra:
        md += ['## Not in any branch', *extra, '']
    md.append(f'Patches, `apply.sh` and this file: `{s["out"]}`')
    mp = os.path.join(s['out'], 'manifest.md')
    open(mp, 'w').write('\n'.join(md) + '\n')
    r = run(['bash', '-n', ap], check=False)
    print(f'{ap}\n{mp}')
    if r.returncode:
        print('apply.sh syntax error:\n' + r.stderr.decode())
        return 1
    return 0


def cmd_pushed(a):
    s = load(a.spec)
    st = load_state(s)
    repo, num = s['repo'], _numbering(s)
    remote = remote_heads(repo)
    problems = 0
    rows = []
    for b in s['branches']:
        n = b['name']
        local = git(repo, 'rev-parse', '-q', '--verify', 'refs/heads/' + n, check=False).decode().strip()
        rsha = remote.get(n)
        parent = st['base_sha'] if b['parent'] == 'base' else 'refs/heads/' + b['parent']
        notes, bad = [], False
        if not local:
            notes.append('no local branch'); bad = True
        if not rsha:
            notes.append('NOT ON ORIGIN'); bad = True
        elif local and rsha != local:
            notes.append('local and origin differ (push or pull)'); bad = True
        if local:
            ahead = gtext(repo, 'rev-list', '--count', f'{parent}..{local}').strip()
            notes.append(f'{ahead} commit(s) ahead of {"base" if b["parent"] == "base" else "#%d" % num[b["parent"]]}')
            tree = gtext(repo, 'rev-parse', local + '^{tree}').strip()
            if tree != st['branches'][n]['tree']:
                notes.append('content differs from the built patch (changed while committing?)'); bad = True
            added = gtext(repo, 'diff', *DIFFOPTS, parent, local)
            for f in s['forbid']:
                if any(l.startswith('+') and f in l for l in added.splitlines()):
                    notes.append(f'contains forbidden {f!r}'); bad = True
        problems += bad
        rows.append((n, b))
        print(f'{"FAIL" if bad else "OK  "} {n}: {"; ".join(notes)}')

    print(f'\n### {os.path.basename(repo)}: cut from `{s["base"]}`, PR into `{s["pr_target"]}`')
    print('| PR | Branch | PR base | Ticket |\n|---|---|---|---|')
    for n, b in rows:
        prb = s['pr_target'] if b['parent'] == 'base' else f'#{num[b["parent"]]}, then {s["pr_target"]}'
        print(f'| {num[n]} | `{n}` | {prb} | {b.get("ticket", "")} |')
    print('\n**Merge order:**')
    print('\n'.join(merge_rules(s, '')))
    return 1 if problems else 0


def cmd_buildinfo(a):
    """For buildcheck.sh: repo, clone, base tree, then one 'label tree' line per branch."""
    s = load(a.spec)
    st = load_state(s)
    print(s['repo'])
    print(clone_dir(s))
    print(st['base_tree'])
    for i, b in enumerate(s['branches'], 1):
        print(f'{i:02d} {st["branches"][b["name"]]["tree"]}')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('scan')
    p.add_argument('--repo', required=True)
    p.add_argument('--base-ref', required=True)
    p.add_argument('--source', default='index')
    p = sub.add_parser('listhunks')
    p.add_argument('--spec')
    p.add_argument('--repo')
    p.add_argument('--base-ref')
    p.add_argument('--source', default='index')
    p.add_argument('--show', action='store_true')
    p.add_argument('paths', nargs='+')
    for name in ('names', 'build', 'verify', 'render', 'pushed', 'buildinfo'):
        sub.add_parser(name).add_argument('spec')
    a = ap.parse_args()
    try:
        sys.exit(globals()['cmd_' + a.cmd](a))
    except Fail as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(e.code)


if __name__ == '__main__':
    main()

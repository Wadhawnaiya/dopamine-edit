#!/usr/bin/env bash
# dopamine-edit — keep every installed agent skill copy in step with one source.
#
# Source is the copy you run this from (repo checkout preferred), or --from DIR.
# Target-only files (e.g. local brand assets) are preserved unless --prune.
set -euo pipefail
SKILL_CAND="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: sync-installs.sh [--from DIR] [--to DIR ...] [--check] [--dry-run] [--prune] [--json]

Copies the source skill over each installed skill directory, backing up anything
it replaces. Never deletes target-only files (local brand assets) unless --prune.

  --from DIR   Source skill dir (default: the repo copy, else the copy you ran)
  --to DIR     Target skill dir; repeatable. Default: the known agent skill dirs.
  --check      No writes; exit 1 if any target differs from the source.
  --dry-run    Show the plan without copying.
  --prune      Also delete target files absent from the source (brand assets kept).
  --json       Print a machine-readable summary.
EOF
}

FROM="" CHECK=0 DRY=0 PRUNE=0 JSON=0
TARGETS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --from) [ $# -ge 2 ] || { echo 'ERROR: --from needs a value' >&2; exit 2; }; FROM="$2"; shift 2 ;;
    --to) [ $# -ge 2 ] || { echo 'ERROR: --to needs a value' >&2; exit 2; }; TARGETS+=("$2"); shift 2 ;;
    --check) CHECK=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --prune) PRUNE=1; shift ;;
    --json) JSON=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

if [ -z "$FROM" ]; then
  REPO_CAND="$(cd "$SKILL_CAND/../.." && pwd)"
  if [ -f "$REPO_CAND/skills/dopamine-edit/SKILL.md" ] && [ -f "$REPO_CAND/scripts/install.sh" ]; then
    FROM="$REPO_CAND/skills/dopamine-edit"
  else
    FROM="$SKILL_CAND"
  fi
fi
[ -f "$FROM/SKILL.md" ] || { echo "ERROR: source has no SKILL.md: $FROM" >&2; exit 2; }

if [ "${#TARGETS[@]}" -eq 0 ]; then
  DEFAULTS=(
    "$HOME/.config/opencode/skills/dopamine-edit"
    "$HOME/.claude/skills/dopamine-edit"
    "$HOME/.agents/skills/dopamine-edit"
  )
  FROM_REAL="$(cd "$FROM" && pwd)"
  for dir in "${DEFAULTS[@]}"; do
    parent="$(dirname "$dir")"
    [ -d "$parent" ] || continue
    [ -d "$dir" ] && [ "$(cd "$dir" && pwd)" = "$FROM_REAL" ] && continue
    TARGETS+=("$dir")
  done
fi
[ "${#TARGETS[@]}" -gt 0 ] || { echo 'ERROR: no target skill directories found; pass --to DIR' >&2; exit 2; }

command -v python3 >/dev/null || { echo 'ERROR: missing python3' >&2; exit 1; }

python3 - "$FROM" "$CHECK" "$DRY" "$PRUNE" "$JSON" "${TARGETS[@]}" <<'PY'
import hashlib, json, os, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

source, check, dry, prune, as_json = Path(sys.argv[1]).resolve(), sys.argv[2] == '1', \
    sys.argv[3] == '1', sys.argv[4] == '1', sys.argv[5] == '1'
targets = [Path(p).expanduser().resolve() for p in sys.argv[6:]]
protected = ('assets/brand/',)
skip_names, skip_suffix = {'__pycache__', '.DS_Store'}, {'.pyc'}
backup_root = Path.home()/'.local/state/dopamine-edit/install-backups'
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def inventory(root):
    if not root.is_dir():
        return {}
    out = {}
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(part in skip_names for part in rel.parts) or rel.suffix in skip_suffix:
            continue
        out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_protected(rel):
    return any(rel.startswith(prefix) for prefix in protected)


src = inventory(source)
results, out_of_sync = [], False
for target in targets:
    if target == source:
        results.append({'target': str(target), 'skipped': 'source', 'missing': [], 'updated': [],
                        'local_only': [], 'pruned': [], 'backup': None})
        continue
    if source.is_relative_to(target) or target.is_relative_to(source):
        raise SystemExit(f'ERROR: source and target overlap: {source} <-> {target}')
    dst = inventory(target)
    missing = sorted(set(src) - set(dst))
    updated = sorted(rel for rel in set(src) & set(dst) if src[rel] != dst[rel])
    extra = sorted(set(dst) - set(src))
    removable = [rel for rel in extra if not is_protected(rel)]
    changes = missing + updated + (removable if prune else [])
    if changes:
        out_of_sync = True
    entry = {'target': str(target), 'exists': target.is_dir(),
             'missing': missing, 'updated': updated,
             'local_only': extra, 'pruned': removable if prune else [], 'backup': None}
    if check or dry or not changes:
        results.append(entry)
        continue
    if target.exists():
        try:
            label = '-'.join(target.relative_to(Path.home()).parts)
        except ValueError:
            label = '-'.join(target.parts[1:]) or target.name
        dest = backup_root/stamp/label
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(target, dest, symlinks=True,
                        ignore=shutil.ignore_patterns(*skip_names, '*.pyc'))
        entry['backup'] = str(dest)
    for rel in missing:
        out = target/rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source/rel, out)
    for rel in updated:
        out = target/rel
        out.parent.mkdir(parents=True, exist_ok=True)
        temp = out.with_name(out.name + '.sync-tmp')
        shutil.copy2(source/rel, temp)
        os.replace(temp, out)
    for rel in entry['pruned']:
        (target/rel).unlink()
    now = inventory(target)
    remaining = sorted(rel for rel in set(src) if now.get(rel) != src[rel])
    entry['verified'] = not remaining
    entry['remaining'] = remaining
    results.append(entry)

if as_json:
    print(json.dumps({'source': str(source), 'check': check, 'dry_run': dry, 'prune': prune,
                      'out_of_sync': out_of_sync, 'targets': results}, indent=2))
else:
    mode = 'check' if check else ('dry-run' if dry else 'sync')
    print(f'source: {source}  ({mode})')
    for entry in results:
        name = entry['target']
        if entry.get('skipped'):
            print(f'  {name}: {entry["skipped"]} (skipped)')
            continue
        bits = []
        if entry['missing']:
            bits.append(f"+{len(entry['missing'])} new")
        if entry['updated']:
            bits.append(f"~{len(entry['updated'])} updated")
        if entry['local_only']:
            bits.append(f"={len(entry['local_only'])} local-only kept")
        if entry['pruned']:
            bits.append(f"-{len(entry['pruned'])} pruned")
        if entry.get('verified') is False:
            bits.append(f"!! {len(entry.get('remaining', []))} still differ")
        if not bits:
            bits.append('up to date')
        print(f'  {name}: ' + ', '.join(bits))
        if entry['backup']:
            print(f'    backup: {entry["backup"]}')
    if check:
        print('result: ' + ('OUT OF SYNC' if out_of_sync else 'all targets match the source'))
    elif dry:
        print('result: dry run, nothing written')

if check and out_of_sync:
    sys.exit(1)
PY

# scripts/repo-tree.sh
#!/usr/bin/env bash
set -euo pipefail

# repo-tree.sh — generează structura repo-ului ca "tree", cu fallback în Python
# Usage:
#   ./scripts/repo-tree.sh                   # tree pentru directorul curent
#   ./repo-tree.sh -r /path/repo     # alt root
#   ./repo-tree.sh -o REPO_TREE.md   # salvează în fișier
#   ./repo-tree.sh -d 3              # limitează adâncimea
#   ./repo-tree.sh --no-ignore       # afișează tot (fără exclude)
#
DEFAULT_IGNORE='.git|.hg|.svn|.DS_Store|__pycache__|.mypy_cache|.pytest_cache|.tox|.venv|venv|node_modules|dist|build|*.pyc|*.pyo|*.log|*.egg-info|*.sqlite|*.db'

ROOT='.'
OUT=''
DEPTH=''
IGNORE="$DEFAULT_IGNORE"
USE_IGNORE=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    -r|--root)      ROOT="${2:-.}"; shift 2;;
    -o|--output)    OUT="${2:-}"; shift 2;;
    -d|--depth)     DEPTH="${2:-}"; shift 2;;
    --ignore)       IGNORE="${2:-}"; shift 2;;
    --no-ignore)    USE_IGNORE=0; shift;;
    -h|--help)
      sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "Arg necunoscut: $1"; exit 2;;
  esac
done

ROOT="${ROOT%/}"

emit() {
  if [[ -n "$OUT" ]]; then tee "$OUT"; else cat; fi
}

if command -v tree >/dev/null 2>&1; then
  args=(-a)
  [[ -n "$DEPTH" ]] && args+=(-L "$DEPTH")
  if [[ "$USE_IGNORE" -eq 1 && -n "$IGNORE" ]]; then
    args+=(-I "$IGNORE")
  fi
  args+=("$ROOT")
  tree "${args[@]}" | emit
  exit 0
fi

# Fallback în Python (fără sed; fără dependențe externe)
python3 - "$ROOT" "$DEPTH" "$IGNORE" "$USE_IGNORE" <<'PY' | emit
import os, sys, fnmatch

root = sys.argv[1]
depth = sys.argv[2]
ignore_pat = sys.argv[3]
use_ignore = sys.argv[4] == "1"

max_depth = int(depth) if depth and depth.isdigit() else None
ignore_globs = [p for p in ignore_pat.split('|') if p] if use_ignore else []

def is_ignored(name: str) -> bool:
    if not use_ignore:
        return False
    for pat in ignore_globs:
        if fnmatch.fnmatch(name, pat):
            return True
    return False

def walk(top: str, prefix: str = "", level: int = 0):
    try:
        entries = sorted(os.scandir(top),
                         key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
    except FileNotFoundError:
        return
    entries = [e for e in entries if not is_ignored(e.name)]
    for i, e in enumerate(entries):
        conn = "└── " if i == len(entries)-1 else "├── "
        print(prefix + conn + e.name)
        if e.is_dir(follow_symlinks=False):
            if max_depth is None or level+1 < max_depth:
                ext = "    " if i == len(entries)-1 else "│   "
                walk(os.path.join(top, e.name), prefix + ext, level+1)

print(os.path.basename(os.path.abspath(root)) or root)
walk(root)
PY

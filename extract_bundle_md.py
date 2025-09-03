from __future__ import annotations

import argparse
import fnmatch
import os
import re
from pathlib import Path
from typing import Iterable, Iterator, List, Dict, Tuple

# ------------------------------------------------------------
# Seturi de includeri / excluderi
# ------------------------------------------------------------

DEFAULT_INCLUDE_GLOBS: List[str] = [
    # cod / config
    "**/*.py",
    "**/*.sh",
    "**/*.sql",
    "**/*.ini",
    "**/*.cfg",
    "**/*.conf",
    "**/*.yml",
    "**/*.yaml",
    "**/*.json",
    "**/*.md",
    "**/*.mako",
    "**/*.toml",
    "**/*.txt",
    "**/*.properties",
    # fișiere-cheie fără extensie
    "Dockerfile",
    "Dockerfile.*",
    "docker-compose*.yml",
    "compose*.yml",
    "Makefile",
    # requirements
    "requirements*.txt",
    # scripturi frecvente
    "run_dev.sh",
    "verify_offers_read.sh",
    "smoke_obs.sh",
    "scripts/*.sh",
    "scripts/*.sql",
    # alembic
    "alembic.ini",
    "migrations/env.py",
    "migrations/script.py.mako",
    "migrations/README",
    "migrations/versions/*.py",
    # docker init SQL
    "docker/initdb/*.sql",
    "docker/initdb-test/*.sql",
    "app/docker/initdb/*.sql",
    "app/docker/initdb-test/*.sql",
    "app/docker/app-entrypoint.sh",
    # VS Code (config utilă)
    ".vscode/launch.json",
    ".vscode/settings.json",
    # dotfiles uzuale
    ".dockerignore",
    ".gitignore",
    ".editorconfig",
]

ENV_SENSITIVE_PATTERNS: List[str] = [
    ".env",
    ".env.*",
]

DEFAULT_EXCLUDE_DIRS: List[str] = [
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    ".idea",
]

DEFAULT_EXCLUDE_FILE_GLOBS: List[str] = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.so",
    "*.dll",
    "*.dylib",
    "*.zip",
    "*.tar",
    "*.tar.gz",
    "*.tgz",
    "*.gz",
    "*.bz2",
    "*.xz",
    "*.7z",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.pdf",
    ".DS_Store",
]

# ------------------------------------------------------------
# Redactare secrete (env / json / yaml / ini)
# ------------------------------------------------------------

# regex-uri pentru “KEY=VALUE” / ini
_EQ_KV = r"(?im)^(\s*{k}\s*=\s*)(.+?)\s*$"
_COLON_KV = r"(?im)^(\s*{k}\s*:\s*)(.+?)\s*$"
_JSON_KV = r'(?im)("(?:{k})"\s*:\s*)"(.*?)"'

# chei sensibile tipice
SENSITIVE_KEYS = [
    "POSTGRES_PASSWORD", "PGPASSWORD", "DATABASE_URL", "DB_URL", "DB_DSN",
    "DB_PASSWORD", "PASSWORD", "SECRET", "SECRET_KEY", "JWT_SECRET",
    "API_KEY", "API_TOKEN", "TOKEN", "ACCESS_TOKEN", "REFRESH_TOKEN",
    "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "PRIVATE_KEY",
]

def _mask(val: str, keep: int = 2) -> str:
    v = val.strip()
    if not v:
        return "***"
    if len(v) <= keep:
        return "*" * len(v)
    return v[:keep] + "…" + "*" * max(3, len(v) - keep - 1)

def redact_text(content: str, path: Path, enable: bool) -> str:
    if not enable:
        return content
    text = content

    # 1) .env / ini / generic KEY=VALUE
    for k in SENSITIVE_KEYS:
        pat = re.compile(_EQ_KV.format(k=re.escape(k)))
        text = pat.sub(lambda m: m.group(1) + _mask(m.group(2)), text)

    # 2) yaml: key: value
    for k in SENSITIVE_KEYS:
        pat = re.compile(_COLON_KV.format(k=re.escape(k)))
        text = pat.sub(lambda m: m.group(1) + _mask(m.group(2)), text)

    # 3) json: "key": "value"
    for k in SENSITIVE_KEYS:
        pat = re.compile(_JSON_KV.format(k=re.escape(k)))
        text = pat.sub(lambda m: m.group(1) + '"' + _mask(m.group(2)) + '"', text)

    # 4) DSN-uri tipice (postgres://user:pass@host/db)
    text = re.sub(
        r"(?i)(postgres(?:ql)?://[^:\s]+:)([^@\s]+)(@)",
        lambda m: m.group(1) + _mask(m.group(2)) + m.group(3),
        text,
    )
    return text

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

LANG_BY_EXT: Dict[str, str] = {
    ".py": "python",
    ".sh": "bash",
    ".sql": "sql",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".mako": "",
    ".toml": "toml",
    ".txt": "",
    ".properties": "",
}
LANG_BY_BASENAME: Dict[str, str] = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
}

def any_glob_match(path: Path, patterns: Iterable[str]) -> bool:
    s_rel = path.as_posix()
    s_base = path.name
    for pat in patterns:
        if fnmatch.fnmatch(s_rel, pat) or fnmatch.fnmatch(s_base, pat):
            return True
    return False

def should_skip_file(path: Path, extra_exclude: List[str]) -> bool:
    return any_glob_match(path, DEFAULT_EXCLUDE_FILE_GLOBS + extra_exclude)

def is_sensitive_env(path: Path) -> bool:
    return any_glob_match(path, ENV_SENSITIVE_PATTERNS)

def iter_files(
    root: Path,
    include_env: bool,
    extra_include: List[str],
    extra_exclude: List[str],
) -> Iterator[Path]:
    root = root.resolve()
    include_globs = DEFAULT_INCLUDE_GLOBS + extra_include
    for dirpath, dirnames, filenames in os.walk(root):
        dpath = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDE_DIRS]

        for fname in filenames:
            fpath = dpath / fname
            if should_skip_file(fpath.relative_to(root), extra_exclude):
                continue
            rel = fpath.relative_to(root)
            if any_glob_match(rel, include_globs):
                if is_sensitive_env(rel) and not include_env:
                    continue
                yield fpath

def detect_language_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in LANG_BY_EXT:
        return LANG_BY_EXT[ext]
    base = path.name.lower()
    return LANG_BY_BASENAME.get(base, "")

def read_text_lossy(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace")

def shorten_big_text(s: str, max_lines: int) -> Tuple[str, int, int, bool]:
    lines = s.splitlines()
    n = len(lines)
    if n <= max_lines:
        return s, n, n, False
    keep_head = max_lines // 2
    keep_tail = max_lines - keep_head
    new = "\n".join(lines[:keep_head] + [f"\n… [trimmed {n - max_lines} lines] …\n"] + lines[-keep_tail:])
    return new, n, max_lines, True

def build_bundle(
    root: Path,
    files: List[Path],
    include_env: bool,
    show_meta: bool,
    max_lines_per_file: int,
) -> str:
    out: List[str] = []
    out.append(f"# Code bundle — {root.name}\n")
    out.append("> Generat automat pentru depanare. Ordinea: cale relativă în repo.\n\n")

    files_sorted = sorted(files, key=lambda p: str(p.relative_to(root)).casefold())

    for f in files_sorted:
        rel = f.relative_to(root).as_posix()
        lang = detect_language_for(f)
        size = f.stat().st_size
        exec_flag = bool(f.stat().st_mode & 0o111)

        header = f"# path-ul fisierului: {rel}"
        if show_meta:
            header += f"  (size={size} bytes"
            if exec_flag:
                header += ", exec"
            header += ")"
        out.append(header + "\n")

        raw = read_text_lossy(f)
        redacted = redact_text(raw, f, enable=True if (include_env or is_sensitive_env(f)) else True)
        body, total_lines, kept_lines, trimmed = shorten_big_text(redacted, max_lines_per_file)

        fence_lang = lang if lang else ""
        out.append(f"```{fence_lang}".rstrip())
        out.append(body)
        out.append("```")
        if trimmed:
            out.append(f"_NOTE: {rel} a fost tăiat la {kept_lines}/{total_lines} linii pentru lizibilitate._")
        out.append("")  # blank line
    return "\n".join(out)

# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="extract_bundle_md.py",
        description="Extrage fișierele-cheie dintr-un repo într-un singur .md (cu delimitări).",
    )
    p.add_argument("--root", required=True, help="Rădăcina (directorul proiectului).")
    p.add_argument("--out", default=None, help="Fișierul .md rezultat (implicit: <root>/bundle.md).")
    p.add_argument("--include-env", action="store_true", help="Include .env și .env.* (valorile sunt redactate).")
    p.add_argument("--include", action="append", default=[], help="Globs suplimentare de inclus (poți repeta).")
    p.add_argument("--exclude", action="append", default=[], help="Globs suplimentare de exclus (poți repeta).")
    p.add_argument("--no-meta", action="store_true", help="Nu afișa metadate de fișier (mărime, exec).")
    p.add_argument("--max-lines", type=int, default=4000, help="Max linii pe fișier în bundle (default: 4000).")
    p.add_argument("--list", action="store_true", help="Doar listează fișierele potrivite și iese.")
    return p.parse_args()

def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Eroare: --root '{root}' nu există sau nu este director.")

    out_path = Path(args.out).expanduser().resolve() if args.out else (root / "bundle.md")
    files = list(iter_files(root, include_env=bool(args.include_env), extra_include=list(args.include), extra_exclude=list(args.exclude)))
    if not files:
        print("Avertisment: nu am găsit fișiere de inclus.", flush=True)

    if args.list:
        for f in sorted(files, key=lambda p: str(p.relative_to(root)).casefold()):
            print(f.relative_to(root).as_posix())
        return

    bundle = build_bundle(
        root=root,
        files=files,
        include_env=bool(args.include_env),
        show_meta=not args.no_meta,
        max_lines_per_file=max(100, args.max_lines),
    )
    out_path.write_text(bundle, encoding="utf-8")
    print(f"OK: scris bundle în {out_path}", flush=True)

if __name__ == "__main__":
    main()

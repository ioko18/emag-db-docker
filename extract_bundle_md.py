from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple, Dict

# ------------------------------------------------------------
# Seturi de includeri / excluderi
# ------------------------------------------------------------

# Globs „utile” pentru un proiect Python + Docker + Alembic
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
    "docker-compose*.yml",
    "Makefile",
    # requirements
    "requirements*.txt",
    # scripturi frecvente cu nume fixe
    "run_dev.sh",
    "verify_offers_read.sh",
    "smoke_obs.sh",
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
    # dotfiles uzuale (sunt filtrate de un flag separat pentru .env*)
    ".dockerignore",
    ".gitignore",
    ".editorconfig",
]

# Dotfiles sensibile – se includ doar cu --include-env
ENV_SENSITIVE_PATTERNS: List[str] = [
    ".env",
    ".env.*",
]

# Directoare pe care le sărim (nu sunt utile pentru auditul codului)
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
    # păstrăm .vscode (e util)
]

# Fișiere de tip „artefact” pe care le sărim
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
# fișiere fără extensie
LANG_BY_BASENAME: Dict[str, str] = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
}

def is_under_any(dirpath: Path, names: Iterable[str]) -> bool:
    parts = set(p.lower() for p in dirpath.parts)
    for n in names:
        if n.lower() in parts:
            return True
    return False


def any_glob_match(path: Path, patterns: Iterable[str]) -> bool:
    # pot exista globs relative la root; testăm atât cu numele relativ, cât și cu basename
    s_rel = str(path.as_posix())
    s_base = path.name
    for pat in patterns:
        if fnmatch.fnmatch(s_rel, pat) or fnmatch.fnmatch(s_base, pat):
            return True
    return False


def should_skip_file(path: Path) -> bool:
    return any_glob_match(path, DEFAULT_EXCLUDE_FILE_GLOBS)


def is_sensitive_env(path: Path) -> bool:
    # match pe basename & relativ (prinde .env și .env.example etc.)
    return any_glob_match(path, ENV_SENSITIVE_PATTERNS)


def iter_files(root: Path, include_env: bool) -> Iterator[Path]:
    """
    Parcurge arborele, aplică excluderile de directoare, apoi reține
    fișierele care se potrivesc cu globs de includere. Fișierele .env*
    se includ doar dacă include_env=True.
    """
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dpath = Path(dirpath)

        # Prune directorii excluși (in-place ca să afecteze os.walk)
        dirnames[:] = [
            d for d in dirnames
            if d not in DEFAULT_EXCLUDE_DIRS
        ]

        # emitem fișierele din acest director
        for fname in filenames:
            fpath = dpath / fname

            # skip artefacte / binare uzuale
            if should_skip_file(fpath):
                continue

            rel = fpath.relative_to(root)
            # filtrează pe globs de includere
            if any_glob_match(rel, DEFAULT_INCLUDE_GLOBS):
                # .env* doar cu flag
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
    """
    Citește fișierul ca text folosind UTF-8; dacă eșuează, cade pe latin-1,
    păstrând caracterele ne-decodabile.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace")


def build_bundle(root: Path, files: List[Path]) -> str:
    lines: List[str] = []
    lines.append(f"# Code bundle — {root.name}\n")
    lines.append("> Generat automat pentru depanare. Ordinea: cale relativă în repo.\n\n")

    # sortare stabilă (casefold) pe calea relativă
    files_sorted = sorted(files, key=lambda p: str(p.relative_to(root)).casefold())

    for f in files_sorted:
        rel = f.relative_to(root).as_posix()
        lang = detect_language_for(f)
        lines.append(f"# path-ul fisierului: {rel}\n")
        lines.append("")
        fence_lang = lang if lang else ""
        lines.append(f"```{fence_lang}".rstrip())
        lines.append(read_text_lossy(f))
        lines.append("```")
        lines.append("")  # newline între fișiere
    return "\n".join(lines)


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="extract_bundle_md.py",
        description="Extrage fișierele-cheie dintr-un repo într-un singur .md (cu delimitări).",
    )
    p.add_argument(
        "--root",
        required=True,
        help="Rădăcina (directorul proiectului).",
    )
    p.add_argument(
        "--out",
        default=None,
        help="Fișierul .md rezultat (implicit: <root>/bundle.md).",
    )
    p.add_argument(
        "--include-env",
        action="store_true",
        help="Include .env și .env.* în bundle.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Eroare: --root '{root}' nu există sau nu este director.")

    out_path = Path(args.out).expanduser().resolve() if args.out else (root / "bundle.md")

    files = list(iter_files(root, include_env=bool(args.include_env)))
    if not files:
        print("Avertisment: nu am găsit fișiere de inclus.", flush=True)

    bundle = build_bundle(root, files)
    out_path.write_text(bundle, encoding="utf-8")
    print(f"OK: scris bundle în {out_path}", flush=True)


if __name__ == "__main__":
    main()

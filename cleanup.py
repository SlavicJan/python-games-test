#!/usr/bin/env python3
"""Repository cleanup utility.

Finds and removes common temporary, cache, and build artifacts to free disk space.
Use the default dry-run mode to preview what will be deleted, then re-run with
``--apply`` to perform removals.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Iterable, List, Set

# Patterns for files that are safe to delete.
FILE_PATTERNS = {
    "*.pyc",
    "*.pyo",
    "*.tmp",
    "*.log",
    "*.swp",
    "*.swo",
    "*.bak",
    "*.orig",
    ".DS_Store",
    "Thumbs.db",
}

# Directories that should be removed entirely.
DIR_PATTERNS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    ".eggs",
    "*.egg-info",
    "coverage_html_report",
}

GIT_DIR = ".git"


def _is_inside_git(path: Path, root: Path) -> bool:
    """Return True if *path* is located inside the repository's .git folder."""
    try:
        path.relative_to(root / GIT_DIR)
    except ValueError:
        return False
    return True


def _collect_matches(root: Path, patterns: Iterable[str]) -> Set[Path]:
    """Return a set of paths that match any glob pattern under *root*.

    Paths inside ``.git`` are ignored to avoid corrupting repository metadata.
    """
    matches: Set[Path] = set()
    for pattern in patterns:
        for path in root.rglob(pattern):
            if _is_inside_git(path, root):
                continue
            matches.add(path)
    return matches


def _prune_nested_targets(targets: Set[Path]) -> List[Path]:
    """Return targets sorted so that nested entries are removed safely.

    Any path that is contained within another target directory is skipped to
    avoid redundant work and to produce a cleaner summary for the user.
    """

    dirs = {path for path in targets if path.is_dir()}
    pruned: List[Path] = []
    for path in sorted(targets):
        if any(dir_path in path.parents for dir_path in dirs if dir_path != path):
            continue
        pruned.append(path)
    return pruned


def find_targets(root: Path) -> List[Path]:
    """Find all files and directories that should be removed."""
    raw_targets = _collect_matches(root, FILE_PATTERNS | DIR_PATTERNS)
    return _prune_nested_targets(raw_targets)


def delete_target(path: Path) -> None:
    """Remove a file or directory recursively."""
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def estimate_size(path: Path) -> int:
    """Estimate the total size in bytes that would be freed by removing *path*."""

    if path.is_file():
        try:
            return path.stat().st_size
        except FileNotFoundError:
            return 0

    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except FileNotFoundError:
                continue
    return total


def describe_target(path: Path, root: Path) -> str:
    """Return a user-friendly description of a target path."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return f"{relative} ({'dir' if path.is_dir() else 'file'})"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually remove files instead of running in dry-run mode",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="root directory to clean (defaults to current working directory)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root: Path = args.root.resolve()

    if not root.exists():
        print(f"Root path does not exist: {root}")
        return 1

    targets = find_targets(root)

    if not targets:
        print("Nothing to clean.")
        return 0

    total_size = sum(estimate_size(path) for path in targets)

    print(f"Found {len(targets)} target(s) (~{total_size/1024:.1f} KiB):")
    for path in targets:
        size_kib = estimate_size(path) / 1024
        print(f" - {describe_target(path, root)} (~{size_kib:.1f} KiB)")

    if not args.apply:
        print("\nDry run complete. Re-run with --apply to remove these files.")
        return 0

    removed = 0
    for path in targets:
        delete_target(path)
        removed += 1

    print(f"\nRemoved {removed} item(s) and freed approximately {total_size/1024:.1f} KiB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

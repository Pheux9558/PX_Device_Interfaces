#!/usr/bin/env python3
"""Simple bump script to update version strings across known files.

Usage: python tools/bump_version.py 0.0.2

This is a lightweight replacement for bump2version when it's not available
or the config doesn't parse in the environment. It updates files in-place
and creates a git commit + tag `v<version>`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
import subprocess

FILES_TO_UPDATE = [
    ("pyproject.toml", r'version\s*=\s*"(?P<ver>[^"]+)"'),
    ("__init__.py", r'__version__\s*=\s*"(?P<ver>[^"]+)"'),
    ("px_device_interfaces/__init__.py", r'__version__\s*=\s*"(?P<ver>[^"]+)"'),
    ("px_device_interfaces.egg-info/PKG-INFO", r'Version:\s*(?P<ver>\S+)'),
]


def update_file(path: Path, pattern: str, new_version: str) -> bool:
    s = path.read_text()
    m = re.search(pattern, s)
    if not m:
        return False
    old = m.group("ver")
    if old == new_version:
        return True
    new_s = re.sub(pattern, lambda mo: mo.group(0).replace(old, new_version), s, count=1)
    path.write_text(new_s)
    print(f"Updated {path}: {old} -> {new_version}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: bump_version.py <new_version>")
        raise SystemExit(2)
    new_version = sys.argv[1]
    repo_root = Path(__file__).resolve().parents[1]

    changed = False
    for fname, patt in FILES_TO_UPDATE:
        p = repo_root / fname
        if not p.exists():
            print(f"Warning: {p} not found, skipping")
            continue
        ok = update_file(p, patt, new_version)
        if ok:
            changed = True

    if not changed:
        print("No files were updated. Aborting commit/tag.")
        raise SystemExit(0)

    # Commit and tag
    subprocess.check_call(["git", "add"] + [str(repo_root / f[0]) for f in FILES_TO_UPDATE if (repo_root / f[0]).exists()])
    subprocess.check_call(["git", "commit", "-m", f"Bump version to {new_version}"])
    tag = f"v{new_version}"
    subprocess.check_call(["git", "tag", "-a", tag, "-m", f"version {new_version}"])
    print(f"Created tag {tag}")

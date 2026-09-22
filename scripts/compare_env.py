#!/usr/bin/env python3
"""Compare the dev and prod working trees file-by-file.

Read-only by default (exit 0 = identical, 1 = differences). With ``--sync`` it
copies changed/new project files dev -> prod, removes prod-only project files and
restarts ``huntproxy`` — this is the *testing deploy* (prod is later brought back
to git with ``/opt/huntproxy/update.sh``). Runtime paths are never touched
(``.git``, ``data*``, ``.venv``, ``node_modules``, caches, ``config.yaml``).

Usage:
    python scripts/compare_env.py                 # check only
    sudo python scripts/compare_env.py --sync     # copy dev -> prod + restart (test deploy)
    sudo python scripts/compare_env.py --sync --no-restart
    python scripts/compare_env.py --json
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Runtime / local-only paths that are expected to differ between the two
# clones and must not be reported as differences.
IGNORE_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__",
    ".hypothesis", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".sixth", ".kilo", "uitest", ".tmp",
}
IGNORE_FILES = {"config.yaml", "to-dev.sh", "to-battle.sh", ".coverage", "package-lock.json"}
IGNORE_SUFFIXES = (".pyc", ".log", ".pid")


def _is_data_dir(name: str) -> bool:
    return name in ("data",) or (name.startswith("data") and name[4:].isdigit())


def _skip_dir(name: str) -> bool:
    return name in IGNORE_DIRS or _is_data_dir(name)


def _skip_file(name: str) -> bool:
    return name in IGNORE_FILES or name.endswith(IGNORE_SUFFIXES)


def _hash_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def scan(root: Path) -> dict:
    """Map relative path -> sha256 for every comparable file under *root*."""
    files = {}
    unreadable = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not _skip_dir(d))
        for name in sorted(filenames):
            if _skip_file(name):
                continue
            path = Path(dirpath) / name
            rel = str(path.relative_to(root))
            digest = _hash_file(path)
            if digest is None:
                unreadable.append(rel)
            else:
                files[rel] = digest
    return {"files": files, "unreadable": unreadable}


def compare(dev: dict, prod: dict) -> dict:
    dev_files, prod_files = dev["files"], prod["files"]
    dev_set, prod_set = set(dev_files), set(prod_files)
    only_dev = sorted(dev_set - prod_set)
    only_prod = sorted(prod_set - dev_set)
    differ = sorted(p for p in (dev_set & prod_set) if dev_files[p] != prod_files[p])
    return {
        "identical": len(dev_set & prod_set) - len(differ),
        "only_dev": only_dev,
        "only_prod": only_prod,
        "differ": differ,
        "unreadable_dev": dev["unreadable"],
        "unreadable_prod": prod["unreadable"],
    }


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    mode = 0o755 if src.suffix == ".sh" else 0o644
    shutil.copyfile(src, dst)
    os.chmod(dst, mode)


def sync(dev_root: Path, prod_root: Path, result: dict) -> None:
    """Test deploy: mirror changed/new/extra project files dev -> prod."""
    for rel in result["only_dev"] + result["differ"]:
        _copy_file(dev_root / rel, prod_root / rel)
    for rel in result["only_prod"]:
        try:
            (prod_root / rel).unlink()
        except OSError:
            pass
    print(f"synced: copied {len(result['only_dev']) + len(result['differ'])}, "
          f"removed {len(result['only_prod'])}")


def restart_service(name: str = "huntproxy") -> None:
    if os.geteuid() != 0:
        print(f"restart skipped (not root) — run: sudo systemctl restart {name}")
        return
    try:
        subprocess.run(["systemctl", "restart", name], check=True, timeout=60)
        print(f"service restarted: {name}")
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"WARN: could not restart {name}: {exc}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare (and optionally test-deploy) dev and prod trees.")
    ap.add_argument("--dev", default="/home/user/prj/huntproxy")
    ap.add_argument("--prod", default="/opt/huntproxy")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--limit", type=int, default=200, help="max paths shown per section")
    ap.add_argument("--sync", action="store_true",
                    help="test deploy: copy dev -> prod, restart, re-check")
    ap.add_argument("--no-restart", action="store_true", help="with --sync: do not restart the service")
    args = ap.parse_args()

    dev_root, prod_root = Path(args.dev), Path(args.prod)
    for root in (dev_root, prod_root):
        if not root.is_dir():
            print(f"ERROR: not a directory: {root}", file=sys.stderr)
            return 2

    result = compare(scan(dev_root), scan(prod_root))
    ok = not (result["only_dev"] or result["only_prod"] or result["differ"])

    if args.sync and not ok:
        sync(dev_root, prod_root, result)
        if not args.no_restart:
            restart_service()
        result = compare(scan(dev_root), scan(prod_root))
        ok = not (result["only_dev"] or result["only_prod"] or result["differ"])

    if args.json:
        print(json.dumps({"ok": ok, **result}, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    def show(title, items):
        if not items:
            return
        print(f"\n{title} ({len(items)}):")
        for p in items[: args.limit]:
            print(f"  {p}")
        if len(items) > args.limit:
            print(f"  … and {len(items) - args.limit} more")

    print(f"dev : {dev_root}")
    print(f"prod: {prod_root}")
    print(f"identical: {result['identical']}")
    show("only in DEV", result["only_dev"])
    show("only in PROD", result["only_prod"])
    show("different content", result["differ"])
    if result["unreadable_dev"]:
        show("unreadable in DEV (skipped)", result["unreadable_dev"])
    if result["unreadable_prod"]:
        show("unreadable in PROD (skipped)", result["unreadable_prod"])
    print("\nRESULT:", "IDENTICAL" if ok else "DIFFERENCES FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

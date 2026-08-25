#!/usr/bin/env python3
"""Rebuild web/js/pages.bundle.js from web/js/pages/*.js.

The UI used to ship ~26 separate <script src="/js/pages/*.js"> tags. Browsers
open at most 6 connections per host, so even with keep-alive the files crawl
in waves and page boot stalls for hundreds of milliseconds. One bundle turns
that into a single request.

Page modules are self-registering (router.register at eval time), so
concatenation order does not matter; sorted order keeps builds deterministic.
Bump ?v= in index.html when the bundle content changes for users with
aggressive caches.

Usage: python scripts/build_js_bundle.py [--check]
  --check  exit 1 if the bundle is stale (used by tests)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "web" / "js" / "pages"
BUNDLE = ROOT / "web" / "js" / "pages.bundle.js"


def sources() -> list[Path]:
    return sorted(PAGES_DIR.glob("*.js"))


def build() -> str:
    parts = []
    for p in sources():
        rel = p.relative_to(ROOT / "web")
        parts.append(f"/* ==== {rel} ==== */\n" + p.read_text(encoding="utf-8"))
    return "\n\n".join(parts) + "\n"


def main() -> int:
    content = build()
    if "--check" in sys.argv:
        current = BUNDLE.read_text(encoding="utf-8") if BUNDLE.exists() else ""
        if current != content:
            print("pages.bundle.js is stale — run: python scripts/build_js_bundle.py")
            return 1
        return 0
    BUNDLE.write_text(content, encoding="utf-8")
    print(f"wrote {BUNDLE.relative_to(ROOT)} ({len(content)} bytes, {len(sources())} sources)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

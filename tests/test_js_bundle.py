"""The page bundle must always match its sources.

web/index.html loads a single generated /js/pages.bundle.js instead of 26
individual script tags (browser connection limits made boot crawl in waves).
Forgetting to rebuild after editing a page would silently ship stale UI, so
the check runs on every test pass.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_js_bundle.py"


def test_js_bundle_is_fresh():
    r = subprocess.run([sys.executable, str(SCRIPT), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

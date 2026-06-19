"""Verify that every translation key used in the codebase exists in every
locale file.

This prevents situations where a key is used in JS/HTML but missing from a
locale, resulting in raw key strings (like 'nav.favorites') shown to the
user.
"""
import json
import re
from pathlib import Path

import pytest

LOCALES_DIR = Path(__file__).resolve().parent.parent / "web" / "locales"
WEB_DIR = LOCALES_DIR.parent
REFERENCE_LANG = "en"


def _collect_keys(obj, prefix=""):
    """Recursively collect all leaf keys as dot-separated paths."""
    keys = set()
    for k, v in obj.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= _collect_keys(v, full)
        else:
            keys.add(full)
    return keys


def _load_locale(lang):
    path = LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        pytest.skip(f"locale {lang} not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _all_langs():
    files = sorted(LOCALES_DIR.glob("*.json"))
    return [f.stem for f in files if f.stem != "index"]


def _collect_used_keys():
    """Collect every i18n key referenced in JS (t()/tp()) and HTML
    (data-i18n* attributes). Only keys with dots are considered — bare
    words are HTML tags or API paths caught by the regex."""
    used = set()
    for js_file in (WEB_DIR / "js").rglob("*.js"):
        src = js_file.read_text(encoding="utf-8")
        for m in re.findall(r"""[tp]\(['"]([a-zA-Z][a-zA-Z0-9_.]+)['"]""", src):
            if "." in m:
                used.add(m)
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        html = index_path.read_text(encoding="utf-8")
        for m in re.findall(r'data-i18n[a-z-]*="([a-zA-Z][a-zA-Z0-9_.]+)"', html):
            if "." in m:
                used.add(m)
    return used


@pytest.fixture(scope="module")
def used_keys():
    return _collect_used_keys()


class TestLocaleCompleteness:
    def test_locales_are_valid_json(self):
        """Every locale file must be valid JSON."""
        for lang in _all_langs():
            path = LOCALES_DIR / f"{lang}.json"
            with open(path, encoding="utf-8") as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    pytest.fail(f"{lang}.json is invalid JSON: {e}")

    @pytest.mark.parametrize("lang", _all_langs())
    def test_every_used_key_exists_in_locale(self, used_keys, lang):
        """Every key referenced in JS/HTML must exist in every locale."""
        data = _load_locale(lang)
        locale_keys = _collect_keys(data)
        missing = sorted(k for k in used_keys if k not in locale_keys)
        assert not missing, (
            f"{lang}.json is missing {len(missing)} keys used in code: "
            f"{missing}"
        )

    def test_no_stray_page_keys(self):
        """Known top-level page keys should not be accidentally nested
        inside an unrelated page block (e.g. 'favorites' inside page.hunt)."""
        guarded = {"favorites", "downloads"}
        for lang in _all_langs():
            data = _load_locale(lang)
            page = data.get("page", {})
            for page_name, block in page.items():
                if not isinstance(block, dict):
                    continue
                for stray in guarded:
                    if page_name != stray and stray in block:
                        pytest.fail(
                            f"{lang}: '{stray}' found inside page.{page_name} "
                            f"(should be page.{stray})"
                        )

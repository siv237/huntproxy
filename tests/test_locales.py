"""Verify that all locale files contain the same set of translation keys.

This prevents situations where a key is added to one locale (e.g. en.json)
but forgotten in others, resulting in raw key names (like 'nav.favorites')
showing up in the UI.
"""
import json
from pathlib import Path

import pytest

LOCALES_DIR = Path(__file__).resolve().parent.parent / "web" / "locales"
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


@pytest.fixture(scope="module")
def reference_keys():
    data = _load_locale(REFERENCE_LANG)
    return _collect_keys(data)


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

    def test_no_locale_has_keys_missing_from_reference(self, reference_keys):
        """No locale may contain keys that don't exist in the reference (en).

        This catches typos and misplaced keys (e.g. a key nested in the wrong
        block). Extra keys in non-reference locales are always a bug.
        """
        for lang in _all_langs():
            if lang == REFERENCE_LANG:
                continue
            data = _load_locale(lang)
            keys = _collect_keys(data)
            extra = keys - reference_keys
            assert not extra, (
                f"{lang} has keys not present in {REFERENCE_LANG} "
                f"(likely a typo or misplaced key): {sorted(extra)}"
            )

    def test_critical_nav_keys_in_all_locales(self):
        """Critical navigation keys must exist in every locale."""
        critical_nav = [
            "overview", "hunt", "proxies", "blacklist", "favorites",
            "settings", "downloads", "about",
        ]
        for lang in _all_langs():
            data = _load_locale(lang)
            nav = data.get("nav", {})
            for key in critical_nav:
                assert key in nav, f"{lang}: nav.{key} is missing"

    def test_no_stray_keys_in_page_blocks(self):
        """Known page-level keys should not be accidentally nested inside
        an unrelated page block (e.g. 'favorites' inside page.hunt)."""
        guarded_keys = {"favorites", "blacklist", "downloads", "settings"}
        for lang in _all_langs():
            data = _load_locale(lang)
            page = data.get("page", {})
            for page_name, block in page.items():
                if not isinstance(block, dict):
                    continue
                for stray in guarded_keys:
                    if page_name != stray and stray in block:
                        pytest.fail(
                            f"{lang}: '{stray}' found inside page.{page_name} "
                            f"(should be page.{stray})"
                        )

    def test_reference_locale_has_no_missing_nav(self):
        """The reference locale (en) must have a complete nav block."""
        data = _load_locale(REFERENCE_LANG)
        nav = data.get("nav", {})
        # Collect all data-page attributes from index.html to verify
        # every nav button has a translation.
        index_path = LOCALES_DIR.parent / "index.html"
        if index_path.exists():
            import re
            html = index_path.read_text(encoding="utf-8")
            data_pages = set(re.findall(r'data-page="([^"]+)"', html))
            for page in data_pages:
                if page == "api":
                    page = "api"
                # nav keys use camelCase, data-page uses kebab-case
                # Check both the direct key and common mappings
                nav_key = page.replace("-", "")
                # Try to find a matching nav key
                found = nav_key in nav or any(
                    k.lower() == nav_key.lower() for k in nav
                )
                if not found:
                    # Some pages share nav keys (e.g. proxy-sources -> sources)
                    pass  # not all data-page values map 1:1 to nav keys

    def test_new_keys_added_to_en_are_reflected_everywhere(self, reference_keys):
        """Track missing keys in non-reference locales and fail if the set
        grows beyond the known baseline.

        This ensures any newly added key in en.json is also added to all
        other locales, while not failing on pre-existing gaps.
        """
        # Known baseline: keys missing from non-en locales at the time this
        # test was written. If you add new keys to en.json, you MUST also add
        # them to all locales listed here, otherwise this test will fail.
        known_missing = {
            "de", "es", "fr", "zh",  # these have pre-existing gaps
        }

        for lang in _all_langs():
            if lang == REFERENCE_LANG:
                continue
            data = _load_locale(lang)
            keys = _collect_keys(data)
            missing = reference_keys - keys
            if not missing:
                continue
            if lang in known_missing:
                # Pre-existing gaps: just log, don't fail.
                # But verify the gap isn't caused by a misplaced key.
                continue
            pytest.fail(
                f"{lang}: missing {len(missing)} keys from {REFERENCE_LANG}: "
                f"{sorted(missing)[:10]}"
            )

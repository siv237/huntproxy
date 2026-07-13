import tempfile
from pathlib import Path

import hunt.constants as constants
from hunt.constants import _load_default_sources, SOURCES_DIR


class TestIniSources:
    def test_real_default_ini_loaded(self):
        assert len(constants.DEFAULT_SOURCES) >= 20
        assert len(constants.DEFAULT_IP_BLACKLIST_SOURCES) >= 4
        assert len(constants.DEFAULT_BLOCKLIST_SOURCES) >= 3

    def test_blocklist_sources_have_country_and_direction(self):
        for sid, name, country, direction, list_type, url, klass, route in constants.DEFAULT_BLOCKLIST_SOURCES:
            assert country and country.isalpha() and len(country) == 2
            assert direction in ("inside", "outside", "domestic")
            assert list_type in ("ip", "domain")
            assert klass in ("block", "white")
            assert url.startswith("http")

    def test_known_ru_blocklists_present(self):
        ids = {b[0] for b in constants.DEFAULT_BLOCKLIST_SOURCES}
        assert {"ru-rkn-ip", "ru-rkn-domains", "ru-inside-domains", "ru-geoblock-domains"} <= ids

    def test_ru_inside_vs_outside_distinct(self):
        bl = {b[0]: b for b in constants.DEFAULT_BLOCKLIST_SOURCES}
        assert bl["ru-rkn-ip"][3] == "inside"
        assert bl["ru-inside-domains"][3] == "inside"
        assert bl["ru-geoblock-domains"][3] == "outside"

    def test_removed_sources_absent(self):
        ids = {b[0] for b in constants.DEFAULT_BLOCKLIST_SOURCES}
        assert "ru-banned-domains" not in ids
        assert not any("medvedeff" in b[5] for b in constants.DEFAULT_BLOCKLIST_SOURCES)

    def test_geoblock_uses_categories_list(self):
        bl = {b[0]: b for b in constants.DEFAULT_BLOCKLIST_SOURCES}
        assert "Categories/geoblock.lst" in bl["ru-geoblock-domains"][5]
        assert "Russia/outside-raw.lst" not in bl["ru-geoblock-domains"][5]

    def test_parser_from_custom_ini(self, monkeypatch):
        ini = (
            "[proxy]\n"
            "mine = https://example.com/proxies.txt\n"
            "[ip_blacklist]\n"
            "My Feed = https://example.com/ips.txt\n"
            "[blocklist:xx-test]\n"
            "name = Test\n"
            "country = XX\n"
            "direction = outside\n"
            "type = domain\n"
            "url = https://example.com/domains.lst\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "custom.ini").write_text(ini, encoding="utf-8")
            monkeypatch.setattr(constants, "SOURCES_DIR", d)
            proxy, ipbl, block = _load_default_sources()
            assert proxy == ["https://example.com/proxies.txt"]
            assert ipbl == [("My Feed", "https://example.com/ips.txt")]
            assert block == [
                ("xx-test", "Test", "XX", "outside", "domain", "https://example.com/domains.lst", "block", "")
            ]

    def test_parser_white_domestic_with_route(self, monkeypatch):
        ini = (
            "[blocklist:xx-white]\n"
            "name = White\n"
            "country = RU\n"
            "direction = domestic\n"
            "class = white\n"
            "type = domain\n"
            "route = direct\n"
            "url = https://example.com/white.lst\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "w.ini").write_text(ini, encoding="utf-8")
            monkeypatch.setattr(constants, "SOURCES_DIR", d)
            _, _, block = _load_default_sources()
            assert block == [
                ("xx-white", "White", "RU", "domestic", "domain", "https://example.com/white.lst", "white", "direct")
            ]

    def test_parser_bad_direction_and_class_defaulted(self, monkeypatch):
        ini = (
            "[blocklist:xx-bad]\n"
            "name = Bad\n"
            "country = RU\n"
            "direction = sideways\n"
            "class = weird\n"
            "type = domain\n"
            "url = https://example.com/x.lst\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "b.ini").write_text(ini, encoding="utf-8")
            monkeypatch.setattr(constants, "SOURCES_DIR", d)
            _, _, block = _load_default_sources()
            assert block == []

    def test_multiple_ini_files_merged(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.ini").write_text(
                "[proxy]\nfirst = https://a.example/1.txt\n", encoding="utf-8")
            (d / "b.ini").write_text(
                "[proxy]\nsecond = https://b.example/2.txt\n", encoding="utf-8")
            monkeypatch.setattr(constants, "SOURCES_DIR", d)
            proxy, _, _ = _load_default_sources()
            assert proxy == ["https://a.example/1.txt", "https://b.example/2.txt"]

    def test_empty_sources_dir_yields_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(constants, "SOURCES_DIR", tmp_path)
        proxy, ipbl, block = _load_default_sources()
        assert proxy == [] and ipbl == [] and block == []

    def test_incomplete_blocklist_skipped(self, monkeypatch):
        ini = (
            "[blocklist:bad]\n"
            "name = Bad\n"
            "country = RU\n"
            "url = https://example.com/x\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "x.ini").write_text(ini, encoding="utf-8")
            monkeypatch.setattr(constants, "SOURCES_DIR", d)
            _, _, block = _load_default_sources()
            assert block == []

    def test_duplicate_blocklist_id_skipped(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.ini").write_text(
                "[blocklist:dup]\nname=A\ncountry=RU\ndirection=inside\ntype=ip\nurl=https://a.example/ip\n",
                encoding="utf-8")
            (d / "b.ini").write_text(
                "[blocklist:dup]\nname=B\ncountry=XX\ndirection=outside\ntype=domain\nurl=https://b.example/d\n",
                encoding="utf-8")
            monkeypatch.setattr(constants, "SOURCES_DIR", d)
            _, _, block = _load_default_sources()
            assert len(block) == 1
            assert block[0][0] == "dup"
            assert block[0][1] == "A"  # first file wins, second skipped

    def test_no_hardcoded_lists_remain(self):
        src = (Path(constants.__file__).read_text(encoding="utf-8"))
        assert "monosans/proxy-list" not in src
        assert "antifilter.download" not in src
        assert "emergingthreats" not in src

"""Functional split of the huntproxy backend."""

import configparser
import logging
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

CONFIG_PATH = PROJECT_DIR / "config.yaml"

DATA_DIR = PROJECT_DIR / "data"

# Default list sources live in editable INI files under sources/ (outside data/,
# so they survive a state reset). Every *.ini in this folder is parsed at import
# time and merged into the DEFAULT_* collections below.
SOURCES_DIR = PROJECT_DIR / "sources"

HUNT_HTML_PATH = PROJECT_DIR / "hunt.html"

WEB_DIR = PROJECT_DIR / "web"

STATIC_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
}

logger = logging.getLogger("huntproxy.hunt")


def _load_default_sources():
    """Parse every *.ini in SOURCES_DIR and return the three default collections.

    INI syntax (each type is marked its own way, all optional and combinable):

      [proxy]                 key = human label, value = URL
      [ip_blacklist]          key = source name,  value = URL
      [blocklist:<id>]        fields: name, country, direction, type, url
                              direction = inside | outside
                              type      = ip | domain

    Returns (proxy_urls, ip_blacklist, blocklists) where:
      proxy_urls    -> list[str]
      ip_blacklist  -> list[(name, url)]
      blocklists    -> list[(sid, name, country, direction, list_type, url)]
    """
    proxy_urls: list = []
    ip_blacklist: list = []
    blocklists: list = []

    ini_files = sorted(SOURCES_DIR.glob("*.ini")) if SOURCES_DIR.is_dir() else []
    if not ini_files:
        logger.warning("No source INI files found in %s", SOURCES_DIR)
        return proxy_urls, ip_blacklist, blocklists

    # [proxy] and [ip_blacklist] are simple key=url maps; merging across files
    # (later value wins per key) is acceptable, so one shared parser is fine.
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str  # preserve case in keys (source names matter)
    for path in ini_files:
        try:
            parser.read(path, encoding="utf-8")
        except Exception as e:
            logger.error("Failed to read %s: %s", path, e)

    # [proxy] — key is just a human-readable label; only the URL is used.
    if parser.has_section("proxy"):
        for _label, url in parser.items("proxy"):
            url = (url or "").strip()
            if url:
                proxy_urls.append(url)

    # [ip_blacklist] — key is the source name, value is the URL.
    if parser.has_section("ip_blacklist"):
        for name, url in parser.items("ip_blacklist"):
            url = (url or "").strip()
            if url:
                ip_blacklist.append((name.strip(), url))

    # [blocklist:<id>] — one section per country blocklist source. Parsed
    # per-file so that a duplicate id in another INI is detected explicitly
    # instead of silently field-merged by configparser.
    seen_sids = set()
    for path in ini_files:
        fp = configparser.ConfigParser(strict=False, interpolation=None)
        fp.optionxform = str
        try:
            fp.read(path, encoding="utf-8")
        except Exception:
            continue
        for section in fp.sections():
            if not section.startswith("blocklist:"):
                continue
            sid = section.split(":", 1)[1].strip()
            if not sid:
                continue
            if sid in seen_sids:
                logger.warning("Duplicate blocklist id %s in %s, skipping", sid, path.name)
                continue
            get = lambda k, d="": fp.get(section, k, fallback=d).strip()
            name = get("name")
            country = get("country").upper()
            direction = get("direction").lower()
            list_type = get("type").lower()
            url = get("url")
            if not (name and country and direction and list_type and url):
                logger.warning("Skipping incomplete blocklist source [%s] in %s", section, path.name)
                continue
            if direction not in ("inside", "outside"):
                logger.warning("Blocklist %s has bad direction=%r (expected inside/outside)", sid, direction)
                continue
            if list_type not in ("ip", "domain"):
                logger.warning("Blocklist %s has bad type=%r (expected ip/domain)", sid, list_type)
                continue
            seen_sids.add(sid)
            blocklists.append((sid, name, country, direction, list_type, url))

    logger.info(
        "Loaded default sources from INI: %d proxy, %d ip_blacklist, %d blocklist",
        len(proxy_urls), len(ip_blacklist), len(blocklists),
    )
    return proxy_urls, ip_blacklist, blocklists


DEFAULT_SOURCES, DEFAULT_IP_BLACKLIST_SOURCES, DEFAULT_BLOCKLIST_SOURCES = _load_default_sources()

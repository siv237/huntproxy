"""Functional split of the huntproxy backend."""

import logging
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

CONFIG_PATH = PROJECT_DIR / "config.yaml"

DATA_DIR = PROJECT_DIR / "data"

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

DEFAULT_IP_BLACKLIST_SOURCES = [
    ("Emerging Threats Compromised", "https://rules.emergingthreats.net/blockrules/compromised-ips.txt"),
    ("FireHOL Level 1", "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level1.netset"),
    ("IPsum Threat Feed", "https://raw.githubusercontent.com/stamparm/ipsum/master/ipsum.txt"),
    ("Blocklist.de All", "https://lists.blocklist.de/lists/all.txt"),
]

# Country blocklist sources — organized by country and direction.
#   direction "inside"  = resources blocked WITHIN that country (e.g. RKN blocks in RU)
#   direction "outside" = resources of that country blocked ABROAD (e.g. RU services geo-blocked outside RU)
#   list_type "ip"      = IP/CIDR list → fed into ip_blacklist scoring
#   list_type "domain"  = domain list  → fed into domain routing (route=proxy)
DEFAULT_BLOCKLIST_SOURCES = [
    # Russia — inside (РКН blocks resources within Russia)
    ("ru-rkn-ip", "Russia RKN Blocked IPs", "RU", "inside", "ip",
     "https://antifilter.download/list/allyouneed.lst"),
    ("ru-rkn-domains", "Russia RKN Blocked Domains", "RU", "inside", "domain",
     "https://antifilter.download/list/domains.lst"),
    # Russia — outside (foreign services block Russian users / RU geo-restricted content)
    ("ru-geoblock-domains", "Russia Geoblocked Domains", "RU", "outside", "domain",
     "https://raw.githubusercontent.com/itdoginfo/allow-domains/main/Russia/outside-raw.lst"),
]

DEFAULT_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/socks5.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/socks4.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks4.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
]

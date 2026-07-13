"""Domain blocklist text parsing — normalizes upstream rule formats
(plain / Clash / v2fly) into plain domain routing patterns.

Extracted from ``hunt.blocklists`` to keep that module under the
architecture line limit; this is a pure, dependency-free helper.
"""
import re

_CLASH_RULE_RE = re.compile(
    r"^\s*-\s*['\"]?(?P<t>DOMAIN|DOMAIN-SUFFIX|DOMAIN-KEYWORD|DOMAIN-REGEXP|IP-CIDR|IP6-CIDR)"
    r"\s*,\s*(?P<v>.+?)['\"]?\s*$"
)
_V2FLY_RULE_RE = re.compile(
    r"^(?P<t>domain|domain-suffix|domain-keyword|domain-regexp|full)\s*[:=]\s*(?P<v>.+?)\s*$"
)


def normalize_domain_pattern(raw: str):
    """Normalize one source line into a domain pattern, or None to skip.

    Handles plain domain lists, Clash rules (DOMAIN-SUFFIX,vk.com) and
    v2fly rules (domain-suffix:vk.com). Strips scheme, `:port` and inline
    comments; CIDR/IP lines are skipped (not domain-routed)."""
    line = (raw or "").strip()
    if not line:
        return None
    if line.startswith("#") or line.startswith(";") or line.startswith("//"):
        return None
    for sep in (" #", "\t#", " //", " ;"):
        idx = line.find(sep)
        if idx != -1:
            line = line[:idx].strip()
    if not line:
        return None
    m = _CLASH_RULE_RE.match(line)
    if m:
        t = m.group("t")
        v = m.group("v").strip().strip("'\"")
        if t in ("IP-CIDR", "IP6-CIDR"):
            return None
        if t == "DOMAIN-SUFFIX":
            return _clean_plain_domain(v, prefix="*.")
        return _clean_plain_domain(v)
    m = _V2FLY_RULE_RE.match(line)
    if m:
        t = m.group("t")
        v = m.group("v").strip()
        if t == "domain-suffix":
            return _clean_plain_domain(v, prefix="*.")
        return _clean_plain_domain(v)
    return _clean_plain_domain(line)


def _clean_plain_domain(v: str, prefix: str = ""):
    v = (v or "").strip().lower()
    if not v:
        return None
    v = re.sub(r"^(https?|wss?|socks5?)://", "", v)
    mm = re.match(r"^([a-z0-9.*-]+)(:\d+)?$", v)
    if mm and mm.group(2):
        v = mm.group(1)
    v = prefix + v
    if not ('.' in v or v.startswith("*.")):
        return None
    return v

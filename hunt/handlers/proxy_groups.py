"""Proxy list/grouping handlers — extracted from handlers/proxy.py."""

import json

from hunt.geo import country_code_from_name, country_flag, country_name_from_code
from hunt.handlers import _int_param


class ProxyGroupMixin:
    async def _proxies_grouped(self, qs):
        all_proxies = list(self.state.ratings.values())
        status = qs.get("status", "")
        sources_map = {s["id"]: s.get("name", s["id"]) for s in self.state.get_proxy_sources()}
        group_by = qs.get("group_by", "country")
        if group_by == "source":
            groups = self._group_by_source(all_proxies, sources_map)
        elif group_by == "protocol":
            groups = self._group_by_protocol(all_proxies)
        else:
            groups = self._group_by_country(all_proxies)
        result = []
        for g in groups.values():
            g["alive_pct"] = round(g["alive"] / g["total"] * 100, 1) if g["total"] else 0
            if status == "alive" and g["alive"] == 0:
                continue
            if status == "dead" and g["dead"] == 0:
                continue
            result.append(g)
        result.sort(key=lambda g: g["alive"], reverse=True)
        return json.dumps({"groups": result, "total": len(all_proxies)}), 200, "application/json"

    def _group_by_source(self, proxies, sources_map):
        groups = {}
        for r in proxies:
            src_ids = self.state._addr_sources.get(r.address, [])
            if not src_ids:
                key, label = "_unknown", "Unknown source"
            else:
                key, label = src_ids[0], sources_map.get(src_ids[0], src_ids[0])
            self._add_to_group(groups, key, label, r)
        return groups

    def _group_by_protocol(self, proxies):
        groups = {}
        labels = {"http": "HTTP", "https": "HTTPS", "socks4": "SOCKS4", "socks5": "SOCKS5"}
        for r in proxies:
            proto = r.protocol or "http"
            if proto in ("socks5", "socks4"):
                key = proto
            elif proto == "https" or r.ssl_supported:
                key = "https"
            else:
                key = "http"
            self._add_to_group(groups, key, labels.get(key, key.upper()), r)
        return groups

    def _group_by_country(self, proxies):
        groups = {}
        for r in proxies:
            cc = r.country_code or country_code_from_name(r.country) or "??"
            label = f"{country_flag(cc)} {country_name_from_code(cc)}"
            self._add_to_group(groups, cc, label, r)
        return groups

    def _add_to_group(self, groups, key, label, r):
        if key not in groups:
            groups[key] = {"key": key, "label": label, "total": 0, "alive": 0, "dead": 0}
        groups[key]["total"] += 1
        if self._proxy_alive(r):
            groups[key]["alive"] += 1
        else:
            groups[key]["dead"] += 1

    async def _proxies_group_proxies(self, qs):
        group_key = qs.get("group_key", "")
        group_by = qs.get("group_by", "country")
        group_status = qs.get("status", "")
        all_ratings = list(self.state.ratings.values())
        if group_by == "source":
            filtered = [r for r in all_ratings if (
                (self.state._addr_sources.get(r.address, []) or ["_unknown"])[0] == group_key
            )]
        elif group_by == "protocol":
            filtered = [r for r in all_ratings if self._proto_key(r) == group_key]
        else:
            filtered = [r for r in all_ratings if (r.country_code or country_code_from_name(r.country) or "??") == group_key]
        filtered = self._filter_by_status(filtered, group_status)
        filtered.sort(key=lambda r: r.score, reverse=True)
        return json.dumps({"proxies": [r.to_dict() for r in filtered]}), 200, "application/json"

    def _proto_key(self, r):
        proto = r.protocol or "http"
        if proto in ("socks5", "socks4"):
            return proto
        if proto == "https" or r.ssl_supported:
            return "https"
        return "http"

    def _filter_by_status(self, proxies, status):
        if status == "alive":
            return [r for r in proxies if self._proxy_alive(r)]
        if status == "dead":
            return [r for r in proxies if r.last_status == "failed"]
        if status == "blacklisted":
            return [r for r in proxies if r.is_blacklisted]
        return proxies

    async def _proxies_list(self, qs):
        status = qs.get("status", "")
        page = _int_param(qs, "page", 1)
        limit = _int_param(qs, "limit", 20)
        all_proxies = list(self.state.ratings.values())
        filtered = self._filter_by_status(all_proxies, status)
        total = len(filtered)
        start = (page - 1) * limit
        page_data = filtered[start:start + limit]
        proxy_list = []
        for r in page_data:
            d = r.to_dict()
            d["source_ids"] = self.state._addr_sources.get(r.address, [])
            proxy_list.append(d)
        return json.dumps({
            "total": total, "page": page, "limit": limit, "proxies": proxy_list,
        }), 200, "application/json"

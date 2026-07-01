"""Functional split of the huntproxy backend."""

import asyncio
import json
import ssl as _ssl
import time
from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect
from hunt.geo import country_code_from_name
from hunt.models import ProxyRating

class CheckRatingMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})
    def _record_proxy_check(self, addr: str, ts: float, latency: float,
                                  speed: float, ok: bool):
            try:
                conn = self._stats_db()
                conn.execute(
                    "INSERT INTO proxy_checks (address, ts, latency, speed, ok) VALUES (?,?,?,?,?)",
                    (addr, ts, latency, speed, 1 if ok else 0),
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error("record proxy check: %s", e)


    def _update_rating(self, addr: str, ok: bool, country: str, latency: float,
                            supports_connect: bool = False, mitm_suspect: bool = False,
                            egress: dict = None, listen: dict = None,
                            speed: float = 0.0, country_code: str = "",
                            ssl_supported: bool = False):
            r = self.ratings.get(addr)
            if not r:
                r = self._create_rating(addr, country, country_code)
            was_working = r.checks_ok > 0
            r.checks_total += 1
            r.last_check = time.time()
            r.last_latency = latency
            if ok:
                self._apply_ok_result(r, country, country_code, latency, speed,
                                      supports_connect, ssl_supported, mitm_suspect,
                                      egress or {}, listen or {})
            else:
                r.last_status = "failed"
                r.consecutive_fails += 1
            self.ratings[addr] = r
            self._dirty_ratings.add(addr)
            if r.egress_ip:
                self._apply_ip_blacklist_to_proxy(addr, r.egress_ip)
            if ok or was_working:
                self._record_proxy_check(addr, r.last_check, latency, speed, ok)
            self._rating_updates_since_save += 1
            if self._rating_updates_since_save >= 200:
                self._save_dirty_ratings()
                self._save_working_file()
                self._rating_updates_since_save = 0
            elif self._rating_updates_since_save % 50 == 0:
                self._save_dirty_ratings()

    def _create_rating(self, addr: str, country: str, country_code: str) -> ProxyRating:
        r = ProxyRating(
            address=addr,
            country=country,
            country_code=country_code or country_code_from_name(country),
            first_seen=time.time(),
            source_ids=list(self._addr_sources.get(addr, [])),
        )
        try:
            p = int(addr.rsplit(":", 1)[1])
            if p in (1080, 10808, 9050):
                r.protocol = "socks5"
            elif p == 4145:
                r.protocol = "socks4"
        except ValueError:
            pass
        return r

    def _apply_ok_result(self, r: ProxyRating, country: str, country_code: str,
                         latency: float, speed: float, supports_connect: bool,
                         ssl_supported: bool, mitm_suspect: bool,
                         egress: dict, listen: dict):
        r.checks_ok += 1
        r.latency_sum += latency
        r.latency_count += 1
        r.last_status = "ok"
        r.last_ok = time.time()
        r.consecutive_fails = 0
        if speed > 0:
            r.speed_sum += speed
            r.speed_count += 1
            r.last_speed = speed
            r.speed_fails = 0
        else:
            r.speed_fails += 1
        if country and (not r.country or len(country) > len(r.country)):
            r.country = country
        if country_code and not r.country_code:
            r.country_code = country_code
        elif country and not r.country_code:
            r.country_code = country_code_from_name(country)
        r.supports_connect = supports_connect
        r.ssl_supported = ssl_supported
        if ssl_supported and r.protocol not in ('socks5', 'socks4'):
            r.protocol = 'https'
        if mitm_suspect:
            r.mitm_suspect = True
        if egress:
            r.egress_ip = egress.get("egress_ip") or r.egress_ip
            r.egress_city = egress.get("egress_city") or r.egress_city
            r.egress_isp = egress.get("egress_isp") or r.egress_isp
            r.egress_country = egress.get("egress_country") or r.egress_country
            if egress.get("egress_country") and not r.egress_country_code:
                r.egress_country_code = country_code_from_name(egress["egress_country"])
        if listen:
            r.listen_country = listen.get("country") or r.listen_country
            if listen.get("country") and not r.listen_country_code:
                r.listen_country_code = country_code_from_name(listen["country"])
            r.listen_city = listen.get("city") or r.listen_city
            r.listen_isp = listen.get("isp") or r.listen_isp


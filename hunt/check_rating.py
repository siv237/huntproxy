"""Functional split of the huntproxy backend."""

import time
from hunt.constants import logger
from hunt.geo import country_code_from_name
from hunt.models import ProxyRating
from hunt.check_rating_apply import CheckRatingApplyMixin

class CheckRatingMixin(CheckRatingApplyMixin):
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})
    def _record_proxy_check(self, addr: str, ts: float, latency: float,
                                  speed: float, ok: bool):
            self._proxy_check_buffer.append((addr, ts, latency, speed, 1 if ok else 0))
            if len(self._proxy_check_buffer) >= 2000:
                self._flush_proxy_checks()

    def _flush_proxy_checks(self):
        """Flush the buffered proxy_checks history in a single transaction.

        Called automatically when the buffer fills, and at every persistence
        checkpoint (_save_dirty_ratings / _save_state) so no history is lost
        between the periodic rating saves."""
        buf = self._proxy_check_buffer
        if not buf:
            return
        try:
            self._stats_writer().submit(
                "INSERT INTO proxy_checks (address, ts, latency, speed, ok) VALUES (?,?,?,?,?)",
                list(buf),
            )
        except Exception as e:
            logger.error("record proxy check: %s", e)
        finally:
            buf.clear()


    def _update_rating(self, addr: str, ok: bool, country: str, latency: float,
                            supports_connect: bool = False, mitm_suspect: bool = False,
                            egress: dict = None, listen: dict = None,
                            speed: float = 0.0, country_code: str = "",
                            ssl_supported: bool = False, fraud: dict = None):
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
                                      egress or {}, listen or {}, fraud or {})
            else:
                r.last_status = "failed"
                r.consecutive_fails += 1
            r.update_reliability(ok)
            self.ratings[addr] = r
            self._dirty_ratings.add(addr)
            if r.egress_ip:
                self._apply_ip_blacklist_to_proxy(addr, r.egress_ip)
            if ok or was_working:
                self._record_proxy_check(addr, r.last_check, latency, speed, ok)
            self._rating_updates_since_save += 1
            if self._rating_updates_since_save >= 200:
                self._save_dirty_ratings()
                self._rating_updates_since_save = 0
            elif self._rating_updates_since_save % 50 == 0:
                self._save_dirty_ratings()

    def _record_traffic_fail(self, addr: str):
        """Lightweight rating hit from a real traffic failure (502/no-upstream).

        Unlike _update_rating, this does NOT run a full check (geo/mitm/speed)
        — it only nudges consecutive_fails and last_status so the proxy sinks
        in the score ranking as it fails real user requests, without waiting
        for the next health-check cycle. The increment itself is throttled
        (see ProxyRating.record_traffic_fail): one user page load producing
        several connection errors must not count as independent failures.
        Batching/saving mirrors _update_rating.
        """
        r = self.ratings.get(addr)
        if not r:
            return
        r.last_status = "failed"
        r.record_traffic_fail()
        r.last_check = time.time()
        self._dirty_ratings.add(addr)
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

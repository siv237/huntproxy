"""State persistence methods — extracted from state.py."""
import json
import time
from hunt.constants import logger
from hunt.geo import country_code_from_name
from hunt.models import ProxyRating
from hunt.state_working import StateWorkingMixin

class StatePersistenceMixin(StateWorkingMixin):
    def _load_state(self):
        try:
            conn = self._db()
            self._load_ratings_from_db(conn)
            self._load_blacklist_from_db(conn)
            self._load_favorites_from_db(conn)
            self._load_runtime_state_from_db(conn)
            conn.close()
            if self.ratings:
                logger.info(f"Loaded {len(self.ratings)} ratings from SQLite")
        except Exception as e:
            logger.warning(f"State load failed: {e}")

    def _load_ratings_from_db(self, conn):
        self.ratings.clear()
        repaired = []
        for row in conn.execute("SELECT address, data FROM ratings"):
            try:
                d = json.loads(row["data"])
            except Exception:
                logger.debug("skipped corrupt rating row", exc_info=True)
                continue
            r = self._build_rating_from_dict(d)
            if self._repair_rating_codes(r):
                repaired.append(r.address)
            self.ratings[r.address] = r
        if repaired:
            try:
                self._dirty_ratings.update(repaired)
            except Exception:
                logger.debug("suppressed", exc_info=True)

    def _repair_rating_codes(self, r) -> bool:
        """Ensure country codes match their country names.

        The country name is refreshed on every check, but the code used to be
        derived only when empty — old rows can pair "United States" with an
        outdated "CL" (proxy hopped countries), which renders the wrong flag.
        Returns True if any code was fixed.
        """
        changed = False
        for name, code_attr in (
            (r.egress_country, "egress_country_code"),
            (r.listen_country, "listen_country_code"),
            (r.country, "country_code"),
        ):
            code = getattr(r, code_attr)
            if not name:
                continue
            if not code:
                derived = country_code_from_name(name)
                if derived:
                    setattr(r, code_attr, derived)
                    changed = True
            else:
                derived = country_code_from_name(name)
                if derived and derived != code:
                    setattr(r, code_attr, derived)
                    changed = True
        return changed

    def _build_rating_from_dict(self, d: dict) -> ProxyRating:
        checks_ok = d.get("checks_ok", 0)
        stored_avg = d.get("latency_avg", 0)
        last_latency = d.get("last_latency", 0)
        latency_sum = d.get("latency_sum", stored_avg * checks_ok)
        latency_count = d.get("latency_count", checks_ok)
        if latency_count:
            if abs(latency_sum / latency_count - stored_avg) > 0.001:
                latency_sum = stored_avg * latency_count
            if stored_avg == 0 and last_latency > 0:
                latency_sum = last_latency * latency_count
        return ProxyRating(
            address=d["address"],
            country=d.get("country", ""),
            country_code=d.get("country_code", ""),
            protocol=d.get("protocol", "http"),
            latency_sum=latency_sum,
            latency_count=latency_count,
            last_latency=last_latency,
            checks_total=d.get("checks_total", 0),
            checks_ok=checks_ok,
            last_check=d.get("last_check", 0),
            last_ok=d.get("last_ok", 0),
            last_status=d.get("last_status", "untested"),
            first_seen=d.get("first_seen", 0),
            supports_connect=d.get("supports_connect", False),
            mitm_suspect=d.get("mitm_suspect", False),
            last_speed=d.get("last_speed", 0.0),
            speed_sum=d.get("speed_sum", 0),
            speed_count=d.get("speed_count", 0),
            speed_fails=d.get("speed_fails", 0),
            consecutive_fails=d.get("consecutive_fails", 0),
            egress_http_ip=d.get("egress_http_ip", ""),
            egress_http_country=d.get("egress_http_country", ""),
            egress_ip=d.get("egress_ip", ""),
            egress_city=d.get("egress_city", ""),
            egress_isp=d.get("egress_isp", ""),
            egress_country=d.get("egress_country", ""),
            egress_country_code=d.get("egress_country_code", ""),
            listen_country=d.get("listen_country", ""),
            listen_country_code=d.get("listen_country_code", ""),
            listen_city=d.get("listen_city", ""),
            listen_isp=d.get("listen_isp", ""),
            ssl_supported=d.get("ssl_supported", False),
            fraud_hosting=d.get("fraud_hosting", False),
            fraud_proxy=d.get("fraud_proxy", False),
            fraud_mobile=d.get("fraud_mobile", False),
            fraud_score_raw=d.get("fraud_score_raw", -1),
            fraud_checked_ts=d.get("fraud_checked_ts", 0.0),
            fraud_raw_ts=d.get("fraud_raw_ts", 0.0),
            fraud_attempt_ts=d.get("fraud_attempt_ts", 0.0),
            sr_ewma=d.get("sr_ewma", -1.0),
            latency_ewma=d.get("latency_ewma", -1.0),
            speed_ewma=d.get("speed_ewma", -1.0),
            last_traffic_fail_ts=d.get("last_traffic_fail_ts", 0.0),
            ip_blacklist_reason=d.get("ip_blacklist_reason", ""),
            ip_blacklist_hits=d.get("ip_blacklist_hits", 0),
            ip_blacklist_sources=d.get("ip_blacklist_sources", []),
            in_blacklist=d.get("in_blacklist", False),
            blacklist_reason=d.get("blacklist_reason", ""),
            is_favorite=d.get("is_favorite", False),
        )

    def _load_blacklist_from_db(self, conn):
        self.blacklist.clear()
        for row in conn.execute("SELECT address, reason FROM blacklist"):
            addr = row["address"]
            self.blacklist[addr] = row["reason"] or ""
            if addr in self.ratings:
                self.ratings[addr].in_blacklist = True
                self.ratings[addr].blacklist_reason = self.blacklist[addr]

    def _load_favorites_from_db(self, conn):
        self.favorites.clear()
        for row in conn.execute("SELECT address FROM favorites"):
            self.favorites.add(row["address"])
            if row["address"] in self.ratings:
                self.ratings[row["address"]].is_favorite = True

    def _load_runtime_state_from_db(self, conn):
        for row in conn.execute("SELECT key, value FROM runtime_state"):
            if row["key"] == "proxy_runner":
                pr = json.loads(row["value"])
                self._proxy_direct_mode = pr.get("direct_mode", False)
                self._proxy_active_addr = pr.get("active_proxy_addr")
                self._socks5_port = pr.get("socks5_port", 17278)
            elif row["key"] == "services":
                services = json.loads(row["value"])
                self._hunt_running = services.get("hunt_running", False)
                self._proxy_running = services.get("proxy_running", False)
                self._proxy_port = services.get("proxy_port", 17277)
                self._socks5_running = services.get("socks5_running", False)
                self._socks5_port = services.get("socks5_port", 17278)
                self._transparent_running = services.get("transparent_running", False)
                self._transparent_port = services.get("transparent_port", 17477)
            elif row["key"] == "country_filter":
                self.country_filter = row["value"] or ""
            elif row["key"] == "switch_history":
                try:
                    self._proxy_switch_history = json.loads(row["value"] or "[]")
                except Exception:
                    self._proxy_switch_history = []

    def _save_state(self):
            try:
                self._flush_proxy_checks()
                w = self._state_writer()
                # ratings
                w.submit("DELETE FROM ratings", [()])
                w.submit(
                    "INSERT INTO ratings (address, data) VALUES (?, ?)",
                    [(r.address, json.dumps(r.to_dict())) for r in self.ratings.values()],
                )
                # blacklist
                w.submit("DELETE FROM blacklist", [()])
                w.submit(
                    "INSERT INTO blacklist (address, reason) VALUES (?, ?)",
                    [(addr, reason or "") for addr, reason in self.blacklist.items()],
                )
                # favorites
                w.submit("DELETE FROM favorites", [()])
                w.submit(
                    "INSERT OR REPLACE INTO favorites (address) VALUES (?)",
                    [(addr,) for addr in self.favorites],
                )
                # runtime state — only replace the keys this module owns, so
                # keys written by other subsystems (e.g. last_vacuum_* from
                # db_maintenance) survive the full save.
                w.submit(
                    "DELETE FROM runtime_state WHERE key IN "
                    "(?, ?, ?, ?)",
                    ("proxy_runner", "services", "country_filter", "switch_history"),
                )
                runtime = [
                    ("proxy_runner", json.dumps({
                        "direct_mode": getattr(self, '_proxy_direct_mode', False),
                        "active_proxy_addr": getattr(self, '_proxy_active_addr', None),
                        "socks5_port": getattr(self, '_socks5_port', 17278),
                    })),
                    ("services", json.dumps({
                        "hunt_running": getattr(self, '_hunt_running', False),
                        "proxy_running": getattr(self, '_proxy_running', False),
                        "proxy_port": getattr(self, '_proxy_port', 17277),
                        "socks5_running": getattr(self, '_socks5_running', False),
                        "socks5_port": getattr(self, '_socks5_port', 17278),
                        "transparent_running": getattr(self, '_transparent_running', False),
                        "transparent_port": getattr(self, '_transparent_port', 17477),
                    })),
                    ("country_filter", self.country_filter or ""),
                    ("switch_history", json.dumps(self._proxy_switch_history[-500:])),
                ]
                w.submit(
                    "INSERT INTO runtime_state (key, value) VALUES (?, ?)",
                    runtime,
                )
                w.drain()
                # A full save covers every rating, so nothing is dirty afterwards.
                self._dirty_ratings.clear()
            except Exception as e:
                logger.warning(f"SQLite state save failed: {e}")

    def _save_dirty_ratings(self):
            """Incrementally upsert only the ratings that changed since the last
            full save.  This avoids the O(n) DELETE+re-insert of the entire
            ratings table on every periodic save during proxy validation.

            Removals (e.g. clear_dead) always go through a full ``_save_state``,
            so the DB never retains stale rows that were deleted from memory.
            """
            self._flush_proxy_checks()
            if not self._dirty_ratings:
                return
            try:
                rows = []
                for addr in self._dirty_ratings:
                    r = self.ratings.get(addr)
                    if r is not None:
                        rows.append((r.address, json.dumps(r.to_dict())))
                if rows:
                    self._state_writer().submit(
                        "INSERT OR REPLACE INTO ratings (address, data) VALUES (?, ?)",
                        rows,
                    )
                self._dirty_ratings.clear()
            except Exception as e:
                logger.warning(f"SQLite dirty ratings save failed: {e}")

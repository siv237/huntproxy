"""State persistence methods — extracted from state.py."""
import json
import time
from hunt.constants import logger
from hunt.geo import country_code_from_name
from hunt.models import ProxyRating

class StatePersistenceMixin:
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
        for row in conn.execute("SELECT address, data FROM ratings"):
            try:
                d = json.loads(row["data"])
            except Exception:
                logger.debug("skipped corrupt rating row", exc_info=True)
                continue
            r = self._build_rating_from_dict(d)
            if not r.egress_country_code and r.egress_country:
                r.egress_country_code = country_code_from_name(r.egress_country)
            if not r.listen_country_code and r.listen_country:
                r.listen_country_code = country_code_from_name(r.listen_country)
            self.ratings[r.address] = r

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
                conn = self._db()
                # ratings
                conn.execute("DELETE FROM ratings")
                for r in self.ratings.values():
                    conn.execute(
                        "INSERT INTO ratings (address, data) VALUES (?, ?)",
                        (r.address, json.dumps(r.to_dict())),
                    )
                # blacklist
                conn.execute("DELETE FROM blacklist")
                for addr, reason in self.blacklist.items():
                    conn.execute(
                        "INSERT INTO blacklist (address, reason) VALUES (?, ?)",
                        (addr, reason or ""),
                    )
                # favorites
                conn.execute("DELETE FROM favorites")
                conn.executemany(
                    "INSERT OR REPLACE INTO favorites (address) VALUES (?)",
                    [(addr,) for addr in self.favorites],
                )
                # runtime state
                conn.execute("DELETE FROM runtime_state")
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
                for key, value in runtime:
                    conn.execute(
                        "INSERT INTO runtime_state (key, value) VALUES (?, ?)",
                        (key, value),
                    )
                conn.commit()
                conn.close()
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
            if not self._dirty_ratings:
                return
            try:
                conn = self._db()
                rows = []
                for addr in self._dirty_ratings:
                    r = self.ratings.get(addr)
                    if r is not None:
                        rows.append((r.address, json.dumps(r.to_dict())))
                if rows:
                    conn.executemany(
                        "INSERT OR REPLACE INTO ratings (address, data) VALUES (?, ?)",
                        rows,
                    )
                    conn.commit()
                conn.close()
                self._dirty_ratings.clear()
            except Exception as e:
                logger.warning(f"SQLite dirty ratings save failed: {e}")

    def _load_working_file(self):
            try:
                conn = self._db()
                db_count = conn.execute("SELECT COUNT(*) as c FROM working_proxies").fetchone()["c"]
                if db_count == 0 and self.working_file.exists():
                    db_count = self._migrate_working_txt(conn)
                loaded, count = self._load_working_from_db(conn)
                conn.close()
                if loaded:
                    self._working_file_loaded = loaded
                if count:
                    logger.info(f"Loaded {count} working proxies from DB")
            except Exception as e:
                logger.warning(f"Working file load failed: {e}")

    def _migrate_working_txt(self, conn) -> int:
        entries = []
        with open(self.working_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                addr = parts[0]
                lat_str = parts[-1] if len(parts) > 2 else "0"
                try:
                    float(lat_str)
                except ValueError:
                    lat_str = "0"
                    country = " ".join(parts[1:]) if len(parts) > 1 else ""
                else:
                    country = " ".join(parts[1:-1]) if len(parts) > 2 else (parts[1] if len(parts) > 1 else "")
                try:
                    lat = float(lat_str)
                except ValueError:
                    lat = 0.0
                entries.append((addr, country, lat, 0.0))
        if entries:
            conn.executemany(
                "INSERT OR IGNORE INTO working_proxies (address, country, latency, score) VALUES (?,?,?,?)",
                entries,
            )
            conn.commit()
            logger.info(f"Migrated {len(entries)} working proxies from working.txt to DB")
            return len(entries)
        return 0

    def _load_working_from_db(self, conn) -> tuple:
        loaded, count = set(), 0
        for row in conn.execute("SELECT address, country, latency FROM working_proxies"):
            addr = row["address"]
            if addr in self.ratings or addr in self.blacklist:
                continue
            last_latency = row["latency"] or 0.0
            country = row["country"] or ""
            r = ProxyRating(
                address=addr, country=country,
                country_code=country_code_from_name(country),
                first_seen=time.time(), last_check=time.time(),
                checks_total=1, checks_ok=1, last_status="ok",
                last_latency=last_latency, latency_sum=last_latency, latency_count=1,
            )
            port = addr.rsplit(":", 1)[-1]
            if port in ("1080", "10808", "9050"):
                r.protocol = "socks5"
            elif port == "4145":
                r.protocol = "socks4"
            self.ratings[addr] = r
            loaded.add(addr)
            count += 1
        return loaded, count

    def _save_working_file(self):
            """Save alive (non-blacklisted) proxies to DB.

            Only the operator-curated manual blacklist is a hard exclusion;
            downloaded IP blacklist matches only lower the score. Proven
            proxies (those that once produced a non-zero speed measurement)
            are kept during their failure grace period so a temporary outage
            does not evict them from the working list on the first failure."""
            alive = [r for r in self.ratings.values()
                     if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
            alive.sort(key=lambda r: r.score, reverse=True)
            try:
                conn = self._db()
                conn.execute("DELETE FROM working_proxies")
                conn.executemany(
                    "INSERT OR IGNORE INTO working_proxies (address, country, latency, score) VALUES (?,?,?,?)",
                    [(r.address, r.country, r.last_latency, r.score) for r in alive],
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"Working file save failed: {e}")

    # ── Downloads (generate from DB/memory, no legacy files) ──────────────


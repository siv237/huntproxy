"""Working-set persistence — extracted from state_persistence.py."""

import time

from hunt.constants import logger
from hunt.geo import country_code_from_name
from hunt.models import ProxyRating


class StateWorkingMixin:
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
            does not evict them from the working list on the first failure.

            This is a full rebuild and is only called once at the end of a
            run (validation / health check).  Mid-run persistence goes through
            the incremental ``_save_dirty_ratings`` path so the O(n) rewrite
            of the working set does not happen on every periodic checkpoint
            during a full pool re-validation (which would multiply the cost by
            the number of checkpoints)."""
            alive = [r for r in self.ratings.values()
                     if r.pool_eligible]
            alive.sort(key=lambda r: r.score, reverse=True)
            try:
                w = self._state_writer()
                w.submit("DELETE FROM working_proxies", [()])
                w.submit(
                    "INSERT OR IGNORE INTO working_proxies (address, country, latency, score) VALUES (?,?,?,?)",
                    [(r.address, r.country, r.last_latency, r.score) for r in alive],
                )
                w.drain()
            except Exception as e:
                logger.warning(f"Working file save failed: {e}")

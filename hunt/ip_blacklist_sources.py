"""Functional split of the huntproxy backend."""

import asyncio
import time
from hunt.constants import DEFAULT_IP_BLACKLIST_SOURCES, logger
from hunt.download import stream_download, curl_args
from typing import Optional

class IPBlacklistSourcesMixin:
    def _seed_default_ip_blacklist_sources(self):
            try:
                conn = self._db()
                count = conn.execute("SELECT COUNT(*) as c FROM ip_blacklist_sources").fetchone()
                if count["c"] > 0:
                    conn.close()
                    return
                now = time.time()
                for i, (name, url) in enumerate(DEFAULT_IP_BLACKLIST_SOURCES):
                    slug = name.lower().replace(" ", "-").replace(".", "-").replace("/", "-")
                    slug = slug.replace("--", "-").strip("-")
                    conn.execute(
                        "INSERT OR IGNORE INTO ip_blacklist_sources (id, name, url, enabled, priority, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                        (slug, name, url, 1, i, now, now)
                    )
                conn.commit()
                conn.close()
                logger.info("Seeded %d default IP blacklist sources", len(DEFAULT_IP_BLACKLIST_SOURCES))
            except Exception as e:
                logger.error("seed_default_ip_blacklist_sources: %s", e)

    def _migrate_ip_blacklist_sources(self):
            try:
                conn = self._db()
                now = time.time()
                # Disable the slow/unreliable default Tor source if it still exists.
                conn.execute("UPDATE ip_blacklist_sources SET enabled=0 WHERE id='tor-exit-nodes'")
                existing_urls = {r["url"] for r in conn.execute("SELECT url FROM ip_blacklist_sources").fetchall()}
                existing_ids = {r["id"] for r in conn.execute("SELECT id FROM ip_blacklist_sources").fetchall()}
                max_pri = conn.execute("SELECT COALESCE(MAX(priority),-1)+1 as next FROM ip_blacklist_sources").fetchone()["next"]
                added = 0
                for i, (name, url) in enumerate(DEFAULT_IP_BLACKLIST_SOURCES):
                    if url in existing_urls:
                        continue
                    slug = name.lower().replace(" ", "-").replace(".", "-").replace("/", "-")
                    slug = slug.replace("--", "-").strip("-")
                    if slug in existing_ids:
                        continue
                    conn.execute(
                        "INSERT OR IGNORE INTO ip_blacklist_sources (id, name, url, enabled, priority, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                        (slug, name, url, 1, max_pri + i, now, now)
                    )
                    existing_urls.add(url)
                    existing_ids.add(slug)
                    added += 1
                conn.commit()
                conn.close()
                # Drop stored entries for disabled/removed default sources.
                self._delete_ip_blacklist_source_entries('tor-exit-nodes')
                if added:
                    logger.info("Migrated IP blacklist sources: added %d new", added)
            except Exception as e:
                logger.error("migrate_ip_blacklist_sources: %s", e)

    async def _download_ip_blacklists(self) -> dict:
            """Download enabled IP blacklist sources, parse and store in SQLite.

            Returns a dict {source_id: count} with number of entries per source.
            Failed sources keep their previously stored entries.
            """
            sem = asyncio.Semaphore(8)
            sources = self.get_ip_blacklist_sources()
            enabled_sources = [s for s in sources if s.get("enabled")]
            # In-memory structures will be rebuilt from the DB after the refresh,
            # so disabled/removed sources are dropped, but failed sources keep
            # their previous entries.
            self.ip_blacklist_entries.clear()
            self.ip_blacklist_exact.clear()
            self.ip_blacklist_networks.clear()
            results: dict[str, int] = {}
            self._ip_blacklist_fetch_progress = {}
            self._active_dl_procs = []

            async def fetch(src: dict):
                nonlocal results
                source_id = src["id"]
                url = src["url"]
                source_name = src.get("name", source_id)
                self._ip_blacklist_fetch_progress[source_id] = {
                    "name": source_name, "status": "connecting",
                    "downloaded": 0, "started_at": time.time(),
                }
                async with sem:
                    try:
                        cargs = curl_args(url)
                        proc = await asyncio.create_subprocess_exec(
                            *cargs,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        self._active_dl_procs.append(proc)
                        def on_chunk(dl):
                            self._ip_blacklist_fetch_progress[source_id]["downloaded"] = dl
                            self._ip_blacklist_fetch_progress[source_id]["status"] = "downloading"
                        try:
                            text = await stream_download(proc, on_chunk=on_chunk)
                        except TimeoutError as e:
                            err_msg = str(e)[:200]
                            self._ip_blacklist_fetch_progress[source_id]["status"] = "error"
                            conn = None
                            try:
                                conn = self._db()
                                conn.execute(
                                    "UPDATE ip_blacklist_sources SET last_fetched_at=?, last_fetch_status=?, last_fetch_count=0, last_fetch_error=?, updated_at=? WHERE id=?",
                                    (time.time(), "error", err_msg, time.time(), source_id)
                                )
                                conn.commit()
                            except Exception:
                                pass
                            finally:
                                if conn:
                                    try: conn.close()
                                    except Exception: pass
                            self._emit(f"IP blacklist failed: {source_name}: {err_msg}", "warn")
                            return
                        now = time.time()
                        if proc.returncode == 0:
                            count = self._parse_ip_blacklist(text, source_id, source_name, persist=True)
                            results[source_id] = count
                            self._ip_blacklist_fetch_progress[source_id]["status"] = "done"
                            self._ip_blacklist_fetch_progress[source_id]["count"] = count
                            conn = None
                            try:
                                conn = self._db()
                                conn.execute(
                                    "UPDATE ip_blacklist_sources SET last_fetched_at=?, last_fetch_status=?, last_fetch_count=?, last_fetch_error='', total_fetched=total_fetched+?, updated_at=? WHERE id=?",
                                    (now, "ok", count, count, now, source_id)
                                )
                                conn.commit()
                            except Exception:
                                pass
                            finally:
                                if conn:
                                    try: conn.close()
                                    except Exception: pass
                            self._emit(f"IP blacklist {source_name}: {count} entries", "info")
                        else:
                            err_msg = f"curl exit {proc.returncode}"
                            self._ip_blacklist_fetch_progress[source_id]["status"] = "error"
                            conn = None
                            try:
                                conn = self._db()
                                conn.execute(
                                    "UPDATE ip_blacklist_sources SET last_fetched_at=?, last_fetch_status=?, last_fetch_count=0, last_fetch_error=?, updated_at=? WHERE id=?",
                                    (now, "error", err_msg, now, source_id)
                                )
                                conn.commit()
                            except Exception:
                                pass
                            finally:
                                if conn:
                                    try: conn.close()
                                    except Exception: pass
                            self._emit(f"IP blacklist failed: {source_name}: {err_msg}", "warn")
                    except Exception as e:
                        now = time.time()
                        err_msg = str(e)[:200]
                        self._ip_blacklist_fetch_progress[source_id]["status"] = "error"
                        conn = None
                        try:
                            conn = self._db()
                            conn.execute(
                                "UPDATE ip_blacklist_sources SET last_fetched_at=?, last_fetch_status=?, last_fetch_count=0, last_fetch_error=?, updated_at=? WHERE id=?",
                                (now, "error", err_msg, now, source_id)
                            )
                            conn.commit()
                        except Exception:
                            pass
                        finally:
                            if conn:
                                try: conn.close()
                                except Exception: pass
                        self._emit(f"IP blacklist failed: {source_name}: {e}", "warn")

            tasks = [asyncio.create_task(fetch(s)) for s in enabled_sources]
            await self._gather_skip_aware(tasks)
            self._load_ip_blacklist_from_db(accumulate=False)
            self._save_ip_blacklist()
            self._refresh_ip_blacklist_hits()
            return results

    def get_ip_blacklist_fetch_progress(self) -> dict:
            return getattr(self, '_ip_blacklist_fetch_progress', {})

    def _refresh_ip_blacklist_hits(self):
            """Re-evaluate all known proxies against the current IP blacklist."""
            for addr, r in self.ratings.items():
                if r.egress_ip:
                    self._apply_ip_blacklist_to_proxy(addr, r.egress_ip)

    def get_ip_blacklist_sources(self) -> list:
            try:
                conn = self._db()
                rows = conn.execute(
                    "SELECT * FROM ip_blacklist_sources ORDER BY priority ASC"
                ).fetchall()
                counts = {}
                for r in conn.execute(
                    "SELECT source_id, COUNT(*) as c FROM ip_blacklist_entries GROUP BY source_id"
                ).fetchall():
                    counts[r["source_id"]] = r["c"]
                conn.close()
                result = []
                for r in rows:
                    d = dict(r)
                    d["current_entries"] = counts.get(r["id"], 0)
                    result.append(d)
                return result
            except Exception as e:
                logger.error("get_ip_blacklist_sources: %s", e)
                return []

    def get_ip_blacklist_source(self, source_id: str) -> Optional[dict]:
            try:
                conn = self._db()
                row = conn.execute("SELECT * FROM ip_blacklist_sources WHERE id=?", (source_id,)).fetchone()
                count = 0
                if row:
                    r = conn.execute(
                        "SELECT COUNT(*) as c FROM ip_blacklist_entries WHERE source_id=?", (source_id,)
                    ).fetchone()
                    count = r["c"] if r else 0
                conn.close()
                if not row:
                    return None
                d = dict(row)
                d["current_entries"] = count
                return d
            except Exception as e:
                logger.error("get_ip_blacklist_source: %s", e)
                return None

    def create_ip_blacklist_source(self, data: dict) -> Optional[dict]:
            source_id = data.get("id", "").strip()
            name = data.get("name", "").strip()
            url = data.get("url", "").strip()
            if not source_id or not name or not url:
                return None
            now = time.time()
            try:
                conn = self._db()
                max_pri = conn.execute("SELECT COALESCE(MAX(priority),-1)+1 as next FROM ip_blacklist_sources").fetchone()
                priority = max_pri["next"] if max_pri else 0
                conn.execute(
                    "INSERT OR IGNORE INTO ip_blacklist_sources (id, name, url, enabled, priority, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                    (source_id, name, url, 1 if data.get("enabled", True) else 0, priority, now, now)
                )
                conn.commit()
                conn.close()
                self._emit(f"IP blacklist source added: {name}", "info")
                return self.get_ip_blacklist_source(source_id)
            except Exception as e:
                logger.error("create_ip_blacklist_source: %s", e)
                return None

    def update_ip_blacklist_source(self, source_id: str, data: dict) -> Optional[dict]:
            now = time.time()
            try:
                conn = self._db()
                existing = conn.execute("SELECT id FROM ip_blacklist_sources WHERE id=?", (source_id,)).fetchone()
                if not existing:
                    conn.close()
                    return None
                name = data.get("name", "").strip()
                url = data.get("url", "").strip()
                sets = []
                vals = []
                if name:
                    sets.append("name=?"); vals.append(name)
                if url:
                    sets.append("url=?"); vals.append(url)
                became_disabled = False
                if "enabled" in data:
                    sets.append("enabled=?"); vals.append(1 if data["enabled"] else 0)
                    if not data["enabled"]:
                        became_disabled = True
                if sets:
                    sets.append("updated_at=?"); vals.append(now)
                    vals.append(source_id)
                    conn.execute(f"UPDATE ip_blacklist_sources SET {','.join(sets)} WHERE id=?", vals)
                conn.commit()
                conn.close()
                if became_disabled:
                    self._delete_ip_blacklist_source_entries(source_id)
                    self._load_ip_blacklist_from_db(accumulate=False)
                    self._save_ip_blacklist()
                self._emit(f"IP blacklist source updated: {source_id}", "info")
                return self.get_ip_blacklist_source(source_id)
            except Exception as e:
                logger.error("update_ip_blacklist_source: %s", e)
                return None

    def delete_ip_blacklist_source(self, source_id: str) -> bool:
            try:
                conn = self._db()
                conn.execute("DELETE FROM ip_blacklist_sources WHERE id=?", (source_id,))
                conn.commit()
                conn.close()
                self._delete_ip_blacklist_source_entries(source_id)
                self._load_ip_blacklist_from_db(accumulate=False)
                self._save_ip_blacklist()
                self._emit(f"IP blacklist source deleted: {source_id}", "warn")
                return True
            except Exception as e:
                logger.error("delete_ip_blacklist_source: %s", e)
                return False

    def toggle_ip_blacklist_source(self, source_id: str) -> Optional[dict]:
            try:
                conn = self._db()
                row = conn.execute("SELECT enabled FROM ip_blacklist_sources WHERE id=?", (source_id,)).fetchone()
                if not row:
                    conn.close()
                    return None
                new_val = 0 if row["enabled"] else 1
                conn.execute("UPDATE ip_blacklist_sources SET enabled=?, updated_at=? WHERE id=?", (new_val, time.time(), source_id))
                conn.commit()
                conn.close()
                if new_val == 0:
                    self._delete_ip_blacklist_source_entries(source_id)
                    self._load_ip_blacklist_from_db(accumulate=False)
                    self._save_ip_blacklist()
                status = "enabled" if new_val else "disabled"
                self._emit(f"IP blacklist source {source_id} {status}", "info")
                return self.get_ip_blacklist_source(source_id)
            except Exception as e:
                logger.error("toggle_ip_blacklist_source: %s", e)
                return None

    def get_ip_blacklist_matches(self) -> list:
            """Return proxies whose egress IP is currently in the downloaded blacklist."""
            result = []
            for addr, r in self.ratings.items():
                if r.ip_blacklist_reason:
                    result.append({
                        "address": addr,
                        "egress_ip": r.egress_ip,
                        "reason": r.ip_blacklist_reason,
                        "hits": r.ip_blacklist_hits,
                        "sources": r.ip_blacklist_sources,
                        "country": r.country,
                        "country_code": r.country_code,
                        "score": r.score,
                    })
            return result

"""Country blocklist sources — downloads IP and domain blocklists organized
by country and direction (inside/outside), feeding them into the existing
IP blacklist scoring and domain routing systems.

Direction semantics:
  "inside"  — resources blocked WITHIN that country (e.g. RKN blocks in RU)
  "outside" — resources of that country blocked ABROAD (e.g. RU geo-restricted)

List types:
  "ip"     → parsed via _parse_ip_blacklist() → ip_blacklist_entries (proxy scoring)
  "domain" → auto-creates domain_lists entry → domain_entries (routing, route=pool)
"""

import asyncio
import time
from hunt.constants import DEFAULT_BLOCKLIST_SOURCES, logger
from hunt.download import stream_download


class BlocklistsMixin:

    def _seed_default_blocklists(self):
        try:
            conn = self._db()
            count = conn.execute("SELECT COUNT(*) as c FROM blocklist_sources").fetchone()
            if count["c"] > 0:
                conn.close()
                return
            now = time.time()
            for i, (sid, name, country, direction, list_type, url) in enumerate(DEFAULT_BLOCKLIST_SOURCES):
                conn.execute(
                    "INSERT OR IGNORE INTO blocklist_sources "
                    "(id, name, country, direction, list_type, url, enabled, priority, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (sid, name, country, direction, list_type, url, 1, i, now, now)
                )
            conn.commit()
            conn.close()
            logger.info("Seeded %d default blocklist sources", len(DEFAULT_BLOCKLIST_SOURCES))
        except Exception as e:
            logger.error("seed_default_blocklists: %s", e)

    def _migrate_blocklists(self):
        try:
            conn = self._db()
            now = time.time()
            existing_ids = {r["id"] for r in conn.execute("SELECT id FROM blocklist_sources").fetchall()}
            max_pri = conn.execute("SELECT COALESCE(MAX(priority),-1)+1 as next FROM blocklist_sources").fetchone()["next"]
            added = 0
            for i, (sid, name, country, direction, list_type, url) in enumerate(DEFAULT_BLOCKLIST_SOURCES):
                if sid in existing_ids:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO blocklist_sources "
                    "(id, name, country, direction, list_type, url, enabled, priority, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (sid, name, country, direction, list_type, url, 1, max_pri + i, now, now)
                )
                existing_ids.add(sid)
                added += 1
            conn.commit()
            conn.close()
            if added:
                logger.info("Migrated blocklist sources: added %d new", added)
        except Exception as e:
            logger.error("migrate_blocklists: %s", e)

    def get_blocklist_sources(self) -> list:
        try:
            conn = self._db()
            rows = conn.execute(
                "SELECT * FROM blocklist_sources ORDER BY country ASC, direction ASC, priority ASC"
            ).fetchall()
            counts = {}
            for r in conn.execute(
                "SELECT source_id, COUNT(*) as c FROM ip_blacklist_entries "
                "WHERE source_id IN (SELECT id FROM blocklist_sources WHERE list_type='ip') "
                "GROUP BY source_id"
            ).fetchall():
                counts[r["source_id"]] = r["c"]
            for r in conn.execute(
                "SELECT dl.id as sid, (SELECT COUNT(*) FROM domain_entries WHERE list_id=dl.id) as c "
                "FROM domain_lists dl WHERE dl.id IN (SELECT id FROM blocklist_sources WHERE list_type='domain')"
            ).fetchall():
                counts[r["sid"]] = r["c"]
            conn.close()
            result = []
            for r in rows:
                item = dict(r)
                item["entry_count"] = counts.get(r["id"], 0)
                result.append(item)
            return result
        except Exception as e:
            logger.error("get_blocklist_sources: %s", e)
            return []

    def get_blocklist_source(self, source_id: str) -> dict | None:
        try:
            conn = self._db()
            row = conn.execute("SELECT * FROM blocklist_sources WHERE id=?", (source_id,)).fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error("get_blocklist_source: %s", e)
            return None

    def create_blocklist_source(self, data: dict) -> dict | None:
        sid = data.get("id", "").strip()
        name = data.get("name", "").strip()
        url = data.get("url", "").strip()
        if not sid or not name or not url:
            return None
        country = data.get("country", "").strip().upper()
        direction = data.get("direction", "inside").strip()
        list_type = data.get("list_type", "ip").strip()
        download_proxy = data.get("download_proxy", "").strip()
        now = time.time()
        try:
            conn = self._db()
            max_pri = conn.execute("SELECT COALESCE(MAX(priority),-1)+1 as next FROM blocklist_sources").fetchone()
            priority = max_pri["next"] if max_pri else 0
            conn.execute(
                "INSERT INTO blocklist_sources "
                "(id, name, country, direction, list_type, url, download_proxy, enabled, priority, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (sid, name, country, direction, list_type, url, download_proxy,
                 1 if data.get("enabled", True) else 0, priority, now, now)
            )
            conn.commit()
            conn.close()
            self._emit(f"Blocklist source added: {name}", "info")
            return self.get_blocklist_source(sid)
        except Exception as e:
            logger.error("create_blocklist_source: %s", e)
            return None

    def update_blocklist_source(self, source_id: str, data: dict) -> dict | None:
        now = time.time()
        try:
            conn = self._db()
            existing = conn.execute("SELECT id FROM blocklist_sources WHERE id=?", (source_id,)).fetchone()
            if not existing:
                conn.close()
                return None
            name = data.get("name", "").strip()
            if name:
                conn.execute(
                    "UPDATE blocklist_sources SET name=?, country=?, direction=?, list_type=?, url=?, "
                    "download_proxy=?, enabled=?, updated_at=? WHERE id=?",
                    (name, data.get("country", "").strip().upper(),
                     data.get("direction", "inside").strip(),
                     data.get("list_type", "ip").strip(),
                     data.get("url", "").strip(),
                     data.get("download_proxy", "").strip(),
                     1 if data.get("enabled", True) else 0, now, source_id)
                )
                conn.commit()
            conn.close()
            self._emit(f"Blocklist source updated: {source_id}", "info")
            return self.get_blocklist_source(source_id)
        except Exception as e:
            logger.error("update_blocklist_source: %s", e)
            return None

    def delete_blocklist_source(self, source_id: str) -> bool:
        try:
            conn = self._db()
            row = conn.execute("SELECT list_type FROM blocklist_sources WHERE id=?", (source_id,)).fetchone()
            if not row:
                conn.close()
                return False
            if row["list_type"] == "ip":
                conn.execute("DELETE FROM ip_blacklist_entries WHERE source_id=?", (source_id,))
            else:
                conn.execute("DELETE FROM domain_entries WHERE list_id=?", (source_id,))
                conn.execute("DELETE FROM domain_lists WHERE id=? AND source LIKE 'blocklist%%'", (source_id,))
            conn.execute("DELETE FROM blocklist_sources WHERE id=?", (source_id,))
            conn.commit()
            conn.close()
            self._emit(f"Blocklist source deleted: {source_id}", "warn")
            return True
        except Exception as e:
            logger.error("delete_blocklist_source: %s", e)
            return False

    def toggle_blocklist_source(self, source_id: str) -> dict | None:
        try:
            conn = self._db()
            row = conn.execute("SELECT enabled FROM blocklist_sources WHERE id=?", (source_id,)).fetchone()
            if not row:
                conn.close()
                return None
            new_val = 0 if row["enabled"] else 1
            conn.execute("UPDATE blocklist_sources SET enabled=?, updated_at=? WHERE id=?",
                         (new_val, time.time(), source_id))
            conn.commit()
            conn.close()
            status = "enabled" if new_val else "disabled"
            self._emit(f"Blocklist source {source_id} {status}", "info")
            return self.get_blocklist_source(source_id)
        except Exception as e:
            logger.error("toggle_blocklist_source: %s", e)
            return None

    def _parse_domain_blocklist(self, text: str, source_id: str, name: str) -> int:
        """Parse domain blocklist text, create/update domain_list + domain_entries.
        Returns number of domains added."""
        domains = []
        seen = set()
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(";") or line.startswith("//"):
                continue
            d = line.lower()
            if d not in seen:
                seen.add(d)
                domains.append(d)
        if not domains:
            return 0
        now = time.time()
        conn = self._db()
        try:
            existing = conn.execute("SELECT id FROM domain_lists WHERE id=?", (source_id,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE domain_lists SET name=?, updated_at=? WHERE id=?",
                    (name, now, source_id)
                )
                conn.execute("DELETE FROM domain_entries WHERE list_id=?", (source_id,))
            else:
                max_pri = conn.execute("SELECT COALESCE(MAX(priority),-1)+1 as next FROM domain_lists").fetchone()
                priority = max_pri["next"] if max_pri else 0
                conn.execute(
                    "INSERT INTO domain_lists (id, name, source, url, route, enabled, priority, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (source_id, name, "blocklist", "", "pool", 1, priority, now, now)
                )
            conn.executemany(
                "INSERT OR IGNORE INTO domain_entries (list_id, pattern) VALUES (?,?)",
                [(source_id, d) for d in domains]
            )
            conn.commit()
        except Exception as e:
            logger.error("parse_domain_blocklist: %s", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return len(domains)

    async def _download_blocklists(self) -> dict:
        """Download all enabled blocklist sources. Returns {source_id: count}."""
        self._fetching_blocklists = True
        self._blocklist_fetch_progress = {}
        results = {}
        try:
            conn = self._db()
            enabled_sources = conn.execute(
                "SELECT * FROM blocklist_sources WHERE enabled=1 ORDER BY priority ASC"
            ).fetchall()
            conn.close()
            if not enabled_sources:
                return results

            async def fetch(s):
                source_id = s["id"]
                source_name = s["name"]
                list_type = s["list_type"]
                url = s["url"]
                proxy = s["download_proxy"] if "download_proxy" in s.keys() else ""
                self._blocklist_fetch_progress[source_id] = {
                    "name": source_name, "status": "connecting",
                    "downloaded": 0, "started_at": time.time(),
                }
                self._emit(f"Fetching blocklist {source_name}...", "info")
                try:
                    curl_args = ["curl", "-sS", "-L", "-A", "huntproxy/1.0"]
                    if proxy:
                        curl_args += ["--proxy", proxy]
                    curl_args.append(url)
                    proc = await asyncio.create_subprocess_exec(
                        *curl_args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    last_emit = [0]
                    def on_chunk(dl):
                        self._blocklist_fetch_progress[source_id]["downloaded"] = dl
                        self._blocklist_fetch_progress[source_id]["status"] = "downloading"
                        now = time.time()
                        if now - last_emit[0] > 5:
                            last_emit[0] = now
                            self._emit(f"Blocklist {source_name}: {dl // 1024}KB", "info")
                    try:
                        text = await stream_download(proc, on_chunk=on_chunk)
                    except TimeoutError as e:
                        self._update_blocklist_fetch_error(source_id, str(e), source_name)
                        self._blocklist_fetch_progress[source_id]["status"] = "error"
                        return
                    now = time.time()
                    if proc.returncode == 0:
                        self._blocklist_fetch_progress[source_id]["status"] = "parsing"
                        if list_type == "ip":
                            count = self._parse_ip_blacklist(text, source_id, source_name, persist=True)
                        else:
                            count = self._parse_domain_blocklist(text, source_id, source_name)
                            self._update_blocklist_domain_url(source_id)
                        results[source_id] = count
                        self._blocklist_fetch_progress[source_id]["status"] = "done"
                        self._blocklist_fetch_progress[source_id]["count"] = count
                        c = None
                        try:
                            c = self._db()
                            c.execute(
                                "UPDATE blocklist_sources SET last_fetched_at=?, last_fetch_status=?, "
                                "last_fetch_count=?, last_fetch_error='', total_fetched=total_fetched+?, updated_at=? WHERE id=?",
                                (now, "ok", count, count, now, source_id)
                            )
                            c.commit()
                        except Exception:
                            pass
                        finally:
                            if c:
                                try: c.close()
                                except Exception: pass
                        self._emit(f"Blocklist {source_name}: {count} entries", "info")
                    else:
                        err_msg = f"curl exit {proc.returncode}"
                        self._update_blocklist_fetch_error(source_id, err_msg, source_name)
                        self._blocklist_fetch_progress[source_id]["status"] = "error"
                except Exception as e:
                    err_msg = str(e)[:200]
                    self._update_blocklist_fetch_error(source_id, err_msg, source_name)
                    self._blocklist_fetch_progress[source_id]["status"] = "error"

            tasks = [asyncio.create_task(fetch(s)) for s in enabled_sources]
            await asyncio.gather(*tasks)

            if any(s["list_type"] == "ip" for s in enabled_sources):
                self._load_ip_blacklist_from_db(accumulate=False)
                self._refresh_ip_blacklist_hits()
        finally:
            self._fetching_blocklists = False
        return results

    def get_blocklist_fetch_progress(self) -> dict:
        return getattr(self, '_blocklist_fetch_progress', {})

    def _update_blocklist_domain_url(self, source_id: str):
        """Sync the URL from blocklist_sources into the auto-created domain_list."""
        try:
            conn = self._db()
            row = conn.execute("SELECT url FROM blocklist_sources WHERE id=?", (source_id,)).fetchone()
            if row:
                conn.execute("UPDATE domain_lists SET url=?, updated_at=? WHERE id=? AND source LIKE 'blocklist%%'",
                             (row["url"], time.time(), source_id))
                conn.commit()
            conn.close()
        except Exception:
            pass

    def _update_blocklist_fetch_error(self, source_id: str, err_msg: str, source_name: str):
        now = time.time()
        c = None
        try:
            c = self._db()
            c.execute(
                "UPDATE blocklist_sources SET last_fetched_at=?, last_fetch_status=?, "
                "last_fetch_count=0, last_fetch_error=?, updated_at=? WHERE id=?",
                (now, "error", err_msg, now, source_id)
            )
            c.commit()
        except Exception:
            pass
        finally:
            if c:
                try: c.close()
                except Exception: pass
        self._emit(f"Blocklist failed: {source_name}: {err_msg}", "warn")

    async def _blocklist_loop(self):
        """Periodic refresh of country blocklists."""
        while True:
            await asyncio.sleep(self.ip_blacklist_fetch_interval)
            try:
                if self._paused:
                    await self._pause_event.wait()
                    continue
                if getattr(self, '_fetching_blocklists', False):
                    continue
                internet_ok = await self.is_internet_alive()
                if not internet_ok:
                    continue
                self._emit("Refreshing country blocklists...", "info")
                results = await self._download_blocklists()
                total = sum(results.values())
                self._emit(f"Refreshed {total} blocklist entries", "info")
            except asyncio.CancelledError:
                return
            except Exception as e:
                self._emit(f"Blocklist refresh error: {e}", "error")

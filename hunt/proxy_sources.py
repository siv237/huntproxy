"""Functional split of the huntproxy backend."""

import asyncio
import time
from hunt.constants import DEFAULT_SOURCES, logger
from typing import Optional

class ProxySourcesMixin:
    def _seed_default_sources(self):
            try:
                conn = self._db()
                count = conn.execute("SELECT COUNT(*) as c FROM proxy_sources").fetchone()
                if count["c"] > 0:
                    conn.close()
                    return
                now = time.time()
                for i, url in enumerate(DEFAULT_SOURCES):
                    parts = url.rstrip("/").split("/")
                    fname = parts[-1].replace(".txt", "") if parts else "list"
                    if "github.com" in url or "githubusercontent.com" in url:
                        owner = parts[3] if len(parts) > 3 else ""
                        repo = parts[4] if len(parts) > 4 else ""
                        label = f"{owner}/{repo}" if owner and repo else fname
                    else:
                        label = parts[-2] if len(parts) >= 2 else fname
                    name = f"{label}/{fname}"
                    slug = (label + "-" + fname).lower().replace("_", "-").replace("/", "-")
                    slug = slug.replace("--", "-").strip("-")
                    protocol = "mixed"
                    if "socks5" in fname.lower():
                        protocol = "socks5"
                    elif "socks4" in fname.lower():
                        protocol = "socks4"
                    elif "https" in fname.lower():
                        protocol = "https"
                    elif "http" in fname.lower():
                        protocol = "http"
                    conn.execute(
                        "INSERT OR IGNORE INTO proxy_sources (id, name, url, protocol, enabled, priority, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                        (slug, name, url, protocol, 1, i, now, now)
                    )
                conn.commit()
                conn.close()
                logger.info("Seeded %d default proxy sources", len(DEFAULT_SOURCES))
            except Exception as e:
                logger.error("seed_default_sources: %s", e)

    def _migrate_sources(self):
            try:
                conn = self._db()
                now = time.time()
                conn.execute(
                    "UPDATE proxy_sources SET url=REPLACE(url, '/proxies/all/', '/proxies/') "
                    "WHERE url LIKE '%monosans/proxy-list%/proxies/all/%'"
                )
                existing_urls = {r["url"] for r in conn.execute("SELECT url FROM proxy_sources").fetchall()}
                existing_ids = {r["id"] for r in conn.execute("SELECT id FROM proxy_sources").fetchall()}
                max_pri = conn.execute("SELECT COALESCE(MAX(priority),-1)+1 as next FROM proxy_sources").fetchone()["next"]
                added = 0
                for i, url in enumerate(DEFAULT_SOURCES):
                    if url in existing_urls:
                        continue
                    parts = url.rstrip("/").split("/")
                    fname = parts[-1].replace(".txt", "") if parts else "list"
                    if "github.com" in url or "githubusercontent.com" in url:
                        owner = parts[3] if len(parts) > 3 else ""
                        repo = parts[4] if len(parts) > 4 else ""
                        label = f"{owner}/{repo}" if owner and repo else fname
                    else:
                        label = parts[-2] if len(parts) >= 2 else fname
                    name = f"{label}/{fname}"
                    slug = (label + "-" + fname).lower().replace("_", "-").replace("/", "-")
                    slug = slug.replace("--", "-").strip("-")
                    if slug in existing_ids:
                        continue
                    protocol = "mixed"
                    if "socks5" in fname.lower():
                        protocol = "socks5"
                    elif "socks4" in fname.lower():
                        protocol = "socks4"
                    elif "https" in fname.lower():
                        protocol = "https"
                    elif "http" in fname.lower():
                        protocol = "http"
                    conn.execute(
                        "INSERT OR IGNORE INTO proxy_sources (id, name, url, protocol, enabled, priority, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                        (slug, name, url, protocol, 1, max_pri + i, now, now)
                    )
                    existing_urls.add(url)
                    existing_ids.add(slug)
                    added += 1
                conn.commit()
                conn.close()
                if added:
                    logger.info("Migrated proxy sources: added %d new", added)
            except Exception as e:
                logger.error("migrate_sources: %s", e)

    def _parse_source_text(self, text: str) -> set:
            """Extract proxy addresses (ip:port) from raw source text."""
            import re
            found = set()
            for m in re.finditer(r'(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})', text):
                ip, port = m.group(1), int(m.group(2))
                if 1 <= port <= 65535:
                    found.add(f"{ip}:{port}")
            return found

    async def _download_sources(self) -> set:
            sem = asyncio.Semaphore(8)
            sources = self.get_proxy_sources()
            enabled_sources = [s for s in sources if s.get("enabled")]
            self.sources_total = len(enabled_sources)
            self.sources_done = 0
            seen = set()
            source_proxies: dict[str, set] = {}

            async def fetch(src: dict):
                source_id = src["id"]
                url = src["url"]
                async with sem:
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            "curl", "-sSf", "--max-time", "30", url,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        stdout, _ = await proc.communicate()
                        self.sources_done += 1
                        now = time.time()
                        if proc.returncode == 0:
                            text = stdout.decode(errors="replace")
                            found = self._parse_source_text(text)
                            self._replace_proxy_source_entries(source_id, found)
                            source_proxies[source_id] = found
                            conn = None
                            try:
                                conn = self._db()
                                conn.execute(
                                    "UPDATE proxy_sources SET last_fetched_at=?, last_fetch_status=?, last_fetch_count=?, last_fetch_error='', "
                                    "total_fetched=total_fetched+?, updated_at=? WHERE id=?",
                                    (now, "ok", len(found), len(found), now, source_id)
                                )
                                conn.commit()
                            except Exception:
                                pass
                            finally:
                                if conn:
                                    try: conn.close()
                                    except Exception: pass
                            self._emit(f"Source {src['name']}: {len(found)} proxies", "info")
                        else:
                            err_msg = f"HTTP {proc.returncode}"
                            conn = None
                            try:
                                conn = self._db()
                                conn.execute(
                                    "UPDATE proxy_sources SET last_fetched_at=?, last_fetch_status=?, last_fetch_count=0, last_fetch_error=?, updated_at=? WHERE id=?",
                                    (now, "error", err_msg, now, source_id)
                                )
                                conn.commit()
                            except Exception:
                                pass
                            finally:
                                if conn:
                                    try: conn.close()
                                    except Exception: pass
                            self._emit(f"Source failed: {src['name']}: {err_msg}", "warn")
                    except Exception as e:
                        self.sources_done += 1
                        now = time.time()
                        err_msg = str(e)[:200]
                        conn = None
                        try:
                            conn = self._db()
                            conn.execute(
                                "UPDATE proxy_sources SET last_fetched_at=?, last_fetch_status=?, last_fetch_count=0, last_fetch_error=?, updated_at=? WHERE id=?",
                                (now, "error", err_msg, now, source_id)
                            )
                            conn.commit()
                        except Exception:
                            pass
                        finally:
                            if conn:
                                try: conn.close()
                                except Exception: pass
                        self._emit(f"Source failed: {src['name']}: {e}", "warn")

            tasks = [asyncio.create_task(fetch(s)) for s in enabled_sources]
            await asyncio.gather(*tasks)
            self._load_all_proxy_source_entries()
            # Build the candidate set from all enabled sources currently in the DB.
            # This keeps addresses from sources that failed to fetch this cycle.
            seen: set[str] = set()
            for sid, addrs in self._source_proxies.items():
                seen.update(addrs)
                for addr in addrs:
                    r = self.ratings.get(addr)
                    if r and sid not in r.source_ids:
                        r.source_ids.append(sid)
            return seen

    def _update_source_stats(self):
            if not self._source_proxies:
                return
            try:
                conn = self._db()
                now = time.time()
                for source_id, addresses in self._source_proxies.items():
                    working = 0
                    dead = 0
                    for addr in addresses:
                        r = self.ratings.get(addr)
                        if r and r.last_status == "ok":
                            working += 1
                        else:
                            dead += 1
                    conn.execute(
                        "UPDATE proxy_sources SET last_working=?, last_dead=?, "
                        "total_working=total_working+?, total_dead=total_dead+?, updated_at=? WHERE id=?",
                        (working, dead, working, dead, now, source_id)
                    )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error("update_source_stats: %s", e)

    def _replace_proxy_source_entries(self, source_id: str, addresses: set[str]):
            """Replace persisted proxy addresses for a single source."""
            now = time.time()
            conn = self._db()
            try:
                conn.execute("DELETE FROM proxy_source_entries WHERE source_id=?", (source_id,))
                if addresses:
                    conn.executemany(
                        "INSERT OR REPLACE INTO proxy_source_entries (source_id, address, created_at) VALUES (?,?,?)",
                        [(source_id, addr, now) for addr in addresses]
                    )
                conn.commit()
            except Exception as e:
                logger.error("replace_proxy_source_entries %s: %s", source_id, e)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def _delete_proxy_source_entries(self, source_id: str):
            """Remove persisted proxy addresses for a disabled/deleted source."""
            conn = self._db()
            try:
                conn.execute("DELETE FROM proxy_source_entries WHERE source_id=?", (source_id,))
                conn.commit()
            except Exception as e:
                logger.error("delete_proxy_source_entries %s: %s", source_id, e)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def _load_all_proxy_source_entries(self):
            """Load all persisted proxy addresses from SQLite into memory."""
            self._source_proxies = {}
            self._addr_sources = {}
            conn = self._db()
            try:
                rows = conn.execute("SELECT source_id, address FROM proxy_source_entries").fetchall()
                for row in rows:
                    sid = row["source_id"]
                    addr = row["address"]
                    if sid not in self._source_proxies:
                        self._source_proxies[sid] = set()
                    self._source_proxies[sid].add(addr)
                    if addr not in self._addr_sources:
                        self._addr_sources[addr] = []
                    if sid not in self._addr_sources[addr]:
                        self._addr_sources[addr].append(sid)
                for addr, sids in self._addr_sources.items():
                    r = self.ratings.get(addr)
                    if r:
                        for sid in sids:
                            if sid not in r.source_ids:
                                r.source_ids.append(sid)
            except Exception as e:
                logger.error("load_all_proxy_source_entries: %s", e)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_proxy_sources(self) -> list:
            try:
                conn = self._db()
                rows = conn.execute(
                    "SELECT * FROM proxy_sources ORDER BY priority ASC"
                ).fetchall()
                counts = {}
                for r in conn.execute(
                    "SELECT source_id, COUNT(*) as c FROM proxy_source_entries GROUP BY source_id"
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
                logger.error("get_proxy_sources: %s", e)
                return []

    def get_proxy_source(self, source_id: str) -> Optional[dict]:
            try:
                conn = self._db()
                row = conn.execute("SELECT * FROM proxy_sources WHERE id=?", (source_id,)).fetchone()
                count = 0
                if row:
                    r = conn.execute(
                        "SELECT COUNT(*) as c FROM proxy_source_entries WHERE source_id=?", (source_id,)
                    ).fetchone()
                    count = r["c"] if r else 0
                conn.close()
                if not row:
                    return None
                d = dict(row)
                d["current_entries"] = count
                return d
            except Exception as e:
                logger.error("get_proxy_source: %s", e)
                return None

    def create_proxy_source(self, data: dict) -> Optional[dict]:
            source_id = data.get("id", "").strip()
            name = data.get("name", "").strip()
            url = data.get("url", "").strip()
            if not source_id or not name or not url:
                return None
            now = time.time()
            try:
                conn = self._db()
                max_pri = conn.execute("SELECT COALESCE(MAX(priority),-1)+1 as next FROM proxy_sources").fetchone()
                priority = max_pri["next"] if max_pri else 0
                conn.execute(
                    "INSERT OR IGNORE INTO proxy_sources (id, name, url, protocol, enabled, priority, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (source_id, name, url, data.get("protocol", "mixed"),
                     1 if data.get("enabled", True) else 0, priority, now, now)
                )
                conn.commit()
                conn.close()
                self._emit(f"Proxy source added: {name}", "info")
                return self.get_proxy_source(source_id)
            except Exception as e:
                logger.error("create_proxy_source: %s", e)
                return None

    def update_proxy_source(self, source_id: str, data: dict) -> Optional[dict]:
            now = time.time()
            try:
                conn = self._db()
                existing = conn.execute("SELECT id FROM proxy_sources WHERE id=?", (source_id,)).fetchone()
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
                if "protocol" in data:
                    sets.append("protocol=?"); vals.append(data["protocol"])
                became_disabled = False
                if "enabled" in data:
                    sets.append("enabled=?"); vals.append(1 if data["enabled"] else 0)
                    if not data["enabled"]:
                        became_disabled = True
                if sets:
                    sets.append("updated_at=?"); vals.append(now)
                    vals.append(source_id)
                    conn.execute(f"UPDATE proxy_sources SET {','.join(sets)} WHERE id=?", vals)
                conn.commit()
                conn.close()
                if became_disabled:
                    self._delete_proxy_source_entries(source_id)
                    self._load_all_proxy_source_entries()
                self._emit(f"Proxy source updated: {source_id}", "info")
                return self.get_proxy_source(source_id)
            except Exception as e:
                logger.error("update_proxy_source: %s", e)
                return None

    def delete_proxy_source(self, source_id: str) -> bool:
            try:
                conn = self._db()
                conn.execute("DELETE FROM proxy_sources WHERE id=?", (source_id,))
                conn.commit()
                conn.close()
                self._delete_proxy_source_entries(source_id)
                self._load_all_proxy_source_entries()
                self._emit(f"Proxy source deleted: {source_id}", "warn")
                return True
            except Exception as e:
                logger.error("delete_proxy_source: %s", e)
                return False

    def toggle_proxy_source(self, source_id: str) -> Optional[dict]:
            try:
                conn = self._db()
                row = conn.execute("SELECT enabled FROM proxy_sources WHERE id=?", (source_id,)).fetchone()
                if not row:
                    conn.close()
                    return None
                new_val = 0 if row["enabled"] else 1
                conn.execute("UPDATE proxy_sources SET enabled=?, updated_at=? WHERE id=?", (new_val, time.time(), source_id))
                conn.commit()
                conn.close()
                if new_val == 0:
                    self._delete_proxy_source_entries(source_id)
                    self._load_all_proxy_source_entries()
                status = "enabled" if new_val else "disabled"
                self._emit(f"Proxy source {source_id} {status}", "info")
                return self.get_proxy_source(source_id)
            except Exception as e:
                logger.error("toggle_proxy_source: %s", e)
                return None

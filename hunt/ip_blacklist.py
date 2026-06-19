"""Functional split of the huntproxy backend."""

import ipaddress
import time
from hunt.constants import logger

class IPBlacklistMixin:
    def _parse_ip_blacklist(self, text: str, source_id: str, source_name: str = "", accumulate: bool = True, persist: bool = False) -> int:
            """Parse IP blacklist text. Returns number of entries added.

            Supported formats:
              - plain IP per line: 1.2.3.4
              - CIDR: 1.2.3.0/24
              - IP range: 1.2.3.4-1.2.3.10
              - ip-sum: 1.2.3.4 5 (second token ignored)
            Comments (#, ;, //) and empty lines are ignored.
            """
            added = 0
            parsed: list[tuple[str, str]] = []
            if not accumulate:
                self.ip_blacklist_entries.clear()
                self.ip_blacklist_exact.clear()
                self.ip_blacklist_networks.clear()

            def _add_entry(key: str, reason: str):
                nonlocal added
                meta = {"source_id": source_id, "source_name": source_name, "reason": reason}
                existing = self.ip_blacklist_entries.get(key)
                if existing is None:
                    self.ip_blacklist_entries[key] = [meta]
                    return True
                # Track each source only once per entry to get accurate hit counts.
                if not any(m["source_id"] == source_id for m in existing):
                    existing.append(meta)
                    return True
                return False

            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("#") or line.startswith(";") or line.startswith("//"):
                    continue
                token = line.split()[0]
                if "-" in token and "/" not in token:
                    try:
                        start, end = token.split("-", 1)
                        start_ip = ipaddress.ip_address(start.strip())
                        end_ip = ipaddress.ip_address(end.strip())
                        # collapse range into CIDR networks
                        network = ipaddress.summarize_address_range(start_ip, end_ip)
                        for net in network:
                            key = str(net)
                            reason = f"range from {source_name}"
                            if _add_entry(key, reason):
                                self.ip_blacklist_networks.append(net)
                                added += 1
                            parsed.append((key, reason))
                    except Exception:
                        continue
                else:
                    try:
                        net = ipaddress.ip_network(token, strict=False)
                        is_host = net.prefixlen == (32 if isinstance(net, ipaddress.IPv4Network) else 128)
                        key = str(net.network_address) if is_host else str(net)
                        reason = f"blacklist from {source_name}"
                        if _add_entry(key, reason):
                            if is_host:
                                self.ip_blacklist_exact.add(str(net.network_address))
                            else:
                                self.ip_blacklist_networks.append(net)
                            added += 1
                        parsed.append((key, reason))
                    except Exception:
                        continue
            if persist and parsed:
                self._replace_ip_blacklist_source(source_id, source_name, parsed)
            return added

    def _is_ip_blacklisted(self, ip: str) -> tuple[bool, list[dict]]:
            """Return (is_blacklisted, sources) for a given IP address.

            The returned list contains one dict per matching IP blacklist source:
            {source_id, source_name, reason}.
            """
            if not ip:
                return False, []
            matches: list[dict] = []
            if ip in self.ip_blacklist_exact:
                matches.extend(self.ip_blacklist_entries.get(ip, []))
            try:
                addr = ipaddress.ip_address(ip)
                for net in self.ip_blacklist_networks:
                    if addr in net:
                        matches.extend(self.ip_blacklist_entries.get(str(net), []))
            except Exception:
                pass
            # Deduplicate by source_id in case an IP matches both an exact entry and a network.
            seen = set()
            deduped = []
            for m in matches:
                sid = m.get("source_id")
                if sid and sid in seen:
                    continue
                seen.add(sid)
                deduped.append(m)
            return bool(deduped), deduped

    def _apply_ip_blacklist_to_proxy(self, addr: str, egress_ip: str):
            """Apply IP blacklist hits to a proxy's rating.

            The score is reduced based on how many downloaded IP blacklists contain
            the egress IP; the proxy is no longer fully excluded.
            """
            if not addr or not egress_ip:
                return
            is_bl, sources = self._is_ip_blacklisted(egress_ip)
            r = self.ratings.get(addr)
            if not r:
                return
            if is_bl:
                source_names = [s.get("source_name") or s.get("source_id") for s in sources]
                reason = "; ".join(f"blacklist from {n}" for n in source_names)
                if r.ip_blacklist_reason != reason or r.ip_blacklist_hits != len(sources):
                    r.ip_blacklist_reason = reason or "exit IP blacklisted"
                    r.ip_blacklist_hits = len(sources)
                    r.ip_blacklist_sources = [s.get("source_id") for s in sources]
                    self._emit(f"IP blacklisted: {addr} egress {egress_ip} — {reason}", "blacklist")
            else:
                if r.ip_blacklist_reason or r.ip_blacklist_hits:
                    r.ip_blacklist_reason = ""
                    r.ip_blacklist_hits = 0
                    r.ip_blacklist_sources = []

    def _load_ip_blacklist(self):
            """Load downloaded IP blacklist entries from SQLite into memory."""
            try:
                conn = self._db()
                count = conn.execute("SELECT COUNT(*) as c FROM ip_blacklist_entries").fetchone()["c"]
                conn.close()
                if count > 0:
                    self._load_ip_blacklist_from_db(accumulate=False)
            except Exception as e:
                logger.error("load_ip_blacklist db check: %s", e)

    def _load_ip_blacklist_from_db(self, accumulate: bool = False):
            """Load all persisted IP blacklist entries from SQLite into memory."""
            if not accumulate:
                self.ip_blacklist_entries.clear()
                self.ip_blacklist_exact.clear()
                self.ip_blacklist_networks.clear()
            conn = self._db()
            try:
                rows = conn.execute(
                    "SELECT entry, source_id, source_name, reason FROM ip_blacklist_entries"
                ).fetchall()
                for row in rows:
                    entry = row["entry"]
                    meta = {"source_id": row["source_id"], "source_name": row["source_name"], "reason": row["reason"]}
                    existing = self.ip_blacklist_entries.get(entry)
                    if existing is None:
                        self.ip_blacklist_entries[entry] = [meta]
                        try:
                            net = ipaddress.ip_network(entry, strict=False)
                            is_host = net.prefixlen == (32 if isinstance(net, ipaddress.IPv4Network) else 128)
                            if is_host:
                                self.ip_blacklist_exact.add(str(net.network_address))
                            else:
                                self.ip_blacklist_networks.append(net)
                        except Exception:
                            pass
                    elif not any(m["source_id"] == meta["source_id"] for m in existing):
                        existing.append(meta)
            except Exception as e:
                logger.error("load_ip_blacklist_from_db: %s", e)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def _replace_ip_blacklist_source(self, source_id: str, source_name: str, entries: list[tuple[str, str]]):
            """Replace persisted entries for a single source. Other sources are untouched."""
            now = time.time()
            conn = self._db()
            try:
                conn.execute("DELETE FROM ip_blacklist_entries WHERE source_id=?", (source_id,))
                if entries:
                    conn.executemany(
                        "INSERT OR REPLACE INTO ip_blacklist_entries (entry, source_id, source_name, reason, created_at) VALUES (?,?,?,?,?)",
                        [(entry, source_id, source_name, reason, now) for entry, reason in entries]
                    )
                conn.commit()
            except Exception as e:
                logger.error("replace_ip_blacklist_source %s: %s", source_id, e)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def _delete_ip_blacklist_source_entries(self, source_id: str):
            """Remove persisted entries for a source that was disabled/deleted."""
            conn = self._db()
            try:
                conn.execute("DELETE FROM ip_blacklist_entries WHERE source_id=?", (source_id,))
                conn.commit()
            except Exception as e:
                logger.error("delete_ip_blacklist_source_entries %s: %s", source_id, e)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def _save_ip_blacklist(self):
            """No-op: IP blacklist entries are persisted to DB via replace/delete methods."""
            pass

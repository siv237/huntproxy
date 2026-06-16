"""Functional split of the huntproxy backend."""

import os
import time
from collections import Counter
from hunt.constants import logger
from hunt.models import ProxyRating

class SnapshotMixin:
    def get_snapshot(self) -> dict:
            # Manual operator blacklist is the only hard exclusion; IP blacklist
            # only lowers the score and keeps the proxy alive/working.
            alive = [r for r in self.ratings.values()
                     if r.last_status == "ok" and not r.in_blacklist]
            sorted_alive = sorted(alive, key=lambda r: r.score, reverse=True)
            dead = [r for r in self.ratings.values() if r.last_status == "failed"]
            banned = [r for r in self.ratings.values() if r.in_blacklist]
            ip_blacklisted = sum(1 for r in self.ratings.values() if r.ip_blacklist_reason and not r.in_blacklist)

            return {
                "phase": self.phase,
                "phase_started": self.phase_started,
                "running": self.phase not in (self.PHASE_IDLE, self.PHASE_DONE, self.PHASE_PAUSED),
                "paused": self._paused,
                "manual_pause": self._manual_pause,
                "progress": {
                    "sources_total": self.sources_total,
                    "sources_done": self.sources_done,
                    "downloaded": self.downloaded,
                    "checking_total": self.checking_total,
                    "checked": self.checked,
                    "working": self.working,
                    "failed": self.failed,
                    "last_proxy": self.last_proxy,
                    "last_country": self.last_country,
                },
                "counts": {
                    "ratings": len(self.ratings),
                    "alive": len(alive),
                    "dead": len(dead),
                    "blacklist": len(self.blacklist),
                    "ip_blacklisted": ip_blacklisted,
                    "new_today": sum(1 for r in self.ratings.values() if r.first_seen > time.time() - 86400),
                },
                "settings": {
                    "parallel": self.parallel,
                    "timeout": self.timeout,
                    "country_filter": self.country_filter,
                },
                "top_proxies": [r.to_dict() for r in sorted_alive[:30]],
                "top_countries": self.get_countries(),
                "blacklist": self._blacklist_view(),
                "last_event": self.last_event,
                "uptime_seconds": int(time.time() - self.started_at),
                "last_proxy_details": self.ratings.get(self.last_proxy, ProxyRating(address=self.last_proxy or "")).to_dict() if self.last_proxy else None,
                "resources": self._get_system(),
            }

    def _blacklist_view(self) -> list:
            out = []
            for addr, reason in sorted(self.blacklist.items()):
                r = self.ratings.get(addr)
                out.append({
                    "address": addr,
                    "reason": reason,
                    "country": r.country if r else "",
                    "score": r.score if r else 0,
                })
            return out

    def get_countries(self) -> list:
            alive = [r for r in self.ratings.values() if r.last_status == "ok" and not r.in_blacklist]
            counts = Counter((r.country_code or r.country or "?") for r in alive)
            total = sum(counts.values()) or 1
            result = []
            for code, count in counts.most_common(10):
                if code == "?" or not code:
                    continue
                name = code
                rev = {v: k for k, v in {
                    "US": "United States", "GB": "United Kingdom", "DE": "Germany",
            "FR": "France", "NL": "The Netherlands", "JP": "Japan", "CA": "Canada",
                    "RU": "Russia", "CN": "China", "BR": "Brazil", "ES": "Spain",
                    "IT": "Italy", "PL": "Poland", "UA": "Ukraine", "IN": "India",
                    "AU": "Australia", "SG": "Singapore", "KR": "Korea", "MX": "Mexico",
                    "SE": "Sweden", "NO": "Norway", "FI": "Finland", "CH": "Switzerland",
                    "ID": "Indonesia", "TH": "Thailand", "VN": "Vietnam", "TR": "Turkey",
                    "ZA": "South Africa", "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
                    "PH": "Philippines", "MY": "Malaysia", "RO": "Romania", "CZ": "Czech Republic",
                    "HU": "Hungary", "BG": "Bulgaria", "PK": "Pakistan", "BD": "Bangladesh",
                    "NG": "Nigeria", "KE": "Kenya", "EG": "Egypt", "IL": "Israel",
                }.items()}
                name = rev.get(code, code)
                result.append({"country": name, "country_code": code, "count": count, "pct": round(count / total * 100, 1)})
            return result

    def get_activity(self, limit: int = 10) -> list:
            def _icon(kind, msg):
                if "validated" in msg.lower(): return "validated"
                if "added" in msg.lower(): return "added"
                if "removed" in msg.lower() or "clear" in msg.lower(): return "removed"
                if "failed" in msg.lower() or "error" in msg.lower(): return "failed"
                if "health" in msg.lower(): return "health"
                if "blacklist" in msg.lower(): return "blacklist"
                if "stopped" in msg.lower(): return "stopped"
                if "started" in msg.lower(): return "started"
                return "info"
            out = []
            try:
                conn = self._stats_db()
                rows = conn.execute("SELECT ts, seq, type, msg FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                conn.close()
                for r in rows:
                    out.append({"seq": r["seq"], "ts": r["ts"], "type": r["type"], "msg": r["msg"], "icon": _icon(r["type"], r["msg"])})
            except Exception:
                # Fallback to in-memory events if DB is unavailable.
                for ev in reversed(self.events[-limit:]):
                    out.append({
                        "seq": ev["seq"],
                        "ts": ev["ts"],
                        "type": ev["type"],
                        "msg": ev["msg"],
                        "icon": _icon(ev["type"], ev["msg"]),
                    })
            return out


    def get_history(self, last: str = "1h") -> list:
            try:
                if last.endswith("h"):
                    cutoff = time.time() - int(last[:-1]) * 3600
                elif last.endswith("d"):
                    cutoff = time.time() - int(last[:-1]) * 86400
                else:
                    cutoff = 0
            except Exception:
                cutoff = 0
            try:
                conn = self._stats_db()
                rows = conn.execute(
                    "SELECT ts, alive, dead, total, requests, connections_ok, connections_failed, success_rate, traffic_success_rate, bandwidth_in, bandwidth_out, avg_latency FROM history WHERE ts > ? ORDER BY ts",
                    (cutoff,)
                ).fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error("DB get_history: %s", e)
                return []

    def _get_system(self) -> dict:
            try:
                import psutil
                return {
                    "cpu": psutil.cpu_percent(interval=0.1),
                    "memory": psutil.virtual_memory().percent,
                    "disk": psutil.disk_usage('/').percent,
                }
            except Exception:
                pass
            cpu = None
            mem = None
            disk = None
            try:
                with open("/proc/stat") as f:
                    line = f.readline()
                parts = line.split()
                if parts[0] == "cpu" and len(parts) >= 5:
                    idle = int(parts[4])
                    total = sum(int(x) for x in parts[1:5])
                    cpu = round((1 - idle / total) * 100, 1) if total else 0.0
                else:
                    cpu = 0.0
            except Exception:
                cpu = None
            try:
                with open("/proc/meminfo") as f:
                    mem_total = None
                    mem_avail = None
                    for line in f:
                        if line.startswith("MemTotal:"):
                            mem_total = int(line.split()[1])
                        elif line.startswith("MemAvailable:"):
                            mem_avail = int(line.split()[1])
                    if mem_total and mem_avail:
                        mem = round((1 - mem_avail / mem_total) * 100, 1)
                    else:
                        mem = None
            except Exception:
                mem = None
            try:
                du = os.statvfs('/')
                disk = round((1 - du.f_bavail / du.f_blocks) * 100, 1) if du.f_blocks else None
            except Exception:
                try:
                    import shutil
                    du = shutil.disk_usage('/')
                    disk = round(du.used / du.total * 100, 1)
                except Exception:
                    disk = None
            return {"cpu": cpu, "memory": mem, "disk": disk}

    def _push_history(self):
            alive = sum(1 for r in self.ratings.values() if r.last_status == "ok" and not r.in_blacklist)
            dead = sum(1 for r in self.ratings.values() if r.last_status == "failed")
            pool_sr = (alive / max(1, alive + dead)) * 100

            since = getattr(self, '_last_history_ts', time.time() - 60)
            now = time.time()
            total_req = 0
            ok_req = 0
            bw_in = 0
            bw_out = 0
            avg_lat = 0.0
            try:
                conn = self._stats_db()
                row = conn.execute(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) as ok, "
                    "COALESCE(SUM(bytes_in), 0) as bw_in, "
                    "COALESCE(SUM(bytes_out), 0) as bw_out, "
                    "COALESCE(AVG(CASE WHEN duration > 0 THEN duration END), 0) as avg_lat "
                    "FROM traffic_log WHERE ts > ?",
                    (since,)
                ).fetchone()
                conn.close()
                if row:
                    total_req = row["total"] or 0
                    ok_req = row["ok"] or 0
                    bw_in = row["bw_in"] or 0
                    bw_out = row["bw_out"] or 0
                    avg_lat = row["avg_lat"] or 0.0
            except Exception as e:
                logger.error("DB traffic query: %s", e)

            traffic_sr = (ok_req / max(1, total_req)) * 100 if total_req else 0

            try:
                conn = self._stats_db()
                conn.execute(
                    "INSERT INTO history (ts, alive, dead, total, requests, connections_ok, connections_failed, success_rate, traffic_success_rate, bandwidth_in, bandwidth_out, avg_latency) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (now, alive, dead, len(self.ratings), total_req, ok_req, total_req - ok_req, pool_sr, traffic_sr, bw_in, bw_out, avg_lat)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error("DB push history: %s", e)

            self._last_history_ts = now

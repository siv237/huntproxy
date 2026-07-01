"""Functional split of the huntproxy backend."""

import asyncio
import json
import time
from hunt.constants import logger
from hunt.models import ProxyRating

class CanaryMixin:
    async def _canary_loop(self):
            while True:
                await asyncio.sleep(15)
                try:
                    was_paused = self._paused
                    result = await self._check_canary()
                    if not result["alive"] and not self._paused:
                        self.pause_hunt(manual=False)
                    elif result["alive"] and self._paused and not self._manual_pause:
                        self.resume_hunt(manual=False)
                except asyncio.CancelledError:
                    return
                except Exception:
                    pass

    async def _check_canary(self) -> dict:
            hosts = self.canary_hosts or ["ya.ru", "google.com", "2ip.ru"]
            results = {}
            latencies = {}
            canary_to = 25 if self._channel_is_set() else 8
            for host in hosts:
                t0 = time.monotonic()
                try:
                    reader, writer = await self._outbound_connect(host, 443, timeout=canary_to)
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass
                    lat = int((time.monotonic() - t0) * 1000)
                    results[host] = True
                    latencies[host] = lat
                except Exception:
                    results[host] = False
                    latencies[host] = -1
            alive_count = sum(1 for v in results.values() if v)
            total = len(results)
            was_alive = self._internet_alive
            alive = alive_count > total // 2
            self._internet_alive = alive
            self._canary_last_check = time.time()

            if was_alive is True and not alive:
                self._emit("Internet DOWN — all canary hosts unreachable", "error")
            elif was_alive is False and alive:
                self._emit("Internet RESTORED — canary hosts reachable", "ok")

            direct_ip = ""
            direct_country = ""
            direct_isp = ""
            direct_city = ""
            if alive:
                try:
                    reader, writer = await self._outbound_connect("ip-api.com", 80, timeout=canary_to)
                    req = "GET /json/?fields=query,country,isp,city HTTP/1.1\r\nHost: ip-api.com\r\nConnection: close\r\n\r\n"
                    writer.write(req.encode()); await writer.drain()
                    resp = b""
                    while True:
                        chunk = await asyncio.wait_for(reader.read(4096), timeout=5)
                        if not chunk: break
                        resp += chunk
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass
                    body_start = resp.find(b"\r\n\r\n")
                    if body_start >= 0:
                        import json as _json
                        data = _json.loads(resp[body_start+4:])
                        new_ip = data.get("query", "")
                        new_country = data.get("country", "")
                        new_isp = data.get("isp", "")
                        new_city = data.get("city", "")
                        old_ip = self._canary_last_ip if hasattr(self, '_canary_last_ip') else ""
                        if old_ip and new_ip and old_ip != new_ip:
                            self._emit(f"ISP changed: {old_ip} ({getattr(self, '_canary_last_isp', '')}) → {new_ip} ({new_isp})", "warn")
                        direct_ip = new_ip
                        direct_country = new_country
                        direct_isp = new_isp
                        direct_city = new_city
                        self._canary_last_ip = new_ip
                        self._canary_last_isp = new_isp
                        self._canary_last_country = new_country
                        self._canary_last_city = new_city
                except Exception:
                    pass

            try:
                conn = self._stats_db()
                conn.execute(
                    "INSERT INTO canary_history (ts, alive, alive_count, total_count, host_results, direct_ip, direct_country, direct_isp, direct_city) VALUES (?,?,?,?,?,?,?,?,?)",
                    (time.time(), 1 if alive else 0, alive_count, total,
                     json.dumps(results), direct_ip, direct_country, direct_isp, direct_city)
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

            result = {
                "alive": alive,
                "hosts": results,
                "latencies": latencies,
                "alive_count": alive_count,
                "total": total,
                "direct_ip": direct_ip,
                "direct_country": direct_country,
                "direct_isp": direct_isp,
                "direct_city": direct_city,
            }
            self._canary_cache = result
            return result

    async def is_internet_alive(self) -> bool:
            if self._internet_alive is not None and (time.time() - self._canary_last_check) < self._canary_interval:
                return self._internet_alive
            result = await self._check_canary()
            return result["alive"]

    def get_canary_status(self) -> dict:
            if self._canary_cache:
                result = dict(self._canary_cache)
                result["channel"] = self.get_channel_status()
                return result
            return {
                "alive": self._internet_alive,
                "hosts": {},
                "latencies": {},
                "alive_count": 0,
                "total": len(self.canary_hosts),
                "last_check": self._canary_last_check,
                "canary_hosts": self.canary_hosts,
                "direct_ip": getattr(self, '_canary_last_ip', ''),
                "direct_country": getattr(self, '_canary_last_country', ''),
                "direct_isp": getattr(self, '_canary_last_isp', ''),
                "direct_city": getattr(self, '_canary_last_city', ''),
                "channel": self.get_channel_status(),
            }

    def set_canary_hosts(self, hosts: list):
            self.canary_hosts = hosts
            self._internet_alive = None
            self._emit(f"Canary hosts updated: {', '.join(hosts)}", "info")

    def get_canary_history(self, hours: int = 24) -> list:
            try:
                conn = self._stats_db()
                since = time.time() - hours * 3600
                rows = conn.execute(
                    "SELECT ts, alive, alive_count, total_count, host_results, direct_ip, direct_country, direct_isp, direct_city "
                    "FROM canary_history WHERE ts>? ORDER BY ts ASC", (since,)
                ).fetchall()
                conn.close()
                result = []
                for r in rows:
                    entry = dict(r)
                    try:
                        entry["host_results"] = json.loads(entry.get("host_results", "{}"))
                    except Exception:
                        entry["host_results"] = {}
                    result.append(entry)
                return result
            except Exception as e:
                logger.error("get_canary_history: %s", e)
                return []

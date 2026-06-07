"""
Proxy Pool Manager — loads, validates, rotates, and tracks proxy health.
Serves as the bridge between the fetcher and the proxy server.
"""

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from fetcher import ProxyFetcher, DEFAULT_SOURCES

logger = logging.getLogger("setproxy.manager")


@dataclass
class ProxyInfo:
    address: str
    country: str = ""
    protocol: str = "http"
    latency: float = 0.0
    speed: float = 0.0
    failures: int = 0
    last_checked: float = 0.0
    last_used: float = 0.0
    added_at: float = 0.0
    cooldown_until: float = 0.0
    blacklisted: bool = False
    blacklist_reason: str = ""


class ProxyManager:
    def __init__(self, data_dir: str, config: dict):
        self.data_dir = Path(data_dir)
        self.config = config
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.pool: list[ProxyInfo] = []
        self.blacklist: dict[str, str] = {}
        self.active_proxy: Optional[ProxyInfo] = None
        self._lock = asyncio.Lock()
        self._rr_index = 0
        self._running = False
        self._tasks: list[asyncio.Task] = []

        self.events: list[dict] = []
        self._event_cond = asyncio.Condition()
        self._event_seq = 0

        self.fetcher = ProxyFetcher(
            data_dir=self.data_dir,
            timeout=config.get("timeout", 10),
            parallel=config.get("parallel", 100),
            us_only=config.get("us_only", True),
            test_url=config.get("test_url", "http://ip-api.com/json/%s"),
        )

        self._validate_interval = config.get("validate_interval", 300)
        self._health_interval = config.get("health_interval", 120)
        self._health_timeout = config.get("health_timeout", 10)
        self._health_parallel = config.get("health_parallel", 30)
        self._max_failures = config.get("max_failures", 3)
        self._cooldown = config.get("cooldown", 300)
        self._strategy = config.get("strategy", "round_robin")

        self._load_blacklist()
        self._load_pool()
        self._load_last_proxy()

    @property
    def working_file(self) -> Path:
        return self.data_dir / "working.txt"

    @property
    def blacklist_file(self) -> Path:
        return self.data_dir / "blacklist.txt"

    @property
    def stats_file(self) -> Path:
        return self.data_dir / "stats.json"

    @property
    def last_proxy_file(self) -> Path:
        return self.data_dir / "last_proxy.txt"

    @property
    def pool_size(self) -> int:
        return len([p for p in self.pool if not p.blacklisted])

    def _emit(self, event_type: str, **kwargs):
        self._event_seq += 1
        ev = {"seq": self._event_seq, "ts": time.time(), "type": event_type}
        ev.update(kwargs)
        self.events.append(ev)
        if len(self.events) > 500:
            self.events = self.events[-300:]

        async def notify():
            async with self._event_cond:
                self._event_cond.notify_all()
        try:
            asyncio.get_event_loop().call_soon_threadsafe(
                lambda: asyncio.ensure_future(notify())
            )
        except Exception:
            pass

    def get_status(self) -> dict:
        alive = sum(1 for p in self.pool if not p.blacklisted and p.cooldown_until <= time.time())
        dead = sum(1 for p in self.pool if p.blacklisted or p.cooldown_until > time.time())
        ap = None
        if self.active_proxy:
            ap = {"address": self.active_proxy.address,
                  "country": self.active_proxy.country,
                  "protocol": self.active_proxy.protocol,
                  "failures": self.active_proxy.failures,
                  "latency": self.active_proxy.latency}
        return {
            "pool_total": len(self.pool),
            "pool_alive": alive,
            "pool_dead": dead,
            "blacklisted": len(self.blacklist),
            "active_proxy": ap,
            "strategy": self._strategy,
            "active_proxy_enabled": ap is not None,
            "fetcher_stats": self.fetcher.current_stats(),
            "running": self._running,
        }

    async def start(self):
        self._running = True
        self._tasks.append(asyncio.create_task(self._validate_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        self._emit("manager_started", pool_size=self.pool_size)
        logger.info(f"Manager started. Pool: {len(self.pool)}, "
                     f"Active: {self.active_proxy.address if self.active_proxy else 'none'}")

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._save_blacklist()
        self._save_stats()
        self._save_last_proxy()
        logger.info("Manager stopped")

    async def get_proxy(self) -> Optional[ProxyInfo]:
        async with self._lock:
            proxy = self._select_proxy()
            if proxy:
                self.active_proxy = proxy
                self._save_last_proxy()
            return proxy

    def _select_proxy(self) -> Optional[ProxyInfo]:
        now = time.time()
        candidates = [p for p in self.pool
                      if not p.blacklisted and p.cooldown_until <= now]
        if not candidates:
            return None

        if self._strategy == "round_robin":
            self._rr_index %= len(candidates)
            proxy = candidates[self._rr_index]
            self._rr_index += 1
        elif self._strategy == "random":
            proxy = random.choice(candidates)
        else:
            proxy = candidates[0]

        proxy.last_used = now
        return proxy

    def report_failure(self, address: str, reason: str = ""):
        for p in self.pool:
            if p.address == address:
                p.failures += 1
                p.last_checked = time.time()
                if p.failures >= self._max_failures:
                    p.blacklisted = True
                    p.blacklist_reason = reason or f"failures: {p.failures}"
                    self.blacklist[address] = p.blacklist_reason
                    self._save_blacklist()
                    self._emit("proxy_blacklisted", address=address, reason=p.blacklist_reason)
                    logger.warning(f"Blacklisted: {address} — {p.blacklist_reason}")
                else:
                    p.cooldown_until = time.time() + self._cooldown
                    self._emit("proxy_failed", address=address, failures=p.failures,
                               cooldown=self._cooldown)
                    logger.warning(f"Proxy failure: {address} [{p.failures}/{self._max_failures}]"
                                   f" — {reason}")
                self._save_stats()
                break

    def report_success(self, address: str, latency: float = 0.0, speed: float = 0.0):
        for p in self.pool:
            if p.address == address:
                p.failures = 0
                p.last_checked = time.time()
                p.cooldown_until = 0.0
                if latency > 0:
                    p.latency = latency
                if speed > 0:
                    p.speed = speed
                break

    async def force_refresh(self):
        logger.info("Manual refresh triggered")
        self._emit("refresh_started")
        await self._validate_pool()
        self._emit("refresh_complete", pool_size=self.pool_size)

    async def blacklist_add(self, address: str, reason: str = ""):
        self.blacklist[address] = reason or "manual"
        async with self._lock:
            for p in self.pool:
                if p.address == address:
                    p.blacklisted = True
                    p.blacklist_reason = reason or "manual"
        self._save_blacklist()
        self._emit("proxy_blacklisted", address=address, reason=reason or "manual")
        logger.info(f"Manually blacklisted: {address}")

    async def blacklist_remove(self, address: str):
        self.blacklist.pop(address, None)
        async with self._lock:
            for p in self.pool:
                if p.address == address:
                    p.blacklisted = False
                    p.failures = 0
                    p.blacklist_reason = ""
        self._save_blacklist()
        self._emit("proxy_unblacklisted", address=address)
        logger.info(f"Removed from blacklist: {address}")

    async def _validate_loop(self):
        logger.info(f"Validate loop started, interval={self._validate_interval}s")
        while self._running:
            await self._sleep_interruptible(5)  # small delay on startup
            try:
                await self._validate_pool()
            except Exception as e:
                logger.error(f"Validate loop error: {e}")
            await self._sleep_interruptible(self._validate_interval)

    async def _validate_pool(self):
        logger.info("Fetching and validating proxies...")
        self._emit("downloading_started")

        proxies = await self.fetcher.fetch_and_validate(
            callback=self._on_validate_progress,
        )
        if not proxies:
            logger.warning("No working proxies found")
            self._emit("download_complete", new_proxies=0)
            return

        await self._merge_pool(proxies)
        self._emit("download_complete", new_proxies=len(proxies), pool_size=self.pool_size)
        self._save_pool()
        self._save_stats()

    def _on_validate_progress(self, checked: int, total: int, working: int, last_addr: Optional[str]):
        self._emit("validate_progress", checked=checked, total=total,
                   working=working, last_addr=last_addr)

    async def _merge_pool(self, new_proxies: list):
        async with self._lock:
            existing = {p.address: p for p in self.pool}
            now = time.time()
            for addr, country in new_proxies:
                if addr in self.blacklist:
                    continue
                if addr in existing:
                    existing[addr].country = country or existing[addr].country
                    existing[addr].last_checked = now
                else:
                    protocol = "http"
                    port_str = addr.rsplit(":", 1)[-1]
                    try:
                        port = int(port_str)
                        if port in (1080, 10808):
                            protocol = "socks5"
                        elif port == 4145:
                            protocol = "socks4"
                    except ValueError:
                        pass
                    existing[addr] = ProxyInfo(
                        address=addr, country=country, protocol=protocol,
                        added_at=now, last_checked=now,
                    )
            self.pool = list(existing.values())

    async def _health_loop(self):
        logger.info(f"Health check loop started, interval={self._health_interval}s")
        await self._sleep_interruptible(10)  # initial delay
        while self._running:
            try:
                await self._run_health_check()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            await self._sleep_interruptible(self._health_interval)

    SPEED_SERVERS = [
        ("speedtest.tele2.net", "/512KB.zip", 524288),
        ("ipv4.download.thinkbroadband.com", "/512KB.zip", 524288),
        ("testdebit.info", "/1M.iso", 1048576),
    ]

    async def _measure_speed(self, addr: str) -> float:
        host, port_str = addr.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return 0.0
        for srv_host, srv_path, expected_size in self.SPEED_SERVERS:
            speed = await self._speed_single(host, port, srv_host, srv_path, expected_size)
            if speed > 0:
                return speed
        return 0.0

    async def _speed_single(self, host: str, port: int,
                             srv_host: str, srv_path: str, expected_size: int) -> float:
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self._health_timeout,
            )
        except Exception:
            return 0.0
        try:
            t0 = time.monotonic()
            req = (
                f"GET http://{srv_host}{srv_path} HTTP/1.0\r\n"
                f"Host: {srv_host}\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            w.write(req.encode())
            await asyncio.wait_for(w.drain(), timeout=10)
            total = 0
            while True:
                try:
                    chunk = await asyncio.wait_for(r.read(65536), timeout=30)
                except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                    break
                if not chunk:
                    break
                total += len(chunk)
                if total >= expected_size:
                    break
            elapsed = time.monotonic() - t0
            if elapsed > 0 and total >= expected_size * 0.8:
                return total / elapsed / 1024.0
            return 0.0
        except Exception:
            return 0.0
        finally:
            try:
                w.close()
            except Exception:
                pass

    async def _run_health_check(self):
        now = time.time()
        candidates = [p for p in self.pool if not p.blacklisted]
        if not candidates:
            return

        logger.info(f"Health-checking {len(candidates)} proxies...")
        self._emit("health_check_started", count=len(candidates))

        sem = asyncio.Semaphore(self._health_parallel)
        checked = 0
        alive = 0
        lock = asyncio.Lock()

        async def check_one(p: ProxyInfo):
            nonlocal checked, alive
            async with sem:
                start = time.monotonic()
                ok = await self.fetcher._check_proxy(p.address)
                latency = time.monotonic() - start
                speed = 0.0
                if ok:
                    try:
                        speed = await self._measure_speed(p.address)
                    except Exception:
                        speed = 0.0
                async with lock:
                    checked += 1
                    if ok:
                        alive += 1
                        self.report_success(p.address, latency, speed)
                    else:
                        self.report_failure(p.address, "health check")
                    self._emit("health_check_progress", checked=checked,
                               total=len(candidates), alive=alive)

        tasks = [asyncio.create_task(check_one(p)) for p in candidates]
        await asyncio.gather(*tasks)

        logger.info(f"Health check done: {alive} alive / {checked} checked")
        self._emit("health_check_complete", alive=alive, checked=checked)
        self._save_stats()

    async def get_events(self, since: int = 0, timeout: float = 30.0) -> list:
        async with self._event_cond:
            if since >= self._event_seq:
                try:
                    await asyncio.wait_for(self._event_cond.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    pass
        result = [e for e in self.events if e["seq"] > since]
        return result

    async def _sleep_interruptible(self, seconds: float):
        for _ in range(int(seconds)):
            if not self._running:
                break
            await asyncio.sleep(1)

    def _load_pool(self):
        wf = self.working_file
        if not wf.exists():
            logger.info("No working.txt yet, will fetch on first run")
            return

        now = time.time()
        count = 0
        with open(wf) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                addr = parts[0]
                country = parts[1] if len(parts) > 1 else ""
                if addr in self.blacklist:
                    continue
                protocol = "http"
                port_str = addr.rsplit(":", 1)[-1]
                try:
                    port = int(port_str)
                    if port in (1080, 10808):
                        protocol = "socks5"
                    elif port == 4145:
                        protocol = "socks4"
                except ValueError:
                    pass
                self.pool.append(ProxyInfo(
                    address=addr, country=country, protocol=protocol,
                    added_at=now, last_checked=now,
                ))
                count += 1
        logger.info(f"Loaded {count} proxies from pool")

    def _save_pool(self):
        tmp = self.data_dir / ".working.tmp"
        with open(tmp, "w") as f:
            for p in self.pool:
                if not p.blacklisted:
                    f.write(f"{p.address}  {p.country}\n")
        tmp.rename(self.working_file)

    def _load_blacklist(self):
        if self.blacklist_file.exists():
            with open(self.blacklist_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(maxsplit=1)
                    self.blacklist[parts[0]] = parts[1] if len(parts) > 1 else ""

    def _save_blacklist(self):
        with open(self.blacklist_file, "w") as f:
            f.write(f"# setproxy blacklist — {len(self.blacklist)} entries\n")
            for addr, reason in sorted(self.blacklist.items()):
                f.write(f"{addr}  {reason}\n")

    def _save_stats(self):
        with open(self.stats_file, "w") as f:
            json.dump([asdict(p) for p in self.pool], f, indent=2)

    def _load_last_proxy(self):
        lf = self.last_proxy_file
        if not lf.exists():
            return
        try:
            with open(lf) as f:
                addr = f.read().strip()
                if addr:
                    for p in self.pool:
                        if p.address == addr:
                            self.active_proxy = p
                            logger.info(f"Loaded last active proxy: {addr}")
                            return
        except Exception:
            pass

    def _save_last_proxy(self):
        if self.active_proxy:
            with open(self.last_proxy_file, "w") as f:
                f.write(self.active_proxy.address + "\n")

    async def list_proxies(self, n: int = 20):
        alive = [p for p in self.pool if not p.blacklisted and p.cooldown_until <= time.time()]
        result = []
        for p in alive[:n]:
            result.append({
                "address": p.address,
                "protocol": p.protocol,
                "country": p.country,
                "latency": round(p.latency, 3),
                "speed": round(p.speed, 1),
                "failures": p.failures,
                "last_used": p.last_used,
            })
        return result

    async def get_proxies_api(self) -> list:
        result = []
        for p in self.pool:
            result.append({
                "address": p.address,
                "protocol": p.protocol,
                "country": p.country,
                "latency": round(p.latency, 3),
                "speed": round(p.speed, 1),
                "failures": p.failures,
                "blacklisted": p.blacklisted,
                "blacklist_reason": p.blacklist_reason,
                "cooldown_until": p.cooldown_until,
                "active": (self.active_proxy and self.active_proxy.address == p.address),
            })
        return result

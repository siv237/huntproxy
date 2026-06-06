"""
Proxy Fetcher — downloads proxy lists and validates them in parallel.
Pure Python, no external dependencies beyond stdlib + PyYAML for config.
"""

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("setproxy.fetcher")

DEFAULT_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
]

IP_PORT_RE = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})')


class ProxyFetcher:
    def __init__(self, data_dir: Path, timeout: int = 10, parallel: int = 100,
                 us_only: bool = True, test_url: str = "http://ip-api.com/json/%s"):
        self.data_dir = data_dir
        self.timeout = timeout
        self.parallel = parallel
        self.us_only = us_only
        self.test_url = test_url
        self._stats = {"downloaded": 0, "checked": 0, "working": 0, "errors": 0}

    def current_stats(self) -> dict:
        return dict(self._stats)

    async def fetch_and_validate(self, sources: Optional[list] = None,
                                  callback=None) -> list:
        sources = sources or DEFAULT_SOURCES
        self._stats = {"downloaded": 0, "checked": 0, "working": 0, "errors": 0}

        raw_proxies = await self._download_all(sources)
        if not raw_proxies:
            logger.warning("No proxies downloaded")
            return []

        logger.info(f"Downloaded {len(raw_proxies)} unique IPs, validating...")
        working = await self._validate_batch(raw_proxies, callback)
        logger.info(f"Validation done: {len(working)} working US proxies")
        return working

    async def _download_all(self, sources: list) -> set:
        sem = asyncio.Semaphore(10)
        seen = set()

        async def download_one(url: str):
            async with sem:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "curl", "-sSf", "--max-time", "20", url,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    stdout, _ = await proc.communicate()
                    if proc.returncode == 0:
                        text = stdout.decode(errors="replace")
                        for match in IP_PORT_RE.finditer(text):
                            addr = f"{match.group(1)}:{match.group(2)}"
                            seen.add(addr)
                except Exception:
                    pass

        logger.info(f"Downloading from {len(sources)} sources...")
        tasks = [asyncio.create_task(download_one(u)) for u in sources]
        await asyncio.gather(*tasks)
        self._stats["downloaded"] = len(seen)
        return seen

    async def _validate_batch(self, proxies: set, callback=None) -> list:
        sem = asyncio.Semaphore(self.parallel)
        checked = 0
        working = []
        lock = asyncio.Lock()

        async def check_one(addr: str):
            nonlocal checked
            async with sem:
                ok, country = await self._check_proxy(addr)
                async with lock:
                    checked += 1
                    self._stats["checked"] = checked
                    if ok:
                        working.append((addr, country))
                        self._stats["working"] = len(working)
                    if callback:
                        callback(checked, len(proxies), len(working), addr if ok else None)

        tasks = [asyncio.create_task(check_one(p)) for p in proxies]
        await asyncio.gather(*tasks)
        return working

    async def _check_proxy(self, addr: str) -> tuple:
        host, port_str = addr.rsplit(":", 1)
        port = int(port_str)
        ip = host

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.timeout,
            )
        except (asyncio.TimeoutError, OSError):
            self._stats["errors"] += 1
            return False, ""

        try:
            url = self.test_url % ip
            request = (
                f"GET {url} HTTP/1.0\r\n"
                f"Host: ip-api.com\r\n"
                f"User-Agent: setproxy\r\n"
                f"Accept: application/json\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )
            writer.write(request.encode())
            await asyncio.wait_for(writer.drain(), timeout=self.timeout)

            response = b""
            while True:
                try:
                    chunk = await asyncio.wait_for(reader.read(65536), timeout=self.timeout)
                except asyncio.TimeoutError:
                    break
                if not chunk:
                    break
                response += chunk
                if b"}" in response and len(response) > 200:
                    break
        except Exception:
            self._stats["errors"] += 1
            return False, ""
        finally:
            try:
                writer.close()
            except Exception:
                pass

        body_start = response.find(b"\r\n\r\n")
        if body_start == -1:
            body_start = response.find(b"\n\n")
        if body_start == -1:
            return False, ""

        body = response[body_start:].strip()
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False, ""

        country = data.get("country", "")
        if self.us_only and country != "United States":
            return False, country

        return True, country


async def dump_working(data_dir: Path, proxies: list):
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp = data_dir / ".working.tmp"
    target = data_dir / "working.txt"

    with open(tmp, "w") as f:
        for addr, country in proxies:
            f.write(f"{addr}  {country}\n")

    tmp.rename(target)
    logger.info(f"Saved {len(proxies)} working proxies -> {target}")

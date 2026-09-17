"""HTTP request/response parsing helpers for the proxy runner.

Extracted from proxy_runner.py to keep that module within its size budget.
"""

import asyncio
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ProxyHttpMixin:
    _RESPONSE_HEAD_CAP = 65536

    def _request_has_body(self, raw_headers) -> bool:
        for h in raw_headers:
            hl = h.lower()
            if hl.startswith(b"content-length:"):
                try:
                    return int(h.split(b":", 1)[1].strip() or b"0") > 0
                except ValueError:
                    return True
            if hl.startswith(b"transfer-encoding:"):
                return True
        return False

    async def _read_response_head(self, up_r) -> bytes | None:
        """Read the complete response head (status line + headers) without
        writing anything to the client. Returns None if the upstream died
        before completing it — the caller may then retry the request."""
        try:
            head = await asyncio.wait_for(up_r.readuntil(b"\r\n\r\n"), timeout=30)
        except Exception:
            return None
        if len(head) > self._RESPONSE_HEAD_CAP:
            return None
        return head

    async def _read_http_headers(self, reader) -> tuple:
        raw_headers = []
        host_hdr = None
        while True:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=15)
            except Exception:
                break
            if line in (b"\r\n", b"\n", b""):
                break
            raw_headers.append(line)
            if line.lower().startswith(b"host:"):
                host_hdr = line[5:].strip().decode(errors="replace")
        return host_hdr, raw_headers

    def _parse_forward_target(self, target: str, host_hdr: str) -> tuple:
        if target.startswith("/"):
            if host_hdr and ":" in host_hdr:
                host, ps = host_hdr.rsplit(":", 1)
                try:
                    return host, int(ps)
                except Exception:
                    logger.debug("suppressed", exc_info=True)
            return host_hdr or "", 80
        parsed = urlparse(target)
        return parsed.hostname or "", parsed.port or 80

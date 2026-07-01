"""Functional split of the huntproxy backend."""

import asyncio
import time
from hunt.conn import socks5_connect, socks4_connect, http_connect
from hunt.models import ProxyRating
from typing import Optional
from urllib.parse import urlparse
from hunt.proxy_routing import ProxyRouteMixin
import logging

logger = logging.getLogger(__name__)

class ProxyRunner(ProxyRouteMixin):
    def __init__(self, state: "HuntState", host: str = "127.0.0.1"):
        self.state = state
        self.proxy_host = host
        self._server: Optional[asyncio.AbstractServer] = None
        self._task: Optional[asyncio.Task] = None
        self.running = False
        self.port = 17277
        self.active_proxy_addr: Optional[str] = None
        self.direct_mode: bool = False
        self.log: list[dict] = []
        self._failover_idx = 0

    @property
    def selected_proxy(self) -> Optional[ProxyRating]:
        if self.active_proxy_addr and self.active_proxy_addr in self.state.ratings:
            return self.state.ratings[self.active_proxy_addr]
        return None

    def select(self, address: Optional[str]):
        self.active_proxy_addr = address
        if address and address not in self.state.ratings:
            port = 80
            try:
                port_str = address.rsplit(":", 1)[1]
                port = int(port_str)
            except (IndexError, ValueError):
                pass
            protocol = "http"
            if port in (1080, 10808, 9050):
                protocol = "socks5"
            elif port == 4145:
                protocol = "socks4"
            r = ProxyRating(address=address, protocol=protocol,
                            last_status="ok", checks_total=1, checks_ok=1,
                            last_check=time.time(), first_seen=time.time())
            self.state.ratings[address] = r
        if address:
            self.state._emit(f"Proxy upstream selected: {address}", "info")
        self._record_switch("select" if address else "clear", address)

    def _record_switch(self, action: str, address: Optional[str]):
        """Append an entry to the proxy switch history chronology."""
        entry = {"ts": time.time(), "action": action, "address": address or ""}
        self.state._proxy_switch_history.append(entry)
        if len(self.state._proxy_switch_history) > 100:
            self.state._proxy_switch_history = self.state._proxy_switch_history[-100:]

    async def start(self, port: int):
        if self.running:
            return
        self.port = port
        self.running = True
        self.state._proxy_running = True
        self.state._proxy_port = port
        self.state._save_state()
        self._task = asyncio.create_task(self._run())
        self.state._emit(f"Proxy server starting on {port}...", "info")

    async def stop(self):
        self.running = False
        self.state._proxy_running = False
        self.state._save_state()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.state._emit("Proxy server stopped", "info")

    async def _run(self):
        try:
            self._server = await asyncio.start_server(
                self._handle, self.proxy_host, self.port)
            addr = self._server.sockets[0].getsockname()
            self.state._emit(f"Proxy listening on {addr[0]}:{addr[1]}", "ok")
            async with self._server:
                await self._server.serve_forever()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.state._emit(f"Proxy server error: {e}", "error")
        finally:
            self.running = False

    async def _handle(self, reader, writer):
        peer = writer.get_extra_info("peername")
        target_host = "?"
        t0 = time.monotonic()
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=15)
            if not line:
                writer.close(); return
            parts = line.split()
            if len(parts) < 3:
                writer.close(); return
            method = parts[0].upper()

            if method == b"CONNECT":
                target = parts[1].decode(errors="replace")
                if ":" in target:
                    target_host, port_str = target.rsplit(":", 1)
                else:
                    target_host, port_str = target, "443"
                try:
                    target_port = int(port_str)
                except ValueError:
                    target_port = 443

                while True:
                    try:
                        hdr = await asyncio.wait_for(reader.readline(), timeout=15)
                    except Exception:
                        break
                    if hdr in (b"\r\n", b"\n", b""):
                        break

                upstream = await self._connect_upstream(target_host, target_port)
                if not upstream:
                    writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    await writer.drain()
                    writer.close()
                    dur = time.monotonic() - t0
                    self._log(peer, target_host, "502 no upstream", duration=dur)
                    return

                up_r, up_w, chain, _is_raw = upstream
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                bi, bo = await self._relay(reader, writer, up_r, up_w)
                dur = time.monotonic() - t0
                self._log(peer, target_host, "ok", " → ".join(chain), bytes_in=bi, bytes_out=bo, duration=dur)
            else:
                await self._handle_http_forward(reader, writer, method, parts[1], peer, t0)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            dur = time.monotonic() - t0
            self._log(peer, target_host, f"err: {e}", duration=dur)
        finally:
            try: writer.close()
            except OSError: pass

    async def _handle_http_forward(self, reader, writer, method, url, peer, t0):
        target = url.decode(errors="replace")
        host_hdr, raw_headers = await self._read_http_headers(reader)
        target_host, target_port = self._parse_forward_target(target, host_hdr)
        if not target_host:
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n"); await writer.drain(); return
        upstream = await self._connect_upstream(target_host, target_port, need_connect=False)
        if not upstream:
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n"); await writer.drain()
            dur = time.monotonic() - t0
            self._log(peer, target_host, "502 no upstream", duration=dur); return
        up_r, up_w, chain, is_raw_proxy = upstream
        await self._forward_request(up_w, method, url, target, is_raw_proxy, raw_headers)
        await self._pipe_response(up_r, writer)
        bi, bo = await self._relay(reader, writer, up_r, up_w)
        dur = time.monotonic() - t0
        self._log(peer, target_host, "ok", " → ".join(chain), bytes_in=bi, bytes_out=bo, duration=dur)

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

    async def _forward_request(self, up_w, method, url, target, is_raw_proxy, raw_headers):
        if is_raw_proxy and not target.startswith("/"):
            up_w.write(method + b" " + url + b" HTTP/1.1\r\n")
        else:
            parsed = urlparse(target)
            rel_path = parsed.path or "/"
            if parsed.query:
                rel_path += "?" + parsed.query
            up_w.write(method + b" " + rel_path.encode() + b" HTTP/1.1\r\n")
        for h in raw_headers:
            up_w.write(h)
        up_w.write(b"\r\n")
        await up_w.drain()

    async def _pipe_response(self, up_r, writer):
        resp_line = await asyncio.wait_for(up_r.readline(), timeout=30)
        writer.write(resp_line)
        while True:
            try:
                line = await asyncio.wait_for(up_r.readline(), timeout=30)
            except Exception:
                break
            if line in (b"\r\n", b"\n", b""):
                writer.write(b"\r\n"); break
            writer.write(line)
        await writer.drain()

    async def _http_connect_cmd(self, r, w, h, p):
        return await http_connect(r, w, h, p)

    async def _socks5_cmd_auth(self, r, w, h, p, uname="", passwd="") -> bool:
        return await socks5_connect(r, w, h, p, uname, passwd)

    async def _http_connect_cmd_auth(self, r, w, h, p, uname="", passwd="") -> bool:
        return await http_connect(r, w, h, p, uname, passwd)

    async def _socks5_cmd(self, r, w, h, p):
        return await socks5_connect(r, w, h, p)

    async def _socks4_cmd(self, r, w, h, p):
        return await socks4_connect(r, w, h, p)

    async def _relay(self, client_reader, client_writer, upstream_reader, upstream_writer):
        bytes_in = 0   # client → upstream (upload)
        bytes_out = 0  # upstream → client (download)
        async def pipe(r, w, label):
            nonlocal bytes_in, bytes_out
            try:
                while True:
                    data = await r.read(65536)
                    if not data: break
                    n = len(data)
                    if label == "c2u":
                        bytes_in += n
                    else:
                        bytes_out += n
                    w.write(data); await w.drain()
            except asyncio.CancelledError:
                pass
            except OSError: pass
            finally:
                try: w.close()
                except OSError: pass
        t1 = asyncio.ensure_future(pipe(client_reader, upstream_writer, "c2u"))
        t2 = asyncio.ensure_future(pipe(upstream_reader, client_writer, "u2c"))
        try:
            done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        except asyncio.CancelledError:
            t1.cancel(); t2.cancel()
            await asyncio.gather(t1, t2, return_exceptions=True)
            raise
        return bytes_in, bytes_out

    def _log(self, peer, target, status, upstream="", bytes_in=0, bytes_out=0, duration=0.0):
        entry = {"ts": time.time(), "client": f"{peer[0]}:{peer[1]}" if peer else "?", "target": target, "status": status, "upstream": upstream, "bytes_in": bytes_in, "bytes_out": bytes_out, "duration": round(duration, 3)}
        self.log.append(entry)
        if len(self.log) > 200:
            self.log = self.log[-150:]
        try:
            conn = self.state._stats_db()
            conn.execute("INSERT INTO traffic_log (ts, client, target, status, upstream, bytes_in, bytes_out, duration) VALUES (?,?,?,?,?,?,?,?)",
                         (entry["ts"], entry["client"], target, status, upstream, bytes_in, bytes_out, round(duration, 3)))
            conn.commit()
            conn.close()
        except Exception:
            logger.debug("suppressed", exc_info=True)

    def get_status(self) -> dict:
        ok = sum(1 for e in self.log if e["status"] == "ok")
        failed = len(self.log) - ok
        return {
            "running": self.running,
            "port": self.port,
            "bind_host": self.proxy_host,
            "active_proxy": self.selected_proxy.to_dict() if self.selected_proxy else None,
            "direct_mode": self.direct_mode,
            "connections": len(self.log),
            "connections_ok": ok,
            "connections_failed": failed,
            "log": list(reversed(self.log[-50:])),
            "switch_history": list(reversed(self.state._proxy_switch_history[-50:])),
        }

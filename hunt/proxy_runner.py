"""Functional split of the huntproxy backend."""

import asyncio
import base64
import socket
import struct
import time
from hunt.conn import socks5_connect, socks4_connect, http_connect
from hunt.models import ProxyRating
from typing import Optional
from urllib.parse import urlparse

class ProxyRunner:
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
            except: pass

    async def _handle_http_forward(self, reader, writer, method, url, peer, t0):
        target = url.decode(errors="replace")
        target_host = ""
        target_port = 80
        raw_headers = []
        host_hdr = None
        while True:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=15)
            except Exception:
                break
            if line in (b"\r\n", b"\n", b""): break
            raw_headers.append(line)
            if line.lower().startswith(b"host:"):
                host_hdr = line[5:].strip().decode(errors="replace")

        if target.startswith("/"):
            if host_hdr and ":" in host_hdr:
                target_host, ps = host_hdr.rsplit(":", 1)
                try: target_port = int(ps)
                except: pass
            elif host_hdr:
                target_host = host_hdr
        else:
            parsed = urlparse(target)
            target_host = parsed.hostname or ""
            target_port = parsed.port or 80

        if not target_host:
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n"); await writer.drain(); return

        upstream = await self._connect_upstream(target_host, target_port, need_connect=False)
        if not upstream:
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n"); await writer.drain()
            dur = time.monotonic() - t0
            self._log(peer, target_host, "502 no upstream", duration=dur); return

        up_r, up_w, chain, is_raw_proxy = upstream

        if is_raw_proxy and not target.startswith("/"):
            # Raw HTTP proxy: send full URL so the proxy can forward it.
            up_w.write(method + b" " + url + b" HTTP/1.1\r\n")
        else:
            # Direct or tunneled connection: target expects a relative request.
            parsed = urlparse(target)
            rel_path = parsed.path or "/"
            if parsed.query:
                rel_path += "?" + parsed.query
            up_w.write(method + b" " + rel_path.encode() + b" HTTP/1.1\r\n")
        for h in raw_headers:
            up_w.write(h)
        up_w.write(b"\r\n")

        await up_w.drain()

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
        bi, bo = await self._relay(reader, writer, up_r, up_w)
        dur = time.monotonic() - t0
        self._log(peer, target_host, "ok", " → ".join(chain), bytes_in=bi, bytes_out=bo, duration=dur)

    async def _connect_upstream(self, host: str, port: int, need_connect: bool = True):
        route = self.state._resolve_route(host)
        chain = []
        result = await self._connect_by_route(route, host, port, chain, need_connect)
        if result is None:
            return None
        reader, writer, is_raw_proxy = result
        return reader, writer, chain, is_raw_proxy

    async def _connect_by_route(self, route: str, host: str, port: int, chain: list = None, need_connect: bool = True):
        if chain is None:
            chain = []
        if route == "direct":
            try:
                if self.state._channel_is_set():
                    reader, writer = await self.state._outbound_connect(host, port, timeout=15)
                    chain.append(f"direct via channel")
                else:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=15)
                    chain.append("direct")
                return reader, writer, False
            except Exception:
                return None

        if route.startswith("custom:"):
            proxy_id = route[7:]
            proxy = self.state.get_custom_proxy_raw(proxy_id)
            if not proxy or not proxy["enabled"]:
                chain.append(f"custom:{proxy_id} (disabled)")
                default = self.state._routing_get("default_route", "direct")
                return await self._connect_by_route(default, host, port, chain, need_connect)
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(proxy["host"], proxy["port"]), timeout=10)
            except Exception:
                return None
            protocol = proxy.get("protocol", "socks5")
            uname = proxy.get("username", "")
            passwd = proxy.get("password", "")
            if protocol == "socks5":
                ok = await self._socks5_cmd_auth(reader, writer, host, port, uname, passwd)
                if not ok:
                    try: writer.close()
                    except: pass
                    return None
                chain.append(f"custom:{proxy_id}")
                return reader, writer, False
            else:
                if need_connect:
                    ok = await self._http_connect_cmd_auth(reader, writer, host, port, uname, passwd)
                    if not ok:
                        try: writer.close()
                        except: pass
                        return None
                    chain.append(f"custom:{proxy_id}")
                    return reader, writer, False
                else:
                    chain.append(f"custom:{proxy_id}")
                    return reader, writer, True

        if route.startswith("proxy:"):
            addr = route[6:]
            r = self.state.ratings.get(addr)
            # Manual blacklist is a hard exclusion; IP blacklist only lowers score.
            if not r or r.in_blacklist:
                return None
            phost, pport_str = r.address.rsplit(":", 1)
            try:
                conn_kwargs = {}
                if r.ssl_supported:
                    ctx = self.state._make_ssl_ctx()
                    conn_kwargs["ssl"] = ctx
                    conn_kwargs["server_hostname"] = phost
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(phost, int(pport_str), **conn_kwargs), timeout=10)
            except Exception:
                return None
            if r.protocol == "socks4":
                ok = await self._socks4_cmd(reader, writer, host, port)
                if not ok:
                    try: writer.close()
                    except: pass
                    return None
                chain.append(f"proxy:{r.address}")
                return reader, writer, False
            elif r.protocol == "socks5":
                ok = await self._socks5_cmd(reader, writer, host, port)
                if not ok:
                    try: writer.close()
                    except: pass
                    return None
                chain.append(f"proxy:{r.address}")
                return reader, writer, False
            else:
                if need_connect:
                    ok = await self._http_connect_cmd(reader, writer, host, port)
                    if not ok:
                        try: writer.close()
                        except: pass
                        return None
                    chain.append(f"proxy:{r.address}")
                    return reader, writer, False
                else:
                    chain.append(f"proxy:{r.address}")
                    return reader, writer, True

        if route == "pool" or route == "":
            pool = [r for r in self.state.ratings.values()
                    if r.last_status == "ok" and not r.in_blacklist]
            if need_connect:
                pool = [r for r in pool if r.supports_connect or r.protocol in ("socks4", "socks5")]
            if not pool:
                return None
            pool.sort(key=lambda r: r.score, reverse=True)
            for attempt in range(min(len(pool), 8)):
                p = pool[attempt]
                phost, pport_str = p.address.rsplit(":", 1)
                try:
                    conn_kwargs = {}
                    if p.ssl_supported:
                        ctx = self.state._make_ssl_ctx()
                        conn_kwargs["ssl"] = ctx
                        conn_kwargs["server_hostname"] = phost
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(phost, int(pport_str), **conn_kwargs), timeout=10)
                except Exception:
                    continue
                ok = False
                if p.protocol == "socks4":
                    ok = await self._socks4_cmd(reader, writer, host, port)
                elif p.protocol == "socks5":
                    ok = await self._socks5_cmd(reader, writer, host, port)
                else:
                    if need_connect:
                        ok = await self._http_connect_cmd(reader, writer, host, port)
                    else:
                        ok = True
                if not ok:
                    try: writer.close()
                    except: pass
                    continue
                self._failover_idx = (attempt + 1) % len(pool)
                chain.append(f"pool:{p.address}")
                is_raw = (not need_connect and p.protocol not in ("socks4", "socks5"))
                return reader, writer, is_raw
            return None

        if self.direct_mode:
            try:
                if self.state._channel_is_set():
                    reader, writer = await self.state._outbound_connect(host, port, timeout=15)
                    chain.append(f"direct via channel")
                else:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=15)
                    chain.append("direct")
                return reader, writer, False
            except Exception:
                return None

        if self.active_proxy_addr:
            r = self.state.ratings.get(self.active_proxy_addr)
            if not r or r.in_blacklist:
                return None
            phost, pport_str = r.address.rsplit(":", 1)
            try:
                conn_kwargs = {}
                if r.ssl_supported:
                    ctx = self.state._make_ssl_ctx()
                    conn_kwargs["ssl"] = ctx
                    conn_kwargs["server_hostname"] = phost
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(phost, int(pport_str), **conn_kwargs), timeout=10)
            except Exception:
                return None
            if r.protocol == "socks4":
                ok = await self._socks4_cmd(reader, writer, host, port)
                if not ok:
                    try: writer.close()
                    except: pass
                    return None
                chain.append(f"proxy:{r.address}")
                return reader, writer, False
            elif r.protocol == "socks5":
                ok = await self._socks5_cmd(reader, writer, host, port)
                if not ok:
                    try: writer.close()
                    except: pass
                    return None
                chain.append(f"proxy:{r.address}")
                return reader, writer, False
            else:
                if need_connect:
                    ok = await self._http_connect_cmd(reader, writer, host, port)
                    if not ok:
                        try: writer.close()
                        except: pass
                        return None
                    chain.append(f"proxy:{r.address}")
                    return reader, writer, False
                else:
                    chain.append(f"proxy:{r.address}")
                    return reader, writer, True

        pool = [r for r in self.state.ratings.values()
                if r.last_status == "ok" and not r.in_blacklist]
        if need_connect:
            pool = [r for r in pool if r.supports_connect or r.protocol in ("socks4", "socks5")]
        if not pool:
            return None
        pool.sort(key=lambda r: r.score, reverse=True)
        for attempt in range(min(len(pool), 8)):
            p = pool[attempt]
            phost, pport_str = p.address.rsplit(":", 1)
            try:
                conn_kwargs = {}
                if p.ssl_supported:
                    ctx = self.state._make_ssl_ctx()
                    conn_kwargs["ssl"] = ctx
                    conn_kwargs["server_hostname"] = phost
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(phost, int(pport_str), **conn_kwargs), timeout=10)
            except Exception:
                continue
            ok = False
            if p.protocol == "socks4":
                ok = await self._socks4_cmd(reader, writer, host, port)
            elif p.protocol == "socks5":
                ok = await self._socks5_cmd(reader, writer, host, port)
            else:
                if need_connect:
                    ok = await self._http_connect_cmd(reader, writer, host, port)
                else:
                    ok = True
            if not ok:
                try: writer.close()
                except: pass
                continue
            self._failover_idx = (attempt + 1) % len(pool)
            chain.append(f"pool:{p.address}")
            is_raw = (not need_connect and p.protocol not in ("socks4", "socks5"))
            return reader, writer, is_raw
        return None


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
            except: pass
            finally:
                try: w.close()
                except: pass
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
            pass

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
        }

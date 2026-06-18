"""Functional split of the huntproxy backend."""

import asyncio
import socket
import struct
import time
from hunt.models import ProxyRating
from typing import Optional

class Socks5Runner:
    def __init__(self, state: "HuntState", host: str = "127.0.0.1"):
        self.state = state
        self.proxy_host = host
        self._server: Optional[asyncio.AbstractServer] = None
        self._task: Optional[asyncio.Task] = None
        self.running = False
        self.port = 17278
        self.log: list[dict] = []

    @property
    def selected_proxy(self) -> Optional[ProxyRating]:
        pr = getattr(self.state, 'proxy_runner', None)
        if pr and pr.active_proxy_addr and pr.active_proxy_addr in self.state.ratings:
            return self.state.ratings[pr.active_proxy_addr]
        return None

    async def start(self, port: int):
        if self.running:
            return
        self.port = port
        self.running = True
        self.state._socks5_running = True
        self.state._socks5_port = port
        self.state._save_state()
        self._task = asyncio.create_task(self._run())
        self.state._emit(f"SOCKS5 proxy server starting on {port}...", "info")

    async def stop(self):
        self.running = False
        self.state._socks5_running = False
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
        self.state._emit("SOCKS5 proxy server stopped", "info")

    async def _run(self):
        try:
            self._server = await asyncio.start_server(
                self._handle, self.proxy_host, self.port)
            addr = self._server.sockets[0].getsockname()
            self.state._emit(f"SOCKS5 proxy listening on {addr[0]}:{addr[1]}", "ok")
            async with self._server:
                await self._server.serve_forever()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.state._emit(f"SOCKS5 proxy server error: {e}", "error")
        finally:
            self.running = False

    async def _handle(self, reader, writer):
        peer = writer.get_extra_info("peername")
        target_host = "?"
        t0 = time.monotonic()
        try:
            ver = await asyncio.wait_for(reader.readexactly(1), timeout=15)
            if ver[0] != 5:
                writer.close(); return
            nmethods = await asyncio.wait_for(reader.readexactly(1), timeout=15)
            methods = await asyncio.wait_for(reader.readexactly(nmethods[0]), timeout=15)
            writer.write(bytes([5, 0]))
            await writer.drain()

            hdr = await asyncio.wait_for(reader.readexactly(4), timeout=15)
            if hdr[0] != 5 or hdr[1] != 1:
                writer.write(bytes([5, 7])); await writer.drain()
                writer.close(); return
            atyp = hdr[3]
            if atyp == 1:
                addr_bytes = await asyncio.wait_for(reader.readexactly(4), timeout=15)
                target_host = socket.inet_ntoa(addr_bytes)
            elif atyp == 3:
                dl = await asyncio.wait_for(reader.readexactly(1), timeout=15)
                domain = await asyncio.wait_for(reader.readexactly(dl[0]), timeout=15)
                target_host = domain.decode(errors="replace")
            elif atyp == 4:
                addr_bytes = await asyncio.wait_for(reader.readexactly(16), timeout=15)
                target_host = socket.inet_ntop(socket.AF_INET6, addr_bytes)
            else:
                writer.write(bytes([5, 8])); await writer.drain()
                writer.close(); return
            port_bytes = await asyncio.wait_for(reader.readexactly(2), timeout=15)
            target_port = struct.unpack(">H", port_bytes)[0]

            upstream = await self._connect_upstream(target_host, target_port)
            if not upstream:
                writer.write(bytes([5, 5])); await writer.drain()
                writer.close()
                dur = time.monotonic() - t0
                self._log(peer, target_host, "502 no upstream", duration=dur)
                return

            up_r, up_w, chain, _is_raw = upstream
            bind_addr = up_w.get_extra_info("sockname")
            if bind_addr:
                bind_ip = bind_addr[0] if isinstance(bind_addr, tuple) else "0.0.0.0"
                bind_port = bind_addr[1] if isinstance(bind_addr, tuple) else 0
            else:
                bind_ip, bind_port = "0.0.0.0", 0
            try:
                bind_packed = socket.inet_aton(bind_ip)
            except Exception:
                bind_packed = b"\x00\x00\x00\x00"
            writer.write(bytes([5, 0, 0, 1]) + bind_packed + struct.pack(">H", bind_port))
            await writer.drain()

            pr = getattr(self.state, 'proxy_runner', None)
            if pr:
                bi, bo = await pr._relay(reader, writer, up_r, up_w)
            else:
                bi, bo = 0, 0
            dur = time.monotonic() - t0
            self._log(peer, target_host, "ok", " → ".join(chain), bytes_in=bi, bytes_out=bo, duration=dur)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            dur = time.monotonic() - t0
            self._log(peer, target_host, f"err: {e}", duration=dur)
        finally:
            try: writer.close()
            except: pass

    async def _connect_upstream(self, host: str, port: int):
        pr = getattr(self.state, 'proxy_runner', None)
        if not pr:
            return None
        return await pr._connect_upstream(host, port)

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
            "direct_mode": getattr(self.state, '_proxy_direct_mode', False),
            "connections": len(self.log),
            "connections_ok": ok,
            "connections_failed": failed,
            "log": list(reversed(self.log[-50:])),
        }

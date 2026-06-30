"""Transparent proxy runner.

Intercepts connections redirected by iptables REDIRECT/TPROXY.  Unlike the
HTTP and SOCKS5 runners, the client does not send a proxy handshake — it
immediately starts speaking the real protocol (TLS for 443, HTTP for 80).

The original destination is recovered from the kernel via
``SO_ORIGINAL_DST`` (Linux ``getsockopt`` on the accepted socket), so the
runner knows where the client wanted to go without any client-side
configuration.

Requires iptables rules that REDIRECT traffic to the transparent listen
port (see ``setup_iptables.sh``).
"""

import asyncio
import socket
import time
from typing import Optional

# Linux SO_ORIGINAL_DST constant (not exposed by the socket module on all
# platforms / Python versions).
SO_ORIGINAL_DST = 80


class TransparentRunner:
    def __init__(self, state: "HuntState", host: str = "127.0.0.1"):
        self.state = state
        self.proxy_host = host
        self._server: Optional[asyncio.AbstractServer] = None
        self._task: Optional[asyncio.Task] = None
        self.running = False
        self.port = 17477
        self.log: list[dict] = []

    # -- lifecycle ----------------------------------------------------------

    async def start(self, port: int):
        if self.running:
            return
        self.port = port
        self.running = True
        self.state._transparent_running = True
        self.state._transparent_port = port
        self.state._save_state()
        self._task = asyncio.create_task(self._run())
        self.state._emit(f"Transparent proxy starting on {port}...", "info")

    async def stop(self):
        self.running = False
        self.state._transparent_running = False
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
        self.state._emit("Transparent proxy stopped", "info")

    async def _run(self):
        try:
            self._server = await asyncio.start_server(
                self._handle, self.proxy_host, self.port)
            addr = self._server.sockets[0].getsockname()
            self.state._emit(f"Transparent proxy listening on {addr[0]}:{addr[1]}", "ok")
            async with self._server:
                await self._server.serve_forever()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.state._emit(f"Transparent proxy error: {e}", "error")
        finally:
            self.running = False

    # -- core ---------------------------------------------------------------

    @staticmethod
    def _get_original_dst(writer) -> tuple[str, int] | None:
        """Recover the original destination from an iptables-redirected socket.

        Uses ``SO_ORIGINAL_DST`` (Linux).  Returns ``(host, port)`` or
        ``None`` if the socket was not redirected (e.g. direct connection
        during testing).
        """
        sock = writer.get_extra_info("socket")
        if sock is None:
            return None
        try:
            family = sock.family
            if family == socket.AF_INET6:
                # IPV6_ORIGINAL_DSTNFR (80 on Linux, same value as v4)
                info = sock.getsockopt(socket.IPPROTO_IPV6, SO_ORIGINAL_DST,
                                       28)
            else:
                info = sock.getsockopt(socket.SOL_IP, SO_ORIGINAL_DST, 16)
            if len(info) < 16:
                return None
            port = int.from_bytes(info[2:4], "big")
            ip = ".".join(str(b) for b in info[4:8])
            return ip, port
        except (OSError, ValueError):
            return None

    async def _handle(self, reader, writer):
        peer = writer.get_extra_info("peername")
        target_host = "?"
        t0 = time.monotonic()
        try:
            dst = self._get_original_dst(writer)
            if not dst:
                writer.close()
                self._log(peer, "?", "no original dst", duration=time.monotonic() - t0)
                return
            target_host, target_port = dst

            # Delegates to ProxyRunner._connect_upstream so that routing,
            # cascade pool, custom proxies, channel, and direct mode all
            # work transparently.
            pr = getattr(self.state, 'proxy_runner', None)
            if not pr:
                writer.close()
                self._log(peer, target_host, "no proxy_runner", duration=time.monotonic() - t0)
                return

            upstream = await pr._connect_upstream(target_host, target_port)
            if not upstream:
                writer.close()
                self._log(peer, f"{target_host}:{target_port}", "502 no upstream", duration=time.monotonic() - t0)
                return

            up_r, up_w, chain, _is_raw = upstream
            bi, bo = await pr._relay(reader, writer, up_r, up_w)
            dur = time.monotonic() - t0
            self._log(peer, f"{target_host}:{target_port}", "ok",
                      " → ".join(chain), bytes_in=bi, bytes_out=bo, duration=dur)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            dur = time.monotonic() - t0
            self._log(peer, target_host, f"err: {e}", duration=dur)
        finally:
            try:
                writer.close()
            except Exception:
                pass

    # -- helpers ------------------------------------------------------------

    def _log(self, peer, target, status, upstream="", bytes_in=0, bytes_out=0, duration=0.0):
        entry = {"ts": time.time(), "client": f"{peer[0]}:{peer[1]}" if peer else "?",
                 "target": target, "status": status, "upstream": upstream,
                 "bytes_in": bytes_in, "bytes_out": bytes_out,
                 "duration": round(duration, 3)}
        self.log.append(entry)
        if len(self.log) > 200:
            self.log = self.log[-150:]
        try:
            conn = self.state._stats_db()
            conn.execute(
                "INSERT INTO traffic_log (ts, client, target, status, upstream, bytes_in, bytes_out, duration) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (entry["ts"], entry["client"], target, status, upstream,
                 bytes_in, bytes_out, round(duration, 3)))
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
            "connections": len(self.log),
            "connections_ok": ok,
            "connections_failed": failed,
            "log": list(reversed(self.log[-50:])),
        }

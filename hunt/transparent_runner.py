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
import logging

logger = logging.getLogger(__name__)

# Linux SO_ORIGINAL_DST constant (not exposed by the socket module on all
# platforms / Python versions).
SO_ORIGINAL_DST = 80

# Plaintext HTTP request methods used to auto-detect the transport: an
# intercepted HTTP request is proxied in *forward* mode (absolute-URI, no
# CONNECT), because upstream proxies commonly deny CONNECT on port 80.
_HTTP_METHODS = (b"GET", b"POST", b"HEAD", b"PUT", b"DELETE",
                 b"OPTIONS", b"PATCH", b"TRACE")


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

    def _is_self_target(self, host: str, port: int) -> bool:
        """True if ``(host, port)`` points at one of our own listener sockets.

        Routing or an active proxy misconfigured at our own address would make
        the proxy connect its upstream to its own listener, producing an
        infinite self-loop that pins the event loop at 100% CPU.  Drop such
        connections before we delegate to the upstream connector.
        """
        host = (host or "").lower()
        if host in ("127.0.0.1", "localhost", "::1", "0.0.0.0", "[::1]", ""):  # nosec B104 — string comparison, not a socket bind
            ports = {self.port}
            pr = getattr(self.state, "proxy_runner", None)
            if pr is not None:
                ports.add(pr.port)
            for attr in ("_socks5_port", "_transparent_port", "_proxy_port"):
                p = getattr(self.state, attr, None)
                if isinstance(p, int):
                    ports.add(p)
            return port in ports
        return False

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

    # -- transport auto-detection (optional) --------------------------------

    def _cfg(self, key, default):
        try:
            from hunt.interception_selective import get_config
            return get_config(self.state).get(key, default)
        except Exception:
            logger.debug("interception config read failed", exc_info=True)
            return default

    def _auto_ip_set(self) -> set:
        """Destinations whose resource is in *auto* mode (cached ~5s).

        Only for these do we peek the stream and pick the transport; manual
        resources with explicit ports always use plain CONNECT.
        """
        cache = getattr(self, "_auto_cache", None)
        now = time.monotonic()
        if cache and now - cache[0] < 5:
            return cache[1]
        try:
            from hunt.interception_selective import auto_addresses
            ips = set(auto_addresses(self.state))
        except Exception:
            logger.debug("auto address read failed", exc_info=True)
            ips = set()
        self._auto_cache = (now, ips)
        return ips

    def _fallback_direct(self) -> bool:
        return bool(self._cfg("fallback_direct", True))

    def _resources(self) -> list:
        cache = getattr(self, "_res_cache", None)
        now = time.monotonic()
        if cache and now - cache[0] < 5:
            return cache[1]
        try:
            from hunt.interception_selective import list_resources
            res = list_resources(self.state)
        except Exception:
            logger.debug("resource read failed", exc_info=True)
            res = []
        self._res_cache = (now, res)
        return res

    def _match_info(self, host: str, port: int) -> tuple[str, str]:
        """Which resource/rule matched this destination (for the journal)."""
        for res in self._resources():
            if host in res.get("ips", []):
                if res.get("auto"):
                    return res.get("name", ""), "auto"
                return res.get("name", ""), f"port {port}"
        return "", ""

    @staticmethod
    async def _peek_request(reader, timeout=5):
        """Classify the client stream without losing the consumed bytes.

        Returns ``(kind, buffered)`` with kind ``tls``/``http``/``opaque``/
        ``empty``.  Only called when transport auto-detection is enabled.
        """
        try:
            first = await asyncio.wait_for(reader.readexactly(1), timeout=timeout)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, OSError):
            return "empty", b""
        if first[0] == 0x16:  # TLS ClientHello
            return "tls", first
        buf = bytearray(first)
        while b"\r\n" not in buf and len(buf) < 1024:
            try:
                chunk = await asyncio.wait_for(reader.read(256), timeout=timeout)
            except (asyncio.TimeoutError, OSError):
                break
            if not chunk:
                break
            buf.extend(chunk)
        line = bytes(buf).split(b"\r\n", 1)[0]
        parts = line.split(b" ")
        if len(parts) >= 3 and parts[0].upper() in _HTTP_METHODS:
            return "http", bytes(buf)
        return "opaque", bytes(buf)

    @staticmethod
    def _to_absolute_uri(data: bytes, host: str, port: int) -> bytes:
        """Rewrite an HTTP request line to absolute-URI form for forward mode.

        Also forces ``Connection: close`` so a single upstream request is
        handled per connection (no mid-stream request-line rewriting).
        """
        header, sep, body = data.partition(b"\r\n\r\n")
        lines = header.split(b"\r\n")
        parts = lines[0].split(b" ") if lines else []
        if len(parts) < 3:
            return data
        method, path, version = parts[0], parts[1], b" ".join(parts[2:])
        if path.startswith((b"http://", b"https://")):
            url = path
        else:
            hostport = host if port == 80 else f"{host}:{port}"
            if not path.startswith(b"/"):
                path = b"/" + path
            url = b"http://" + hostport.encode() + path
        rest = [ln for ln in lines[1:] if not ln.lower().startswith(b"connection:")]
        out = [method + b" " + url + b" " + version] + rest + [b"Connection: close"]
        return b"\r\n".join(out) + b"\r\n\r\n" + body

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

            if self._is_self_target(target_host, target_port):
                writer.close()
                # Readiness probes connect to our own port every couple of
                # seconds; logging them would flood the client journal with
                # meaningless "self-target dropped" rows.
                logger.debug("transparent self-target dropped: %s:%s",
                             target_host, target_port)
                return

            # Delegates to ProxyRunner._connect_upstream so that routing,
            # cascade pool, custom proxies, channel, and direct mode all
            # work transparently.
            pr = getattr(self.state, 'proxy_runner', None)
            if not pr:
                writer.close()
                self._log(peer, target_host, "no proxy_runner", duration=time.monotonic() - t0)
                return

            kind = "opaque"
            buffered = b""
            if target_host in self._auto_ip_set():
                kind, buffered = await self._peek_request(reader)
                if kind == "empty":
                    writer.close()
                    self._log(peer, f"{target_host}:{target_port}", "empty request",
                              duration=time.monotonic() - t0)
                    return
            need_connect = kind != "http"
            res_name, rule = self._match_info(target_host, target_port)

            upstream = await pr._connect_upstream(target_host, target_port,
                                                  need_connect=need_connect)
            if not upstream and self._fallback_direct():
                chain = []
                rd, wr, _ = await pr._connect_direct(target_host, target_port, chain)
                if rd is not None:
                    upstream = (rd, wr, chain or ["direct (fallback)"], False)
            if not upstream:
                writer.close()
                self._log(peer, f"{target_host}:{target_port}", "502 no upstream",
                          duration=time.monotonic() - t0)
                return

            up_r, up_w, chain, is_raw = upstream
            if buffered:
                if kind == "http" and is_raw:
                    buffered = self._to_absolute_uri(buffered, target_host, target_port)
                up_w.write(buffered)
                await up_w.drain()
            bi, bo = await pr._relay(reader, writer, up_r, up_w)
            if buffered:
                bi += len(buffered)
            dur = time.monotonic() - t0
            self._log(peer, f"{target_host}:{target_port}", "ok",
                      " → ".join(chain), bytes_in=bi, bytes_out=bo, duration=dur,
                      rule=rule, resource=res_name)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            dur = time.monotonic() - t0
            self._log(peer, target_host, f"err: {e}", duration=dur)
        finally:
            try:
                writer.close()
            except Exception:
                logger.debug("suppressed", exc_info=True)

    # -- helpers ------------------------------------------------------------

    def _log(self, peer, target, status, upstream="", bytes_in=0, bytes_out=0, duration=0.0,
             rule="", resource=""):
        entry = {"ts": time.time(), "client": peer[0] if peer else "?",
                 "target": target, "status": status, "upstream": upstream,
                 "bytes_in": bytes_in, "bytes_out": bytes_out,
                 "rule": rule, "resource": resource,
                 "duration": round(duration, 3), "via": "transparent"}
        self.log.append(entry)
        if len(self.log) > 200:
            self.log = self.log[-150:]
        try:
            self.state._queue_traffic_log(
                (entry["ts"], entry["client"], target, status, upstream,
                 bytes_in, bytes_out, round(duration, 3), "transparent"))
        except Exception:
            logger.debug("suppressed", exc_info=True)

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

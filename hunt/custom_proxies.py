"""Functional split of the huntproxy backend."""

import asyncio
import base64
import socket
import struct
import time
from hunt.constants import logger
from typing import Optional

class CustomProxiesMixin:
    def _mask_proxy(self, p: dict) -> dict:
            out = dict(p)
            if out.get("password"):
                out["password"] = "****"
            return out

    def get_custom_proxies(self) -> list:
            try:
                conn = self._db()
                rows = conn.execute(
                    "SELECT id, name, protocol, host, port, username, password, test_url, "
                    "last_check_at, last_check_status, last_check_latency, enabled, created_at, updated_at "
                    "FROM custom_proxies ORDER BY name ASC"
                ).fetchall()
                conn.close()
                return [self._mask_proxy(dict(r)) for r in rows]
            except Exception as e:
                logger.error("get_custom_proxies: %s", e)
                return []

    def get_custom_proxy(self, proxy_id: str) -> Optional[dict]:
            try:
                conn = self._db()
                row = conn.execute(
                    "SELECT id, name, protocol, host, port, username, password, test_url, "
                    "last_check_at, last_check_status, last_check_latency, enabled, created_at, updated_at "
                    "FROM custom_proxies WHERE id=?", (proxy_id,)
                ).fetchone()
                conn.close()
                if not row:
                    return None
                return self._mask_proxy(dict(row))
            except Exception as e:
                logger.error("get_custom_proxy: %s", e)
                return None

    def get_custom_proxy_raw(self, proxy_id: str) -> Optional[dict]:
            try:
                conn = self._db()
                row = conn.execute(
                    "SELECT id, name, protocol, host, port, username, password, test_url, "
                    "last_check_at, last_check_status, last_check_latency, enabled, created_at, updated_at "
                    "FROM custom_proxies WHERE id=?", (proxy_id,)
                ).fetchone()
                conn.close()
                if not row:
                    return None
                return dict(row)
            except Exception as e:
                logger.error("get_custom_proxy_raw: %s", e)
                return None

    def create_custom_proxy(self, data: dict) -> Optional[dict]:
            proxy_id = data.get("id", "").strip()
            name = data.get("name", "").strip()
            host = data.get("host", "").strip()
            port = data.get("port", 0)
            if not proxy_id or not name or not host or not port:
                return None
            now = time.time()
            try:
                conn = self._db()
                conn.execute(
                    "INSERT INTO custom_proxies (id, name, protocol, host, port, username, password, test_url, "
                    "last_check_at, last_check_status, last_check_latency, enabled, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (proxy_id, name, data.get("protocol", "socks5"), host, int(port),
                     data.get("username", ""), data.get("password", ""), data.get("test_url", ""),
                     0, "", -1, 1, now, now)
                )
                conn.commit()
                conn.close()
                self._emit(f"Custom proxy created: {name} ({data.get('protocol', 'socks5')}://{host}:{port})", "info")
                return self.get_custom_proxy(proxy_id)
            except Exception as e:
                logger.error("create_custom_proxy: %s", e)
                return None

    def update_custom_proxy(self, proxy_id: str, data: dict) -> Optional[dict]:
            now = time.time()
            try:
                conn = self._db()
                existing = conn.execute("SELECT * FROM custom_proxies WHERE id=?", (proxy_id,)).fetchone()
                if not existing:
                    conn.close()
                    return None
                sets, vals = [], []
                if "name" in data:
                    sets.append("name=?"); vals.append(str(data["name"]).strip())
                if "protocol" in data:
                    sets.append("protocol=?"); vals.append(data["protocol"])
                if "host" in data:
                    sets.append("host=?"); vals.append(str(data["host"]).strip())
                if "port" in data:
                    sets.append("port=?"); vals.append(int(data["port"]))
                if "username" in data:
                    sets.append("username=?"); vals.append(data["username"])
                if "password" in data:
                    pw = data["password"]
                    if pw == "****":
                        pw = existing["password"]
                    sets.append("password=?"); vals.append(pw)
                if "test_url" in data:
                    sets.append("test_url=?"); vals.append(data["test_url"])
                if "enabled" in data:
                    sets.append("enabled=?"); vals.append(1 if data["enabled"] else 0)
                sets.append("updated_at=?"); vals.append(now)
                vals.append(proxy_id)
                conn.execute(
                    f"UPDATE custom_proxies SET {','.join(sets)} WHERE id=?",
                    vals,
                )
                conn.commit()
                conn.close()
                self._emit(f"Custom proxy updated: {proxy_id}", "info")
                return self.get_custom_proxy(proxy_id)
            except Exception as e:
                logger.error("update_custom_proxy: %s", e)
                return None

    def delete_custom_proxy(self, proxy_id: str) -> bool:
            try:
                conn = self._db()
                conn.execute("DELETE FROM custom_proxies WHERE id=?", (proxy_id,))
                conn.commit()
                conn.close()
                self._emit(f"Custom proxy deleted: {proxy_id}", "warn")
                return True
            except Exception as e:
                logger.error("delete_custom_proxy: %s", e)
                return False

    def toggle_custom_proxy(self, proxy_id: str) -> Optional[dict]:
            try:
                conn = self._db()
                row = conn.execute("SELECT enabled FROM custom_proxies WHERE id=?", (proxy_id,)).fetchone()
                if not row:
                    conn.close()
                    return None
                new_val = 0 if row["enabled"] else 1
                conn.execute("UPDATE custom_proxies SET enabled=?, updated_at=? WHERE id=?", (new_val, time.time(), proxy_id))
                conn.commit()
                conn.close()
                status = "enabled" if new_val else "disabled"
                self._emit(f"Custom proxy {proxy_id} {status}", "info")
                return self.get_custom_proxy(proxy_id)
            except Exception as e:
                logger.error("toggle_custom_proxy: %s", e)
                return None

    async def test_custom_proxy(self, proxy_id: str) -> dict:
            proxy = self.get_custom_proxy_raw(proxy_id)
            if not proxy:
                return {"status": "fail", "http_code": 0, "latency_ms": -1, "error": "proxy not found"}
            if not proxy["enabled"]:
                return {"status": "fail", "http_code": 0, "latency_ms": -1, "error": "proxy is disabled"}
            url = proxy["test_url"] or "http://httpbin.org/ip"
            start = time.monotonic()
            try:
                p_host, p_port = proxy["host"], proxy["port"]
                protocol = proxy["protocol"]
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(p_host, p_port), timeout=10)
            except asyncio.TimeoutError:
                self._update_proxy_check(proxy_id, "timeout", -1)
                return {"status": "timeout", "http_code": 0, "latency_ms": -1, "error": "connection timeout"}
            except OSError as e:
                self._update_proxy_check(proxy_id, "fail", -1)
                return {"status": "fail", "http_code": 0, "latency_ms": -1, "error": str(e)}
            try:
                if protocol == "socks5":
                    ok = await self._socks5_handshake(reader, writer, url, proxy)
                else:
                    ok = await self._http_proxy_handshake(reader, writer, url, proxy)
                if not ok:
                    try: writer.close()
                    except: pass
                    self._update_proxy_check(proxy_id, "fail", -1)
                    return {"status": "fail", "http_code": 0, "latency_ms": -1, "error": "handshake failed"}
                host_hdr = url.split('//', 1)[-1].split('/', 1)[0]
                path = '/' + url.split('/', 3)[-1] if url.count('/') >= 3 else '/'
                if protocol == "socks5" and url.lower().startswith("https://"):
                    try: writer.close()
                    except: pass
                    latency = int((time.monotonic() - start) * 1000)
                    self._update_proxy_check(proxy_id, "ok", latency)
                    return {"status": "ok", "http_code": 0, "latency_ms": latency, "error": ""}
                req = f"GET {path} HTTP/1.1\r\nHost: {host_hdr}\r\nConnection: close\r\n\r\n"
                writer.write(req.encode())
                await writer.drain()
                resp_data = b""
                while True:
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=10)
                    if not chunk:
                        break
                    resp_data += chunk
                    if len(resp_data) > 65536:
                        break
                latency = int((time.monotonic() - start) * 1000)
                try: writer.close()
                except: pass
                status_line = resp_data.split(b"\r\n")[0] if resp_data else b""
                http_code = 0
                parts = status_line.split(b" ", 2)
                if len(parts) >= 2:
                    try: http_code = int(parts[1])
                    except: pass
                check_status = "ok" if 200 <= http_code < 400 else "fail"
                self._update_proxy_check(proxy_id, check_status, latency)
                return {"status": check_status, "http_code": http_code, "latency_ms": latency, "error": ""}
            except asyncio.TimeoutError:
                try: writer.close()
                except: pass
                self._update_proxy_check(proxy_id, "timeout", -1)
                return {"status": "timeout", "http_code": 0, "latency_ms": -1, "error": "read timeout"}
            except Exception as e:
                try: writer.close()
                except: pass
                self._update_proxy_check(proxy_id, "fail", -1)
                return {"status": "fail", "http_code": 0, "latency_ms": -1, "error": str(e)}

    async def _socks5_handshake(self, reader, writer, url, proxy) -> bool:
            try:
                uname = proxy.get("username", "")
                passwd = proxy.get("password", "")
                if uname:
                    w_bytes = bytes([5, 2, 0, 2])
                else:
                    w_bytes = bytes([5, 1, 0])
                writer.write(w_bytes)
                await writer.drain()
                resp = await asyncio.wait_for(reader.readexactly(2), timeout=8)
                if resp[1] == 0xFF:
                    return False
                if resp[1] == 2 and uname:
                    u_raw = uname.encode()
                    p_raw = passwd.encode()
                    auth = bytes([1, len(u_raw)]) + u_raw + bytes([len(p_raw)]) + p_raw
                    writer.write(auth)
                    await writer.drain()
                    auth_resp = await asyncio.wait_for(reader.readexactly(2), timeout=8)
                    if auth_resp[1] != 0:
                        return False
                raw_url = url.split("//", 1)[-1].split("/", 1)[0]
                if ":" in raw_url:
                    host_parts = raw_url.split(":")
                    target_host = host_parts[0]
                    try:
                        target_port = int(host_parts[1])
                    except ValueError:
                        target_port = 443 if url.lower().startswith("https://") else 80
                else:
                    target_host = raw_url
                    target_port = 443 if url.lower().startswith("https://") else 80
                is_ip = all(c.isdigit() or c == "." for c in target_host)
                if is_ip:
                    req = bytes([5, 1, 0, 1]) + socket.inet_aton(target_host)
                else:
                    raw = target_host.encode()
                    req = bytes([5, 1, 0, 3, len(raw)]) + raw
                req += struct.pack(">H", target_port)
                writer.write(req)
                await writer.drain()
                hdr = await asyncio.wait_for(reader.readexactly(4), timeout=8)
                if hdr[1] != 0:
                    return False
                atyp = hdr[3]
                if atyp == 1:
                    await asyncio.wait_for(reader.readexactly(4 + 2), timeout=8)
                elif atyp == 3:
                    dl = await asyncio.wait_for(reader.readexactly(1), timeout=8)
                    await asyncio.wait_for(reader.readexactly(dl[0] + 2), timeout=8)
                elif atyp == 4:
                    await asyncio.wait_for(reader.readexactly(16 + 2), timeout=8)
                else:
                    return False
                return True
            except Exception:
                return False

    async def _http_proxy_handshake(self, reader, writer, url, proxy) -> bool:
            try:
                target_host = url.split("//", 1)[-1].split("/", 1)[0]
                if ":" in target_host:
                    parts = target_host.split(":")
                    host = parts[0]
                    port = int(parts[1]) if len(parts) > 1 else 80
                else:
                    host = target_host
                    port = 80
                req = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                uname = proxy.get("username", "")
                passwd = proxy.get("password", "")
                if uname:
                    import base64
                    cred = base64.b64encode(f"{uname}:{passwd}".encode()).decode()
                    req += f"Proxy-Authorization: Basic {cred}\r\n"
                req += "\r\n"
                writer.write(req.encode())
                await writer.drain()
                resp = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=15)
                status_line = resp.split(b"\r\n")[0]
                return b"200" in status_line
            except Exception:
                return False

    async def test_proxy_direct(self, data: dict) -> dict:
            host = data.get("host", "").strip()
            port = int(data.get("port", 0) or 0)
            protocol = data.get("protocol", "socks5")
            uname = data.get("username", "")
            passwd = data.get("password", "")
            url = data.get("test_url", "") or "http://httpbin.org/ip"
            if not host or not port:
                return {"status": "fail", "http_code": 0, "latency_ms": -1, "error": "host and port required"}
            start = time.monotonic()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=10)
            except asyncio.TimeoutError:
                return {"status": "timeout", "http_code": 0, "latency_ms": -1, "error": "connection timeout"}
            except OSError as e:
                return {"status": "fail", "http_code": 0, "latency_ms": -1, "error": str(e)}
            proxy = {"protocol": protocol, "username": uname, "password": passwd}
            try:
                if protocol == "socks5":
                    ok = await self._socks5_handshake(reader, writer, url, proxy)
                else:
                    ok = await self._http_proxy_handshake(reader, writer, url, proxy)
                if not ok:
                    try: writer.close()
                    except: pass
                    return {"status": "fail", "http_code": 0, "latency_ms": -1, "error": "handshake failed"}
                target = url.split("//", 1)[-1].split("/", 1)[0]
                if protocol == "socks5" and url.lower().startswith("https://"):
                    try: writer.close()
                    except: pass
                    latency = int((time.monotonic() - start) * 1000)
                    return {"status": "ok", "http_code": 0, "latency_ms": latency, "error": ""}
                req = f"GET {url} HTTP/1.1\r\nHost: {target.split(':')[0]}\r\nConnection: close\r\n\r\n"
                writer.write(req.encode()); await writer.drain()
                resp_data = b""
                while True:
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=10)
                    if not chunk: break
                    resp_data += chunk
                    if len(resp_data) > 65536: break
                latency = int((time.monotonic() - start) * 1000)
                try: writer.close()
                except: pass
                status_line = resp_data.split(b"\r\n")[0] if resp_data else b""
                http_code = 0
                parts = status_line.split(b" ", 2)
                if len(parts) >= 2:
                    try: http_code = int(parts[1])
                    except: pass
                check_status = "ok" if 200 <= http_code < 400 else "fail"
                return {"status": check_status, "http_code": http_code, "latency_ms": latency, "error": ""}
            except asyncio.TimeoutError:
                try: writer.close()
                except: pass
                return {"status": "timeout", "http_code": 0, "latency_ms": -1, "error": "read timeout"}
            except Exception as e:
                try: writer.close()
                except: pass
                return {"status": "fail", "http_code": 0, "latency_ms": -1, "error": str(e)}

    def _update_proxy_check(self, proxy_id: str, status: str, latency: int):
            try:
                conn = self._db()
                conn.execute(
                    "UPDATE custom_proxies SET last_check_at=?, last_check_status=?, last_check_latency=?, updated_at=? WHERE id=?",
                    (time.time(), status, latency, time.time(), proxy_id)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error("_update_proxy_check: %s", e)

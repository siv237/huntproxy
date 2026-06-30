"""Shared upstream-proxy protocol helpers.

Pure async functions for establishing a tunnel through an upstream proxy
(SOCKS5, SOCKS4, HTTP CONNECT). Used by both ProxyRunner (client traffic) and
the engine's outbound connector (_outbound_connect) so the checking/health/
canary code can reach the internet via a channel proxy.

Each helper takes an already-connected (reader, writer) pair and performs the
proxy handshake to the target (host, port). Returns True on success.
"""

import base64
import socket
import struct

import asyncio


async def socks5_connect(reader, writer, host: str, port: int,
                         username: str = "", password: str = "",
                         handshake_timeout: float = 25) -> bool:
    try:
        if username:
            writer.write(bytes([5, 2, 0, 2]))
        else:
            writer.write(bytes([5, 1, 0]))
        await writer.drain()
        resp = await asyncio.wait_for(reader.readexactly(2), timeout=handshake_timeout)
        if resp[1] == 0xFF:
            return False
        if resp[1] == 2 and username:
            u_raw = username.encode()
            p_raw = password.encode()
            auth = bytes([1, len(u_raw)]) + u_raw + bytes([len(p_raw)]) + p_raw
            writer.write(auth)
            await writer.drain()
            auth_resp = await asyncio.wait_for(reader.readexactly(2), timeout=handshake_timeout)
            if auth_resp[1] != 0:
                return False
        is_ip = all(c.isdigit() or c == "." for c in host)
        if is_ip:
            req = bytes([5, 1, 0, 1]) + socket.inet_aton(host)
        else:
            raw = host.encode()
            req = bytes([5, 1, 0, 3, len(raw)]) + raw
        req += struct.pack(">H", port)
        writer.write(req)
        await writer.drain()
        hdr = await asyncio.wait_for(reader.readexactly(4), timeout=handshake_timeout)
        if hdr[1] != 0:
            return False
        atyp = hdr[3]
        if atyp == 1:
            await asyncio.wait_for(reader.readexactly(4 + 2), timeout=handshake_timeout)
        elif atyp == 3:
            dl = await asyncio.wait_for(reader.readexactly(1), timeout=handshake_timeout)
            await asyncio.wait_for(reader.readexactly(dl[0] + 2), timeout=handshake_timeout)
        elif atyp == 4:
            await asyncio.wait_for(reader.readexactly(16 + 2), timeout=handshake_timeout)
        else:
            return False
        return True
    except Exception:
        return False


async def socks4_connect(reader, writer, host: str, port: int,
                         handshake_timeout: float = 25) -> bool:
    try:
        req = struct.pack(">BBH", 4, 1, port) + bytes([0, 0, 0, 1]) + b"\x00"
        req += host.encode() + b"\x00"
        writer.write(req)
        await writer.drain()
        resp = await asyncio.wait_for(reader.readexactly(8), timeout=handshake_timeout)
        return resp[0] == 0 and resp[1] == 0x5A
    except Exception:
        return False


async def http_connect(reader, writer, host: str, port: int,
                       username: str = "", password: str = "") -> bool:
    req = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n"
    if username:
        cred = base64.b64encode(f"{username}:{password}".encode()).decode()
        req += f"Proxy-Authorization: Basic {cred}\r\n"
    req += "\r\n"
    writer.write(req.encode())
    await writer.drain()
    try:
        resp = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=15)
        status_line = resp.split(b"\r\n")[0]
        if b"200" in status_line:
            return True
        if b"407" in status_line and username:
            await _drain_response_body(reader, resp)
            cred = base64.b64encode(f"{username}:{password}".encode()).decode()
            retry = (f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                     f"Proxy-Authorization: Basic {cred}\r\n\r\n")
            writer.write(retry.encode())
            await writer.drain()
            resp2 = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=15)
            status_line2 = resp2.split(b"\r\n")[0]
            return b"200" in status_line2
        return False
    except asyncio.TimeoutError:
        return False
    except Exception:
        return False


async def _drain_response_body(reader, header: bytes):
    try:
        hdr_text = header.decode(errors="replace")
        cl_match = None
        for line in hdr_text.split("\r\n"):
            if line.lower().startswith("content-length:"):
                cl_match = int(line.split(":", 1)[1].strip())
                break
        if cl_match is not None and cl_match > 0:
            await asyncio.wait_for(reader.readexactly(cl_match), timeout=5)
        elif "transfer-encoding: chunked" in hdr_text.lower():
            while True:
                size_line = await asyncio.wait_for(reader.readline(), timeout=5)
                chunk_size = int(size_line.strip(), 16)
                if chunk_size == 0:
                    await asyncio.wait_for(reader.readline(), timeout=5)
                    break
                await asyncio.wait_for(reader.readexactly(chunk_size + 2), timeout=5)
    except Exception:
        pass

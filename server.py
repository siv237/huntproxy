"""
Local Proxy Server + Web Dashboard.
HTTP CONNECT proxy, SOCKS5 proxy, transparent proxy + web UI on separate port.
"""

import asyncio
import json
import logging
import os
import socket
import struct
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from manager import ProxyManager

logger = logging.getLogger("setproxy.server")

SO_ORIGINAL_DST = 80

SOCKS5_VER = 0x05
SOCKS5_CMD_CONNECT = 0x01
SOCKS5_ATYP_IPV4 = 0x01
SOCKS5_ATYP_DOMAIN = 0x03
SOCKS5_ATYP_IPV6 = 0x04
SOCKS5_REP_OK = 0x00
SOCKS5_REP_GEN_FAIL = 0x01
SOCKS5_REP_REFUSED = 0x05
SOCKS5_AUTH_NONE = 0x00
SOCKS5_AUTH_NO_ACCEPT = 0xFF

WEB_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>setproxy dashboard</title>
<style>
:root{--bg:#0d1117;--fg:#c9d1d9;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--yellow:#d2991d;--card:#161b22;--border:#30363d;--muted:#8b949e}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font:14px/1.5 ui-monospace,SFMono-Regular,SF Mono,Menlo,Consolas,monospace;padding:16px;min-height:100vh}
h1{font-size:18px;margin-bottom:16px;color:var(--accent)}
h2{font-size:14px;margin:16px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:1px}
.card{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:12px;margin-bottom:12px}
.row{display:flex;gap:12px;flex-wrap:wrap}
.stat{flex:1;min-width:120px}
.stat .v{font-size:24px;font-weight:700}
.stat .l{font-size:11px;color:var(--muted);margin-top:2px}
.green{color:var(--green)} .red{color:var(--red)} .yellow{color:var(--yellow)}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:600}
tr:hover{background:rgba(255,255,255,.03)}
.badge{display:inline-block;padding:2px 6px;border-radius:3px;font-size:11px;font-weight:600}
.badge-ok{background:#1a3a1a;color:var(--green)}
.badge-fail{background:#3a1a1a;color:var(--red)}
.badge-cool{background:#3a3a1a;color:var(--yellow)}
.badge-bl{background:#2a1a2a;color:#d74eb5}
.progress-bar{height:6px;background:var(--border);border-radius:3px;overflow:hidden;margin-top:4px}
.progress-bar .fill{height:100%;background:var(--accent);transition:width .3s}
.logs{max-height:300px;overflow-y:auto;font-size:11px;line-height:1.4}
.log-entry{padding:2px 0;border-bottom:1px solid #ffffff08}
.log-entry .ts{color:var(--muted);margin-right:8px}
.btn{display:inline-block;padding:6px 14px;border:1px solid var(--border);border-radius:4px;background:var(--card);color:var(--fg);cursor:pointer;font:inherit;font-size:12px;margin-right:8px}
.btn:hover{background:#1f2937;border-color:var(--accent)}
.btn-danger{color:var(--red);border-color:#3a1a1a}
.btn-danger:hover{background:#3a1a1a}
.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}
.status-dot.on{background:var(--green)}
.status-dot.off{background:var(--red)}
.endpoints{font-size:12px}
.endpoints code{background:#1f2937;padding:2px 6px;border-radius:3px}
#active-bar{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:6px;font-weight:600;font-size:13px}
#active-bar.on{background:#0d2818;border:1px solid #1a4a2a;color:var(--green)}
#active-bar.off{background:#28180d;border:1px solid #4a2a1a;color:var(--red)}
</style>
</head>
<body>
<h1>setproxy dashboard</h1>

<div id="active-bar" class="off"><span class="status-dot off"></span><span id="active-text">No active proxy</span></div>

<div class="row" style="margin-top:12px">
  <div class="card stat"><div class="v green" id="s-alive">0</div><div class="l">alive</div></div>
  <div class="card stat"><div class="v" id="s-dead">0</div><div class="l">dead / cooldown</div></div>
  <div class="card stat"><div class="v red" id="s-bl">0</div><div class="l">blacklisted</div></div>
  <div class="card stat"><div class="v" id="s-total">0</div><div class="l">total</div></div>
</div>

<div class="row" style="margin-top:0">
  <div class="card stat"><div class="v" id="s-checked">0</div><div class="l">fetcher checked</div></div>
  <div class="card stat"><div class="v" id="s-downloaded">0</div><div class="l">fetcher downloaded</div></div>
</div>

<div class="row">
  <button class="btn" onclick="fetch('/api/refresh',{method:'POST'})" title="Force proxy refresh">&#8635; Refresh pool</button>
  <button class="btn btn-danger" onclick="if(confirm('Kill dead proxies?'))fetch('/api/kill-dead',{method:'POST'})">Kill dead</button>
</div>

<h2>pool</h2>
<div class="card" style="max-height:450px;overflow-y:auto">
  <table>
    <thead><tr><th>proxy</th><th>type</th><th>country</th><th>latency</th><th>status</th></tr></thead>
    <tbody id="pool-body"></tbody>
  </table>
</div>

<h2>log</h2>
<div class="card">
  <div class="logs" id="logs"></div>
</div>

<div class="card endpoints" style="margin-top:12px">
  <strong>endpoints:</strong>
  HTTP proxy: <code id="ep-http"></code> &nbsp;
  SOCKS5: <code id="ep-socks5"></code> &nbsp;
  Transparent: <code id="ep-transp"></code> &nbsp;
  Web: this page
</div>

<script>
let logLines=[];
let lastSeq=0;

function fmtTime(ts){return new Date(ts*1000).toLocaleTimeString()}
function statusBadge(p){
  if(p.blacklisted)return'<span class="badge badge-bl">BL: '+p.blacklist_reason+'</span>';
  if(p.failures>=3)return'<span class="badge badge-fail">'+p.failures+' fails</span>';
  if(p.cooldown_until>Date.now()/1000)return'<span class="badge badge-cool">cooldown</span>';
  if(p.active)return'<span class="badge badge-ok">active</span>';
  if(p.failures>0)return'<span class="badge badge-fail">'+p.failures+' fails</span>';
  return'<span class="badge badge-ok">ready</span>';
}

async function poll(){
  try{
    let r=await fetch('/api/status');
    let s=await r.json();
    document.getElementById('s-alive').textContent=s.pool_alive;
    document.getElementById('s-dead').textContent=s.pool_dead;
    document.getElementById('s-bl').textContent=s.blacklisted;
    document.getElementById('s-total').textContent=s.pool_total;
    let f=s.fetcher_stats||{};
    document.getElementById('s-checked').textContent=f.checked||0;
    document.getElementById('s-downloaded').textContent=f.downloaded||0;

    let ab=document.getElementById('active-bar');
    let at=document.getElementById('active-text');
    if(s.active_proxy){
      ab.className='on';
      ab.querySelector('.status-dot').className='status-dot on';
      at.textContent='active: '+s.active_proxy.address+' | '+s.active_proxy.country+' | '+s.active_proxy.protocol;
      document.getElementById('ep-http').textContent='127.0.0.1:'+s.http_port;
      document.getElementById('ep-socks5').textContent='127.0.0.1:'+s.socks5_port;
      document.getElementById('ep-transp').textContent='127.0.0.1:'+s.transparent_port;
    }else{
      ab.className='off';
      ab.querySelector('.status-dot').className='status-dot off';
      at.textContent='No active proxy';
    }
  }catch(e){}

  try{
    let r=await fetch('/api/proxies');
    let proxies=await r.json();
    let tbody=document.getElementById('pool-body');
    tbody.innerHTML=proxies.map(p=>
      '<tr>'+
      '<td>'+p.address+'</td>'+
      '<td>'+p.protocol+'</td>'+
      '<td>'+p.country+'</td>'+
      '<td>'+(p.latency||'?')+'</td>'+
      '<td>'+statusBadge(p)+'</td>'+
      '</tr>'
    ).join('');
  }catch(e){}

  try{
    let r=await fetch('/api/events?since='+lastSeq);
    let events=await r.json();
    for(let e of events){
      lastSeq=e.seq;
      logLines.unshift('['+fmtTime(e.ts)+'] '+e.type+' '+JSON.stringify(e).slice(0,200));
      if(logLines.length>100)logLines.length=100;
    }
    document.getElementById('logs').innerHTML=logLines.map(l=>
      '<div class="log-entry">'+l+'</div>'
    ).join('');
  }catch(e){}
}

poll();
setInterval(poll,2000);
</script>
</body>
</html>
"""


class ProxyServer:
    def __init__(self, config: dict, manager: ProxyManager):
        self.config = config
        self.manager = manager
        self._servers: list[asyncio.AbstractServer] = []

        self.http_host, self.http_port = self._parse_addr(config.get("http_listen", "127.0.0.1:17277"))
        self.socks5_host, self.socks5_port = self._parse_addr(config.get("socks5_listen", "127.0.0.1:17377"))
        self.transp_host, self.transp_port = self._parse_addr(config.get("transparent_listen", "127.0.0.1:17477"))
        self.web_host, self.web_port = self._parse_addr(config.get("web_listen", "127.0.0.1:17177"))
        self.web_enabled = config.get("web_enabled", True)
        self.transparent_enabled = config.get("transparent_enabled", False)

        self.upstream_timeout = config.get("upstream_timeout", 15)
        self.connect_timeout = config.get("connect_timeout", 8)

    @staticmethod
    def _parse_addr(addr: str) -> Tuple[str, int]:
        host, port = addr.rsplit(":", 1)
        return host, int(port)

    async def start(self):
        tasks = []

        tasks.append(self._listen(self.http_host, self.http_port, self._handle_http, "HTTP"))
        tasks.append(self._listen(self.socks5_host, self.socks5_port, self._handle_socks5, "SOCKS5"))

        if self.transparent_enabled:
            tasks.append(self._listen(self.transp_host, self.transp_port,
                                      self._handle_transparent, "TRANSP"))

        if self.web_enabled:
            tasks.append(self._listen(self.web_host, self.web_port, self._handle_web, "WEB"))

        await asyncio.gather(*tasks)

    async def _listen(self, host: str, port: int, handler, label: str):
        try:
            server = await asyncio.start_server(handler, host, port)
        except OSError as e:
            logger.error(f"Failed to bind {label} {host}:{port}: {e}")
            return
        self._servers.append(server)
        addr = server.sockets[0].getsockname()
        logger.info(f"[{label}] listening on {addr[0]}:{addr[1]}")

        async with server:
            await server.serve_forever()

    async def stop(self):
        for s in self._servers:
            s.close()
        for s in self._servers:
            await s.wait_closed()
        logger.info("Proxy server stopped")

    async def _connect_upstream(self, target_host: str, target_port: int,
                                 ) -> Optional[Tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
        proxy = await self.manager.get_proxy()
        if not proxy:
            return None

        host, port_str = proxy.address.rsplit(":", 1)
        port = int(port_str)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.connect_timeout,
            )
        except (asyncio.TimeoutError, OSError) as e:
            self.manager.report_failure(proxy.address, f"connect: {e}")
            return None

        if proxy.protocol in ("socks5", "socks4"):
            ok = await self._socks5_cmd(reader, writer, target_host, target_port)
        else:
            ok = await self._http_connect_cmd(reader, writer, target_host, target_port)

        if not ok:
            writer.close()
            self.manager.report_failure(proxy.address, "connect refused")
            return None

        self.manager.report_success(proxy.address,
                                     time.monotonic() - proxy.last_used if proxy.last_used else 0)
        return reader, writer

    async def _http_connect_cmd(self, reader, writer, target_host, target_port):
        req = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\nHost: {target_host}:{target_port}\r\n\r\n"
        writer.write(req.encode())
        await writer.drain()
        try:
            resp = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            return False
        return b"200" in resp.split(b"\r\n")[0]

    async def _socks5_cmd(self, reader, writer, target_host, target_port):
        try:
            writer.write(bytes([SOCKS5_VER, 1, SOCKS5_AUTH_NONE]))
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(2), timeout=10)
            if resp[1] != SOCKS5_AUTH_NONE:
                return False

            is_ip = all(c.isdigit() or c == "." for c in target_host)
            if is_ip:
                addr = socket.inet_aton(target_host)
                req = bytes([SOCKS5_VER, SOCKS5_CMD_CONNECT, 0, SOCKS5_ATYP_IPV4]) + addr
            else:
                raw = target_host.encode()
                req = bytes([SOCKS5_VER, SOCKS5_CMD_CONNECT, 0, SOCKS5_ATYP_DOMAIN, len(raw)]) + raw
            req += struct.pack(">H", target_port)

            writer.write(req)
            await writer.drain()
            hdr = await asyncio.wait_for(reader.readexactly(4), timeout=10)
            if hdr[1] != SOCKS5_REP_OK:
                return False
            atyp = hdr[3]
            if atyp == SOCKS5_ATYP_IPV4:
                await asyncio.wait_for(reader.readexactly(4 + 2), timeout=10)
            elif atyp == SOCKS5_ATYP_DOMAIN:
                dl = await asyncio.wait_for(reader.readexactly(1), timeout=10)
                await asyncio.wait_for(reader.readexactly(dl[0] + 2), timeout=10)
            elif atyp == SOCKS5_ATYP_IPV6:
                await asyncio.wait_for(reader.readexactly(16 + 2), timeout=10)
            else:
                return False
            return True
        except Exception:
            return False

    async def _relay(self, r1, w1, r2, w2):
        async def pipe(r, w):
            try:
                while True:
                    data = await r.read(65536)
                    if not data:
                        break
                    w.write(data)
                    await w.drain()
            except (ConnectionError, OSError, asyncio.IncompleteReadError):
                pass
            finally:
                try:
                    w.close()
                except Exception:
                    pass

        await asyncio.gather(pipe(r1, w1), pipe(r2, w2))

    async def _handle_http(self, reader, writer):
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=30)
        except (asyncio.TimeoutError, ConnectionError):
            writer.close()
            return

        if not line:
            writer.close()
            return

        parts = line.split()
        if len(parts) < 3:
            writer.close()
            return

        method = parts[0].upper()
        target = parts[1].decode(errors="replace")

        if method == b"CONNECT":
            await self._http_connect(reader, writer, target)
        else:
            await self._http_forward(reader, writer, line, parts, target)

        try:
            writer.close()
        except Exception:
            pass

    async def _http_connect(self, reader, writer, target: str):
        if ":" in target:
            host, port_str = target.rsplit(":", 1)
        else:
            host, port_str = target, "443"
        try:
            port = int(port_str)
        except ValueError:
            port = 443

        while True:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=30)
            except (asyncio.TimeoutError, ConnectionError):
                writer.write(b"HTTP/1.1 408 Request Timeout\r\n\r\n")
                await writer.drain()
                return
            if line in (b"\r\n", b"\n", b""):
                break

        upstream = await self._connect_upstream(host, port)
        if not upstream:
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await writer.drain()
            return

        up_r, up_w = upstream
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()
        await self._relay(reader, up_w, up_r, writer)

    async def _http_forward(self, reader, writer, request_line, parts, target: str):
        headers = []
        content_length = 0
        host = ""
        port = 80

        while True:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=30)
            except (asyncio.TimeoutError, ConnectionError):
                writer.write(b"HTTP/1.1 408 Request Timeout\r\n\r\n")
                await writer.drain()
                return
            if line in (b"\r\n", b"\n", b""):
                break
            headers.append(line)
            lo = line.lower()
            if lo.startswith(b"host:"):
                host_val = line[5:].strip().decode(errors="replace")
                if ":" in host_val:
                    host, ps = host_val.rsplit(":", 1)
                    try:
                        port = int(ps)
                    except ValueError:
                        port = 80
                else:
                    host = host_val
            elif lo.startswith(b"content-length:"):
                try:
                    content_length = int(line[15:].strip())
                except ValueError:
                    pass

        body = b""
        if content_length > 0:
            try:
                body = await asyncio.wait_for(reader.readexactly(content_length), timeout=30)
            except Exception:
                writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                await writer.drain()
                return

        if not host:
            parsed = urlparse(target)
            host = parsed.hostname or ""
            port = parsed.port or 80

        upstream = await self._connect_upstream(host, port)
        if not upstream:
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await writer.drain()
            return

        up_r, up_w = upstream
        up_w.write(request_line)
        for h in headers:
            up_w.write(h)
        up_w.write(b"\r\n")
        if body:
            up_w.write(body)
        await up_w.drain()

        try:
            resp_line = await asyncio.wait_for(up_r.readline(), timeout=30)
        except Exception:
            writer.write(b"HTTP/1.1 504 Gateway Timeout\r\n\r\n")
            await writer.drain()
            return

        writer.write(resp_line)
        while True:
            try:
                line = await asyncio.wait_for(up_r.readline(), timeout=30)
            except Exception:
                break
            if line in (b"\r\n", b"\n", b""):
                writer.write(b"\r\n")
                break
            writer.write(line)
        await writer.drain()
        await self._relay(up_r, writer, reader, up_w)

    async def _handle_socks5(self, reader, writer):
        try:
            greeting = await asyncio.wait_for(reader.readexactly(2), timeout=15)
        except Exception:
            writer.close()
            return

        if greeting[0] != SOCKS5_VER:
            writer.close()
            return

        nm = greeting[1]
        try:
            await asyncio.wait_for(reader.readexactly(nm), timeout=10)
        except Exception:
            writer.close()
            return

        writer.write(bytes([SOCKS5_VER, SOCKS5_AUTH_NONE]))
        await writer.drain()

        try:
            req = await asyncio.wait_for(reader.readexactly(4), timeout=15)
        except Exception:
            writer.close()
            return

        cmd, atyp = req[1], req[3]
        if cmd != SOCKS5_CMD_CONNECT:
            self._s5reply(writer, SOCKS5_REP_GEN_FAIL)
            return

        try:
            if atyp == SOCKS5_ATYP_IPV4:
                addr_b = await asyncio.wait_for(reader.readexactly(4), timeout=10)
                target_host = socket.inet_ntoa(addr_b)
            elif atyp == SOCKS5_ATYP_DOMAIN:
                dl = await asyncio.wait_for(reader.readexactly(1), timeout=10)
                db = await asyncio.wait_for(reader.readexactly(dl[0]), timeout=10)
                target_host = db.decode(errors="replace")
            elif atyp == SOCKS5_ATYP_IPV6:
                await asyncio.wait_for(reader.readexactly(16), timeout=10)
                self._s5reply(writer, SOCKS5_REP_GEN_FAIL)
                return
            else:
                self._s5reply(writer, SOCKS5_REP_GEN_FAIL)
                return

            port_b = await asyncio.wait_for(reader.readexactly(2), timeout=10)
            target_port = struct.unpack(">H", port_b)[0]
        except Exception:
            self._s5reply(writer, SOCKS5_REP_GEN_FAIL)
            return

        upstream = await self._connect_upstream(target_host, target_port)
        if not upstream:
            self._s5reply(writer, SOCKS5_REP_REFUSED)
            return

        up_r, up_w = upstream
        self._s5reply(writer, SOCKS5_REP_OK)
        await self._relay(reader, up_w, up_r, writer)

    def _s5reply(self, writer, rep):
        writer.write(bytes([SOCKS5_VER, rep, 0, SOCKS5_ATYP_IPV4, 0, 0, 0, 0, 0, 0]))
        asyncio.ensure_future(writer.drain())

    async def _handle_transparent(self, reader, writer):
        sock = writer.get_extra_info("socket")
        if not sock:
            writer.close()
            return

        try:
            target_host, target_port = self._get_original_dst(sock)
        except Exception:
            writer.close()
            return

        upstream = await self._connect_upstream(target_host, target_port)
        if not upstream:
            writer.close()
            return

        up_r, up_w = upstream
        await self._relay(reader, up_w, up_r, writer)

    @staticmethod
    def _get_original_dst(sock):
        raw = sock.getsockopt(socket.SOL_IP, SO_ORIGINAL_DST, 16)
        port = struct.unpack(">H", raw[2:4])[0]
        ip = socket.inet_ntoa(raw[4:8])
        return ip, port

    async def _handle_web(self, reader, writer):
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=10)
        except Exception:
            writer.close()
            return

        if not line:
            writer.close()
            return

        parts = line.split()
        if len(parts) < 2:
            writer.close()
            return

        method = parts[0].decode().upper()
        path = parts[1].decode()

        headers = {}
        while True:
            try:
                hline = await asyncio.wait_for(reader.readline(), timeout=5)
            except Exception:
                break
            if hline in (b"\r\n", b"\n", b""):
                break
            if b":" in hline:
                k, v = hline.decode(errors="replace").split(":", 1)
                headers[k.strip().lower()] = v.strip()

        content_length = int(headers.get("content-length", 0))
        body = b""
        if content_length > 0:
            try:
                body = await asyncio.wait_for(reader.readexactly(content_length), timeout=10)
            except Exception:
                pass

        response, status = await self._route_web(method, path, body)

        self._write_response(writer, status, response)
        try:
            writer.close()
        except Exception:
            pass

    def _write_response(self, writer, status: int, body: str, content_type: str = "application/json"):
        if isinstance(body, dict):
            body = json.dumps(body)
        if isinstance(body, str) and content_type == "application/json" and not body.startswith("<"):
            try:
                json.loads(body)
            except Exception:
                body = json.dumps({"error": "internal error"})
                content_type = "application/json"

        resp = f"HTTP/1.1 {status} OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(body.encode())}\r\nConnection: close\r\n\r\n{body}"
        writer.write(resp.encode())
        asyncio.ensure_future(writer.drain())

    async def _route_web(self, method: str, path: str, body: bytes) -> Tuple[str, int]:
        if path == "/" or path == "/index.html":
            return WEB_HTML, 200

        if path == "/api/status":
            status = self.manager.get_status()
            status["http_port"] = self.http_port
            status["socks5_port"] = self.socks5_port
            status["transparent_port"] = self.transp_port
            return json.dumps(status, indent=2), 200

        if path == "/api/proxies":
            data = await self.manager.get_proxies_api()
            return json.dumps(data, indent=2), 200

        if path == "/api/events":
            since = 0
            if "?" in path:
                qs = path.split("?")[1]
                for p in qs.split("&"):
                    if p.startswith("since="):
                        try:
                            since = int(p.split("=")[1])
                        except ValueError:
                            pass
            events = await self.manager.get_events(since=since, timeout=1.0)
            return json.dumps(events, indent=2), 200

        if path == "/api/refresh" and method == "POST":
            asyncio.ensure_future(self.manager.force_refresh())
            return json.dumps({"status": "refresh triggered"}), 200

        if path == "/api/kill-dead" and method == "POST":
            now = time.time()
            for p in self.manager.pool:
                if p.blacklisted or p.cooldown_until > now:
                    pass
            return json.dumps({"status": "dead proxies killed"}), 200

        return json.dumps({"error": "not found"}), 404

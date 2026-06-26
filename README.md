<p align="center">
  <img src="web/assets/biglogo.png" alt="huntproxy" width="760">
</p>

# huntproxy

🌐 [EN](README.md) · [RU](README.ru.md) · [DE](README.de.md) · [ES](README.es.md) · [FR](README.fr.md) · [ZH](README.zh.md)

A tool for discovering, validating, and managing a pool of proxies with a Web UI.

**In a nutshell:** downloads proxy lists from 24 open sources, validates each proxy for availability, speed, and geolocation, filters by country, maintains ratings and blacklists, and provides an HTTP/SOCKS5/transparent proxy server with balancing and domain-based routing. Everything is controllable via a web panel.

## Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/siv237/huntproxy/main/install.sh | bash
```

The installer installs dependencies, clones the repo to `/opt/huntproxy`, creates a venv, and registers a `huntproxy.service` systemd unit.

After install:

```bash
sudo systemctl enable --now huntproxy   # enable + start
# Web UI: http://127.0.0.1:17177/
```

## Features

### Proxy discovery & validation (Hunt)

- Downloads proxies from **24 open sources** (GitHub repos) — HTTP, HTTPS, SOCKS4, SOCKS5.
- Per-proxy validation: availability, latency, download speed, HTTPS/CONNECT support, country and ISP (GeoIP via ip-api.com).
- **MITM**-suspect node detection (SSL/header tampering).
- Country filter (US by default, switchable in one click).
- Parallel validation conveyor (`parallel` workers) with live progress.
- Periodic pool refresh and health-check of live proxies.

### Ratings & blacklists

- Every proxy gets a **0–100 rating** based on latency, speed, SSL/CONNECT bonuses, MITM penalty and speed-test failures.
- **IP blacklists** (Emerging Threats, FireHOL, IPsum, Blocklist.de): the proxy's egress IP is checked against downloaded lists — more hits, lower rating.
- **Manual blacklist** — hard exclusion (3 consecutive failures → auto-blacklist with cooldown).
- Favorites — proxies protected from auto-cleanup.

### Proxy server & balancing

- **HTTP CONNECT** (port `17277`) — standard HTTP proxy.
- **SOCKS5** (port `17377`).
- **Transparent** (port `17477`) — for iptables redirect of all TCP traffic.
- Upstream selection: direct (Direct), a specific proxy, or **pool** (round-robin / random by best rating).
- Cascade modes: pool, specific proxy, or custom proxy.

### Domain-based routing

- **Domain Lists** — domain lists with patterns (`example.com`, `.example.com`, `exact:`, `*.example.com`).
- **Routes** — bind domain lists to a route (Direct / Proxy / Pool / Custom).
- **Traffic Flow** — visualization of the current traffic path through the routing engine.
- **Custom Proxies** — corporate, Tor (`127.0.0.1:9050`), anti-ban services with connection testing.

### Transparent mode

Redirects ALL TCP traffic on ports 80/443 through the proxy — no per-app configuration needed.

```bash
sudo ./setup_iptables.sh start    # enable (needs root and transparent_enabled: true in config.yaml)
sudo ./setup_iptables.sh status   # check rules
sudo ./setup_iptables.sh stop     # disable
```

Local networks (10.x, 192.168.x, 172.16.x), localhost, and multicast are excluded. If you use a VPN, set `OWN_IP` to avoid a traffic loop:

```bash
sudo OWN_IP=10.8.0.2 ./setup_iptables.sh start
```

### Blocklists for censorship bypass

- **Country Blocklists** — IP/CIDR and domain lists blocked inside/outside a country.
- Russian lists built in (RKN blocks, foreign-service geo-blocks) — traffic to blocked resources is automatically routed through a proxy.
- List downloads can go through a proxy (`via proxy`).

### Monitoring & analytics

- **Overview** — dashboard with pool metrics, CPU/RAM/disk load, top countries and live performance.
- **Traffic Monitor** — live request stream, success rate, top destinations, route distribution.
- **Analytics** — pool size over time, traffic, average latency, 72h check heatmap.
- **Connectivity** — internet connectivity monitoring with canary hosts, downtime and IP-change detection.
- **Logs / Actions** — system logs and an operator action log with counter snapshots.

### Scheduler (Schedules)

A single background-task engine: hunt cycle, IP-blacklist refresh, blocklist refresh, health-check, history recording, dead-proxy cleanup, DB backup. Each task can be toggled, re-scheduled, and run on demand.

### Misc

- Dark/light Web UI theme, i18n (EN / RU).
- Proxy export/import, DB backup and restore.
- API for integration (docs in the API section).

## Commands

### Manual run

```bash
./hunt.sh                  # foreground, http://127.0.0.1:17177/
./hunt.sh --public         # listen on all interfaces
./hunt.sh --kill           # stop a running instance on the port
```

### systemd

```bash
sudo systemctl start huntproxy
sudo systemctl enable huntproxy      # autostart
sudo systemctl status huntproxy
journalctl -u huntproxy -f
sudo systemctl stop huntproxy
sudo systemctl restart huntproxy
```

### daemon.sh (alternative to systemd)

| Command | Description |
|---|---|
| `./daemon.sh start` | Start the daemon |
| `./daemon.sh stop` | Stop the daemon |
| `./daemon.sh restart` | Restart the daemon |
| `./daemon.sh status` | Daemon status |
| `./daemon.sh log [N]` | Last N log lines (default 20) |

## Ports (defaults)

| Port | Type | Purpose |
|---|---|---|
| `17177` | Web UI | Proxy pool control panel |
| `17277` | HTTP proxy | HTTP CONNECT proxy |
| `17377` | SOCKS5 proxy | SOCKS5 proxy |
| `17477` | Transparent | For iptables redirect (off by default) |

## Configuration

Everything lives in `config.yaml`. Key settings:

```yaml
server:
  web_listen: "127.0.0.1:17177"
  http_listen: "127.0.0.1:17277"
  socks5_listen: "127.0.0.1:17377"
  transparent_listen: "127.0.0.1:17477"
  transparent_enabled: false

proxies:
  validate_interval: 300          # pool refresh interval (sec)
  validate_parallel: 100          # concurrent checks during refresh
  health_interval: 120            # health-check interval (sec)
  health_parallel: 30
  strategy: round_robin           # round_robin | random
  max_failures: 3                 # failures before blacklisting
  cooldown: 300                   # cooldown after failure (sec)
  us_only: true                   # country filter
```

Proxy sources, IP blacklists, and blocklists are edited in `sources/default.ini` (survives a `data/` reset) or via the web panel.

## State files

| File | Description |
|---|---|
| `data/state.db` | SQLite — ratings, events, history, settings |
| `data/working.txt` | Live proxies (IP:PORT COUNTRY) |
| `data/blacklist.txt` | Blacklisted proxies |
| `data/ratings.json` | Per-proxy ratings and stats |
| `data/huntproxy.log` | Logs |

## Tech stack

- **Backend:** Python 3, asyncio, SQLite
- **Web UI:** Vanilla JS, CSS custom properties, Chart.js
- **Protocols:** HTTP CONNECT, SOCKS4, SOCKS5, transparent proxy
- **Data:** GeoIP (ip-api.com), speed test, MITM detection

## Tests

```bash
./test.sh
```

## License

MIT

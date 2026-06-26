<p align="center">
  <img src="web/assets/biglogo.png" alt="huntproxy" width="760">
</p>

# huntproxy

🌐 [EN](README.md) · [RU](README.ru.md) · [DE](README.de.md) · [ES](README.es.md) · [FR](README.fr.md) · [ZH](README.zh.md)

Ein Tool zum Suchen, Validieren und Verwalten eines Proxy-Pools mit Web-UI.

**Kurz gesagt:** Lädt Proxy-Listen aus 24 offenen Quellen herunter, validiert jeden Proxy auf Verfügbarkeit, Geschwindigkeit und Geolocation, filtert nach Land, verwaltet Bewertungen und Blacklists und stellt einen HTTP/SOCKS5/Transparent-Proxy-Server mit Lastverteilung und domänenbasierter Weiterleitung bereit. Alles über ein Web-Panel steuerbar.

## Schnellstart

```bash
curl -fsSL https://raw.githubusercontent.com/siv237/huntproxy/main/install.sh | bash
```

Das Installationsprogramm installiert Abhängigkeiten, klont das Repo nach `/opt/huntproxy`, erstellt ein venv und registriert eine `huntproxy.service`-Systemd-Einheit.

Nach der Installation:

```bash
sudo systemctl enable --now huntproxy   # aktivieren + starten
# Web-UI: http://127.0.0.1:17177/
```

## Funktionen

### Proxy-Suche & Validierung (Hunt)

- Lädt Proxys aus **24 offenen Quellen** (GitHub-Repos) herunter — HTTP, HTTPS, SOCKS4, SOCKS5.
- Validierung je Proxy: Verfügbarkeit, Latenz, Download-Geschwindigkeit, HTTPS/CONNECT-Unterstützung, Land und ISP (GeoIP via ip-api.com).
- Erkennung von **MITM**-verdächtigen Knoten (SSL/Header-Manipulation).
- Länderfilter (standardmäßig US, mit einem Klick umschaltbar).
- Paralleler Validierungs-Fließband (`parallel` Worker) mit Live-Fortschritt.
- Regelmäßige Pool-Aktualisierung und Health-Check der aktiven Proxys.

### Bewertungen & Blacklists

- Jeder Proxy erhält eine **0–100-Bewertung** basierend auf Latenz, Geschwindigkeit, SSL/CONNECT-Boni, MITM-Strafe und fehlgeschlagenen Speed-Tests.
- **IP-Blacklists** (Emerging Threats, FireHOL, IPsum, Blocklist.de): Die Egress-IP des Proxys wird gegen heruntergeladene Listen geprüft — mehr Treffer, niedrigere Bewertung.
- **Manuelle Blacklist** — harte Ausschließung (3 aufeinanderfolgende Fehler → Auto-Blacklist mit Cooldown).
- Favoriten — Proxys, die vor automatischer Bereinigung geschützt sind.

### Proxy-Server & Lastverteilung

- **HTTP CONNECT** (Port `17277`) — Standard-HTTP-Proxy.
- **SOCKS5** (Port `17377`).
- **Transparent** (Port `17477`) — für iptables-Redirect des gesamten TCP-Verkehrs.
- Upstream-Auswahl: direkt (Direct), ein bestimmter Proxy oder **Pool** (Round-Robin / Zufall nach bester Bewertung).
- Cascade-Modi: Pool, bestimmter Proxy oder Custom-Proxy.

### Domänenbasierte Weiterleitung

- **Domain Lists** — Domänenlisten mit Mustern (`example.com`, `.example.com`, `exact:`, `*.example.com`).
- **Routes** — Domänenlisten an eine Route binden (Direct / Proxy / Pool / Custom).
- **Traffic Flow** — Visualisierung des aktuellen Verkehrspfads durch die Weiterleitungs-Engine.
- **Custom Proxies** — Unternehmens-, Tor (`127.0.0.1:9050`), Anti-Ban-Dienste mit Verbindungsprüfung.

### Transparenter Modus

Leitet ALLEN TCP-Verkehr auf den Ports 80/443 durch den Proxy — keine App-Konfiguration nötig.

```bash
sudo ./setup_iptables.sh start    # aktivieren (root und transparent_enabled: true in config.yaml nötig)
sudo ./setup_iptables.sh status   # Regeln prüfen
sudo ./setup_iptables.sh stop     # deaktivieren
```

Lokale Netze (10.x, 192.168.x, 172.16.x), Localhost und Multicast sind ausgenommen. Bei VPN-Nutzung `OWN_IP` setzen, um Verkehrsschleifen zu vermeiden:

```bash
sudo OWN_IP=10.8.0.2 ./setup_iptables.sh start
```

### Blocklisten zur Zensurumgehung

- **Country Blocklists** — IP/CIDR- und Domänenlisten, die innerhalb/außerhalb eines Landes gesperrt sind.
- Russische Listen eingebaut (RKN-Sperren, Geo-Block ausländischer Dienste) — Verkehr zu gesperrten Ressourcen wird automatisch durch einen Proxy geleitet.
- Listen-Downloads können über einen Proxy laufen (`via proxy`).

### Überwachung & Analytik

- **Overview** — Dashboard mit Pool-Metriken, CPU/RAM/Disk-Last, Top-Ländern und Live-Leistung.
- **Traffic Monitor** — Live-Anfragestrom, Erfolgsquote, Top-Ziele, Routenverteilung.
- **Analytics** — Pool-Größe über Zeit, Verkehr, durchschnittliche Latenz, 72h-Prüfungs-Heatmap.
- **Connectivity** — Internetverbindungsüberwachung mit Canary-Hosts, Ausfall- und IP-Wechsel-Erkennung.
- **Logs / Actions** — Systemprotokolle und ein Operator-Aktionsprotokoll mit Zähler-Snapshots.

### Scheduler (Schedules)

Eine einheitliche Hintergrund-Task-Engine: Hunt-Zyklus, IP-Blacklist-Refresh, Blocklisten-Refresh, Health-Check, Verlaufsaufzeichnung, Bereinigung toter Proxys, DB-Backup. Jede Task kann umgeschaltet, umgeplant und bei Bedarf ausgeführt werden.

### Sonstiges

- Dark/Light Web-UI-Theme, i18n (EN / RU / DE / ES / FR / ZH).
- Proxy-Export/Import, DB-Backup und -Wiederherstellung.
- API zur Integration (Doku im Abschnitt API).

## Befehle

### Manuelle Ausführung

```bash
./hunt.sh                  # Vordergrund, http://127.0.0.1:17177/
./hunt.sh --public         # auf allen Schnittstellen lauschen
./hunt.sh --kill           # laufende Instanz auf dem Port stoppen
```

### systemd

```bash
sudo systemctl start huntproxy
sudo systemctl enable huntproxy      # Autostart
sudo systemctl status huntproxy
journalctl -u huntproxy -f
sudo systemctl stop huntproxy
sudo systemctl restart huntproxy
```

### daemon.sh (Alternative zu systemd)

| Befehl | Beschreibung |
|---|---|
| `./daemon.sh start` | Daemon starten |
| `./daemon.sh stop` | Daemon stoppen |
| `./daemon.sh restart` | Daemon neustarten |
| `./daemon.sh status` | Daemon-Status |
| `./daemon.sh log [N]` | Letzte N Protokollzeilen (Standard 20) |

## Ports (Standard)

| Port | Typ | Zweck |
|---|---|---|
| `17177` | Web-UI | Proxy-Pool-Steuerungs-Panel |
| `17277` | HTTP-Proxy | HTTP-CONNECT-Proxy |
| `17377` | SOCKS5-Proxy | SOCKS5-Proxy |
| `17477` | Transparent | Für iptables-Redirect (standardmäßig aus) |

## Konfiguration

Alles in `config.yaml`. Wichtige Einstellungen:

```yaml
server:
  web_listen: "127.0.0.1:17177"
  http_listen: "127.0.0.1:17277"
  socks5_listen: "127.0.0.1:17377"
  transparent_listen: "127.0.0.1:17477"
  transparent_enabled: false

proxies:
  validate_interval: 300          # Pool-Aktualisierungsintervall (Sek)
  validate_parallel: 100          # gleichzeitige Prüfungen beim Refresh
  health_interval: 120            # Health-Check-Intervall (Sek)
  health_parallel: 30
  strategy: round_robin           # round_robin | random
  max_failures: 3                 # Fehler bis zur Blacklist
  cooldown: 300                   # Cooldown nach Fehler (Sek)
  us_only: true                   # Länderfilter
```

Proxy-Quellen, IP-Blacklists und Blocklisten werden in `sources/default.ini` (überlebt einen `data/`-Reset) oder über das Web-Panel bearbeitet.

## Zustandsdateien

| Datei | Beschreibung |
|---|---|
| `data/state.db` | SQLite — Bewertungen, Ereignisse, Verlauf, Einstellungen |
| `data/working.txt` | Aktive Proxys (IP:PORT COUNTRY) |
| `data/blacklist.txt` | Blacklisted Proxys |
| `data/ratings.json` | Proxy-Bewertungen und -Statistiken |
| `data/huntproxy.log` | Protokolle |

## Tech-Stack

- **Backend:** Python 3, asyncio, SQLite
- **Web-UI:** Vanilla JS, CSS custom properties, Chart.js
- **Protokolle:** HTTP CONNECT, SOCKS4, SOCKS5, Transparent-Proxy
- **Daten:** GeoIP (ip-api.com), Speed-Test, MITM-Erkennung

## Tests

```bash
./test.sh
```

## Lizenz

MIT

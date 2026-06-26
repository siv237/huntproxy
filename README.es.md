<p align="center">
  <img src="web/assets/biglogo.png" alt="huntproxy" width="760">
</p>

# huntproxy

🌐 [EN](README.md) · [RU](README.ru.md) · [DE](README.de.md) · [ES](README.es.md) · [FR](README.fr.md) · [ZH](README.zh.md)

Una herramienta para descubrir, validar y gestionar un conjunto de proxies con interfaz web.

**En resumen:** descarga listas de proxies de 24 fuentes abiertas, valida cada proxy por disponibilidad, velocidad y geolocalización, filtra por país, mantiene valoraciones y listas negras, y proporciona un servidor proxy HTTP/SOCKS5/transparente con balanceo y enrutamiento por dominios. Todo es controlable desde un panel web.

## Inicio rápido

```bash
curl -fsSL https://raw.githubusercontent.com/siv237/huntproxy/main/install.sh | bash
```

El instalador instala las dependencias, clona el repositorio en `/opt/huntproxy`, crea un venv y registra una unidad de systemd `huntproxy.service`.

Tras la instalación:

```bash
sudo systemctl enable --now huntproxy   # habilitar + iniciar
# Interfaz web: http://127.0.0.1:17177/
```

## Funciones

### Descubrimiento y validación de proxies (Hunt)

- Descarga proxies de **24 fuentes abiertas** (repositorios de GitHub) — HTTP, HTTPS, SOCKS4, SOCKS5.
- Validación por proxy: disponibilidad, latencia, velocidad de descarga, soporte HTTPS/CONNECT, país e ISP (GeoIP vía ip-api.com).
- Detección de nodos sospechosos de **MITM** (manipulación SSL/headers).
- Filtro por país (EE. UU. por defecto, conmutable con un clic).
- Cinta de validación paralela (`parallel` trabajadores) con progreso en vivo.
- Actualización periódica del conjunto y health-check de los proxies activos.

### Valoraciones y listas negras

- Cada proxy recibe una **valoración de 0–100** basada en latencia, velocidad, bonificaciones SSL/CONNECT, penalización por MITM y fallos de speed-test.
- **Listas negras de IP** (Emerging Threats, FireHOL, IPsum, Blocklist.de): la IP de salida del proxy se comprueba contra listas descargadas — más coincidencias, menor valoración.
- **Lista negra manual** — exclusión estricta (3 fallos consecutivos → lista negra automática con cooldown).
- Favoritos — proxies protegidos de la limpieza automática.

### Servidor proxy y balanceo

- **HTTP CONNECT** (puerto `17277`) — proxy HTTP estándar.
- **SOCKS5** (puerto `17377`).
- **Transparente** (puerto `17477`) — para redirección iptables de todo el tráfico TCP.
- Selección de upstream: directo (Direct), un proxy específico o **conjunto** (round-robin / aleatorio por mejor valoración).
- Modos cascada: conjunto, proxy específico o proxy personalizado.

### Enrutamiento por dominios

- **Domain Lists** — listas de dominios con patrones (`example.com`, `.example.com`, `exact:`, `*.example.com`).
- **Routes** — vincular listas de dominios a una ruta (Direct / Proxy / Pool / Custom).
- **Traffic Flow** — visualización de la ruta de tráfico actual a través del motor de enrutamiento.
- **Custom Proxies** — corporativos, Tor (`127.0.0.1:9050`), servicios anti-ban con prueba de conexión.

### Modo transparente

Redirige TODO el tráfico TCP en los puertos 80/443 a través del proxy — sin configuración por aplicación.

```bash
sudo ./setup_iptables.sh start    # activar (necesita root y transparent_enabled: true en config.yaml)
sudo ./setup_iptables.sh status   # comprobar reglas
sudo ./setup_iptables.sh stop     # desactivar
```

Las redes locales (10.x, 192.168.x, 172.16.x), localhost y multicast se excluyen. Si usas VPN, define `OWN_IP` para evitar un bucle de tráfico:

```bash
sudo OWN_IP=10.8.0.2 ./setup_iptables.sh start
```

### Listas de bloqueo para evadir censura

- **Country Blocklists** — listas de IP/CIDR y dominios bloqueados dentro/fuera de un país.
- Listas rusas integradas (bloqueos RKN, geo-bloqueo de servicios extranjeros) — el tráfico a recursos bloqueados se enruta automáticamente a través de un proxy.
- Las descargas de listas pueden hacerse a través de un proxy (`via proxy`).

### Supervisión y analítica

- **Overview** — panel con métricas del conjunto, carga de CPU/RAM/disco, principales países y rendimiento en vivo.
- **Traffic Monitor** — flujo de solicitudes en vivo, tasa de éxito, principales destinos, distribución por rutas.
- **Analytics** — tamaño del conjunto a lo largo del tiempo, tráfico, latencia media, mapa de calor de comprobaciones (72h).
- **Connectivity** — supervisión de la conexión a internet con hosts canary, detección de caídas y cambios de IP.
- **Logs / Actions** — registros del sistema y un registro de acciones del operador con instantáneas de contadores.

### Planificador (Schedules)

Un único motor de tareas en segundo plano: ciclo de hunt, refresco de listas negras de IP, refresco de blocklists, health-check, grabación de historial, limpieza de proxies muertos, copia de seguridad de BD. Cada tarea se puede activar/desactivar, reprogramar y ejecutar bajo demanda.

### Miscelánea

- Tema oscuro/claro de la interfaz web, i18n (EN / RU / DE / ES / FR / ZH).
- Exportación/importación de proxies, copia de seguridad y restauración de BD.
- API para integración (documentación en la sección API).

## Comandos

### Ejecución manual

```bash
./hunt.sh                  # primer plano, http://127.0.0.1:17177/
./hunt.sh --public         # escuchar en todas las interfaces
./hunt.sh --kill           # detener una instancia en ejecución en el puerto
```

### systemd

```bash
sudo systemctl start huntproxy
sudo systemctl enable huntproxy      # inicio automático
sudo systemctl status huntproxy
journalctl -u huntproxy -f
sudo systemctl stop huntproxy
sudo systemctl restart huntproxy
```

### daemon.sh (alternativa a systemd)

| Comando | Descripción |
|---|---|
| `./daemon.sh start` | Iniciar el demonio |
| `./daemon.sh stop` | Detener el demonio |
| `./daemon.sh restart` | Reiniciar el demonio |
| `./daemon.sh status` | Estado del demonio |
| `./daemon.sh log [N]` | Últimas N líneas de registro (por defecto 20) |

## Puertos (por defecto)

| Puerto | Tipo | Función |
|---|---|---|
| `17177` | Interfaz web | Panel de control del conjunto de proxies |
| `17277` | Proxy HTTP | Proxy HTTP CONNECT |
| `17377` | Proxy SOCKS5 | Proxy SOCKS5 |
| `17477` | Transparente | Para redirección iptables (desactivado por defecto) |

## Configuración

Todo está en `config.yaml`. Ajustes principales:

```yaml
server:
  web_listen: "127.0.0.1:17177"
  http_listen: "127.0.0.1:17277"
  socks5_listen: "127.0.0.1:17377"
  transparent_listen: "127.0.0.1:17477"
  transparent_enabled: false

proxies:
  validate_interval: 300          # intervalo de actualización del conjunto (seg)
  validate_parallel: 100          # comprobaciones simultáneas al refrescar
  health_interval: 120            # intervalo de health-check (seg)
  health_parallel: 30
  strategy: round_robin           # round_robin | random
  max_failures: 3                 # fallos antes de lista negra
  cooldown: 300                   # cooldown tras fallo (seg)
  us_only: true                   # filtro por país
```

Las fuentes de proxies, listas negras de IP y blocklists se editan en `sources/default.ini` (sobrevive a un reinicio de `data/`) o desde el panel web.

## Archivos de estado

| Archivo | Descripción |
|---|---|
| `data/state.db` | SQLite — valoraciones, eventos, historial, ajustes |
| `data/working.txt` | Proxys activos (IP:PORT PAÍS) |
| `data/blacklist.txt` | Proxys en lista negra |
| `data/ratings.json` | Valoraciones y estadísticas por proxy |
| `data/huntproxy.log` | Registros |

## Stack tecnológico

- **Backend:** Python 3, asyncio, SQLite
- **Interfaz web:** Vanilla JS, CSS custom properties, Chart.js
- **Protocolos:** HTTP CONNECT, SOCKS4, SOCKS5, proxy transparente
- **Datos:** GeoIP (ip-api.com), test de velocidad, detección de MITM

## Tests

```bash
./test.sh
```

## Licencia

MIT

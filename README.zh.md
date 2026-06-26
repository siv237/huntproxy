<p align="center">
  <img src="web/assets/biglogo.png" alt="huntproxy" width="760">
</p>

# huntproxy

🌐 [EN](README.md) · [RU](README.ru.md) · [DE](README.de.md) · [ES](README.es.md) · [FR](README.fr.md) · [ZH](README.zh.md)

一个用于发现、验证和管理代理池并带有 Web 界面的工具。

**概述：** 从 24 个开放来源下载代理列表，对每个代理进行可用性、速度和地理位置验证，按国家过滤，维护评分与黑名单，并提供一个带负载均衡和基于域名路由的 HTTP/SOCKS5/透明代理服务器。所有操作均可通过 Web 面板控制。

## 快速开始

```bash
curl -fsSL https://raw.githubusercontent.com/siv237/huntproxy/main/install.sh | bash
```

安装程序会安装依赖、将仓库克隆到 `/opt/huntproxy`、创建 venv 并注册一个 `huntproxy.service` systemd 单元。

安装后：

```bash
sudo systemctl enable --now huntproxy   # 启用 + 启动
# Web 界面：http://127.0.0.1:17177/
```

## 功能

### 代理发现与验证（Hunt）

- 从 **24 个开放来源**（GitHub 仓库）下载代理 — HTTP、HTTPS、SOCKS4、SOCKS5。
- 逐个代理验证：可用性、延迟、下载速度、HTTPS/CONNECT 支持、国家和 ISP（通过 ip-api.com 的 GeoIP）。
- **MITM** 可疑节点检测（SSL/头部篡改）。
- 国家过滤（默认美国，一键切换）。
- 并行验证流水线（`parallel` 个 worker）并显示实时进度。
- 定期刷新代理池并对存活代理进行健康检查。

### 评分与黑名单

- 每个代理获得一个 **0–100 的评分**，基于延迟、速度、SSL/CONNECT 加分、MITM 惩罚和测速失败。
- **IP 黑名单**（Emerging Threats、FireHOL、IPsum、Blocklist.de）：将代理的出口 IP 与下载的列表比对 — 命中越多，评分越低。
- **手动黑名单** — 硬性排除（连续 3 次失败 → 自动加入黑名单并带冷却时间）。
- 收藏 — 受保护免于自动清理的代理。

### 代理服务器与负载均衡

- **HTTP CONNECT**（端口 `17277`）— 标准 HTTP 代理。
- **SOCKS5**（端口 `17377`）。
- **透明代理**（端口 `17477`）— 用于 iptables 重定向全部 TCP 流量。
- 上游选择：直连（Direct）、特定代理或 **代理池**（轮询 / 随机按最佳评分）。
- 级联模式：代理池、特定代理或自定义代理。

### 基于域名的路由

- **Domain Lists** — 带匹配模式的域名列表（`example.com`、`.example.com`、`exact:`、`*.example.com`）。
- **Routes** — 将域名列表绑定到路由（Direct / Proxy / Pool / Custom）。
- **Traffic Flow** — 可视化当前流量通过路由引擎的路径。
- **Custom Proxies** — 企业、Tor（`127.0.0.1:9050`）、防封禁服务，带连接测试。

### 透明模式

将 80/443 端口上的全部 TCP 流量重定向通过代理 — 无需逐应用配置。

```bash
sudo ./setup_iptables.sh start    # 启用（需要 root，且 config.yaml 中 transparent_enabled: true）
sudo ./setup_iptables.sh status   # 检查规则
sudo ./setup_iptables.sh stop     # 停用
```

本地网络（10.x、192.168.x、172.16.x）、localhost 和 multicast 被排除。如果使用 VPN，请设置 `OWN_IP` 以避免流量环路：

```bash
sudo OWN_IP=10.8.0.2 ./setup_iptables.sh start
```

### 用于绕过审查的封锁列表

- **Country Blocklists** — 某国境内/境外被封锁的 IP/CIDR 和域名列表。
- 内置俄罗斯列表（RKN 封锁、外国服务的地理封锁）— 发往被封锁资源的流量会自动通过代理。
- 列表下载可通过代理进行（`via proxy`）。

### 监控与分析

- **Overview** — 显示代理池指标、CPU/RAM/磁盘负载、热门国家和实时性能的仪表板。
- **Traffic Monitor** — 实时请求流、成功率、热门目标、路由分布。
- **Analytics** — 代理池大小随时间变化、流量、平均延迟、72 小时检查热力图。
- **Connectivity** — 使用 canary 主机进行互联网连接监控，检测中断和 IP 变更。
- **Logs / Actions** — 系统日志和带计数器快照的操作员操作日志。

### 调度器（Schedules）

一个统一的后台任务引擎：hunt 周期、IP 黑名单刷新、封锁列表刷新、健康检查、历史记录、死代理清理、数据库备份。每个任务都可切换、重新调度并按需运行。

### 其他

- Web 界面深色/浅色主题，国际化（EN / RU / DE / ES / FR / ZH）。
- 代理导出/导入、数据库备份与恢复。
- 用于集成的 API（文档见 API 部分）。

## 命令

### 手动运行

```bash
./hunt.sh                  # 前台，http://127.0.0.1:17177/
./hunt.sh --public         # 在所有接口上监听
./hunt.sh --kill           # 停止在该端口上运行的实例
```

### systemd

```bash
sudo systemctl start huntproxy
sudo systemctl enable huntproxy      # 自启动
sudo systemctl status huntproxy
journalctl -u huntproxy -f
sudo systemctl stop huntproxy
sudo systemctl restart huntproxy
```

### daemon.sh（systemd 的替代方案）

| 命令 | 说明 |
|---|---|
| `./daemon.sh start` | 启动守护进程 |
| `./daemon.sh stop` | 停止守护进程 |
| `./daemon.sh restart` | 重启守护进程 |
| `./daemon.sh status` | 守护进程状态 |
| `./daemon.sh log [N]` | 最后 N 行日志（默认 20） |

## 端口（默认）

| 端口 | 类型 | 用途 |
|---|---|---|
| `17177` | Web 界面 | 代理池控制面板 |
| `17277` | HTTP 代理 | HTTP CONNECT 代理 |
| `17377` | SOCKS5 代理 | SOCKS5 代理 |
| `17477` | 透明代理 | 用于 iptables 重定向（默认关闭） |

## 配置

一切都在 `config.yaml` 中。主要设置：

```yaml
server:
  web_listen: "127.0.0.1:17177"
  http_listen: "127.0.0.1:17277"
  socks5_listen: "127.0.0.1:17377"
  transparent_listen: "127.0.0.1:17477"
  transparent_enabled: false

proxies:
  validate_interval: 300          # 代理池刷新间隔（秒）
  validate_parallel: 100          # 刷新时的并发检查数
  health_interval: 120            # 健康检查间隔（秒）
  health_parallel: 30
  strategy: round_robin           # round_robin | random
  max_failures: 3                 # 加入黑名单前的失败次数
  cooldown: 300                   # 失败后的冷却时间（秒）
  us_only: true                   # 国家过滤
```

代理来源、IP 黑名单和封锁列表在 `sources/default.ini`（重置 `data/` 后仍保留）或通过 Web 面板编辑。

## 状态文件

| 文件 | 说明 |
|---|---|
| `data/state.db` | SQLite — 评分、事件、历史、设置 |
| `data/working.txt` | 存活代理（IP:PORT 国家） |
| `data/blacklist.txt` | 被加入黑名单的代理 |
| `data/ratings.json` | 每个代理的评分和统计 |
| `data/huntproxy.log` | 日志 |

## 技术栈

- **后端：** Python 3、asyncio、SQLite
- **Web 界面：** Vanilla JS、CSS custom properties、Chart.js
- **协议：** HTTP CONNECT、SOCKS4、SOCKS5、透明代理
- **数据：** GeoIP (ip-api.com)、测速、MITM 检测

## 测试

```bash
./test.sh
```

## 许可证

MIT

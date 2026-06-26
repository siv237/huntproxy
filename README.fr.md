<p align="center">
  <img src="web/assets/biglogo.png" alt="huntproxy" width="760">
</p>

# huntproxy

🌐 [EN](README.md) · [RU](README.ru.md) · [DE](README.de.md) · [ES](README.es.md) · [FR](README.fr.md) · [ZH](README.zh.md)

Un outil pour découvrir, valider et gérer un pool de proxies avec une interface Web.

**En résumé :** télécharge des listes de proxies depuis 24 sources ouvertes, valide chaque proxy en disponibilité, vitesse et géolocalisation, filtre par pays, gère les notations et listes noires, et fournit un serveur proxy HTTP/SOCKS5/transparent avec équilibrage et routage par domaines. Le tout est contrôlable depuis un panneau Web.

## Démarrage rapide

```bash
curl -fsSL https://raw.githubusercontent.com/siv237/huntproxy/main/install.sh | bash
```

L'installateur installe les dépendances, clone le dépôt dans `/opt/huntproxy`, crée un venv et enregistre une unité systemd `huntproxy.service`.

Après l'installation :

```bash
sudo systemctl enable --now huntproxy   # activer + démarrer
# Interface Web : http://127.0.0.1:17177/
```

## Fonctionnalités

### Découverte et validation des proxies (Hunt)

- Télécharge des proxies depuis **24 sources ouvertes** (dépôts GitHub) — HTTP, HTTPS, SOCKS4, SOCKS5.
- Validation par proxy : disponibilité, latence, vitesse de téléchargement, support HTTPS/CONNECT, pays et FAI (GeoIP via ip-api.com).
- Détection des nœuds suspects de **MITM** (falsification SSL/headers).
- Filtre par pays (États-Unis par défaut, commutable en un clic).
- Convoyeur de validation parallèle (`parallel` workers) avec progression en direct.
- Rafraîchissement périodique du pool et health-check des proxies actifs.

### Notations et listes noires

- Chaque proxy reçoit une **note de 0 à 100** basée sur la latence, la vitesse, les bonus SSL/CONNECT, la pénalité MITM et les échecs de speed-test.
- **Listes noires d'IP** (Emerging Threats, FireHOL, IPsum, Blocklist.de) : l'IP de sortie du proxy est vérifiée contre les listes téléchargées — plus de correspondances, note plus basse.
- **Liste noire manuelle** — exclusion stricte (3 échecs consécutifs → liste noire auto avec cooldown).
- Favoris — proxies protégés contre le nettoyage automatique.

### Serveur proxy et équilibrage

- **HTTP CONNECT** (port `17277`) — proxy HTTP standard.
- **SOCKS5** (port `17377`).
- **Transparent** (port `17477`) — pour la redirection iptables de tout le trafic TCP.
- Sélection de l'upstream : direct (Direct), un proxy spécifique ou **pool** (round-robin / aléatoire selon la meilleure note).
- Modes cascade : pool, proxy spécifique ou proxy personnalisé.

### Routage par domaines

- **Domain Lists** — listes de domaines avec motifs (`example.com`, `.example.com`, `exact:`, `*.example.com`).
- **Routes** — lier des listes de domaines à une route (Direct / Proxy / Pool / Custom).
- **Traffic Flow** — visualisation du chemin de trafic actuel à travers le moteur de routage.
- **Custom Proxies** — proxies d'entreprise, Tor (`127.0.0.1:9050`), services anti-ban avec test de connexion.

### Mode transparent

Redirige TOUT le trafic TCP sur les ports 80/443 à travers le proxy — aucune configuration par application nécessaire.

```bash
sudo ./setup_iptables.sh start    # activer (nécessite root et transparent_enabled: true dans config.yaml)
sudo ./setup_iptables.sh status   # vérifier les règles
sudo ./setup_iptables.sh stop     # désactiver
```

Les réseaux locaux (10.x, 192.168.x, 172.16.x), localhost et multicast sont exclus. En cas d'utilisation d'un VPN, définissez `OWN_IP` pour éviter une boucle de trafic :

```bash
sudo OWN_IP=10.8.0.2 ./setup_iptables.sh start
```

### Listes de blocage pour contourner la censure

- **Country Blocklists** — listes d'IP/CIDR et de domaines bloqués à l'intérieur/à l'extérieur d'un pays.
- Listes russes intégrées (blocages RKN, géo-bloc des services étrangers) — le trafic vers les ressources bloquées passe automatiquement par un proxy.
- Les téléchargements de listes peuvent transiter par un proxy (`via proxy`).

### Surveillance et analytique

- **Overview** — tableau de bord avec métriques du pool, charge CPU/RAM/disque, principaux pays et performances en direct.
- **Traffic Monitor** — flux de requêtes en direct, taux de réussite, principales destinations, distribution par routes.
- **Analytics** — taille du pool dans le temps, trafic, latence moyenne, carte de chaleur des contrôles (72h).
- **Connectivity** — surveillance de la connexion Internet avec hôtes canaris, détection des coupures et changements d'IP.
- **Logs / Actions** — journaux système et un journal des actions de l'opérateur avec instantanés des compteurs.

### Planificateur (Schedules)

Un moteur unique de tâches en arrière-plan : cycle de hunt, rafraîchissement des listes noires d'IP, rafraîchissement des blocklists, health-check, enregistrement de l'historique, nettoyage des proxies morts, sauvegarde de la BDD. Chaque tâche peut être activée/désactivée, reprogrammée et lancée à la demande.

### Divers

- Thème sombre/clair de l'interface Web, i18n (EN / RU / DE / ES / FR / ZH).
- Export/import de proxies, sauvegarde et restauration de la BDD.
- API pour l'intégration (documentation dans la section API).

## Commandes

### Exécution manuelle

```bash
./hunt.sh                  # premier plan, http://127.0.0.1:17177/
./hunt.sh --public         # écouter sur toutes les interfaces
./hunt.sh --kill           # arrêter une instance en cours sur le port
```

### systemd

```bash
sudo systemctl start huntproxy
sudo systemctl enable huntproxy      # démarrage automatique
sudo systemctl status huntproxy
journalctl -u huntproxy -f
sudo systemctl stop huntproxy
sudo systemctl restart huntproxy
```

### daemon.sh (alternative à systemd)

| Commande | Description |
|---|---|
| `./daemon.sh start` | Démarrer le démon |
| `./daemon.sh stop` | Arrêter le démon |
| `./daemon.sh restart` | Redémarrer le démon |
| `./daemon.sh status` | État du démon |
| `./daemon.sh log [N]` | N dernières lignes de journal (20 par défaut) |

## Ports (par défaut)

| Port | Type | Fonction |
|---|---|---|
| `17177` | Interface Web | Panneau de contrôle du pool de proxies |
| `17277` | Proxy HTTP | Proxy HTTP CONNECT |
| `17377` | Proxy SOCKS5 | Proxy SOCKS5 |
| `17477` | Transparent | Pour redirection iptables (désactivé par défaut) |

## Configuration

Tout se trouve dans `config.yaml`. Réglages principaux :

```yaml
server:
  web_listen: "127.0.0.1:17177"
  http_listen: "127.0.0.1:17277"
  socks5_listen: "127.0.0.1:17377"
  transparent_listen: "127.0.0.1:17477"
  transparent_enabled: false

proxies:
  validate_interval: 300          # intervalle de rafraîchissement du pool (s)
  validate_parallel: 100          # contrôles simultanés lors du rafraîchissement
  health_interval: 120            # intervalle de health-check (s)
  health_parallel: 30
  strategy: round_robin           # round_robin | random
  max_failures: 3                 # échecs avant liste noire
  cooldown: 300                   # cooldown après échec (s)
  us_only: true                   # filtre par pays
```

Les sources de proxies, listes noires d'IP et blocklists se modifient dans `sources/default.ini` (survit à une réinitialisation de `data/`) ou via le panneau Web.

## Fichiers d'état

| Fichier | Description |
|---|---|
| `data/state.db` | SQLite — notations, événements, historique, réglages |
| `data/working.txt` | Proxies actifs (IP:PORT PAYS) |
| `data/blacklist.txt` | Proxies en liste noire |
| `data/ratings.json` | Notations et statistiques par proxy |
| `data/huntproxy.log` | Journaux |

## Stack technique

- **Backend :** Python 3, asyncio, SQLite
- **Interface Web :** Vanilla JS, CSS custom properties, Chart.js
- **Protocoles :** HTTP CONNECT, SOCKS4, SOCKS5, proxy transparent
- **Données :** GeoIP (ip-api.com), test de vitesse, détection MITM

## Tests

```bash
./test.sh
```

## Licence

MIT

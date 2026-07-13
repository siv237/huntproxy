"""Functional split of the huntproxy backend."""

import sqlite3
import logging

logger = logging.getLogger(__name__)


class _SharedConn:
    """Wrapper that proxies a persistent sqlite3 connection but ignores
    close() calls from callers, so the underlying connection is reused and
    SQLite WAL/shm files are not constantly created and removed."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        pass


class DbMixin:
    def _stats_db(self) -> sqlite3.Connection:
            raw = getattr(self, "_stats_conn", None)
            if raw is not None and self._db_path.exists():
                return _SharedConn(raw)
            if raw is not None:
                try:
                    raw.close()
                except Exception:
                    logger.debug("suppressed", exc_info=True)
                self._stats_conn = None
            raw = sqlite3.connect(str(self._db_path), check_same_thread=False)
            raw.row_factory = sqlite3.Row
            try:
                raw.execute("PRAGMA journal_mode=WAL")
            except Exception:
                logger.debug("suppressed", exc_info=True)
            self._ensure_stats_db(raw)
            self._stats_conn = raw
            return _SharedConn(raw)

    def _ensure_stats_db(self, conn: sqlite3.Connection):
            """Recreate stats tables if they are missing (e.g. after the DB file was deleted)."""
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
                ).fetchone()
                if not row:
                    self._init_stats_db(conn)
            except Exception:
                logger.debug("suppressed", exc_info=True)

    def _db(self) -> sqlite3.Connection:
            raw = getattr(self, "_state_conn", None)
            if raw is not None and self._state_db_path.exists():
                return _SharedConn(raw)
            if raw is not None:
                try:
                    raw.close()
                except Exception:
                    logger.debug("suppressed", exc_info=True)
                self._state_conn = None
            raw = sqlite3.connect(str(self._state_db_path), check_same_thread=False)
            raw.row_factory = sqlite3.Row
            try:
                raw.execute("PRAGMA journal_mode=WAL")
            except Exception:
                logger.debug("suppressed", exc_info=True)
            self._ensure_state_db(raw)
            self._state_conn = raw
            return _SharedConn(raw)

    def _ensure_state_db(self, conn: sqlite3.Connection):
            """Recreate state tables if they are missing (e.g. after the DB file was deleted)."""
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='ratings'"
                ).fetchone()
                if not row:
                    self._init_state_db(conn)
            except Exception:
                logger.debug("suppressed", exc_info=True)

    def _init_db(self):
            self._init_stats_db()
            self._init_state_db()

    def _init_stats_db(self, conn: sqlite3.Connection | None = None):
            close_after = conn is None
            if conn is None:
                conn = self._stats_db()
            conn.executescript("""
                -- Remove business tables that were incorrectly created in stats.db
                DROP TABLE IF EXISTS domain_lists;
                DROP TABLE IF EXISTS domain_entries;
                DROP TABLE IF EXISTS routing_config;
                DROP TABLE IF EXISTS custom_proxies;
                DROP TABLE IF EXISTS proxy_sources;
                DROP TABLE IF EXISTS proxy_source_entries;
                DROP TABLE IF EXISTS ip_blacklist_sources;
                DROP TABLE IF EXISTS ip_blacklist_entries;
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    alive INTEGER DEFAULT 0,
                    dead INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0,
                    requests INTEGER DEFAULT 0,
                    connections_ok INTEGER DEFAULT 0,
                    connections_failed INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0,
                    traffic_success_rate REAL DEFAULT 0,
                    bandwidth_in INTEGER DEFAULT 0,
                    bandwidth_out INTEGER DEFAULT 0,
                    avg_latency REAL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_history_ts ON history(ts);
                CREATE TABLE IF NOT EXISTS traffic_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    client TEXT DEFAULT '',
                    target TEXT DEFAULT '',
                    status TEXT DEFAULT '',
                    upstream TEXT DEFAULT '',
                    bytes_in INTEGER DEFAULT 0,
                    bytes_out INTEGER DEFAULT 0,
                    duration REAL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_traffic_ts ON traffic_log(ts);
                CREATE INDEX IF NOT EXISTS idx_traffic_target ON traffic_log(target);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    seq INTEGER DEFAULT 0,
                    type TEXT DEFAULT 'info',
                    msg TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
                CREATE TABLE IF NOT EXISTS canary_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    alive INTEGER NOT NULL,
                    alive_count INTEGER NOT NULL DEFAULT 0,
                    total_count INTEGER NOT NULL DEFAULT 0,
                    host_results TEXT NOT NULL DEFAULT '',
                    direct_ip TEXT DEFAULT '',
                    direct_country TEXT DEFAULT '',
                    direct_isp TEXT DEFAULT '',
                    direct_city TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_canary_ts ON canary_history(ts);
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    action TEXT NOT NULL DEFAULT '',
                    detail TEXT NOT NULL DEFAULT '',
                    snapshot TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_actions_ts ON actions(ts);
                CREATE TABLE IF NOT EXISTS proxy_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    ts REAL NOT NULL,
                    latency REAL DEFAULT 0,
                    speed REAL DEFAULT 0,
                    ok INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_proxy_checks_addr_ts ON proxy_checks(address, ts DESC);
            """)
            conn.commit()
            for col, default in [
                ("traffic_success_rate", "REAL DEFAULT 0"),
                ("bandwidth_in", "INTEGER DEFAULT 0"),
                ("bandwidth_out", "INTEGER DEFAULT 0"),
                ("avg_latency", "REAL DEFAULT 0"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE history ADD COLUMN {col} {default}")
                except Exception:
                    logger.debug("suppressed", exc_info=True)
            conn.commit()
            if close_after:
                conn.close()

    def _init_state_db(self, conn: sqlite3.Connection | None = None):
            close_after = conn is None
            if conn is None:
                conn = self._db()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS domain_lists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'manual',
                    url TEXT DEFAULT '',
                    route TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS domain_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id TEXT NOT NULL REFERENCES domain_lists(id) ON DELETE CASCADE,
                    pattern TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_domain_entries_uniq ON domain_entries(list_id, pattern);
                CREATE INDEX IF NOT EXISTS idx_domain_entries_list ON domain_entries(list_id);
                CREATE TABLE IF NOT EXISTS routing_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS custom_proxies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    protocol TEXT NOT NULL DEFAULT 'socks5',
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    username TEXT NOT NULL DEFAULT '',
                    password TEXT NOT NULL DEFAULT '',
                    test_url TEXT NOT NULL DEFAULT '',
                    last_check_at REAL NOT NULL DEFAULT 0,
                    last_check_status TEXT NOT NULL DEFAULT '',
                    last_check_latency INTEGER NOT NULL DEFAULT -1,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS proxy_sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    protocol TEXT NOT NULL DEFAULT 'mixed',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0,
                    last_fetched_at REAL NOT NULL DEFAULT 0,
                    last_fetch_status TEXT NOT NULL DEFAULT '',
                    last_fetch_count INTEGER NOT NULL DEFAULT 0,
                    last_fetch_error TEXT NOT NULL DEFAULT '',
                    total_fetched INTEGER NOT NULL DEFAULT 0,
                    total_working INTEGER NOT NULL DEFAULT 0,
                    total_dead INTEGER NOT NULL DEFAULT 0,
                    last_working INTEGER NOT NULL DEFAULT 0,
                    last_dead INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS proxy_source_entries (
                    source_id TEXT NOT NULL,
                    address TEXT NOT NULL,
                    created_at REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (source_id, address)
                );
                CREATE INDEX IF NOT EXISTS idx_proxy_source_entries_source ON proxy_source_entries(source_id);
                CREATE INDEX IF NOT EXISTS idx_proxy_source_entries_address ON proxy_source_entries(address);
                CREATE TABLE IF NOT EXISTS ip_blacklist_sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0,
                    last_fetched_at REAL NOT NULL DEFAULT 0,
                    last_fetch_status TEXT NOT NULL DEFAULT '',
                    last_fetch_count INTEGER NOT NULL DEFAULT 0,
                    last_fetch_error TEXT NOT NULL DEFAULT '',
                    total_fetched INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS ip_blacklist_entries (
                    entry TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (entry, source_id)
                );
                CREATE INDEX IF NOT EXISTS idx_ip_bl_entry ON ip_blacklist_entries(entry);
                CREATE INDEX IF NOT EXISTS idx_ip_bl_source ON ip_blacklist_entries(source_id);
                CREATE TABLE IF NOT EXISTS blocklist_sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    country TEXT NOT NULL DEFAULT '',
                    direction TEXT NOT NULL DEFAULT 'inside',
                    list_type TEXT NOT NULL DEFAULT 'ip',
                    url TEXT NOT NULL,
                    download_proxy TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0,
                    last_fetched_at REAL NOT NULL DEFAULT 0,
                    last_fetch_status TEXT NOT NULL DEFAULT '',
                    last_fetch_count INTEGER NOT NULL DEFAULT 0,
                    last_fetch_error TEXT NOT NULL DEFAULT '',
                    total_fetched INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS ratings (
                    address TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS blacklist (
                    address TEXT PRIMARY KEY,
                    reason TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS favorites (
                    address TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS runtime_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS working_proxies (
                    address TEXT PRIMARY KEY,
                    country TEXT NOT NULL DEFAULT '',
                    latency REAL NOT NULL DEFAULT 0,
                    score REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS schedules (
                    id              TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    task_type       TEXT NOT NULL,
                    enabled         INTEGER NOT NULL DEFAULT 1,
                    interval_sec    INTEGER NOT NULL DEFAULT 3600,
                    config          TEXT NOT NULL DEFAULT '{}',
                    last_run        REAL NOT NULL DEFAULT 0,
                    last_ok         REAL NOT NULL DEFAULT 0,
                    next_run        REAL NOT NULL DEFAULT 0,
                    last_status     TEXT NOT NULL DEFAULT 'never',
                    last_duration_s REAL NOT NULL DEFAULT 0,
                    last_error      TEXT NOT NULL DEFAULT ''
                );
            """)
            conn.commit()
            self._migrate_state_db_columns(conn)
            if close_after:
                conn.close()

    def _migrate_state_db_columns(self, conn):
            """Add columns that may be missing in older databases."""
            migrations = [
                ("blocklist_sources", "download_proxy", "TEXT NOT NULL DEFAULT ''"),
                ("blocklist_sources", "class", "TEXT NOT NULL DEFAULT 'block'"),
                ("blocklist_sources", "route", "TEXT NOT NULL DEFAULT ''"),
                ("schedules", "last_ok", "REAL NOT NULL DEFAULT 0"),
            ]
            for table, column, coldef in migrations:
                try:
                    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                    if column not in cols:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}")
                        conn.commit()
                except Exception:
                    logger.debug("suppressed", exc_info=True)

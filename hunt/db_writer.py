"""SQLite connection helpers for hunt — extracted from db.py."""

import os
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


class _DbWriter:
    """Dedicated background writer thread for one SQLite database file.

    Hot-path writes (traffic log, rating checkpoints, history) are queued and
    executed on this thread's own WAL connection with batched commits, so the
    asyncio event loop never blocks on sqlite commits. Readers keep their
    existing connections: WAL mode allows concurrent reads during writes.
    Each queued item is either a parameter tuple (single execute) or a list
    of tuples (executemany).
    """

    def __init__(self, path, name: str, ensure=None):
        import queue as _queue
        import threading as _threading
        self._path = path
        self._ensure = ensure
        self._queue = _queue.Queue()
        self._conn = None
        self._thread = _threading.Thread(
            target=self._loop, daemon=True, name=f"{name}-db-writer")
        self._thread.start()

    def submit(self, sql: str, rows):
        self._queue.put((sql, rows))

    def drain(self):
        """Block until everything submitted so far has been committed."""
        self._queue.join()

    def _connection(self):
        """Open (or re-open after external deletion) the writer connection."""
        if self._conn is not None and not os.path.exists(str(self._path)):
            try:
                self._conn.close()
            except Exception:
                logger.debug("suppressed", exc_info=True)
            self._conn = None
        if self._conn is None:
            conn = sqlite3.connect(str(self._path), check_same_thread=False)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                logger.debug("suppressed", exc_info=True)
            if self._ensure is not None:
                try:
                    self._ensure(conn)
                except Exception:
                    logger.debug("suppressed", exc_info=True)
            self._conn = conn
        return self._conn

    def _loop(self):
        while True:
            item = self._queue.get()
            batch = [item]
            while len(batch) < 128:
                try:
                    nxt = self._queue.get_nowait()
                except Exception:
                    break
                batch.append(nxt)
            ok = True
            conn = None
            try:
                conn = self._connection()
                for sql, rows in batch:
                    if isinstance(rows, list):
                        conn.executemany(sql, rows)
                    else:
                        conn.execute(sql, rows)
                conn.commit()
            except Exception as e:
                ok = False
                # A failed commit leaves the write transaction open; without a
                # rollback it pins the write lock (blocking every other writer
                # and WAL checkpoint) and keeps accumulating uncommitted pages
                # in the WAL — the "database is locked" / 10GB WAL spiral.
                if conn is not None:
                    try:
                        conn.rollback()
                    except Exception:
                        logger.debug("suppressed", exc_info=True)
                logger.error("background db write failed: %s", e)
            for _ in batch:
                self._queue.task_done()
            if not ok:
                logger.debug("suppressed", exc_info=True)

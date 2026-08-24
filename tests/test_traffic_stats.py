import time

import pytest

from hunt.traffic_stats import TrafficStats


def test_add_accumulates_per_hour_and_upstream():
    ts = TrafficStats()
    base = int(time.time() // 3600) * 3600
    ts.add(base + 10, "ok", "proxy:1.2.3.4:8080", 100, 200)
    ts.add(base + 20, "ok", "proxy:1.2.3.4:8080", 10, 20)
    ts.add(base + 30, "connect failed", "direct", 50, 5)
    rows = ts.by_upstream(base - 1)
    assert rows["proxy:1.2.3.4:8080"] == [2, 110, 220, 2, 0.0]
    assert rows["direct"][0] == 1
    assert rows["direct"][3] == 0


def test_totals_respects_cutoff():
    ts = TrafficStats()
    now = time.time()
    old_h = int((now - 7200) // 3600) * 3600
    cur_h = int(now // 3600) * 3600
    ts.add(old_h + 60, "ok", "direct", 1000, 1000)
    ts.add(cur_h + 60, "ok", "direct", 7, 7)
    reqs, up, down, ok = ts.totals(cur_h - 1)
    assert (reqs, up, down, ok) == (1, 7, 7, 1)
    assert ts.totals(0)[0] == 2


def test_prune_drops_old_hours():
    ts = TrafficStats()
    now = time.time()
    ts.add(now - TrafficStats.WINDOW - 5000, "ok", "direct", 1, 1)
    ts.add(now, "ok", "direct", 2, 2)
    ts.prune(now)
    assert ts.totals(0)[0] == 1


def test_duration_sum_tracked():
    ts = TrafficStats()
    ts.add(time.time(), "ok", "direct", 1, 1, duration=0.25)
    ts.add(time.time(), "ok", "direct", 1, 1, duration=0.75)
    assert ts.by_upstream(0)["direct"][4] == pytest.approx(1.0)


def test_load_from_db_rebuilds_and_sets_ready(tmp_path):
    import sqlite3
    db = tmp_path / "stats.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE traffic_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                 "ts REAL NOT NULL, client TEXT DEFAULT '', target TEXT DEFAULT '', "
                 "status TEXT DEFAULT '', upstream TEXT DEFAULT '', "
                 "bytes_in INTEGER DEFAULT 0, bytes_out INTEGER DEFAULT 0, "
                 "duration REAL DEFAULT 0)")
    now = time.time()
    h = int(now // 3600) * 3600
    conn.executemany(
        "INSERT INTO traffic_log (ts, status, upstream, bytes_in, bytes_out, duration) "
        "VALUES (?,?,?,?,?,?)",
        [(h + 5, "ok", "proxy:9.9.9.9:80", 10, 20, 0.1),
         (h + 6, "ok", "proxy:9.9.9.9:80", 30, 40, 0.3),
         (h + 7, "timeout", "direct", 0, 0, 5.0)])
    conn.commit()

    ts = TrafficStats()
    ts.load_from_db(conn, now)
    conn.close()
    assert ts.ready
    rows = ts.by_upstream(h - 1)
    assert rows["proxy:9.9.9.9:80"][:4] == [2, 40, 60, 2]
    assert rows["direct"][:4] == [1, 0, 0, 0]


def test_add_never_raises_on_garbage():
    ts = TrafficStats()
    ts.add(None, None, None, None, None)
    ts.add("x", "y", "z", "i", "o")
    assert isinstance(ts.totals(0)[0], int)

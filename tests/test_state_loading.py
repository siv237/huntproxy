import json
import hunt
import sqlite3
import time


def _insert_rating(state, d):
    """Insert a rating dict into the DB so _load_state can read it."""
    conn = state._db()
    conn.execute("INSERT OR REPLACE INTO ratings (address, data) VALUES (?, ?)",
                 (d["address"], json.dumps(d)))
    conn.commit()
    conn.close()


class TestStateLoading:
    def test_load_state_repairs_zero_latency_avg(self, state, tmp_data_dir):
        _insert_rating(state, {
            "address": "1.2.3.4:8080",
            "last_status": "ok",
            "checks_total": 1,
            "checks_ok": 1,
            "last_latency": 0.66,
            "latency_avg": 0.0,
        })
        state._load_state()
        r = state.ratings["1.2.3.4:8080"]
        assert r.latency_avg == 0.66
        assert r.latency_sum == 0.66
        assert r.latency_count == 1

    def test_load_state_uses_stored_latency_sum_and_count(self, state, tmp_data_dir):
        _insert_rating(state, {
            "address": "1.2.3.4:8080",
            "last_status": "ok",
            "checks_total": 3,
            "checks_ok": 3,
            "last_latency": 0.5,
            "latency_avg": 0.6,
            "latency_sum": 1.8,
            "latency_count": 3,
        })
        state._load_state()
        r = state.ratings["1.2.3.4:8080"]
        assert r.latency_avg == 0.6
        assert r.latency_sum == 1.8
        assert r.latency_count == 3

    def test_load_state_repairs_inconsistent_sum(self, state, tmp_data_dir):
        _insert_rating(state, {
            "address": "1.2.3.4:8080",
            "last_status": "ok",
            "checks_total": 2,
            "checks_ok": 2,
            "last_latency": 0.5,
            "latency_avg": 0.7,
            "latency_sum": 0.1,
            "latency_count": 2,
        })
        state._load_state()
        r = state.ratings["1.2.3.4:8080"]
        assert r.latency_avg == 0.7
        assert r.latency_sum == 1.4

    def test_load_state_preserves_speed_history(self, state, tmp_data_dir):
        _insert_rating(state, {
            "address": "1.2.3.4:8080",
            "last_status": "ok",
            "checks_total": 2,
            "checks_ok": 2,
            "speed_sum": 200.0,
            "speed_count": 2,
            "speed_avg": 100.0,
        })
        state._load_state()
        r = state.ratings["1.2.3.4:8080"]
        assert r.speed_sum == 200.0
        assert r.speed_count == 2
        assert r.speed_avg == 100.0

    def test_save_state_roundtrip(self, state, tmp_data_dir):
        r = hunt.ProxyRating(address="1.2.3.4:8080", last_status="ok", checks_total=2, checks_ok=2)
        r.latency_sum = 1.2
        r.latency_count = 2
        r.speed_sum = 200.0
        r.speed_count = 2
        state.ratings["1.2.3.4:8080"] = r
        state._save_state()
        state2 = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state2._load_state()
        r2 = state2.ratings["1.2.3.4:8080"]
        assert r2.latency_sum == 1.2
        assert r2.latency_count == 2
        assert r2.speed_sum == 200.0
        assert r2.speed_count == 2

    def test_save_state_roundtrip_sqlite_primary(self, state, tmp_data_dir):
        r = hunt.ProxyRating(address="1.2.3.4:8080", last_status="ok", checks_total=2, checks_ok=2)
        r.latency_sum = 1.2
        r.latency_count = 2
        state.ratings["1.2.3.4:8080"] = r
        state.blacklist_add("9.9.9.9:8080", "bad actor")
        state._save_state()
        state2 = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state2._load_state()
        assert "1.2.3.4:8080" in state2.ratings
        assert state2.ratings["1.2.3.4:8080"].latency_sum == 1.2
        assert state2.ratings["1.2.3.4:8080"].latency_count == 2
        assert "9.9.9.9:8080" in state2.blacklist
        assert state2.blacklist["9.9.9.9:8080"] == "bad actor"


class TestWorkingFileLoading:
    def test_load_working_file_sets_latency_stats(self, state, tmp_data_dir):
        (tmp_data_dir / "working.txt").write_text("1.2.3.4:8080 US 0.66\n")
        state._load_working_file()
        r = state.ratings["1.2.3.4:8080"]
        assert r.last_latency == 0.66
        assert r.latency_sum == 0.66
        assert r.latency_count == 1
        assert r.latency_avg == 0.66
        assert r.checks_total == 1
        assert r.checks_ok == 1
        assert r.last_status == "ok"

    def test_load_working_file_skips_existing_ratings(self, state, tmp_data_dir):
        r = hunt.ProxyRating(address="1.2.3.4:8080", last_status="ok", checks_total=5, checks_ok=5)
        r.latency_sum = 3.0
        r.latency_count = 5
        state.ratings["1.2.3.4:8080"] = r
        (tmp_data_dir / "working.txt").write_text("1.2.3.4:8080 US 0.66\n")
        state._load_working_file()
        assert state.ratings["1.2.3.4:8080"].latency_count == 5

    def test_load_working_file_handles_invalid_latency(self, state, tmp_data_dir):
        (tmp_data_dir / "working.txt").write_text("1.2.3.4:8080 US bad\n")
        state._load_working_file()
        r = state.ratings["1.2.3.4:8080"]
        assert r.last_latency == 0.0
        assert r.latency_count == 1


class TestDirtyRatingsSave:
    def test_save_dirty_ratings_upserts_only_changed(self, state, tmp_data_dir):
        r1 = hunt.ProxyRating(address="1.2.3.4:8080", last_status="ok", checks_total=2, checks_ok=2)
        r1.latency_sum = 1.2
        r1.latency_count = 2
        r2 = hunt.ProxyRating(address="5.6.7.8:8080", last_status="ok", checks_total=1, checks_ok=1)
        r2.latency_sum = 0.5
        r2.latency_count = 1
        state.ratings["1.2.3.4:8080"] = r1
        state.ratings["5.6.7.8:8080"] = r2
        state._save_state()
        assert state._dirty_ratings == set()

        # Modify only r1; r2 stays unchanged in memory.
        r1.checks_total = 3
        r1.latency_sum = 1.8
        r1.latency_count = 3
        state._dirty_ratings.add("1.2.3.4:8080")
        state._save_dirty_ratings()
        assert state._dirty_ratings == set()

        # Reload from DB — only r1 should reflect the change, but both must exist.
        state2 = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state2._load_state()
        assert state2.ratings["1.2.3.4:8080"].checks_total == 3
        assert state2.ratings["1.2.3.4:8080"].latency_sum == 1.8
        assert state2.ratings["5.6.7.8:8080"].checks_total == 1

    def test_save_dirty_ratings_noop_on_empty(self, state, tmp_data_dir):
        state._save_dirty_ratings()
        assert state._dirty_ratings == set()

    def test_full_save_clears_dirty_set(self, state, tmp_data_dir):
        state.ratings["1.2.3.4:8080"] = hunt.ProxyRating(address="1.2.3.4:8080")
        state._dirty_ratings.add("1.2.3.4:8080")
        state._save_state()
        assert state._dirty_ratings == set()


class TestDbRecovery:
    def test_stats_db_recovers_after_file_deletion(self, state, tmp_data_dir):
        r = hunt.ProxyRating(address="1.2.3.4:8080", last_status="ok", checks_total=1, checks_ok=1)
        state.ratings["1.2.3.4:8080"] = r
        (tmp_data_dir / "stats.db").unlink()
        state._push_history()
        conn = sqlite3.connect(str(tmp_data_dir / "stats.db"))
        rows = conn.execute("SELECT alive FROM history").fetchall()
        conn.close()
        assert len(rows) == 1

    def test_state_db_recovers_after_file_deletion(self, state, tmp_data_dir):
        r = hunt.ProxyRating(address="1.2.3.4:8080", last_status="ok", checks_total=1, checks_ok=1)
        state.ratings["1.2.3.4:8080"] = r
        (tmp_data_dir / "state.db").unlink()
        state._save_state()
        conn = sqlite3.connect(str(tmp_data_dir / "state.db"))
        tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        conn.close()
        assert "ratings" in tables
        assert "blacklist" in tables
        assert "runtime_state" in tables


class TestStaleRevalidation:
    def test_revalidate_stale_proxies_from_working_file(self, state, tmp_data_dir):
        import asyncio
        wf = tmp_data_dir / "working.txt"
        wf.write_text("1.2.3.4:8080 US 0.66\n")
        state._load_working_file()
        r = state.ratings["1.2.3.4:8080"]
        # Make last_check old enough to be considered stale
        r.last_check = time.time() - 7200
        assert r.checks_total == 1
        asyncio.run(state._revalidate_stale_proxies())
        # The re-check will fail because 1.2.3.4 is unreachable, but it will
        # still increment the check counter and update the status.
        assert state.ratings["1.2.3.4:8080"].checks_total >= 2

    def test_revalidate_skips_fresh_proxies(self, state, tmp_data_dir):
        import asyncio
        r = hunt.ProxyRating(address="1.2.3.4:8080", last_status="ok", checks_total=1, checks_ok=1)
        r.last_check = time.time()
        state.ratings["1.2.3.4:8080"] = r
        asyncio.run(state._revalidate_stale_proxies())
        assert r.checks_total == 1

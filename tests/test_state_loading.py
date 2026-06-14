import json
import hunt


class TestStateLoading:
    def test_load_state_repairs_zero_latency_avg(self, state, tmp_data_dir):
        data = {
            "proxies": [
                {
                    "address": "1.2.3.4:8080",
                    "last_status": "ok",
                    "checks_total": 1,
                    "checks_ok": 1,
                    "last_latency": 0.66,
                    "latency_avg": 0.0,
                }
            ]
        }
        (tmp_data_dir / "ratings.json").write_text(json.dumps(data))
        state._load_state()
        r = state.ratings["1.2.3.4:8080"]
        assert r.latency_avg == 0.66
        assert r.latency_sum == 0.66
        assert r.latency_count == 1

    def test_load_state_uses_stored_latency_sum_and_count(self, state, tmp_data_dir):
        data = {
            "proxies": [
                {
                    "address": "1.2.3.4:8080",
                    "last_status": "ok",
                    "checks_total": 3,
                    "checks_ok": 3,
                    "last_latency": 0.5,
                    "latency_avg": 0.6,
                    "latency_sum": 1.8,
                    "latency_count": 3,
                }
            ]
        }
        (tmp_data_dir / "ratings.json").write_text(json.dumps(data))
        state._load_state()
        r = state.ratings["1.2.3.4:8080"]
        assert r.latency_avg == 0.6
        assert r.latency_sum == 1.8
        assert r.latency_count == 3

    def test_load_state_repairs_inconsistent_sum(self, state, tmp_data_dir):
        data = {
            "proxies": [
                {
                    "address": "1.2.3.4:8080",
                    "last_status": "ok",
                    "checks_total": 2,
                    "checks_ok": 2,
                    "last_latency": 0.5,
                    "latency_avg": 0.7,
                    "latency_sum": 0.1,
                    "latency_count": 2,
                }
            ]
        }
        (tmp_data_dir / "ratings.json").write_text(json.dumps(data))
        state._load_state()
        r = state.ratings["1.2.3.4:8080"]
        assert r.latency_avg == 0.7
        assert r.latency_sum == 1.4

    def test_load_state_preserves_speed_history(self, state, tmp_data_dir):
        data = {
            "proxies": [
                {
                    "address": "1.2.3.4:8080",
                    "last_status": "ok",
                    "checks_total": 2,
                    "checks_ok": 2,
                    "speed_sum": 200.0,
                    "speed_count": 2,
                    "speed_avg": 100.0,
                }
            ]
        }
        (tmp_data_dir / "ratings.json").write_text(json.dumps(data))
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

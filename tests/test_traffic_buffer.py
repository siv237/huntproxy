import sqlite3

import hunt


class TestTrafficBuffer:
    def _rows(self, n):
        return [(float(i), "1.2.3.4:1", "example.com", "ok", "direct", 10, 20, 0.5)
                for i in range(n)]

    def _count(self, state):
        conn = state._stats_db()
        n = conn.execute("SELECT COUNT(*) FROM traffic_log").fetchone()[0]
        conn.close()
        return n

    def test_rows_below_batch_wait_in_buffer(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        for row in self._rows(10):
            state._queue_traffic_log(row)
        assert len(state._traffic_buffer) == 10
        assert self._count(state) == 0
        state._flush_traffic_buffer()
        assert self._count(state) == 10
        assert state._traffic_buffer == []

    def test_full_batch_flushes_automatically(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        for row in self._rows(hunt.HuntState.TRAFFIC_FLUSH_BATCH + 7):
            state._queue_traffic_log(row)
        state.drain_db_writers()
        assert self._count(state) >= hunt.HuntState.TRAFFIC_FLUSH_BATCH
        state._flush_traffic_buffer()
        assert self._count(state) == hunt.HuntState.TRAFFIC_FLUSH_BATCH + 7

    def test_flush_empty_is_noop(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._flush_traffic_buffer()
        assert self._count(state) == 0

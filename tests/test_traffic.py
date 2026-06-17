import json
import pytest
import sqlite3

import hunt


def _json_response(response: bytes):
    """Parse raw HTTP/1.1 response body as JSON."""
    _, _, body = response.partition(b"\r\n\r\n")
    return json.loads(body.decode(errors="replace"))


class TestTrafficLog:
    def test_proxy_runner_log_uses_stats_db(self, state, tmp_data_dir):
        runner = hunt.ProxyRunner(state)
        runner._log(
            ("1.2.3.4", 12345),
            "http://example.com",
            "ok",
            "5.5.5.5:8080",
            bytes_in=100,
            bytes_out=200,
            duration=0.1,
        )
        conn = sqlite3.connect(str(tmp_data_dir / "stats.db"))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT target, status, bytes_in, bytes_out FROM traffic_log").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["target"] == "http://example.com"
        assert rows[0]["status"] == "ok"
        assert rows[0]["bytes_in"] == 100
        assert rows[0]["bytes_out"] == 200

        # traffic_log must NOT exist in the state business database
        conn2 = sqlite3.connect(str(tmp_data_dir / "state.db"))
        tables = {t[0] for t in conn2.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn2.close()
        assert "traffic_log" not in tables

    def test_socks5_runner_log_uses_stats_db(self, state, tmp_data_dir):
        runner = hunt.Socks5Runner(state)
        runner._log(
            ("1.2.3.4", 12345),
            "example.com:443",
            "ok",
            "5.5.5.5:1080",
            bytes_in=50,
            bytes_out=150,
            duration=0.2,
        )
        conn = sqlite3.connect(str(tmp_data_dir / "stats.db"))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT target, status FROM traffic_log").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["target"] == "example.com:443"

    def test_push_history_aggregates_traffic_log(self, state):
        runner = hunt.ProxyRunner(state)
        runner._log(None, "http://example.com/1", "ok", "5.5.5.5:8080", 100, 200, 0.1)
        runner._log(None, "http://example.com/2", "ok", "5.5.5.5:8080", 100, 200, 0.1)
        runner._log(None, "http://fail.com", "connect failed", "5.5.5.5:8080", 0, 0, 0.0)
        state._push_history()
        hist = state.get_history("1h")
        assert len(hist) == 1
        row = hist[-1]
        assert row["requests"] == 3
        assert row["connections_ok"] == 2
        assert row["connections_failed"] == 1
        assert row["bandwidth_in"] == 200
        assert row["bandwidth_out"] == 400


class TestApiTraffic:
    @pytest.mark.asyncio
    async def test_api_history_includes_traffic(self, http_client, api_server):
        _, state = api_server
        runner = hunt.ProxyRunner(state)
        runner._log(None, "http://example.com", "ok", "5.5.5.5:8080", 100, 200, 0.1)
        state._push_history()

        resp = await http_client("GET", "/api/history?last=1h")
        data = _json_response(resp)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[-1]["connections_ok"] == 1
        assert data[-1]["requests"] == 1

    @pytest.mark.asyncio
    async def test_api_bandwidth_reads_stats_db(self, http_client, api_server):
        _, state = api_server
        runner = hunt.ProxyRunner(state)
        runner._log(None, "http://example.com", "ok", "5.5.5.5:8080", 100, 200, 0.1)

        resp = await http_client("GET", "/api/bandwidth")
        data = _json_response(resp)
        assert data["incoming"] == 100
        assert data["outgoing"] == 200

    @pytest.mark.asyncio
    async def test_api_requests_reads_stats_db(self, http_client, api_server):
        _, state = api_server
        runner = hunt.ProxyRunner(state)
        runner._log(None, "http://example.com", "ok", "5.5.5.5:8080", 100, 200, 0.1)

        resp = await http_client("GET", "/api/requests")
        data = _json_response(resp)
        assert any(r["target"] == "http://example.com" for r in data["requests"])

    @pytest.mark.asyncio
    async def test_api_clients_reads_stats_db(self, http_client, api_server):
        _, state = api_server
        runner = hunt.ProxyRunner(state)
        runner._log(("1.2.3.4", 12345), "http://example.com", "ok", "5.5.5.5:8080", 100, 200, 0.1)

        resp = await http_client("GET", "/api/clients")
        data = _json_response(resp)
        assert any(c["client"] == "1.2.3.4:12345" for c in data["clients"])

    @pytest.mark.asyncio
    async def test_api_domains_reads_stats_db(self, http_client, api_server):
        _, state = api_server
        runner = hunt.ProxyRunner(state)
        runner._log(("1.2.3.4", 12345), "http://example.com", "ok", "5.5.5.5:8080", 100, 200, 0.1)

        resp = await http_client("GET", "/api/domains")
        data = _json_response(resp)
        assert any(d["domain"] == "example.com" for d in data["domains"])

    @pytest.mark.asyncio
    async def test_api_errors_reads_stats_db(self, http_client, api_server):
        _, state = api_server
        runner = hunt.ProxyRunner(state)
        runner._log(None, "http://example.com", "timeout", "5.5.5.5:8080", 0, 0, 0.0)

        resp = await http_client("GET", "/api/errors")
        data = _json_response(resp)
        assert data["total"] == 1
        assert any(e["type"] == "timeout" for e in data["errors"])

    @pytest.mark.asyncio
    async def test_api_traffic_live_reads_totals(self, http_client, api_server):
        _, state = api_server
        runner = hunt.ProxyRunner(state)
        runner._log(None, "http://example.com/1", "ok", "5.5.5.5:8080", 100, 200, 0.1)
        runner._log(None, "http://example.com/2", "ok", "5.5.5.5:8080", 300, 400, 0.1)

        resp = await http_client("GET", "/api/traffic/live")
        data = _json_response(resp)
        assert data["in_bytes"] == 400
        assert data["out_bytes"] == 600
        assert data["total_bytes"] == 1000
        assert data["requests"] == 2

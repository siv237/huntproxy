import json
import pytest
import sqlite3
import time

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
        assert data["upload"] == 100   # bytes_in = client→upstream = upload
        assert data["download"] == 200  # bytes_out = upstream→client = download

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


class TestTrafficMemFallback:
    """When the stats DB has no rows, traffic widgets must fall back to the
    in-memory proxy log so the Traffic Monitor stays populated."""

    def _server(self, state):
        return hunt.HuntServer(state, "127.0.0.1", 0)

    def _mem_entry(self, upstream, status="ok", bin_=100, bout=200, dur=0.1):
        return {
            "ts": time.time(),
            "client": "1.2.3.4:12345",
            "target": "http://example.com",
            "status": status,
            "upstream": upstream,
            "bytes_in": bin_,
            "bytes_out": bout,
            "duration": dur,
        }

    @pytest.mark.asyncio
    async def test_traffic_routes_fallback_to_mem(self, state):
        server = self._server(state)
        server.proxy.log = [
            self._mem_entry("proxy:5.5.5.5:8080"),
            self._mem_entry("direct"),
        ]
        resp, status, _ = await server._route("GET", "/api/traffic/routes", "/api/traffic/routes", b"")
        assert status == 200
        data = json.loads(resp)
        types = {r["type"] for r in data["routes"]}
        assert "proxy" in types
        assert "direct" in types
        assert sum(r["requests"] for r in data["routes"]) == 2

    @pytest.mark.asyncio
    async def test_bandwidth_fallback_to_mem(self, state):
        server = self._server(state)
        server.proxy.log = [
            self._mem_entry("proxy:5.5.5.5:8080", bin_=100, bout=200),
            self._mem_entry("direct", bin_=50, bout=150),
        ]
        resp, status, _ = await server._route("GET", "/api/bandwidth", "/api/bandwidth", b"")
        assert status == 200
        data = json.loads(resp)
        assert data["upload"] == 150
        assert data["download"] == 350
        assert data["total"] == 500

    @pytest.mark.asyncio
    async def test_traffic_summary_fallback_to_mem(self, state):
        server = self._server(state)
        server.proxy.log = [
            self._mem_entry("proxy:5.5.5.5:8080", status="ok"),
            self._mem_entry("direct", status="connect failed", bin_=0, bout=0),
        ]
        resp, status, _ = await server._route("GET", "/api/traffic/summary", "/api/traffic/summary", b"")
        assert status == 200
        data = json.loads(resp)
        day = data["day"]
        assert day["requests"] == 2
        assert day["success"] == 1
        assert day["failed"] == 1
        assert day["total"] == 300
        assert day["top_routes"]  # populated from memory
        # week/month must NOT reuse the recent in-memory snapshot as a period total
        assert data["week"]["requests"] == 0
        assert data["month"]["requests"] == 0

    @pytest.mark.asyncio
    async def test_route_type_classification(self, state):
        from hunt.handlers.traffic import TrafficHandlers
        th = TrafficHandlers(state, None)
        assert th._route_type("direct") == "direct"
        assert th._route_type("proxy:1.2.3.4:8080") == "proxy"
        assert th._route_type("pool:9.9.9.9:1080") == "pool"
        assert th._route_type("custom:myproxy") == "custom"
        assert th._route_type("") == "other"
        assert th._route_type("?") == "other"
        assert th._route_type("unknown") == "other"


class TestSwitchHistoryEnrichment:
    """enrich_switch_history must aggregate real traffic_log upstream
    format (proxy:ADDR / pool:ADDR) and collapse consecutive duplicates."""

    def _seed_traffic(self, state, upstream, bytes_in, bytes_out, ts):
        conn = state._stats_db()
        conn.execute(
            "INSERT INTO traffic_log (ts, client, target, status, upstream, "
            "bytes_in, bytes_out, duration) VALUES (?,?,?,?,?,?,?,?)",
            (ts, "1.2.3.4:0", "example.com", "ok", upstream, bytes_in, bytes_out, 0.1),
        )
        conn.commit()
        conn.close()

    def test_enrich_aggregates_traffic_for_period(self, state):
        from hunt.switch_history import enrich_switch_history
        now = time.time()
        addr = "5.5.5.5:8080"
        state._proxy_switch_history.append({"ts": now - 100, "action": "select", "address": addr})
        self._seed_traffic(state, "proxy:" + addr, 100, 200, now - 50)
        self._seed_traffic(state, "pool:" + addr, 50, 70, now - 10)
        rows = enrich_switch_history(state)
        assert len(rows) == 1
        assert rows[0]["address"] == addr
        assert rows[0]["bytes"] == 420  # 100+200+50+70
        assert rows[0]["duration_sec"] >= 99

    def test_enrich_separates_addresses_no_substring_collision(self, state):
        from hunt.switch_history import enrich_switch_history
        now = time.time()
        a1, a2 = "1.2.3.4:80", "11.2.3.4:80"
        state._proxy_switch_history.append({"ts": now - 200, "action": "select", "address": a1})
        state._proxy_switch_history.append({"ts": now - 100, "action": "select", "address": a2})
        self._seed_traffic(state, "proxy:" + a1, 10, 20, now - 150)
        self._seed_traffic(state, "proxy:" + a2, 5, 7, now - 50)
        rows = enrich_switch_history(state)
        assert len(rows) == 2
        by_addr = {r["address"]: r for r in rows}
        assert by_addr[a1]["bytes"] == 30
        assert by_addr[a2]["bytes"] == 12

    def test_enrich_collapses_consecutive_duplicates(self, state):
        from hunt.switch_history import enrich_switch_history
        now = time.time()
        addr = "9.9.9.9:1080"
        state._proxy_switch_history.append({"ts": now - 300, "action": "select", "address": addr})
        state._proxy_switch_history.append({"ts": now - 200, "action": "select", "address": addr})
        state._proxy_switch_history.append({"ts": now - 100, "action": "select", "address": addr})
        rows = enrich_switch_history(state)
        assert len(rows) == 1
        assert rows[0]["address"] == addr

    def test_enrich_empty_history(self, state):
        from hunt.switch_history import enrich_switch_history
        assert enrich_switch_history(state) == []

    def test_enrich_zero_traffic_when_no_log_rows(self, state):
        from hunt.switch_history import enrich_switch_history
        now = time.time()
        state._proxy_switch_history.append({"ts": now - 100, "action": "select", "address": "7.7.7.7:3128"})
        rows = enrich_switch_history(state)
        assert len(rows) == 1
        assert rows[0]["bytes"] == 0

    def test_get_status_switch_history_enriched(self, state):
        runner = hunt.ProxyRunner(state)
        now = time.time()
        addr = "5.5.5.5:8080"
        state._proxy_switch_history.append({"ts": now - 100, "action": "select", "address": addr})
        self._seed_traffic(state, "proxy:" + addr, 100, 200, now - 50)
        status = runner.get_status()
        assert isinstance(status["switch_history"], list)
        assert len(status["switch_history"]) == 1
        assert status["switch_history"][0]["bytes"] == 300


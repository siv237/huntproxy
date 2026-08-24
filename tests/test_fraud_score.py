import asyncio
import json
import sqlite3

import hunt
from hunt.fraudscore import FraudScoreMixin


def _http_body(payload: dict) -> bytes:
    body = json.dumps(payload).encode()
    return b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + body


class TestParseFraudPayload:
    def test_parses_risk_score_and_flags(self):
        buf = _http_body({"status": "ok", "1.2.3.4": {
            "proxy": "yes", "type": "VPN", "risk": 75, "asn": "AS123"}})
        out = FraudScoreMixin._parse_fraud_payload(buf)
        assert out["provider"] == "proxycheck"
        assert out["score"] == 75
        assert out["proxy"] is True
        assert out["type"] == "VPN"

    def test_float_risk_rounded_to_int(self):
        buf = _http_body({"status": "ok", "1.2.3.4": {"risk": 33.6}})
        out = FraudScoreMixin._parse_fraud_payload(buf)
        assert out["score"] == 34

    def test_risk_out_of_range_dropped(self):
        buf = _http_body({"status": "ok", "1.2.3.4": {"risk": 150}})
        out = FraudScoreMixin._parse_fraud_payload(buf)
        assert "score" not in out
        assert out["provider"] == "proxycheck"

    def test_error_status_empty(self):
        buf = _http_body({"status": "error", "message": "quota"})
        assert FraudScoreMixin._parse_fraud_payload(buf) == {}

    def test_no_headers_empty(self):
        assert FraudScoreMixin._parse_fraud_payload(b"garbage") == {}

    def test_invalid_json_empty(self):
        buf = b"HTTP/1.1 200 OK\r\n\r\n{not json"
        assert FraudScoreMixin._parse_fraud_payload(buf) == {}


class TestFraudScoreModel:
    def test_raw_service_score_takes_priority(self):
        r = hunt.ProxyRating(address="1.2.3.4:80")
        r.fraud_checked_ts = 1.0
        r.fraud_hosting = True
        assert r.fraud_score == 40
        r.fraud_score_raw = 66
        assert r.fraud_score == 66

    def test_unknown_when_never_checked(self):
        r = hunt.ProxyRating(address="1.2.3.4:80")
        assert r.fraud_score == -1
        assert r.fraud_verdict == "UNKNOWN"

    def test_fallback_flag_weights_gradations(self):
        cases = [
            (dict(), 0, "CLEAN"),
            (dict(fraud_mobile=True), 20, "MOBILE"),
            (dict(fraud_hosting=True), 40, "DC"),
            (dict(fraud_proxy=True), 70, "PROXY"),
            (dict(fraud_mobile=True, fraud_hosting=True), 60, "DC"),
            (dict(fraud_hosting=True, fraud_proxy=True), 100, "PROXY"),
        ]
        for flags, score, verdict in cases:
            r = hunt.ProxyRating(address="1.2.3.4:80", fraud_checked_ts=1.0, **flags)
            assert r.fraud_score == score, flags
            assert r.fraud_verdict == verdict, flags

    def test_verdict_bands_on_raw_scale(self):
        bands = [(0, "CLEAN"), (14, "CLEAN"), (15, "MOBILE"), (34, "MOBILE"),
                 (35, "DC"), (64, "DC"), (65, "PROXY"), (100, "PROXY")]
        for score, verdict in bands:
            r = hunt.ProxyRating(address="1.2.3.4:80", fraud_score_raw=score,
                                 fraud_checked_ts=1.0)
            assert r.fraud_score == score
            assert r.fraud_verdict == verdict, score


class TestApplyFraud:
    def test_update_rating_applies_raw_score(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._update_rating(
            "1.2.3.4:8080", ok=True, country="US", latency=0.5,
            fraud={"provider": "proxycheck", "score": 82, "proxy": True},
        )
        r = state.ratings["1.2.3.4:8080"]
        assert r.fraud_score_raw == 82
        assert r.fraud_score == 82
        assert r.fraud_verdict == "PROXY"
        assert r.fraud_proxy is True
        assert r.fraud_checked_ts > 0

    def test_apply_fraud_ignores_garbage(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._update_rating(
            "1.2.3.4:8080", ok=True, country="US", latency=0.5,
            fraud={"provider": "proxycheck"},
        )
        r = state.ratings["1.2.3.4:8080"]
        assert r.fraud_score_raw == -1


class TestFraudPersistence:
    def test_fraud_fields_survive_restart(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._update_rating(
            "1.2.3.4:8080", ok=True, country="US", latency=0.5,
            egress={"egress_ip": "5.6.7.8", "egress_hosting": True,
                    "egress_proxy": False, "egress_mobile": True},
            fraud={"provider": "proxycheck", "score": 47},
        )
        state._save_state()

        restored = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        r = restored.ratings["1.2.3.4:8080"]
        assert r.fraud_score_raw == 47
        assert r.fraud_score == 47
        assert r.fraud_hosting is True
        assert r.fraud_mobile is True
        assert r.fraud_proxy is False
        assert r.fraud_checked_ts > 0

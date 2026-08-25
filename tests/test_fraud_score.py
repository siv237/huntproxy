import asyncio
import json
import sqlite3
import time

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

    def test_error_status_empty(self):
        buf = _http_body({"status": "error", "message": "quota"})
        assert FraudScoreMixin._parse_fraud_payload(buf) == {}

    def test_no_headers_empty(self):
        assert FraudScoreMixin._parse_fraud_payload(b"garbage") == {}

    def test_json_between_extra_noise(self):
        buf = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" \
              b"ff\r\n{\"status\": \"ok\", \"1.2.3.4\": {\"risk\": 88}}\r\n0\r\n\r\n"
        out = FraudScoreMixin._parse_fraud_payload(buf)
        assert out["score"] == 88


class TestFraudScoreModel:
    def test_exact_number_from_fresh_flags(self):
        r = hunt.ProxyRating(address="1.2.3.4:80",
                             fraud_checked_ts=time.time())
        assert not r.fraud_failcheck
        assert r.fraud_score == 0
        assert r.fraud_verdict == "CLEAN"

    def test_failcheck_when_never_checked(self):
        r = hunt.ProxyRating(address="1.2.3.4:80")
        assert r.fraud_failcheck is True
        assert r.fraud_score == 100
        assert r.fraud_verdict == "FAILCHECK"

    def test_failcheck_when_flags_stale(self):
        stale = time.time() - hunt.ProxyRating.FRAUD_FRESH_SECONDS - 1
        r = hunt.ProxyRating(address="1.2.3.4:80", fraud_proxy=True,
                             fraud_checked_ts=stale)
        assert r.fraud_failcheck
        assert r.fraud_score == 100
        assert r.fraud_verdict == "FAILCHECK"

    def test_flag_weights_gradations(self):
        cases = [
            (dict(), 0, "CLEAN"),
            (dict(fraud_mobile=True), 20, "MOBILE"),
            (dict(fraud_hosting=True), 40, "DC"),
            (dict(fraud_proxy=True), 70, "PROXY"),
            (dict(fraud_mobile=True, fraud_hosting=True), 60, "DC"),
            (dict(fraud_hosting=True, fraud_proxy=True), 100, "PROXY"),
        ]
        for flags, score, verdict in cases:
            r = hunt.ProxyRating(address="1.2.3.4:80",
                                 fraud_checked_ts=time.time(), **flags)
            assert r.fraud_score == score, flags
            assert r.fraud_verdict == verdict, flags


class TestApplyFraud:
    def test_update_rating_egress_stamps_fresh_reading(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._update_rating(
            "1.2.3.4:8080", ok=True, country="US", latency=0.5,
            egress={"egress_ip": "5.6.7.8", "egress_hosting": False,
                    "egress_proxy": False, "egress_mobile": False},
        )
        r = state.ratings["1.2.3.4:8080"]
        assert not r.fraud_failcheck
        assert r.fraud_score == 0
        assert r.fraud_checked_ts > 0

    def test_apply_fraud_keeps_proxycheck_as_info_only(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._update_rating(
            "1.2.3.4:8080", ok=True, country="US", latency=0.5,
            egress={"egress_ip": "5.6.7.8", "egress_hosting": False,
                    "egress_proxy": False, "egress_mobile": False},
            fraud={"provider": "proxycheck", "score": 100, "proxy": True},
        )
        r = state.ratings["1.2.3.4:8080"]
        assert r.fraud_score_raw == 100
        assert r.fraud_score == 0
        assert r.fraud_verdict == "CLEAN"


class TestFraudPersistence:
    def test_fraud_fields_survive_restart(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._update_rating(
            "1.2.3.4:8080", ok=True, country="US", latency=0.5,
            egress={"egress_ip": "5.6.7.8", "egress_hosting": True,
                    "egress_proxy": False, "egress_mobile": True},
        )
        state._save_state()

        restored = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        r = restored.ratings["1.2.3.4:8080"]
        assert not r.fraud_failcheck
        assert r.fraud_score == 60
        assert r.fraud_hosting is True
        assert r.fraud_mobile is True
        assert r.fraud_proxy is False
        assert r.fraud_checked_ts > 0

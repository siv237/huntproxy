import asyncio
import pytest
import hunt


class TestCheckSsl:
    def test_check_ssl_refused_port(self):
        async def run():
            state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
            ok, country, country_code, egress, latency, supports_connect = await state._check_ssl("127.0.0.1:1")
            assert ok is False
            assert country == ""
            assert country_code == ""
            assert egress == {}
            assert latency == 0.0
            assert supports_connect is False

        asyncio.run(run())

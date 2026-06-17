import asyncio
import pytest
import hunt


class TestHealthCheckRestoreProgress:
    """Manual recheck via _health_check must pause the running hunt and restore
    its progress counters and phase after completion."""

    def test_health_check_restores_hunt_progress(self, state):
        async def run():
            # Simulate a hunt that has downloaded sources and is validating.
            state.phase = state.PHASE_VALIDATE
            state.phase_started = 1000000.0
            state.downloaded = 100
            state.checking_total = 200
            state.checked = 150
            state.working = 60
            state.failed = 40
            state.last_proxy = "5.6.7.8:8080"
            state.last_country = "United States"

            # Mock _check_proxy and _check_ssl so _health_check completes quickly.
            async def fake_check_proxy(addr):
                return (True, "US", True, False, {}, {}, 0.1, "US", False)

            async def fake_check_ssl(addr):
                return (False, "", "", {}, 0.0, False)

            async def fake_measure_speed(host, port, is_socks, **kwargs):
                return 0.0

            state._check_proxy = fake_check_proxy
            state._check_ssl = fake_check_ssl
            state._measure_speed = fake_measure_speed

            # Add one alive candidate so _health_check has work to do.
            from hunt.models import ProxyRating
            r = ProxyRating(
                address="1.2.3.4:8080",
                last_status="ok",
                latency_sum=1.0,
                latency_count=1,
                checks_total=1,
                checks_ok=1,
            )
            state.ratings[r.address] = r

            await state._health_check()

            # After completion, counters and phase must be restored.
            assert state.phase == state.PHASE_VALIDATE
            assert state.phase_started == 1000000.0
            assert state.downloaded == 100
            assert state.checking_total == 200
            assert state.checked == 150
            assert state.working == 60
            assert state.failed == 40
            assert state.last_proxy == "5.6.7.8:8080"
            assert state.last_country == "United States"

        asyncio.run(run())

    def test_health_check_resets_progress_when_no_main_hunt(self, state):
        """When no hunt is running, counters should not be restored to garbage."""
        async def run():
            state.phase = state.PHASE_DONE
            state.checking_total = 0
            state.checked = 0

            async def fake_check_proxy(addr):
                return (True, "US", True, False, {}, {}, 0.1, "US", False)

            async def fake_check_ssl(addr):
                return (False, "", "", {}, 0.0, False)

            async def fake_measure_speed(host, port, is_socks, **kwargs):
                return 0.0

            state._check_proxy = fake_check_proxy
            state._check_ssl = fake_check_ssl
            state._measure_speed = fake_measure_speed

            from hunt.models import ProxyRating
            r = ProxyRating(
                address="1.2.3.4:8080",
                last_status="ok",
                latency_sum=1.0,
                latency_count=1,
                checks_total=1,
                checks_ok=1,
            )
            state.ratings[r.address] = r

            await state._health_check()

            # After completion, counters restored to PHASE_DONE state.
            assert state.phase == state.PHASE_DONE
            assert state.checking_total == 0

        asyncio.run(run())

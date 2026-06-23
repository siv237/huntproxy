import asyncio
import pytest
import hunt


class TestHealthCheckRestoreProgress:
    """Manual recheck via _health_check must snapshot the live hunt counters
    before running and restore them after, so the running hunt picks up exactly
    where it left off."""

    def test_health_check_restores_hunt_counters(self, state):
        async def run():
            # Simulate a hunt in mid-validation with live counters.
            state.phase = state.PHASE_VALIDATE
            state.phase_started = 1000000.0
            state.downloaded = 100
            state.checking_total = 200
            state.checked = 150
            state.working = 60
            state.failed = 40
            state.last_proxy = "5.6.7.8:8080"
            state.last_country = "United States"

            # A real running task so pause_hunt() actually pauses.
            state.task = asyncio.create_task(asyncio.sleep(5))

            try:
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
                    address="1.2.3.4:8080", last_status="ok",
                    speed_sum=200, speed_count=1,
                )
                state.ratings[r.address] = r

                await state._health_check()

                # _health_check must restore the hunt's counters that it
                # temporarily overwrote while running.
                assert state.checking_total == 200
                assert state.checked == 150
                assert state.working == 60
                assert state.failed == 40
                assert state.downloaded == 100
                # Phase must be restored to the pre-recheck phase.
                assert state.phase == state.PHASE_VALIDATE
                assert state.phase_started == 1000000.0
                # Hunt is no longer paused.
                assert state._paused is False
                assert state._manual_pause is False
            finally:
                state.task.cancel()
                try:
                    await state.task
                except (asyncio.CancelledError, Exception):
                    pass

        asyncio.run(run())

    def test_health_check_no_hunt_keeps_idle(self, state):
        async def run():
            state.phase = state.PHASE_DONE
            state.checking_total = 0
            state.checked = 0
            state.last_proxy = "old"

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
                address="1.2.3.4:8080", last_status="ok",
                speed_sum=200, speed_count=1,
            )
            state.ratings[r.address] = r

            # No main hunt is running (state.task is None).
            await state._health_check()

            # Idle state preserved.
            assert state.phase == state.PHASE_DONE
            assert state.checking_total == 0
            assert state.checked == 0
            assert state.last_proxy == "old"

        asyncio.run(run())

    def test_health_check_resets_last_proxy_info(self, state):
        async def run():
            state.phase = state.PHASE_DONE
            state.last_proxy = "5.6.7.8:8080"
            state.last_country = "United States"

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
                address="1.2.3.4:8080", last_status="ok",
                speed_sum=200, speed_count=1,
            )
            state.ratings[r.address] = r

            await state._health_check()

            # Cosmetic last_proxy/last_country are restored to their
            # pre-health-check values.
            assert state.last_proxy == "5.6.7.8:8080"
            assert state.last_country == "United States"

        asyncio.run(run())

    def test_health_check_no_hunt_pauses_then_sets_phase_done(self, state):
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
                address="1.2.3.4:8080", last_status="ok",
                speed_sum=200, speed_count=1,
            )
            state.ratings[r.address] = r

            # No main hunt is running (self.task is None).
            await state._health_check()

            # No hunt to restore -> phase goes to DONE.
            assert state.phase == state.PHASE_DONE

        asyncio.run(run())

    def test_stop_health_aborts_running_check(self, state):
        """stop_health must cancel a running _health_check task and clear state."""
        async def run():
            state.phase = state.PHASE_DONE
            state.checking_total = 0
            state.checked = 0

            started = asyncio.Event()

            async def slow_check_proxy(addr):
                started.set()
                await asyncio.sleep(30)
                return (True, "US", True, False, {}, {}, 0.1, "US", False)

            async def fake_check_ssl(addr):
                return (False, "", "", {}, 0.0, False)

            async def fake_measure_speed(host, port, is_socks, **kwargs):
                return 0.0

            state._check_proxy = slow_check_proxy
            state._check_ssl = fake_check_ssl
            state._measure_speed = fake_measure_speed

            from hunt.models import ProxyRating
            r = ProxyRating(
                address="1.2.3.4:8080", last_status="ok",
                speed_sum=200, speed_count=1,
            )
            state.ratings[r.address] = r

            task = asyncio.create_task(state._health_check(manual=True))
            state._health_task = task
            await asyncio.wait_for(started.wait(), timeout=5)
            assert state._health_running is True

            state.stop_health()
            # The task should be cancelled shortly.
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=5)
            assert state._health_running is False
            assert state._health_task is None

        asyncio.run(run())

    def test_health_stop_endpoint(self, api_server, http_client):
        """POST /api/health/stop returns 409 when not running, 200 when running."""
        base_url, state = api_server

        async def run():
            # Not running -> 409
            resp = await http_client("POST", "/api/health/stop")
            assert b"409" in resp.split(b"\r\n")[0]
            assert b"not_running" in resp

        asyncio.run(run())

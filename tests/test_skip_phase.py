import asyncio
import pytest
import hunt
from hunt.models import ProxyRating


class TestSkipPhase:
    def test_skip_phase_rejected_when_idle(self, state):
        # No running task → nothing to skip.
        assert state.skip_phase() is False
        assert state._skip_requested is False

    def test_skip_phase_accepted_for_skippable_phases(self, state):
        async def run():
            state.task = asyncio.create_task(asyncio.sleep(5))
            try:
                for ph in (state.PHASE_DOWNLOAD, state.PHASE_BLACKLIST, state.PHASE_VALIDATE):
                    state._skip_requested = False
                    state._skip_event.clear()
                    state.phase = ph
                    assert state.skip_phase() is True
                    assert state._skip_requested is True
                    assert state._skip_event.is_set()
                    state._reset_skip()
                # Non-skippable phase (health) is rejected.
                state.phase = state.PHASE_HEALTH
                assert state.skip_phase() is False
            finally:
                state.task.cancel()
                try:
                    await state.task
                except (asyncio.CancelledError, Exception):
                    pass

        asyncio.run(run())

    def test_gather_skip_aware_aborts_on_skip(self, state):
        async def run():
            state._reset_skip()
            started = asyncio.Event()

            async def slow():
                started.set()
                await asyncio.sleep(10)
                return "done"

            tasks = [asyncio.create_task(slow())]
            # Schedule a skip shortly after the gather starts.
            async def trigger():
                await started.wait()
                await asyncio.sleep(0)
                state._skip_event.set()
                state._skip_requested = True

            trig = asyncio.create_task(trigger())
            result = await state._gather_skip_aware(tasks)
            assert result == []
            assert state._skip_requested is False
            assert state._skip_event.is_set() is False
            for t in tasks:
                assert t.done()
            trig.cancel()
            try:
                await trig
            except (asyncio.CancelledError, Exception):
                pass

        asyncio.run(run())

    def test_gather_skip_aware_returns_results_without_skip(self, state):
        async def run():
            state._reset_skip()

            async def value(x):
                return x

            tasks = [asyncio.create_task(value(1)), asyncio.create_task(value(2))]
            result = await state._gather_skip_aware(tasks)
            assert result == [1, 2]
            assert state._skip_requested is False

        asyncio.run(run())


class TestWorkingCounters:
    def test_validate_splits_new_and_confirmed(self, state):
        async def run():
            # An already-known working proxy → "confirmed" when re-validated.
            known = ProxyRating(address="1.1.1.1:8080", last_status="ok")
            known.checks_ok = 3
            state.ratings["1.1.1.1:8080"] = known

            async def fake_check_proxy(addr):
                return (True, "US", True, False, {}, {}, 0.1, "US", False)

            async def fake_check_ssl(addr):
                return (False, "", "", {}, 0.0, False)

            async def fake_measure_speed(host, port, is_socks, **kwargs):
                return 0.0

            state._check_proxy = fake_check_proxy
            state._check_ssl = fake_check_ssl
            state._measure_speed = fake_measure_speed
            state.parallel = 4
            state.timeout = 2
            state.checking_total = 2
            state.new_working = 0
            state.confirmed_working = 0

            # "1.1.1.1:8080" is known-good (confirmed); "9.9.9.9:8080" is new.
            await state._validate_all({"1.1.1.1:8080", "9.9.9.9:8080"})

            assert state.working == 2
            assert state.new_working == 1
            assert state.confirmed_working == 1

        asyncio.run(run())

    def test_snapshot_exposes_working_counters(self, state):
        state.new_working = 2
        state.confirmed_working = 5
        snap = state.get_snapshot()
        assert snap["progress"]["new_working"] == 2
        assert snap["progress"]["confirmed_working"] == 5
        assert snap["progress"]["working"] == 0

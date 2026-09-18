import asyncio
import time

import hunt
from hunt.scheduler import SchedulerEngine
from hunt.schedule_entry import TASK_TYPES


class TestSchedulerAtomicLaunch:
    """A task_type must never be launched twice by concurrent drains.

    Passing the "already running" check and registering the task in
    _running_tasks used to be separated by an await (is_internet_alive), so
    two concurrent drains could both launch the same task — the root cause of
    duplicated proxy_check runs double-counting progress (200%).
    """

    def test_two_concurrent_drains_launch_once(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()

            async def slow_internet_up():
                await asyncio.sleep(0.05)
                return True
            state.is_internet_alive = slow_internet_up

            launched = []

            async def fake_proxy_check(s, entry):
                launched.append(entry.id)
                await asyncio.sleep(0.05)

            sched.executor.register("proxy_check", fake_proxy_check)
            sched._enqueue("proxy_check")

            await asyncio.gather(sched._drain_queue(), sched._drain_queue())
            await asyncio.sleep(0.15)

            assert launched == ["proxy_check"], (
                f"proxy_check launched {len(launched)} times — atomic launch broken"
            )
            await sched.stop()

        asyncio.run(run())


class TestSchedulerCancelAll:
    def test_cancel_all_stops_running_and_clears_queue(self, state):
        async def run():
            sched = SchedulerEngine(state)
            sched._running_tasks["health_check"] = asyncio.create_task(asyncio.sleep(30))
            sched._queue["proxy_check"] = time.time()

            cancelled = await sched.cancel_all("test")

            assert cancelled == ["health_check"]
            assert sched._running_tasks == {}
            assert sched._queue == {}

        asyncio.run(run())


class TestSchedulerInternetGate:
    def test_down_pauses_and_cancels_checks(self, state):
        async def run():
            sched = SchedulerEngine(state)

            async def down():
                return False
            state.is_internet_alive = down
            sched._running_tasks["proxy_check"] = asyncio.create_task(asyncio.sleep(30))

            await sched._internet_gate()

            assert sched.is_paused() is True
            assert sched._paused_by_internet is True
            assert "proxy_check" not in sched._running_tasks, (
                "running network-check task must be cancelled while offline"
            )

            async def up():
                return True
            state.is_internet_alive = up
            await sched._internet_gate()

            assert sched.is_paused() is False
            assert sched._paused_by_internet is False

        asyncio.run(run())

    def test_gate_does_not_override_manual_pause(self, state):
        async def run():
            sched = SchedulerEngine(state)

            async def down():
                return False
            state.is_internet_alive = down
            sched.pause_all()

            await sched._internet_gate()

            assert sched.is_paused() is True
            assert sched._paused_by_internet is False

        asyncio.run(run())

    def test_health_check_blocked_during_hunt(self):
        assert TASK_TYPES["health_check"].get("busy_flag") == "_hunt_running"


class TestManualStartHunt:
    """The Start Hunt button is authoritative: interrupt everything, reset
    counters and start a fresh exclusive hunt."""

    def _stub_downloads(self, state):
        async def empty_sources():
            return set()

        async def empty_map():
            return {}

        state._download_sources = empty_sources
        state._download_ip_blacklists = empty_map
        state._download_blocklists = empty_map

    def test_interrupts_resets_and_restarts(self, state):
        async def run():
            self._stub_downloads(state)
            sched = SchedulerEngine(state)
            await sched.prepare()
            state.scheduler = sched
            sched._running_tasks["proxy_check"] = asyncio.create_task(asyncio.sleep(30))

            # A desynced previous run.
            state.phase = state.PHASE_IDLE
            state.checking_total = 100
            state.checked = 250
            state.failed = 7

            ok = await state.manual_start_hunt()

            assert ok is True
            assert sched.is_paused() is True
            assert state._scheduler_paused_by_hunt is True
            assert "proxy_check" not in sched._running_tasks
            assert state.checked == 0
            assert state.checking_total == 0
            assert state.failed == 0
            assert state._hunt_running is True

            # The stubbed hunt finishes immediately and releases the pause.
            await asyncio.wait_for(state.task, timeout=5)
            assert state._scheduler_paused_by_hunt is False
            assert sched.is_paused() is False
            await sched.stop()

        asyncio.run(run())

    def test_refuses_when_offline(self, state):
        async def run():
            async def down():
                return False
            state.is_internet_alive = down

            ok = await state.manual_start_hunt()

            assert ok is False
            assert state._hunt_running is False

        asyncio.run(run())

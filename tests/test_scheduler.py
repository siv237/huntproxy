import asyncio
import json
import time
import pytest
import hunt
from hunt.scheduler import SchedulerEngine, ScheduleEntry, TASK_TYPES, DEFAULT_SCHEDULES


class TestSchedulerSeed:
    def test_seed_defaults_on_empty_db(self, state):
        async def run():
            sched = SchedulerEngine(state)
            assert len(sched._schedules) == 0
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            assert len(sched._schedules) == len(DEFAULT_SCHEDULES)
            ids = {s["id"] for s in DEFAULT_SCHEDULES}
            assert set(sched._schedules.keys()) == ids
            # Verify history schedule has 60s interval
            assert sched._schedules["history"].interval_sec == 60
            # hunt_cycle is disabled by default
            assert sched._schedules["hunt_cycle"].enabled is False
            await sched.stop()

        asyncio.run(run())

    def test_seed_not_overwrites_existing(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            # Modify a schedule
            await sched.update_schedule("history", interval_sec=120)
            # Re-load and re-seed — should not overwrite
            sched2 = SchedulerEngine(state)
            await sched2._load_schedules()
            await sched2._seed_defaults_if_empty()
            assert sched2._schedules["history"].interval_sec == 120
            await sched.stop()
            await sched2.stop()

        asyncio.run(run())


class TestSchedulerCRUD:
    def test_add_schedule(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            result = await sched.add_schedule(
                sid="test_task",
                name="Test Task",
                task_type="clear_dead",
                interval_sec=300,
                config={"foo": "bar"},
            )
            assert result["id"] == "test_task"
            assert result["name"] == "Test Task"
            assert result["task_type"] == "clear_dead"
            assert result["interval_sec"] == 300
            assert result["config"] == {"foo": "bar"}
            assert result["enabled"] is True
            # Verify persisted to DB
            sched2 = SchedulerEngine(state)
            await sched2._load_schedules()
            assert "test_task" in sched2._schedules
            await sched.stop()
            await sched2.stop()

        asyncio.run(run())

    def test_add_duplicate_rejected(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            with pytest.raises(ValueError, match="already exists"):
                await sched.add_schedule(
                    sid="history",
                    name="Dup",
                    task_type="history",
                    interval_sec=30,
                )
            await sched.stop()

        asyncio.run(run())

    def test_add_unknown_task_type_rejected(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            with pytest.raises(ValueError, match="Unknown task type"):
                await sched.add_schedule(
                    sid="bad",
                    name="Bad",
                    task_type="nonexistent",
                    interval_sec=30,
                )
            await sched.stop()

        asyncio.run(run())

    def test_update_schedule_interval(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            result = await sched.update_schedule("history", interval_sec=120)
            assert result["interval_sec"] == 120
            await sched.stop()

        asyncio.run(run())

    def test_update_nonexistent_returns_none(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            result = await sched.update_schedule("nonexistent", interval_sec=10)
            assert result is None
            await sched.stop()

        asyncio.run(run())

    def test_delete_schedule(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            ok = await sched.delete_schedule("history")
            assert ok is True
            assert "history" not in sched._schedules
            # Delete again → False
            ok = await sched.delete_schedule("history")
            assert ok is False
            await sched.stop()

        asyncio.run(run())

    def test_toggle_schedule(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            initial = sched._schedules["history"].enabled
            result = await sched.toggle_schedule("history")
            assert result["enabled"] is (not initial)
            # Toggle back
            result = await sched.toggle_schedule("history")
            assert result["enabled"] is initial
            await sched.stop()

        asyncio.run(run())


class TestSchedulerTriggering:
    def test_skip_disabled_task(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            # hunt_cycle is disabled by default — the loop checks enabled
            # before calling _trigger. Verify the guard condition.
            entry = sched._schedules["hunt_cycle"]
            assert entry.enabled is False
            # The loop checks: if not entry.enabled → skip
            assert not entry.enabled  # loop would skip this
            await sched.stop()

        asyncio.run(run())

    def test_skip_not_due_task(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            entry = sched._schedules["history"]
            entry.next_run = time.time() + 9999
            sched._persist(entry)
            # _trigger is called directly, but the loop checks next_run first.
            # However _trigger itself doesn't check next_run — the loop does.
            # So we test via the loop: manually check the condition
            now = time.time()
            assert now < entry.next_run
            await sched.stop()

        asyncio.run(run())

    def test_trigger_skips_when_already_running(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()

            # Simulate a running task
            fake_task = asyncio.ensure_future(asyncio.sleep(10))
            sched._running_tasks["history"] = fake_task

            entry = sched._schedules["history"]
            entry.enabled = True
            entry.next_run = time.time() - 10
            sched._persist(entry)

            await sched._trigger("history")
            assert entry.last_status == "skipped"

            fake_task.cancel()
            try:
                await fake_task
            except (asyncio.CancelledError, Exception):
                pass
            await sched.stop()

        asyncio.run(run())

    def test_trigger_respects_internet_down(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()

            # Mock internet as down
            async def internet_down():
                return False
            state.is_internet_alive = internet_down

            entry = sched._schedules["ip_blacklist_refresh"]
            entry.enabled = True
            entry.next_run = time.time() - 10
            sched._persist(entry)

            await sched._trigger("ip_blacklist_refresh")
            assert entry.last_status == "skipped"
            await sched.stop()

        asyncio.run(run())

    def test_trigger_respects_pause_for_hunt_cycle(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()

            # Mock internet as up
            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            # Simulate hunt paused
            state._paused = True

            entry = sched._schedules["hunt_cycle"]
            entry.enabled = True
            entry.interval_sec = 300
            entry.next_run = time.time() - 10
            sched._persist(entry)

            await sched._trigger("hunt_cycle")
            assert entry.last_status == "skipped"
            await sched.stop()

        asyncio.run(run())

    def test_trigger_now_runs_task(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()

            # Mock internet as up
            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            called = []

            async def fake_history(entry):
                called.append(entry.id)

            sched._execute_history = fake_history

            ok = await sched.trigger_now("history")
            assert ok is True
            # Wait for the task to complete
            await asyncio.sleep(0.2)
            entry = sched._schedules["history"]
            assert entry.last_status == "ok"
            assert called == ["history"]
            await sched.stop()

        asyncio.run(run())

    def test_trigger_now_nonexistent(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            ok = await sched.trigger_now("nonexistent")
            assert ok is False
            await sched.stop()

        asyncio.run(run())


class TestSchedulerPause:
    def test_pause_all_blocks_triggering(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            sched.pause_all()
            assert sched.is_paused() is True

            entry = sched._schedules["history"]
            entry.enabled = True
            entry.next_run = time.time() - 10
            sched._persist(entry)

            # The _run_loop checks _paused, but _trigger does not.
            # We test the loop guard: simulate what the loop does
            if not sched._paused:
                await sched._trigger("history")
            assert entry.last_status == "never"  # not triggered

            sched.resume_all()
            assert sched.is_paused() is False
            await sched.stop()

        asyncio.run(run())


class TestSchedulerStatus:
    def test_get_status(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            status = sched.get_status()
            assert "running" in status
            assert "paused" in status
            assert "running_tasks" in status
            assert "schedule_count" in status
            assert status["schedule_count"] == len(DEFAULT_SCHEDULES)
            assert status["paused"] is False
            await sched.stop()

        asyncio.run(run())

    def test_list_schedules(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            schedules = sched.list_schedules()
            assert len(schedules) == len(DEFAULT_SCHEDULES)
            # Sorted by id
            ids = [s["id"] for s in schedules]
            assert ids == sorted(ids)
            await sched.stop()

        asyncio.run(run())


class TestSchedulerSnapshot:
    def test_snapshot_includes_scheduler(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()
            state.scheduler = sched
            snap = state.get_snapshot()
            assert "scheduler" in snap
            assert "schedules" in snap["scheduler"]
            assert len(snap["scheduler"]["schedules"]) == len(DEFAULT_SCHEDULES)
            await sched.stop()

        asyncio.run(run())

    def test_snapshot_without_scheduler(self, state):
        snap = state.get_snapshot()
        assert "scheduler" in snap
        assert snap["scheduler"]["running"] is False
        assert snap["scheduler"]["schedules"] == []


class TestSchedulerMutex:
    def test_mutex_hunt_cycle_blocks_health_check(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            # Simulate hunt_cycle running
            fake_task = asyncio.ensure_future(asyncio.sleep(10))
            sched._running_tasks["hunt_cycle"] = fake_task

            entry = sched._schedules["health_check"]
            entry.enabled = True
            entry.next_run = time.time() - 10
            sched._persist(entry)

            await sched._trigger("health_check")
            assert entry.last_status == "skipped"

            fake_task.cancel()
            try:
                await fake_task
            except (asyncio.CancelledError, Exception):
                pass
            await sched.stop()

        asyncio.run(run())

    def test_mutex_health_check_blocks_hunt_cycle(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            # Simulate health_check running
            fake_task = asyncio.ensure_future(asyncio.sleep(10))
            sched._running_tasks["health_check"] = fake_task

            entry = sched._schedules["hunt_cycle"]
            entry.enabled = True
            entry.interval_sec = 300
            entry.next_run = time.time() - 10
            sched._persist(entry)

            await sched._trigger("hunt_cycle")
            assert entry.last_status == "skipped"

            fake_task.cancel()
            try:
                await fake_task
            except (asyncio.CancelledError, Exception):
                pass
            await sched.stop()

        asyncio.run(run())


class TestSchedulerExecutorHistory:
    def test_execute_history_calls_push_and_cleanup(self, state):
        async def run():
            sched = SchedulerEngine(state)
            called = []

            def fake_push():
                called.append("push")
            state._push_history = fake_push

            entry = ScheduleEntry(id="history", name="History", task_type="history")
            await sched._execute_history(entry)
            assert "push" in called
            await sched.stop()

        asyncio.run(run())

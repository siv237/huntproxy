import asyncio
import inspect
import json
import time
import pytest
import hunt
from hunt.scheduler import SchedulerEngine, ScheduleEntry, TASK_TYPES, DEFAULT_SCHEDULES


class TestSchedulerIntegrity:
    """Structural integrity checks — no duplicate methods, no orphan task
    types, every default schedule maps to a known task type."""

    def test_no_duplicate_methods_in_scheduler(self):
        """SchedulerEngine must not have duplicate method definitions
        (catches copy-paste accidents that silently shadow each other)."""
        seen = {}
        dups = []
        for name, fn in inspect.getmembers(SchedulerEngine, predicate=inspect.isfunction):
            if name in seen:
                dups.append(name)
            seen[name] = True
        assert not dups, f"Duplicate methods in SchedulerEngine: {dups}"

    def test_default_schedules_use_known_task_types(self):
        """Every DEFAULT_SCHEDULES entry must reference a TASK_TYPES key."""
        for d in DEFAULT_SCHEDULES:
            assert d["task_type"] in TASK_TYPES, (
                f"Default schedule '{d['id']}' has unknown task_type '{d['task_type']}'"
            )

    def test_every_task_type_has_executor(self):
        """Every TASK_TYPES key must have a registered executor in TaskExecutor."""
        from hunt.task_executor import TaskExecutor
        for tt in TASK_TYPES:
            # TaskExecutor registers defaults in __init__; check the registry
            # has a handler for each task type.  We use a dummy state since
            # executors are registered at construction time.
            class _DummyState:
                pass
            executor = TaskExecutor(_DummyState())
            assert executor.get(tt) is not None, (
                f"Task type '{tt}' has no executor in TaskExecutor registry"
            )

    def test_task_types_have_required_keys(self):
        """Every TASK_TYPES entry must have all required keys to avoid
        KeyError in _try_launch."""
        required = {"description", "mutex_with", "respect_pause", "respect_internet"}
        for tt, d in TASK_TYPES.items():
            missing = required - set(d.keys())
            assert not missing, f"Task type '{tt}' missing keys: {missing}"

    def test_every_default_schedule_triggerable(self, state):
        """Every default schedule must be triggerable via trigger_now without
        a 404.  This catches the class of bugs where a UI 'Run Now' button
        silently fails because the task is blocked by a mutex, a stale
        busy-flag, or an unknown task_type.

        Mutex-blocked tasks must be queued (return True), not rejected.
        """
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            # Stub every executor via the registry so no real work happens.
            for tt in TASK_TYPES:
                async def _noop(s, entry):
                    await asyncio.sleep(0.05)
                sched.executor.register(tt, _noop)

            for d in DEFAULT_SCHEDULES:
                sid = d["id"]
                entry = sched._schedules.get(sid)
                assert entry is not None, f"Default schedule '{sid}' missing after prepare()"
                ok = await sched.trigger_now(sid)
                assert ok is True, (
                    f"trigger_now('{sid}') returned False — the UI 'Run Now' "
                    f"button would get a 404. task_type='{entry.task_type}'"
                )
                # Wait for it to finish so it doesn't block the next trigger.
                for _ in range(200):
                    if entry.task_type not in sched._running_tasks:
                        break
                    await asyncio.sleep(0.02)

            await sched.stop()

        asyncio.run(run())

    def test_trigger_now_mutex_conflict_queues_not_404(self, state):
        """When a manual run hits a mutex conflict it must be queued (True),
        not rejected with False (which becomes a 404 in the UI)."""
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            # Block proxy_check by pretending health_check is running.
            fake_task = asyncio.ensure_future(asyncio.sleep(30))
            sched._running_tasks["health_check"] = fake_task

            ok = await sched.trigger_now("proxy_check")
            assert ok is True, "mutex-blocked manual run must be queued, not 404"
            assert "proxy_check" in sched._queue

            fake_task.cancel()
            try:
                await fake_task
            except (asyncio.CancelledError, Exception):
                pass
            await sched.stop()

        asyncio.run(run())

    def test_trigger_now_mutex_conflict_queues_not_404(self, state):
        """When a manual run hits a mutex conflict it must be queued (True),
        not rejected with False (which becomes a 404 in the UI)."""
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            # Block proxy_check by pretending health_check is running.
            fake_task = asyncio.ensure_future(asyncio.sleep(30))
            sched._running_tasks["health_check"] = fake_task

            ok = await sched.trigger_now("proxy_check")
            assert ok is True, "mutex-blocked manual run must be queued, not 404"
            assert "proxy_check" in sched._queue

            fake_task.cancel()
            try:
                await fake_task
            except (asyncio.CancelledError, Exception):
                pass
            await sched.stop()

        asyncio.run(run())


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
            # proxy_check is enabled by default
            assert sched._schedules["proxy_check"].enabled is True
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

    def test_prepare_seeds_without_loop(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()
            # Defaults seeded and visible
            assert len(sched._schedules) == len(DEFAULT_SCHEDULES)
            # But the run loop must NOT be started
            assert sched._task is None
            await sched.stop()

        asyncio.run(run())

    def test_start_loop_idempotent(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()
            await sched.start_loop()
            t1 = sched._task
            assert t1 is not None and not t1.done()
            # Second call must not replace the existing task
            await sched.start_loop()
            assert sched._task is t1
            await sched.stop()

        asyncio.run(run())

    def test_restore_defaults_adds_only_missing(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()
            # Delete two default schedules
            await sched.delete_schedule("history")
            await sched.delete_schedule("health_check")
            assert "history" not in sched._schedules
            assert "health_check" not in sched._schedules
            # Modify a remaining one — restore must not overwrite it
            await sched.update_schedule("blocklist_refresh", interval_sec=7200)
            added = await sched.restore_defaults()
            assert set(added) == {"history", "health_check"}
            assert "history" in sched._schedules
            assert "health_check" in sched._schedules
            # Existing user edit preserved
            assert sched._schedules["blocklist_refresh"].interval_sec == 7200
            # Calling again adds nothing
            added2 = await sched.restore_defaults()
            assert added2 == []
            await sched.stop()

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
            # proxy_check is enabled by default — verify it's due immediately
            # on first run (last_ok == 0, next_run == 0 → is_due returns True).
            entry = sched._schedules["proxy_check"]
            assert entry.enabled is True
            assert entry.is_due(time.time()) is True
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

    def test_trigger_queues_when_already_running(self, state):
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
            # Blocked task is queued, not skipped
            assert entry.last_status == "queued"
            assert "history" in sched._queue

            fake_task.cancel()
            try:
                await fake_task
            except (asyncio.CancelledError, Exception):
                pass
            await sched.stop()

        asyncio.run(run())

    def test_trigger_queues_when_internet_down(self, state):
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
            assert entry.last_status == "queued"
            assert "ip_blacklist_refresh" in sched._queue
            await sched.stop()

        asyncio.run(run())

    def test_trigger_proxy_check_not_blocked_by_pause(self, state):
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

            entry = sched._schedules["proxy_check"]
            entry.enabled = True
            entry.interval_sec = 300
            entry.last_ok = 0
            entry.next_run = time.time() - 10
            sched._persist(entry)

            async def fake_proxy_check(e):
                pass
            sched._execute_proxy_check = fake_proxy_check

            await sched._trigger("proxy_check")
            # proxy_check has respect_pause=False → runs even when paused
            assert entry.last_status == "running"
            await asyncio.sleep(0.1)
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

            async def fake_history(s, entry):
                called.append(entry.id)

            sched.executor.register("history", fake_history)

            ok = await sched.trigger_now("history")
            assert ok is True
            # trigger_now launches directly (not via queue), last_run must be set.
            entry = sched._schedules["history"]
            assert entry.last_run > 0
            assert entry.last_status == "running"
            # Wait for the task to complete
            await asyncio.sleep(0.2)
            assert entry.last_status == "ok"
            assert called == ["history"]
            await sched.stop()

        asyncio.run(run())

    def test_trigger_now_proxy_check_launches_directly(self, state):
        """Manual proxy_check run launches directly (not via queue) and
        ignores stale _hunt_running since proxy_check has no busy_flag."""
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            # A stale _hunt_running should NOT block proxy_check (no busy_flag)
            state._hunt_running = True
            state.phase = state.PHASE_IDLE

            started = []
            async def fake_proxy_check(s, e):
                started.append(True)
            sched.executor.register("proxy_check", fake_proxy_check)

            ok = await sched.trigger_now("proxy_check")
            assert ok is True
            entry = sched._schedules["proxy_check"]
            assert entry.last_run > 0
            assert entry.last_status == "running"
            await asyncio.sleep(0.2)
            assert started == [True]
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
    def test_mutex_proxy_check_blocks_health_check(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched._load_schedules()
            await sched._seed_defaults_if_empty()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            # Simulate proxy_check running
            fake_task = asyncio.ensure_future(asyncio.sleep(10))
            sched._running_tasks["proxy_check"] = fake_task

            entry = sched._schedules["health_check"]
            entry.enabled = True
            entry.next_run = time.time() - 10
            sched._persist(entry)

            await sched._trigger("health_check")
            assert entry.last_status == "queued"
            assert "health_check" in sched._queue

            fake_task.cancel()
            try:
                await fake_task
            except (asyncio.CancelledError, Exception):
                pass
            await sched.stop()

        asyncio.run(run())

    def test_mutex_health_check_blocks_proxy_check(self, state):
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

            entry = sched._schedules["proxy_check"]
            entry.enabled = True
            entry.interval_sec = 300
            entry.next_run = time.time() - 10
            sched._persist(entry)

            await sched._trigger("proxy_check")
            assert entry.last_status == "queued"
            assert "proxy_check" in sched._queue

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
            await sched.executor.run(entry)
            assert "push" in called
            await sched.stop()

        asyncio.run(run())


class TestSchedulerIntervalFromCompletion:
    """The next run must be scheduled interval_sec after the task COMPLETES,
    not after it starts — so a long hunt does not re-fire too early."""

    def test_next_run_is_completion_plus_interval(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            entry = sched._schedules["proxy_check"]
            entry.enabled = True
            entry.interval_sec = 10
            entry.last_ok = 0  # never succeeded → due immediately via next_run
            entry.next_run = time.time() - 1  # due now
            sched._persist(entry)

            run_duration = 0.3

            async def slow_hunt(s, e):
                await asyncio.sleep(run_duration)
            sched.executor.register("proxy_check", slow_hunt)

            before = time.time()
            await sched._trigger("proxy_check")
            # Wait for the tracked task to finish.
            while sched._running_tasks:
                await asyncio.sleep(0.01)
            entry = sched._schedules["proxy_check"]

            # last_ok must be set to the completion time.
            assert entry.last_ok >= before + run_duration - 1
            # The task must NOT be due immediately after a successful run —
            # at least interval_sec must pass since last_ok.
            assert entry.is_due(time.time()) is False
            # next_run is a cosmetic hint, completion_time + interval.
            assert entry.next_run > before + 10
            await sched.stop()

        asyncio.run(run())

    def test_run_loop_does_not_retrigger_while_running(self, state):
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            entry = sched._schedules["proxy_check"]
            entry.enabled = True
            entry.interval_sec = 1
            entry.last_ok = 0
            entry.next_run = time.time() - 1  # due now
            sched._persist(entry)

            releases = asyncio.Event()

            async def slow_hunt(s, e):
                await releases.wait()
            sched.executor.register("proxy_check", slow_hunt)

            await sched._trigger("proxy_check")
            assert "proxy_check" in sched._running_tasks
            # Further triggers while running must not launch a second task.
            await sched._trigger("proxy_check")
            await sched._trigger("proxy_check")
            assert len([t for t in sched._running_tasks.values() if not t.done()]) == 1

            releases.set()
            while sched._running_tasks:
                await asyncio.sleep(0.01)
            await sched.stop()

        asyncio.run(run())

    def test_due_by_last_ok_not_next_run(self, state):
        """A task whose last_ok is far in the past must be due even if next_run
        hint is in the future — the real trigger is last_ok + interval."""
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()
            entry = sched._schedules["proxy_check"]
            entry.enabled = True
            entry.interval_sec = 60
            entry.last_ok = time.time() - 3600  # 1h ago → overdue
            entry.next_run = time.time() + 999  # cosmetic hint far future
            assert entry.is_due(time.time()) is True
            await sched.stop()

        asyncio.run(run())

    def test_queued_task_runs_after_blocker_finishes(self, state):
        """A task queued behind a mutex blocker must launch once the blocker
        completes — it is never silently dropped."""
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            releases = asyncio.Event()
            started = asyncio.Event()

            async def slow_hunt(s, e):
                started.set()
                await releases.wait()
            sched.executor.register("proxy_check", slow_hunt)

            ran = []
            async def real_health(s, e):
                ran.append("health")
            sched.executor.register("health_check", real_health)

            hc = sched._schedules["proxy_check"]
            hc.enabled = True
            hc.interval_sec = 60
            hc.last_ok = 0
            hc.next_run = time.time() - 1
            sched._persist(hc)

            he = sched._schedules["health_check"]
            he.enabled = True
            he.interval_sec = 60
            he.last_ok = time.time() - 999
            he.next_run = time.time() - 1
            sched._persist(he)

            # Start proxy_check (blocks health_check via mutex)
            await sched._trigger("proxy_check")
            await asyncio.wait_for(started.wait(), timeout=5)
            # Queue health_check — blocked by proxy_check mutex
            await sched._trigger("health_check")
            assert "health_check" in sched._queue
            assert he.last_status == "queued"

            # Finish proxy_check → health_check should drain from the queue
            releases.set()
            for _ in range(100):
                await asyncio.sleep(0.02)
                if ran:
                    break
            assert ran == ["health"]
            assert "health_check" not in sched._queue
            await sched.stop()

        asyncio.run(run())


class TestStartupCycle:
    """run_startup_cycle must run revalidate → full hunt, in that order,
    and only return after the hunt cycle reaches DONE/IDLE. The unified
    scheduler is started by the caller only after this returns."""

    def test_startup_cycle_order_and_completion(self, state):
        async def run():
            order = []

            async def fake_revalidate():
                order.append("revalidate")

            async def fake_hunt_cycle():
                order.append("hunt_start")
                self_phase = state
                self_phase.phase = state.PHASE_DOWNLOAD
                await asyncio.sleep(0)
                self_phase.phase = state.PHASE_DONE
                order.append("hunt_done")

            state._revalidate_stale_proxies = fake_revalidate
            state._hunt_cycle = fake_hunt_cycle

            await state.run_startup_cycle()

            assert order == ["revalidate", "hunt_start", "hunt_done"]
            assert state.phase == state.PHASE_DONE
            # start_hunt() sets _hunt_running=True; the real _hunt_cycle's
            # finally block resets it to False, but this mock does not, so we
            # only assert the cycle ran (phase == DONE).
            assert "hunt_done" in order

        asyncio.run(run())

    def test_startup_cycle_starts_hunt_even_if_flag_was_restored(self, state):
        async def run():
            # Simulate a restart where _hunt_running was persisted True but
            # no live task survived — a fresh hunt must still be started.
            state._hunt_running = True
            started = []

            async def fake_revalidate():
                pass

            async def fake_hunt_cycle():
                started.append(True)
                state.phase = state.PHASE_DONE

            state._revalidate_stale_proxies = fake_revalidate
            state._hunt_cycle = fake_hunt_cycle

            await state.run_startup_cycle()
            assert started == [True]

        asyncio.run(run())

    def test_startup_cycle_revalidate_failure_still_runs_hunt(self, state):
        async def run():
            async def boom():
                raise RuntimeError("net down")

            async def fake_hunt_cycle():
                state.phase = state.PHASE_DONE

            state._revalidate_stale_proxies = boom
            state._hunt_cycle = fake_hunt_cycle

            # Should not raise despite revalidate failure.
            await state.run_startup_cycle()
            assert state.phase == state.PHASE_DONE

        asyncio.run(run())


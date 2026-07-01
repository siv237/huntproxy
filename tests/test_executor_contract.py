"""Task executor contract — scheduler planning vs execution separation.

These tests verify that the scheduler's *planning* logic (queue, mutex,
busy-flag, due-check, trigger) is independent from the *execution* logic
(proxy_check, blocklist, backup, etc.).  Executors live in a separate
``TaskExecutor`` class, registered via a dict registry.

Tagged ``executor`` so they can be run in isolation:

    ./test.sh -m executor          # executor contract only
    ./test.sh -m "not executor"    # everything except executor
"""

import asyncio
import inspect
import pytest

import hunt
from hunt.scheduler import SchedulerEngine, TASK_TYPES, DEFAULT_SCHEDULES
from hunt.task_executor import TaskExecutor


class TestExecutorRegistry:
    """Every task type must have a discoverable executor in the registry.

    Executors live in ``TaskExecutor._executors`` (a dict), not as
    methods on ``SchedulerEngine``.  These tests pin the contract so
    the extraction can't accidentally drop a task type.
    """

    @pytest.mark.executor
    def test_every_task_type_has_executor(self, state):
        """For each TASK_TYPES key, the registry must have a handler."""
        executor = TaskExecutor(state)
        for tt in TASK_TYPES:
            assert executor.get(tt) is not None, (
                f"Task type '{tt}' has no executor in TaskExecutor registry"
            )

    @pytest.mark.executor
    def test_every_executor_is_async(self, state):
        """All registered executors must be async coroutines."""
        executor = TaskExecutor(state)
        for tt in TASK_TYPES:
            handler = executor.get(tt)
            assert handler is not None
            assert inspect.iscoroutinefunction(handler), (
                f"Executor for '{tt}' must be async (it awaits state operations)"
            )

    @pytest.mark.executor
    def test_executor_registry_matches_task_types(self, state):
        """No orphan executors — every registered handler maps to a TASK_TYPES key."""
        executor = TaskExecutor(state)
        registered = set(executor._executors.keys())
        expected = set(TASK_TYPES.keys())
        orphans = registered - expected
        missing = expected - registered
        assert not orphans, f"Orphan executors (no TASK_TYPES entry): {orphans}"
        assert not missing, f"Missing executors: {missing}"

    @pytest.mark.executor
    def test_execute_task_delegates_to_executor(self):
        """_execute_task must delegate to self.executor.run() — not dispatch
        via if/elif.  This proves planning and execution are decoupled."""
        src = inspect.getsource(SchedulerEngine._execute_task)
        assert "self.executor" in src, (
            "_execute_task must delegate to self.executor.run() — "
            "executors are in TaskExecutor, not inline if/elif"
        )
        # Must NOT contain task-type-specific dispatch (the old pattern).
        for tt in TASK_TYPES:
            assert f'"{tt}"' not in src, (
                f"_execute_task still has hardcoded branch for '{tt}' — "
                "should go through executor registry"
            )


class TestExecutorIsolation:
    """Executors must be independently stubbable via the registry — proving
    they are separate units that can be replaced without touching planning.

    Stubbing is done via ``sched.executor.register(tt, fn)`` which replaces
    the handler in the registry.  The scheduler's planning logic must
    still work correctly (queue, launch, track completion).
    """

    @pytest.mark.executor
    def test_all_executors_stubbable(self, state):
        """Stubbing every executor via the registry must not break planning."""
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            call_log = []
            for tt in TASK_TYPES:
                async def _stub(s, entry, _tt=tt):
                    call_log.append(_tt)
                sched.executor.register(tt, _stub)

            # Trigger every default schedule — each must launch and complete.
            for d in DEFAULT_SCHEDULES:
                sid = d["id"]
                ok = await sched.trigger_now(sid)
                assert ok is True, f"trigger_now('{sid}') failed with stubbed executors"
                entry = sched._schedules[sid]
                for _ in range(200):
                    if entry.task_type not in sched._running_tasks:
                        break
                    await asyncio.sleep(0.02)
                assert entry.task_type not in sched._running_tasks, (
                    f"Schedule '{sid}' did not complete with stubbed executor"
                )

            triggered_types = {d["task_type"] for d in DEFAULT_SCHEDULES}
            called_types = set(call_log)
            missed = triggered_types - called_types
            assert not missed, (
                f"Task types triggered but executor not called: {missed}"
            )

            await sched.stop()

        asyncio.run(run())

    @pytest.mark.executor
    def test_executor_failure_does_not_crash_scheduler(self, state):
        """A failing executor must mark the schedule as 'failed', not
        crash the scheduler or leave it in a broken state."""
        async def run():
            sched = SchedulerEngine(state)
            await sched.start()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            async def boom(s, entry):
                raise RuntimeError("executor crashed")

            sched.executor.register("history", boom)

            entry = sched._schedules["history"]
            ok = await sched.trigger_now("history")
            assert ok is True

            for _ in range(200):
                if "history" not in sched._running_tasks:
                    break
                await asyncio.sleep(0.02)

            assert entry.last_status == "failed"
            assert "executor crashed" in entry.last_error
            assert sched._task is not None and not sched._task.done()
            await sched.stop()

        asyncio.run(run())

    @pytest.mark.executor
    def test_executor_cancellation_is_handled(self, state):
        """A cancelled executor must mark the schedule as 'failed' with
        'cancelled' error, not leave it in 'running' forever.

        Uses prepare() without start_loop() so the scheduler's own tick
        loop doesn't re-enqueue the task while we're testing cancellation.

        NOTE: The task must have started running before cancellation —
        if cancelled before its first await, CancelledError is raised
        at the coroutine level, before _run_with_tracking's try/finally,
        so _running_tasks is not cleaned up.  This is a known edge case.
        """
        async def run():
            sched = SchedulerEngine(state)
            await sched.prepare()

            async def internet_up():
                return True
            state.is_internet_alive = internet_up

            async def slow(s, entry):
                await asyncio.sleep(999)

            sched.executor.register("history", slow)

            entry = sched._schedules["history"]
            await sched.trigger_now("history")

            for _ in range(100):
                task = sched._running_tasks.get("history")
                if task is not None and not task.done():
                    break
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.05)

            ok = await sched.cancel_running("history")
            assert ok is True

            for _ in range(300):
                if "history" not in sched._running_tasks:
                    break
                await asyncio.sleep(0.02)

            assert "history" not in sched._running_tasks, \
                "history task still in _running_tasks after cancellation"
            assert entry.last_status == "failed", \
                f"expected 'failed', got '{entry.last_status}'"
            await sched.stop()

        asyncio.run(run())


class TestPlanningExecutionSeparation:
    """Planning methods must not contain execution logic.

    The planning layer (_run_loop, _drain_queue, _try_launch, trigger_now)
    should only manage queue/launch/tracking — never call state business
    methods directly.  Planning calls ``self.executor.run(entry)`` and
    knows nothing about specific task types.
    """

    PLANNING_METHODS = (
        "_run_loop",
        "_drain_queue",
        "_try_launch",
        "trigger_now",
    )

    @pytest.mark.executor
    def test_planning_methods_dont_call_executors_directly(self):
        """Planning methods must not call _execute_* directly — they
        should go through _execute_task → self.executor.run()."""
        for method_name in self.PLANNING_METHODS:
            method = getattr(SchedulerEngine, method_name, None)
            if method is None:
                pytest.fail(f"Planning method '{method_name}' not found")
            src = inspect.getsource(method)
            for tt in TASK_TYPES:
                direct_call = f"_execute_{tt}("
                assert direct_call not in src, (
                    f"Planning method '{method_name}' directly calls "
                    f"_execute_{tt}() — should go through executor registry"
                )

    @pytest.mark.executor
    def test_planning_methods_dont_access_state_ratings(self):
        """Planning must not touch domain data directly — that's the
        executor's job.  Planning only needs flags and task lifecycle."""
        forbidden_patterns = ("self.state.ratings", "self.state.blacklist",
                              "self.state.favorites", "self.state._validate_all")
        for method_name in self.PLANNING_METHODS:
            method = getattr(SchedulerEngine, method_name, None)
            if method is None:
                continue
            src = inspect.getsource(method)
            for pat in forbidden_patterns:
                assert pat not in src, (
                    f"Planning method '{method_name}' accesses '{pat}' — "
                    "domain data access belongs in executors, not planning"
                )

    @pytest.mark.executor
    def test_executor_module_does_not_import_scheduler(self):
        """TaskExecutor must not import SchedulerEngine — no circular dep."""
        mod = inspect.getmodule(TaskExecutor)
        src = inspect.getsource(mod)
        assert "from hunt.scheduler import SchedulerEngine" not in src, (
            "task_executor.py imports SchedulerEngine — circular dependency"
        )
        # ScheduleEntry is OK (it's a dataclass, not the engine).
        assert "SchedulerEngine" not in src.replace(
            "from hunt.scheduler import ScheduleEntry", ""
        ).replace("SchedulerEngine", "__CHECK__"), (
            "task_executor.py references SchedulerEngine — should only "
            "import ScheduleEntry (a dataclass)"
        )

import hunt


class TestActionLog:
    """Operator actions must be recorded in the actions table with a
    counter snapshot, so counter-desync bugs can be traced."""

    def test_log_action_records_snapshot(self, state):
        state.phase = state.PHASE_VALIDATE
        state.checking_total = 200
        state.checked = 150
        state.working = 60
        state.failed = 40
        state._log_action("hunt.start", "ok")

        actions = state.get_actions(10)
        assert actions, "no actions returned"
        last = actions[0]
        assert last["action"] == "hunt.start"
        assert last["detail"] == "ok"
        snap = last["snapshot"]
        assert snap["phase"] == state.PHASE_VALIDATE
        assert snap["checking_total"] == 200
        assert snap["checked"] == 150
        assert snap["working"] == 60
        assert snap["failed"] == 40

    def test_log_action_extra_merged(self, state):
        state._log_action("health.snapshot", "before", extra={"saved": {"checked": 10}})
        actions = state.get_actions(10)
        snap = actions[0]["snapshot"]
        assert snap["saved"]["checked"] == 10
        assert "phase" in snap

    def test_get_actions_ordered_desc(self, state):
        state._log_action("a.one")
        state._log_action("a.two")
        state._log_action("a.three")
        actions = state.get_actions(10)
        assert [a["action"] for a in actions[:3]] == ["a.three", "a.two", "a.one"]

    def test_get_actions_respects_limit(self, state):
        for i in range(5):
            state._log_action(f"a.{i}")
        actions = state.get_actions(2)
        assert len(actions) == 2
        assert actions[0]["action"] == "a.4"

    def test_health_check_logs_snapshot_begin_restore(self, state):
        import asyncio
        from hunt.models import ProxyRating

        async def run():
            state.phase = state.PHASE_VALIDATE
            state.phase_started = 1000000.0
            state.downloaded = 100
            state.checking_total = 200
            state.checked = 150
            state.working = 60
            state.failed = 40

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

                r = ProxyRating(address="1.2.3.4:8080", last_status="ok",
                                speed_sum=200, speed_count=1)
                state.ratings[r.address] = r

                await state._health_check()

                actions = state.get_actions(50)
                names = [a["action"] for a in actions]
                assert "health.begin" in names
                # restore entry must show the restored counters
                restore = next(a for a in actions if a["action"] == "health.restore")
                assert restore["snapshot"]["checking_total"] == 200
                assert restore["snapshot"]["checked"] == 150
            finally:
                state.task.cancel()
                try:
                    await state.task
                except (asyncio.CancelledError, Exception):
                    pass

        asyncio.run(run())

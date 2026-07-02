"""Functional split of the huntproxy backend."""

import json
import time

from hunt.constants import logger


class ActionsMixin:
    """Persistent audit log of operator actions (start/stop/pause/resume/
    recheck/select/health-start/etc.).

    Each entry captures a snapshot of the hunt counters at the moment the
    action was performed, so counter desync bugs (e.g. checking_total=150
    while checked keeps growing past it) can be traced back to the exact
    operation that caused them.
    """

    def _log_action(self, action: str, detail: str = "", extra: dict | None = None):
        ts = time.time()
        snapshot = {
            "phase": self.phase,
            "paused": self._paused,
            "manual_pause": self._manual_pause,
            "hunt_running": getattr(self, '_hunt_running', False),
            "health_running": getattr(self, "_health_running", False),
            "checked": self.checked,
            "checking_total": self.checking_total,
            "working": self.working,
            "failed": self.failed,
            "downloaded": self.downloaded,
            "ratings": len(self.ratings),
        }
        if extra:
            snapshot.update(extra)
        try:
            conn = self._stats_db()
            conn.execute(
                "INSERT INTO actions (ts, action, detail, snapshot) VALUES (?,?,?,?)",
                (ts, action, detail or "", json.dumps(snapshot)),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("actions log insert failed: %s", e)
        self._emit(f"[action] {action}" + (f" {detail}" if detail else ""), "info")

    def get_actions(self, limit: int = 100) -> list:
        try:
            conn = self._stats_db()
            rows = conn.execute(
                "SELECT ts, action, detail, snapshot FROM actions "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            result = []
            for r in rows:
                entry = {"ts": r["ts"], "action": r["action"], "detail": r["detail"]}
                try:
                    entry["snapshot"] = json.loads(r["snapshot"] or "{}")
                except Exception:
                    entry["snapshot"] = {}
                result.append(entry)
            return result
        except Exception as e:
            logger.error("get_actions: %s", e)
            return []

"""Functional split of the huntproxy backend."""

import asyncio
import time
import logging

logger = logging.getLogger(__name__)

class EventsMixin:
    def _emit(self, msg: str, kind: str = "info", **kwargs):
            self._event_seq += 1
            ts = time.time()
            ev = {"seq": self._event_seq, "ts": ts, "type": kind, "msg": msg}
            ev.update(kwargs)
            self.events.append(ev)
            if len(self.events) > 500:
                self.events = self.events[-300:]
            self.last_event = msg
            try:
                conn = self._stats_db()
                conn.execute("INSERT INTO events (ts, seq, type, msg) VALUES (?,?,?,?)", (ts, self._event_seq, kind, msg))
                conn.commit()
                conn.close()
            except Exception:
                logger.debug("suppressed", exc_info=True)
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self._notify)
            except Exception:
                logger.debug("suppressed", exc_info=True)

    def _notify(self):
            async def go():
                async with self._cond:
                    self._cond.notify_all()
            try:
                asyncio.ensure_future(go())
            except Exception:
                logger.debug("suppressed", exc_info=True)

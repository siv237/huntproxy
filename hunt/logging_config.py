"""Functional split of the huntproxy backend."""

import logging
import os
from pathlib import Path


class _AsyncioNoiseFilter(logging.Filter):
    """Drop noisy, non-actionable asyncio transport warnings.

    These are emitted by asyncio internals when a relayed peer socket is
    closed mid-transfer (e.g. "socket.send() raised exception."). The proxy
    relay already handles these conditions, so the warnings only spam logs.
    """

    _NOISE = (
        "socket.send() raised exception.",
        "socket.recv() raised exception.",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for needle in self._NOISE:
            if needle in msg:
                return False
        return True


def setup_logging():
    level = os.environ.get("HUNTPROXY_LOG_LEVEL", "INFO")
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_dir = Path(__file__).resolve().parent.parent / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    noise_filter = _AsyncioNoiseFilter()
    file_handler = logging.FileHandler(log_dir / "huntproxy.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    file_handler.addFilter(noise_filter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    stream_handler.addFilter(noise_filter)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    # The asyncio logger emits the transport warnings directly, so attach the
    # filter there too in case handlers are added elsewhere.
    logging.getLogger("asyncio").addFilter(noise_filter)

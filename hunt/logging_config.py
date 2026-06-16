"""Functional split of the huntproxy backend."""

import logging
import os
from pathlib import Path

def setup_logging():
    level = os.environ.get("HUNTPROXY_LOG_LEVEL", "INFO")
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_dir = Path(__file__).resolve().parent.parent / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "huntproxy.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

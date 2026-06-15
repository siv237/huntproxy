"""Functional split of the huntproxy backend."""

import logging
import os

def setup_logging():
    level = os.environ.get("HUNTPROXY_LOG_LEVEL", "INFO")
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")

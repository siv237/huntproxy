import pytest
import tempfile
from pathlib import Path
import sys
import hunt

@pytest.fixture
def tmp_data_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        monkeypatch.setattr(hunt, "DATA_DIR", tmp_path)
        yield tmp_path

@pytest.fixture
def empty_config():
    return {
        "hunt": {"timeout": 8, "parallel": 30, "health_timeout": 10, "health_parallel": 30},
        "proxies": {"validate_interval": 300, "health_interval": 120, "strategy": "round_robin", "max_failures": 3, "cooldown": 300},
        "ip_blacklists": {"enabled": False, "fetch_interval": 3600},
    }

@pytest.fixture
def state(tmp_data_dir, empty_config):
    return hunt.HuntState(empty_config)

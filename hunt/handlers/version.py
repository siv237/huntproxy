"""Version handler — expose the deployed git commit as a clickable build tag."""

import json
import logging
import subprocess

from hunt.constants import PROJECT_DIR

logger = logging.getLogger(__name__)


def _git(*args):
    """Run a git command in the project repo; return stripped stdout or ''."""
    try:
        out = subprocess.run(
            ["git", "-C", str(PROJECT_DIR), *args],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        logger.debug("suppressed", exc_info=True)
    return ""


def _commit_url(commit, remote):
    if not remote or not commit:
        return ""
    r = remote
    if r.startswith("git@"):
        r = "https://" + r[4:].replace(":", "/", 1)
    r = r.replace(".git", "")
    return f"{r}/commit/{commit}"


class VersionHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    async def _handle_version(self, raw_path, body):
        commit = _git("rev-parse", "--short", "HEAD") or "unknown"
        date = _git("show", "-s", "--format=%cs", "HEAD")
        remote = _git("remote", "get-url", "origin")
        url = _commit_url(commit, remote)
        display = f"{date} ({commit})" if date else commit
        return json.dumps({
            "commit": commit,
            "date": date,
            "url": url,
            "display": display,
        }), 200, "application/json"

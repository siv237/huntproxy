"""Backward-compatible entry point for huntproxy.

The real backend now lives in the `hunt` package. This file exists only
so that existing scripts like `./hunt.sh` and `./daemon.sh` keep working.
"""
from hunt import *  # noqa: F401,F403
from hunt import main

if __name__ == "__main__":
    main()

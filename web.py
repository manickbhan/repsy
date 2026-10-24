"""Run the Repsy dashboard without starting the macOS menu-bar app."""

from __future__ import annotations

import os

import store
from server import create_app

if __name__ == "__main__":
    cfg = store.load_config()
    create_app().run(
        host="127.0.0.1",
        port=int(os.environ.get("REPSY_PORT", cfg["port"])),
        threaded=True,
        use_reloader=False,
    )

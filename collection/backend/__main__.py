"""Entry point: `python -m backend` (run from collection/).

Reads collection/backend/config.yaml, creates the FastAPI app, and starts
uvicorn on cfg.host:cfg.port.
"""
from __future__ import annotations

import os
import sys

import uvicorn

# Resolve config.yaml relative to this file so the server can be started from
# any working directory, but the canonical invocation is:
#   cd collection && python -m backend
_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_HERE, "config.yaml")


def main() -> None:
    from .config import load_config
    from .live_config import load_live_config
    from .app import create_app

    cfg = load_config(_CONFIG_PATH)
    live = load_live_config(_CONFIG_PATH)
    app = create_app(cfg, live)

    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()

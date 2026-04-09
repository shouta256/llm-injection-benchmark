#!/usr/bin/env python3
from __future__ import annotations

import argparse

from _bootstrap import ROOT
from benchmark.ui_server import run_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the local benchmark dashboard.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address for the local UI server.")
    parser.add_argument("--port", type=int, default=8000, help="Port for the local UI server.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dashboard(ROOT, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

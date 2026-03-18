#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from benchmark.reporting import build_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate leaderboard, figures, and report from results.csv.")
    parser.add_argument("--results", type=Path, default=ROOT / "results" / "results.csv")
    parser.add_argument("--leaderboard", type=Path, default=ROOT / "results" / "leaderboard.csv")
    parser.add_argument("--category-metrics", type=Path, default=ROOT / "results" / "category_metrics.csv")
    parser.add_argument("--figures-dir", type=Path, default=ROOT / "figures")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_artifacts(
        results_path=args.results,
        leaderboard_path=args.leaderboard,
        category_metrics_path=args.category_metrics,
        figures_dir=args.figures_dir,
        report_dir=args.report_dir,
    )
    print(
        f"Artifacts generated for {summary['total_models']} models and "
        f"{summary['total_evaluations']} prompt-model evaluations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

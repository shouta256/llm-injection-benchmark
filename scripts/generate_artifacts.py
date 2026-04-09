#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ROOT
from benchmark.artifacts import ArtifactPaths
from benchmark.reporting import build_artifacts


def parse_args() -> argparse.Namespace:
    default_paths = ArtifactPaths.standard(ROOT)
    parser = argparse.ArgumentParser(description="Generate leaderboard, figures, and report from results.csv.")
    parser.add_argument("--results", type=Path, default=default_paths.results_path)
    parser.add_argument("--leaderboard", type=Path, default=default_paths.leaderboard_path)
    parser.add_argument("--category-metrics", type=Path, default=default_paths.category_metrics_path)
    parser.add_argument("--figures-dir", type=Path, default=default_paths.figures_dir)
    parser.add_argument("--report-dir", type=Path, default=default_paths.report_dir)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_artifacts(
        ArtifactPaths(
            results_path=args.results,
            leaderboard_path=args.leaderboard,
            category_metrics_path=args.category_metrics,
            figures_dir=args.figures_dir,
            report_dir=args.report_dir,
        )
    )
    print(
        f"Artifacts generated for {summary['total_models']} models and "
        f"{summary['total_evaluations']} prompt-model evaluations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

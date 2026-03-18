#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from benchmark.constants import DEFAULT_SECRET
from benchmark.data import load_model_specs
from benchmark.reporting import build_artifacts
from benchmark.runner import BenchmarkConfig, run_benchmark


def main() -> int:
    models = load_model_specs(ROOT / "configs" / "models.json")
    run_stats = run_benchmark(
        BenchmarkConfig(
            backend_name="mock",
            models=models,
            prompts_path=ROOT / "prompts" / "prompts.jsonl",
            output_path=ROOT / "results" / "results.csv",
            secret=DEFAULT_SECRET,
            temperature=0.0,
            overwrite=True,
        )
    )
    summary = build_artifacts(
        results_path=ROOT / "results" / "results.csv",
        leaderboard_path=ROOT / "results" / "leaderboard.csv",
        category_metrics_path=ROOT / "results" / "category_metrics.csv",
        figures_dir=ROOT / "figures",
        report_dir=ROOT / "report",
    )
    print(
        f"Demo complete: {run_stats['written_rows']} rows, "
        f"{summary['overall_asr_percent']:.2f}% aggregate ASR, "
        f"best model = {summary['strongest_model']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

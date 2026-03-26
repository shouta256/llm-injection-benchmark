#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from benchmark.constants import DEFAULT_SECRET
from benchmark.data import ModelSpec
from benchmark.reporting import build_artifacts
from benchmark.runner import BenchmarkConfig, run_benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full benchmark on macOS using one local model with throttling."
    )
    parser.add_argument("--model", required=True, help="Local Ollama model tag to use.")
    parser.add_argument("--alias", default="mac-full", help="Display name for the single local model.")
    parser.add_argument("--secret", default=DEFAULT_SECRET)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--delay-seconds", type=float, default=2.0, help="Delay between requests. Default: 2.0")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "mac_full_results.csv")
    parser.add_argument("--leaderboard", type=Path, default=ROOT / "results" / "mac_full_leaderboard.csv")
    parser.add_argument(
        "--category-metrics",
        type=Path,
        default=ROOT / "results" / "mac_full_category_metrics.csv",
    )
    parser.add_argument("--figures-dir", type=Path, default=ROOT / "figures" / "mac_full")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "report" / "mac_full")
    parser.add_argument("--resume", action="store_true", help="Resume the full run from the existing output file.")
    parser.add_argument("--no-artifacts", action="store_true", help="Skip leaderboard/chart/report generation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model = ModelSpec(alias=args.alias, model_name=args.model, notes="Single full macOS local model")

    stats = run_benchmark(
        BenchmarkConfig(
            backend_name="ollama",
            models=[model],
            prompts_path=ROOT / "prompts" / "prompts.jsonl",
            output_path=args.output,
            secret=args.secret,
            temperature=args.temperature,
            timeout_seconds=args.timeout,
            overwrite=not args.resume,
            resume=args.resume,
            delay_seconds=args.delay_seconds,
        )
    )

    print(
        f"Mac-full run complete: {stats['written_rows']} rows written, "
        f"{stats['breaches']} breaches, {stats['errors']} errors, {stats['skipped_rows']} skipped."
    )

    if args.no_artifacts:
        return 0

    summary = build_artifacts(
        results_path=args.output,
        leaderboard_path=args.leaderboard,
        category_metrics_path=args.category_metrics,
        figures_dir=args.figures_dir,
        report_dir=args.report_dir,
    )
    print(
        f"Artifacts generated: ASR {summary['overall_asr_percent']:.2f}% "
        f"for model {summary['strongest_model']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

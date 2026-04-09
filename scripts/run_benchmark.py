#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ROOT
from benchmark import DEFAULT_SECRET, DEFAULT_TEMPERATURE, DEFAULT_TIMEOUT_SECONDS
from benchmark.data import load_model_specs
from benchmark.runner import BenchmarkConfig, run_benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local LLM prompt injection benchmark.")
    parser.add_argument("--backend", default="ollama", choices=["ollama", "mock"], help="Model runtime backend.")
    parser.add_argument("--models", nargs="*", help="Model aliases from configs/models.json or raw model names.")
    parser.add_argument("--models-config", type=Path, default=ROOT / "configs" / "models.json")
    parser.add_argument("--prompts", type=Path, default=ROOT / "prompts" / "prompts.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "results.csv")
    parser.add_argument("--secret", default=DEFAULT_SECRET, help="Protected FLAG token for deterministic breach detection.")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--categories", nargs="*", help="Optional category filter.")
    parser.add_argument("--per-category-limit", type=int, help="Run only the first N prompts per category.")
    parser.add_argument("--max-prompts", type=int, help="Hard limit on total prompts after filtering.")
    parser.add_argument("--delay-seconds", type=float, default=0.0, help="Sleep between prompt runs to reduce load.")
    parser.add_argument("--overwrite", action="store_true", help="Replace the output CSV if it already exists.")
    parser.add_argument("--resume", action="store_true", help="Skip rows already present in the output CSV.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    models = load_model_specs(args.models_config, args.models)
    if not models:
        raise SystemExit("No models configured. Update configs/models.json or pass --models.")

    stats = run_benchmark(
        BenchmarkConfig(
            backend_name=args.backend,
            models=models,
            prompts_path=args.prompts,
            output_path=args.output,
            secret=args.secret,
            temperature=args.temperature,
            timeout_seconds=args.timeout,
            overwrite=args.overwrite,
            resume=args.resume,
            categories=args.categories,
            per_category_limit=args.per_category_limit,
            max_prompts=args.max_prompts,
            delay_seconds=args.delay_seconds,
        )
    )

    print(
        f"Completed benchmark: {stats['written_rows']} rows written, "
        f"{stats['breaches']} breaches, {stats['errors']} errors, "
        f"{stats['skipped_rows']} skipped."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

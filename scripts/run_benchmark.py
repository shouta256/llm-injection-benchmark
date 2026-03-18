#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from benchmark.constants import DEFAULT_SECRET, DEFAULT_TEMPERATURE, DEFAULT_TIMEOUT_SECONDS
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

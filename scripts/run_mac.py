#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ROOT
from benchmark import DEFAULT_SECRET, DEFAULT_TEMPERATURE
from benchmark.artifacts import ArtifactPaths
from benchmark.data import ModelSpec
from benchmark.reporting import build_artifacts
from benchmark.runner import BenchmarkConfig, run_benchmark

MAC_RUN_PROFILES = {
    "lite": {
        "description": "Run a low-load local benchmark on macOS using one small Ollama model.",
        "default_alias": "mac-local",
        "timeout": 180,
        "delay_seconds": 1.5,
        "per_category_limit": 3,
        "output_prefix": "mac_lite",
        "model_notes": "Single low-load macOS local model",
        "completion_label": "Mac-lite",
    },
    "full": {
        "description": "Run the full benchmark on macOS using one local model with throttling.",
        "default_alias": "mac-full",
        "timeout": 240,
        "delay_seconds": 2.0,
        "per_category_limit": None,
        "output_prefix": "mac_full",
        "model_notes": "Single full macOS local model",
        "completion_label": "Mac-full",
    },
}


def _resolve_profile_name(default_profile: str | None) -> str:
    if default_profile is not None:
        return default_profile
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--profile", choices=sorted(MAC_RUN_PROFILES), default="lite")
    args, _ = parser.parse_known_args()
    return args.profile


def parse_args(default_profile: str | None = None) -> tuple[argparse.Namespace, dict[str, object]]:
    profile_name = _resolve_profile_name(default_profile)
    profile = MAC_RUN_PROFILES[profile_name]
    default_paths = ArtifactPaths.for_prefix(ROOT, str(profile["output_prefix"]))

    parser = argparse.ArgumentParser(description=str(profile["description"]))
    if default_profile is None:
        parser.add_argument("--profile", choices=sorted(MAC_RUN_PROFILES), default=profile_name)
    parser.add_argument("--model", required=True, help="Local Ollama model tag to use.")
    parser.add_argument("--alias", default=profile["default_alias"], help="Display name for the single local model.")
    parser.add_argument("--secret", default=DEFAULT_SECRET)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--timeout", type=int, default=profile["timeout"])
    parser.add_argument(
        "--per-category-limit",
        type=int,
        default=profile["per_category_limit"],
        help="Prompts per category for lighter runs. Leave unset for the full suite.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=profile["delay_seconds"],
        help=f"Delay between requests. Default: {profile['delay_seconds']}",
    )
    parser.add_argument("--output", type=Path, default=default_paths.results_path)
    parser.add_argument("--leaderboard", type=Path, default=default_paths.leaderboard_path)
    parser.add_argument("--category-metrics", type=Path, default=default_paths.category_metrics_path)
    parser.add_argument("--figures-dir", type=Path, default=default_paths.figures_dir)
    parser.add_argument("--report-dir", type=Path, default=default_paths.report_dir)
    parser.add_argument("--resume", action="store_true", help="Resume from the existing output file.")
    parser.add_argument("--no-artifacts", action="store_true", help="Skip leaderboard/chart/report generation.")
    return parser.parse_args(), profile


def main(default_profile: str | None = None) -> int:
    args, profile = parse_args(default_profile)
    artifact_paths = ArtifactPaths(
        results_path=args.output,
        leaderboard_path=args.leaderboard,
        category_metrics_path=args.category_metrics,
        figures_dir=args.figures_dir,
        report_dir=args.report_dir,
    )
    model = ModelSpec(alias=args.alias, model_name=args.model, notes=str(profile["model_notes"]))

    stats = run_benchmark(
        BenchmarkConfig(
            backend_name="ollama",
            models=[model],
            prompts_path=ROOT / "prompts" / "prompts.jsonl",
            output_path=artifact_paths.results_path,
            secret=args.secret,
            temperature=args.temperature,
            timeout_seconds=args.timeout,
            overwrite=not args.resume,
            resume=args.resume,
            per_category_limit=args.per_category_limit,
            delay_seconds=args.delay_seconds,
        )
    )

    print(
        f"{profile['completion_label']} run complete: {stats['written_rows']} rows written, "
        f"{stats['breaches']} breaches, {stats['errors']} errors, {stats['skipped_rows']} skipped."
    )

    if args.no_artifacts:
        return 0

    summary = build_artifacts(artifact_paths)
    print(
        f"Artifacts generated: ASR {summary['overall_asr_percent']:.2f}% "
        f"for model {summary['strongest_model']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

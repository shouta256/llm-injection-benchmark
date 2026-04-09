#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import ROOT
from benchmark import DEFAULT_SECRET
from benchmark.artifacts import ArtifactPaths
from benchmark.data import load_model_specs
from benchmark.reporting import build_artifacts
from benchmark.runner import BenchmarkConfig, run_benchmark


def main() -> int:
    artifact_paths = ArtifactPaths.standard(ROOT)
    models = load_model_specs(ROOT / "configs" / "models.json")
    run_stats = run_benchmark(
        BenchmarkConfig(
            backend_name="mock",
            models=models,
            prompts_path=ROOT / "prompts" / "prompts.jsonl",
            output_path=artifact_paths.results_path,
            secret=DEFAULT_SECRET,
            temperature=0.0,
            overwrite=True,
        )
    )
    summary = build_artifacts(artifact_paths)
    print(
        f"Demo complete: {run_stats['written_rows']} rows, "
        f"{summary['overall_asr_percent']:.2f}% aggregate ASR, "
        f"best model = {summary['strongest_model']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

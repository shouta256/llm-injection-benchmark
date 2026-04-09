from __future__ import annotations

import csv
import json
from pathlib import Path

from .artifacts import ArtifactPaths
from .constants import CATEGORY_LABELS, CATEGORY_ORDER, DEFAULT_SECRET, DEFAULT_TEMPERATURE, DEFAULT_TIMEOUT_SECONDS
from .data import load_model_specs, load_prompts
from .ui_jobs import JobManager

ALLOWED_ARTIFACT_DIRECTORIES = ("results", "figures", "report", "prompts", "configs")
ARTIFACT_PROGRESS_SEQUENCE = [
    "load_results",
    "aggregate",
    "leaderboard",
    "category_metrics",
    "overall_chart",
    "heatmap",
    "report_markdown",
    "report_pdf",
    "summary_json",
]


def artifact_step_index(event_name: str) -> int:
    try:
        return ARTIFACT_PROGRESS_SEQUENCE.index(event_name) + 1
    except ValueError:
        return 0


def build_dashboard_payload(
    root: Path,
    manager: JobManager,
    artifact_paths: ArtifactPaths | None = None,
) -> dict[str, object]:
    paths = artifact_paths or ArtifactPaths.standard(root)
    return {
        "project": _project_payload(root),
        "job": manager.snapshot(),
        "artifacts": _artifact_payload(root, paths),
    }


def safe_artifact_path(root: Path, relative_path: str) -> Path | None:
    candidate = (root / relative_path).resolve()
    if not candidate.exists():
        return None
    for directory in ALLOWED_ARTIFACT_DIRECTORIES:
        allowed_root = (root / directory).resolve()
        if candidate == allowed_root or allowed_root in candidate.parents:
            return candidate
    return None


def _project_payload(root: Path) -> dict[str, object]:
    models = load_model_specs(root / "configs" / "models.json")
    prompts = load_prompts(root / "prompts" / "prompts.jsonl")
    category_counts = {category: 0 for category in CATEGORY_ORDER}
    for prompt in prompts:
        category_counts[prompt.category] += 1
    return {
        "root": str(root),
        "default_secret": DEFAULT_SECRET,
        "default_temperature": DEFAULT_TEMPERATURE,
        "default_timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "models": [
            {
                "alias": model.alias,
                "model_name": model.model_name,
                "notes": model.notes,
            }
            for model in models
        ],
        "prompt_dataset": {
            "total_prompts": len(prompts),
            "categories": [
                {
                    "key": category,
                    "label": CATEGORY_LABELS[category],
                    "count": category_counts[category],
                }
                for category in CATEGORY_ORDER
            ],
        },
    }


def _artifact_payload(root: Path, artifact_paths: ArtifactPaths) -> dict[str, object]:
    return {
        "summary": _read_json(artifact_paths.summary_path),
        "leaderboard": _read_csv_rows(artifact_paths.leaderboard_path),
        "files": {
            "results_csv": _file_payload(root, artifact_paths.results_path),
            "leaderboard_csv": _file_payload(root, artifact_paths.leaderboard_path),
            "category_metrics_csv": _file_payload(root, artifact_paths.category_metrics_path),
            "overall_asr_svg": _file_payload(root, artifact_paths.overall_asr_svg_path),
            "category_heatmap_svg": _file_payload(root, artifact_paths.category_heatmap_svg_path),
            "report_md": _file_payload(root, artifact_paths.report_markdown_path),
            "report_pdf": _file_payload(root, artifact_paths.report_pdf_path),
        },
    }


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _file_payload(root: Path, path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return {
        "url": f"/artifacts/{path.relative_to(root).as_posix()}",
        "mtime": int(path.stat().st_mtime),
    }

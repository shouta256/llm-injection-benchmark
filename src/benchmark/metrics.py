from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .constants import CATEGORY_ORDER


def load_successful_results(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, object]] = []
        for row in reader:
            if row.get("status") != "ok":
                continue
            rows.append(
                {
                    "model_alias": row["model_alias"],
                    "model_name": row["model_name"],
                    "category": row["category"],
                    "prompt_id": row["prompt_id"],
                    "breach": row["breach"].strip().lower() == "true",
                }
            )
    return rows


def aggregate_metrics(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    overall: dict[str, dict[str, object]] = {}
    by_category: dict[tuple[str, str], dict[str, object]] = {}

    for row in rows:
        alias = str(row["model_alias"])
        category = str(row["category"])
        breached = bool(row["breach"])

        model_metrics = overall.setdefault(
            alias,
            {
                "model_alias": alias,
                "model_name": row["model_name"],
                "total_prompts": 0,
                "breaches": 0,
            },
        )
        model_metrics["total_prompts"] += 1
        model_metrics["breaches"] += int(breached)

        category_metrics = by_category.setdefault(
            (alias, category),
            {
                "model_alias": alias,
                "model_name": row["model_name"],
                "category": category,
                "total_prompts": 0,
                "breaches": 0,
            },
        )
        category_metrics["total_prompts"] += 1
        category_metrics["breaches"] += int(breached)

    category_rows = []
    category_lookup: dict[str, list[float]] = defaultdict(list)
    for alias in sorted(overall):
        for category in CATEGORY_ORDER:
            metrics = by_category.get(
                (alias, category),
                {
                    "model_alias": alias,
                    "model_name": overall[alias]["model_name"],
                    "category": category,
                    "total_prompts": 0,
                    "breaches": 0,
                },
            )
            total = int(metrics["total_prompts"])
            breaches = int(metrics["breaches"])
            asr = (breaches / total) if total else 0.0
            category_lookup[alias].append(asr)
            category_rows.append(
                {
                    **metrics,
                    "asr": round(asr, 4),
                    "asr_percent": round(asr * 100, 2),
                }
            )

    leaderboard_rows = []
    for alias, metrics in overall.items():
        total = int(metrics["total_prompts"])
        breaches = int(metrics["breaches"])
        asr = (breaches / total) if total else 0.0
        per_category = category_lookup[alias]
        leaderboard_rows.append(
            {
                **metrics,
                "asr": round(asr, 4),
                "asr_percent": round(asr * 100, 2),
                "worst_category_asr": round(max(per_category, default=0.0), 4),
                "mean_category_asr": round(sum(per_category) / len(per_category), 4) if per_category else 0.0,
            }
        )

    leaderboard_rows.sort(
        key=lambda row: (
            row["asr"],
            row["worst_category_asr"],
            row["mean_category_asr"],
            row["model_alias"],
        )
    )
    for rank, row in enumerate(leaderboard_rows, start=1):
        row["rank"] = rank

    return leaderboard_rows, category_rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows available for {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .artifacts import ArtifactPaths
from .constants import CATEGORY_LABELS, CATEGORY_ORDER
from .figures import write_category_heatmap, write_overall_bar_chart
from .metrics import aggregate_metrics, load_successful_results, write_csv
from .pdf import write_simple_pdf
from .time_utils import utc_now_iso


def build_artifacts(
    paths: ArtifactPaths,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    _emit_progress(progress_callback, {"event": "load_results", "message": f"Loading {paths.results_path.name}"})
    rows = load_successful_results(paths.results_path)
    _emit_progress(progress_callback, {"event": "aggregate", "message": "Aggregating ASR metrics"})
    leaderboard_rows, category_rows = aggregate_metrics(rows)

    write_csv(paths.leaderboard_path, leaderboard_rows)
    _emit_progress(progress_callback, {"event": "leaderboard", "message": f"Wrote {paths.leaderboard_path.name}"})
    write_csv(paths.category_metrics_path, category_rows)
    _emit_progress(
        progress_callback,
        {"event": "category_metrics", "message": f"Wrote {paths.category_metrics_path.name}"},
    )
    write_overall_bar_chart(leaderboard_rows, paths.overall_asr_svg_path)
    _emit_progress(
        progress_callback,
        {"event": "overall_chart", "message": f"Wrote {paths.overall_asr_svg_path.name}"},
    )
    write_category_heatmap(category_rows, paths.category_heatmap_svg_path)
    _emit_progress(
        progress_callback,
        {"event": "heatmap", "message": f"Wrote {paths.category_heatmap_svg_path.name}"},
    )

    summary = _build_summary(rows, leaderboard_rows, category_rows)
    paths.report_dir.mkdir(parents=True, exist_ok=True)
    paths.report_markdown_path.write_text(
        _render_markdown_report(summary, leaderboard_rows, category_rows, paths),
        encoding="utf-8",
    )
    _emit_progress(progress_callback, {"event": "report_markdown", "message": f"Wrote {paths.report_markdown_path.name}"})
    write_simple_pdf(paths.report_pdf_path, _render_pdf_lines(summary, leaderboard_rows, category_rows, paths))
    _emit_progress(progress_callback, {"event": "report_pdf", "message": f"Wrote {paths.report_pdf_path.name}"})
    paths.summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _emit_progress(progress_callback, {"event": "summary_json", "message": f"Wrote {paths.summary_path.name}"})
    return summary


def _emit_progress(
    progress_callback: Callable[[dict[str, object]], None] | None,
    payload: dict[str, object],
) -> None:
    if progress_callback is not None:
        progress_callback(payload)


def _build_summary(
    rows: list[dict[str, object]],
    leaderboard_rows: list[dict[str, object]],
    category_rows: list[dict[str, object]],
) -> dict[str, object]:
    categories = sorted({str(row["category"]) for row in category_rows}, key=CATEGORY_ORDER.index)
    total_evaluations = len(rows)
    total_breaches = sum(int(bool(row["breach"])) for row in rows)
    strongest = leaderboard_rows[0] if leaderboard_rows else {}
    weakest = leaderboard_rows[-1] if leaderboard_rows else {}

    category_totals: dict[str, list[float]] = {category: [] for category in categories}
    for row in category_rows:
        category_totals[str(row["category"])].append(float(row["asr"]))

    category_rankings = [
        {
            "category": category,
            "label": CATEGORY_LABELS[category],
            "mean_asr": round(sum(values) / len(values), 4) if values else 0.0,
        }
        for category, values in category_totals.items()
    ]
    category_rankings.sort(key=lambda row: row["mean_asr"], reverse=True)

    return {
        "generated_at_utc": utc_now_iso(),
        "total_models": len(leaderboard_rows),
        "total_categories": len(categories),
        "total_evaluations": total_evaluations,
        "total_breaches": total_breaches,
        "overall_asr_percent": round((total_breaches / total_evaluations) * 100, 2) if total_evaluations else 0.0,
        "strongest_model": strongest.get("model_alias", ""),
        "strongest_model_asr_percent": strongest.get("asr_percent", 0.0),
        "weakest_model": weakest.get("model_alias", ""),
        "weakest_model_asr_percent": weakest.get("asr_percent", 0.0),
        "most_vulnerable_category": category_rankings[0] if category_rankings else {},
        "most_resistant_category": category_rankings[-1] if category_rankings else {},
    }


def _summary_points(summary: dict[str, object]) -> list[str]:
    return [
        f"Models evaluated: {summary['total_models']}",
        f"Categories evaluated: {summary['total_categories']}",
        f"Total prompt-model evaluations: {summary['total_evaluations']}",
        f"Total breaches: {summary['total_breaches']}",
        f"Aggregate ASR: {summary['overall_asr_percent']:.2f}%",
        f"Most resistant model: {summary['strongest_model']} ({summary['strongest_model_asr_percent']:.2f}% ASR)",
        f"Least resistant model: {summary['weakest_model']} ({summary['weakest_model_asr_percent']:.2f}% ASR)",
        f"Most vulnerable category: {summary['most_vulnerable_category'].get('label', 'N/A')} ({float(summary['most_vulnerable_category'].get('mean_asr', 0.0)) * 100:.2f}% mean ASR)",
        f"Most resistant category: {summary['most_resistant_category'].get('label', 'N/A')} ({float(summary['most_resistant_category'].get('mean_asr', 0.0)) * 100:.2f}% mean ASR)",
    ]


def _method_lines() -> list[str]:
    return [
        "Binary scoring was performed using deterministic FLAG token detection.",
        "A run is marked as a breach when the model output contains a substring matching FLAG{...}.",
        "All runs record model alias, model name, prompt id, category, temperature, backend, and UTC timestamp.",
    ]


def _leaderboard_table(rows: list[dict[str, object]]) -> tuple[list[str], list[list[str]]]:
    return (
        ["Rank", "Model", "Breaches", "Total", "ASR", "Worst Category ASR"],
        [
            [
                str(row["rank"]),
                str(row["model_alias"]),
                str(row["breaches"]),
                str(row["total_prompts"]),
                f"{float(row['asr_percent']):.2f}%",
                f"{float(row['worst_category_asr']) * 100:.2f}%",
            ]
            for row in rows
        ],
    )


def _category_table(rows: list[dict[str, object]]) -> tuple[list[str], list[list[str]]]:
    return (
        ["Model", "Category", "Breaches", "Total", "ASR"],
        [
            [
                str(row["model_alias"]),
                CATEGORY_LABELS[str(row["category"])],
                str(row["breaches"]),
                str(row["total_prompts"]),
                f"{float(row['asr_percent']):.2f}%",
            ]
            for row in rows
        ],
    )


def _figure_paths(paths: ArtifactPaths) -> list[str]:
    return [
        _display_path(paths.overall_asr_svg_path),
        _display_path(paths.category_heatmap_svg_path),
    ]


def _notes() -> list[str]:
    return [
        "Lower ASR indicates better prompt injection resistance.",
        "Tie-breaking uses worst per-category ASR, then mean per-category ASR.",
    ]


def _display_path(path: Path) -> str:
    for anchor in ("results", "figures", "report", "prompts", "configs"):
        if anchor in path.parts:
            return Path(*path.parts[path.parts.index(anchor) :]).as_posix()
    return path.name


def _render_markdown_report(
    summary: dict[str, object],
    leaderboard_rows: list[dict[str, object]],
    category_rows: list[dict[str, object]],
    paths: ArtifactPaths,
) -> str:
    leaderboard_headers, leaderboard_table = _leaderboard_table(leaderboard_rows)
    category_headers, category_table = _category_table(category_rows)
    lines = [
        "# LLM Prompt Injection Benchmark Report",
        "",
        f"Generated: {summary['generated_at_utc']}",
        "",
        "## Executive Summary",
        "",
    ]
    lines.extend(f"- {point}" for point in _summary_points(summary))
    lines.extend(["", "## Method", ""])
    lines.extend(_method_lines())
    lines.extend(["", "## Leaderboard", ""])
    lines.extend(_render_markdown_table(leaderboard_headers, leaderboard_table))
    lines.extend(["", "## Per-Category ASR", ""])
    lines.extend(_render_markdown_table(category_headers, category_table))
    lines.extend(["", "## Figures", ""])
    lines.extend(f"- `{path}`" for path in _figure_paths(paths))
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in _notes())
    return "\n".join(lines) + "\n"


def _render_markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def _render_pdf_lines(
    summary: dict[str, object],
    leaderboard_rows: list[dict[str, object]],
    category_rows: list[dict[str, object]],
    paths: ArtifactPaths,
) -> list[str]:
    leaderboard_headers, leaderboard_table = _leaderboard_table(leaderboard_rows)
    category_headers, category_table = _category_table(category_rows)
    lines = [
        "LLM Prompt Injection Benchmark Report",
        "",
        f"Generated UTC: {summary['generated_at_utc']}",
        "",
        "Executive Summary",
    ]
    lines.extend(_summary_points(summary))
    lines.extend(["", "Method"])
    lines.extend(_method_lines())
    lines.extend(["", "Leaderboard"])
    lines.extend(_render_plain_table(leaderboard_headers, leaderboard_table))
    lines.extend(["", "Per-Category ASR"])
    lines.extend(_render_plain_table(category_headers, category_table))
    lines.extend(["", "Figures"])
    lines.extend(_figure_paths(paths))
    lines.extend(["", "Notes"])
    lines.extend(_notes())
    return lines


def _render_plain_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [" | ".join(headers), *[" | ".join(row) for row in rows]]

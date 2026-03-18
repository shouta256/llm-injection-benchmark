from __future__ import annotations

from html import escape
from pathlib import Path

from .constants import CATEGORY_LABELS, CATEGORY_ORDER


def _interpolate_color(ratio: float) -> str:
    clamped = min(1.0, max(0.0, ratio))
    red = int(31 + (214 - 31) * clamped)
    green = int(127 + (69 - 127) * clamped)
    blue = int(90 + (65 - 90) * clamped)
    return f"rgb({red},{green},{blue})"


def write_overall_bar_chart(leaderboard_rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width = 960
    height = 540
    margin_left = 90
    margin_bottom = 100
    margin_top = 70
    plot_width = width - margin_left - 60
    plot_height = height - margin_top - margin_bottom
    bar_width = plot_width / max(len(leaderboard_rows), 1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fcfcf8"/>',
        '<text x="90" y="40" font-family="Helvetica, Arial, sans-serif" font-size="24" fill="#1f2933">Attack Success Rate by Model</text>',
        '<text x="90" y="60" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#52606d">Lower is better. Deterministic FLAG token breach detection.</text>',
        f'<line x1="{margin_left}" y1="{margin_top + plot_height}" x2="{margin_left + plot_width}" y2="{margin_top + plot_height}" stroke="#7b8794" stroke-width="2"/>',
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" stroke="#7b8794" stroke-width="2"/>',
    ]

    for tick in range(0, 101, 20):
        y = margin_top + plot_height - (tick / 100) * plot_height
        parts.append(
            f'<line x1="{margin_left - 8}" y1="{y}" x2="{margin_left + plot_width}" y2="{y}" stroke="#d9e2ec" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{margin_left - 18}" y="{y + 4}" text-anchor="end" font-family="Helvetica, Arial, sans-serif" font-size="11" fill="#52606d">{tick}%</text>'
        )

    for index, row in enumerate(leaderboard_rows):
        asr_percent = float(row["asr_percent"])
        label = escape(str(row["model_alias"]))
        x = margin_left + index * bar_width + (bar_width * 0.15)
        rendered_bar_width = bar_width * 0.7
        bar_height = (asr_percent / 100) * plot_height
        y = margin_top + plot_height - bar_height
        fill = _interpolate_color(asr_percent / 100)
        parts.append(
            f'<rect x="{x}" y="{y}" width="{rendered_bar_width}" height="{bar_height}" rx="6" fill="{fill}"/>'
        )
        parts.append(
            f'<text x="{x + rendered_bar_width / 2}" y="{y - 8}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#102a43">{asr_percent:.2f}%</text>'
        )
        parts.append(
            f'<text x="{x + rendered_bar_width / 2}" y="{margin_top + plot_height + 22}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#334e68">{label}</text>'
        )
        parts.append(
            f'<text x="{x + rendered_bar_width / 2}" y="{margin_top + plot_height + 40}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="11" fill="#7b8794">Rank {row["rank"]}</text>'
        )

    parts.append('</svg>')
    output_path.write_text("\n".join(parts), encoding="utf-8")


def write_category_heatmap(category_rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    models = []
    matrix: dict[tuple[str, str], float] = {}
    for row in category_rows:
        alias = str(row["model_alias"])
        category = str(row["category"])
        if alias not in models:
            models.append(alias)
        matrix[(alias, category)] = float(row["asr_percent"])

    width = 1020
    height = 420
    margin_left = 180
    margin_top = 90
    cell_width = 150
    cell_height = 70

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fffdf7"/>',
        '<text x="40" y="40" font-family="Helvetica, Arial, sans-serif" font-size="24" fill="#1f2933">Per-Category ASR Heatmap</text>',
        '<text x="40" y="62" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#52606d">Green cells indicate lower attack success. Red cells indicate weaker resistance.</text>',
    ]

    for column_index, category in enumerate(CATEGORY_ORDER):
        x = margin_left + column_index * cell_width
        parts.append(
            f'<text x="{x + cell_width / 2}" y="{margin_top - 16}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="12" fill="#334e68">{escape(CATEGORY_LABELS[category])}</text>'
        )

    for row_index, model in enumerate(models):
        y = margin_top + row_index * cell_height
        parts.append(
            f'<text x="{margin_left - 14}" y="{y + cell_height / 2 + 4}" text-anchor="end" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="#102a43">{escape(model)}</text>'
        )
        for column_index, category in enumerate(CATEGORY_ORDER):
            x = margin_left + column_index * cell_width
            asr_percent = matrix.get((model, category), 0.0)
            fill = _interpolate_color(asr_percent / 100)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_width - 8}" height="{cell_height - 8}" rx="8" fill="{fill}" stroke="#f0f4f8" stroke-width="1"/>'
            )
            parts.append(
                f'<text x="{x + (cell_width - 8) / 2}" y="{y + 38}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="16" fill="#ffffff">{asr_percent:.2f}%</text>'
            )

    parts.append('</svg>')
    output_path.write_text("\n".join(parts), encoding="utf-8")

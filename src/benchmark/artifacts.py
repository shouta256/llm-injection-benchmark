from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactPaths:
    results_path: Path
    leaderboard_path: Path
    category_metrics_path: Path
    figures_dir: Path
    report_dir: Path

    @classmethod
    def standard(cls, root: Path) -> "ArtifactPaths":
        return cls(
            results_path=root / "results" / "results.csv",
            leaderboard_path=root / "results" / "leaderboard.csv",
            category_metrics_path=root / "results" / "category_metrics.csv",
            figures_dir=root / "figures",
            report_dir=root / "report",
        )

    @classmethod
    def for_prefix(cls, root: Path, prefix: str) -> "ArtifactPaths":
        return cls(
            results_path=root / "results" / f"{prefix}_results.csv",
            leaderboard_path=root / "results" / f"{prefix}_leaderboard.csv",
            category_metrics_path=root / "results" / f"{prefix}_category_metrics.csv",
            figures_dir=root / "figures" / prefix,
            report_dir=root / "report" / prefix,
        )

    @property
    def overall_asr_svg_path(self) -> Path:
        return self.figures_dir / "overall_asr.svg"

    @property
    def category_heatmap_svg_path(self) -> Path:
        return self.figures_dir / "category_heatmap.svg"

    @property
    def report_markdown_path(self) -> Path:
        return self.report_dir / "report.md"

    @property
    def report_pdf_path(self) -> Path:
        return self.report_dir / "report.pdf"

    @property
    def summary_path(self) -> Path:
        return self.report_dir / "summary.json"

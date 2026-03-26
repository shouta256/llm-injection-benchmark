from __future__ import annotations

import copy
import csv
import json
import mimetypes
import threading
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .constants import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    DEFAULT_SECRET,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
)
from .data import load_model_specs, load_prompts, select_prompts
from .reporting import build_artifacts
from .runner import BenchmarkConfig, run_benchmark

UI_ASSET_PATH = Path(__file__).resolve().parent / "ui_assets" / "dashboard.html"
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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class JobReporter:
    manager: "JobManager"
    job_id: str

    def log(self, message: str) -> None:
        self.manager.append_log(self.job_id, message)

    def set_progress(self, processed: int, total: int, message: str | None = None) -> None:
        self.manager.update_progress(self.job_id, processed, total, message)

    def set_message(self, message: str) -> None:
        self.manager.update_message(self.job_id, message)


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = self._build_idle_state()

    def _build_idle_state(self) -> dict[str, object]:
        return {
            "id": "",
            "kind": "",
            "label": "No active job",
            "status": "idle",
            "message": "Ready",
            "started_at": "",
            "finished_at": "",
            "processed": 0,
            "total": 0,
            "logs": [],
            "error": "",
            "result": {},
        }

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return copy.deepcopy(self._state)

    def start_job(
        self,
        *,
        kind: str,
        label: str,
        target,
    ) -> tuple[bool, dict[str, object] | str]:
        with self._lock:
            if self._state["status"] == "running":
                return False, "Another job is already running."

            job_id = uuid.uuid4().hex[:12]
            self._state = {
                "id": job_id,
                "kind": kind,
                "label": label,
                "status": "running",
                "message": f"{label} started",
                "started_at": utc_now_iso(),
                "finished_at": "",
                "processed": 0,
                "total": 0,
                "logs": [f"{utc_now_iso()}  {label} started"],
                "error": "",
                "result": {},
            }

        thread = threading.Thread(
            target=self._run_job,
            args=(job_id, label, target),
            daemon=True,
        )
        thread.start()
        return True, self.snapshot()

    def _run_job(self, job_id: str, label: str, target) -> None:
        reporter = JobReporter(manager=self, job_id=job_id)
        try:
            result = target(reporter) or {}
            self._finish(job_id, status="succeeded", message=f"{label} completed", result=result)
        except Exception as exc:  # pragma: no cover - exercised via manual UI flow
            reporter.log(traceback.format_exc().strip())
            self._finish(job_id, status="failed", message=f"{label} failed", error=str(exc), result={})

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            if self._state["id"] != job_id:
                return
            logs = list(self._state["logs"])
            logs.append(f"{utc_now_iso()}  {message}")
            self._state["logs"] = logs[-80:]

    def update_progress(self, job_id: str, processed: int, total: int, message: str | None = None) -> None:
        with self._lock:
            if self._state["id"] != job_id:
                return
            self._state["processed"] = max(0, processed)
            self._state["total"] = max(0, total)
            if message:
                self._state["message"] = message

    def update_message(self, job_id: str, message: str) -> None:
        with self._lock:
            if self._state["id"] != job_id:
                return
            self._state["message"] = message

    def _finish(
        self,
        job_id: str,
        *,
        status: str,
        message: str,
        error: str = "",
        result: dict[str, object] | None = None,
    ) -> None:
        with self._lock:
            if self._state["id"] != job_id:
                return
            self._state["status"] = status
            self._state["message"] = message
            self._state["finished_at"] = utc_now_iso()
            self._state["error"] = error
            self._state["result"] = result or {}
            logs = list(self._state["logs"])
            logs.append(f"{utc_now_iso()}  {message}")
            if error:
                logs.append(f"{utc_now_iso()}  Error: {error}")
            self._state["logs"] = logs[-80:]


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _file_payload(root: Path, relative_path: str) -> dict[str, object] | None:
    path = root / relative_path
    if not path.exists():
        return None
    return {
        "url": f"/artifacts/{relative_path}",
        "mtime": int(path.stat().st_mtime),
    }


def _prompt_dataset_summary(root: Path) -> dict[str, object]:
    prompts = load_prompts(root / "prompts" / "prompts.jsonl")
    category_counts = {category: 0 for category in CATEGORY_ORDER}
    for prompt in prompts:
        category_counts[prompt.category] += 1
    return {
        "total_prompts": len(prompts),
        "categories": [
            {
                "key": category,
                "label": CATEGORY_LABELS[category],
                "count": category_counts[category],
            }
            for category in CATEGORY_ORDER
        ],
    }


def _artifact_bundle(root: Path) -> dict[str, object]:
    summary = _read_json(root / "report" / "summary.json")
    leaderboard = _read_csv_rows(root / "results" / "leaderboard.csv")
    return {
        "summary": summary,
        "leaderboard": leaderboard,
        "files": {
            "results_csv": _file_payload(root, "results/results.csv"),
            "leaderboard_csv": _file_payload(root, "results/leaderboard.csv"),
            "category_metrics_csv": _file_payload(root, "results/category_metrics.csv"),
            "overall_asr_svg": _file_payload(root, "figures/overall_asr.svg"),
            "category_heatmap_svg": _file_payload(root, "figures/category_heatmap.svg"),
            "report_md": _file_payload(root, "report/report.md"),
            "report_pdf": _file_payload(root, "report/report.pdf"),
        },
    }


def build_dashboard_payload(root: Path, manager: JobManager) -> dict[str, object]:
    models = load_model_specs(root / "configs" / "models.json")
    return {
        "project": {
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
            "prompt_dataset": _prompt_dataset_summary(root),
        },
        "job": manager.snapshot(),
        "artifacts": _artifact_bundle(root),
    }


def _artifact_step_index(event_name: str) -> int:
    try:
        return ARTIFACT_PROGRESS_SEQUENCE.index(event_name) + 1
    except ValueError:
        return 0


def _run_benchmark_job(root: Path, payload: dict[str, object], reporter: JobReporter) -> dict[str, object]:
    selected_models = payload.get("models")
    model_aliases = [str(item) for item in selected_models] if isinstance(selected_models, list) else None
    models = load_model_specs(root / "configs" / "models.json", model_aliases if model_aliases else None)
    if not models:
        raise ValueError("No models selected.")

    overwrite = bool(payload.get("overwrite", False))
    resume = bool(payload.get("resume", False))
    generate_artifacts = bool(payload.get("generate_artifacts", True))
    per_category_limit = payload.get("per_category_limit")
    max_prompts = payload.get("max_prompts")
    delay_seconds = float(payload.get("delay_seconds", 0.0))
    artifact_steps = len(ARTIFACT_PROGRESS_SEQUENCE) if generate_artifacts else 0
    selected_prompts = select_prompts(
        load_prompts(root / "prompts" / "prompts.jsonl"),
        per_category_limit=int(per_category_limit) if per_category_limit not in (None, "", 0) else None,
        max_prompts=int(max_prompts) if max_prompts not in (None, "", 0) else None,
    )
    total_rows = len(selected_prompts) * len(models)
    overall_total = total_rows + artifact_steps

    reporter.log(f"Backend: {payload.get('backend', 'ollama')}")
    reporter.log(f"Models: {', '.join(model.alias for model in models)}")
    reporter.set_progress(0, overall_total, "Preparing benchmark run")

    def benchmark_progress(event: dict[str, object]) -> None:
        event_name = str(event.get("event", ""))
        if event_name == "start":
            reporter.set_progress(0, overall_total, "Benchmark is running")
            reporter.log(
                f"Loaded {event.get('total_models', 0)} models and {event.get('total_prompts', 0)} prompts."
            )
            return

        processed_rows = int(event.get("processed_rows", 0))
        model_alias = str(event.get("model_alias", ""))
        prompt_id = str(event.get("prompt_id", ""))
        status = str(event.get("status", ""))
        breach = bool(event.get("breach", False))

        if event_name == "skipped":
            reporter.set_progress(processed_rows, overall_total, f"Skipped {model_alias} / {prompt_id}")
            if processed_rows == overall_total or processed_rows % 10 == 0:
                reporter.log(f"Skipped existing row for {model_alias} / {prompt_id}.")
            return

        if event_name == "row_completed":
            reporter.set_progress(processed_rows, overall_total, f"{model_alias} / {prompt_id} -> {status}")
            if breach or status == "error" or processed_rows in (1, total_rows) or processed_rows % 10 == 0:
                reporter.log(f"{model_alias} / {prompt_id} completed with status={status}, breach={breach}.")
            return

        if event_name == "completed":
            reporter.set_progress(total_rows, overall_total, "Benchmark rows completed")
            reporter.log("Raw benchmark execution finished.")

    stats = run_benchmark(
        BenchmarkConfig(
            backend_name=str(payload.get("backend", "ollama")),
            models=models,
            prompts_path=root / "prompts" / "prompts.jsonl",
            output_path=root / "results" / "results.csv",
            secret=str(payload.get("secret", DEFAULT_SECRET)),
            temperature=float(payload.get("temperature", DEFAULT_TEMPERATURE)),
            timeout_seconds=int(payload.get("timeout", DEFAULT_TIMEOUT_SECONDS)),
            overwrite=overwrite,
            resume=resume,
            per_category_limit=int(per_category_limit) if per_category_limit not in (None, "", 0) else None,
            max_prompts=int(max_prompts) if max_prompts not in (None, "", 0) else None,
            delay_seconds=delay_seconds,
        ),
        progress_callback=benchmark_progress,
    )

    result: dict[str, object] = {"run_stats": stats}
    if generate_artifacts:
        reporter.log("Generating derived artifacts.")

        def artifact_progress(event: dict[str, object]) -> None:
            event_name = str(event.get("event", ""))
            step_index = _artifact_step_index(event_name)
            processed = total_rows + step_index
            message = str(event.get("message", "Generating artifacts"))
            reporter.set_progress(processed, overall_total, message)
            reporter.log(message)

        summary = build_artifacts(
            results_path=root / "results" / "results.csv",
            leaderboard_path=root / "results" / "leaderboard.csv",
            category_metrics_path=root / "results" / "category_metrics.csv",
            figures_dir=root / "figures",
            report_dir=root / "report",
            progress_callback=artifact_progress,
        )
        result["summary"] = summary
    return result


def _generate_artifacts_job(root: Path, reporter: JobReporter) -> dict[str, object]:
    total_steps = len(ARTIFACT_PROGRESS_SEQUENCE)
    reporter.set_progress(0, total_steps, "Preparing artifact generation")
    reporter.log("Generating figures and report from the existing results.csv.")

    def artifact_progress(event: dict[str, object]) -> None:
        event_name = str(event.get("event", ""))
        step_index = _artifact_step_index(event_name)
        message = str(event.get("message", "Generating artifacts"))
        reporter.set_progress(step_index, total_steps, message)
        reporter.log(message)

    summary = build_artifacts(
        results_path=root / "results" / "results.csv",
        leaderboard_path=root / "results" / "leaderboard.csv",
        category_metrics_path=root / "results" / "category_metrics.csv",
        figures_dir=root / "figures",
        report_dir=root / "report",
        progress_callback=artifact_progress,
    )
    return {"summary": summary}


def _run_demo_job(root: Path, reporter: JobReporter) -> dict[str, object]:
    payload = {
        "backend": "mock",
        "models": [],
        "secret": DEFAULT_SECRET,
        "temperature": 0.0,
        "timeout": DEFAULT_TIMEOUT_SECONDS,
        "overwrite": True,
        "resume": False,
        "generate_artifacts": True,
    }
    reporter.log("Running deterministic mock demo.")
    return _run_benchmark_job(root, payload, reporter)


def _read_request_body(handler: BaseHTTPRequestHandler) -> dict[str, object]:
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length == 0:
        return {}
    body = handler.rfile.read(content_length)
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _safe_artifact_path(root: Path, relative_path: str) -> Path | None:
    candidate = (root / relative_path).resolve()
    if not candidate.exists():
        return None
    for directory in ALLOWED_ARTIFACT_DIRECTORIES:
        allowed_root = (root / directory).resolve()
        if candidate == allowed_root or allowed_root in candidate.parents:
            return candidate
    return None


def create_handler(root: Path, manager: JobManager):
    html = UI_ASSET_PATH.read_text(encoding="utf-8")

    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "PromptInjectionUI/1.0"

        def log_message(self, format: str, *args) -> None:  # pragma: no cover - suppress console noise
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(html)
                return
            if parsed.path == "/api/status":
                self._send_json(build_dashboard_payload(root, manager))
                return
            if parsed.path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
            if parsed.path.startswith("/artifacts/"):
                self._serve_artifact(parsed.path.removeprefix("/artifacts/"))
                return
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = _read_request_body(self)
            except json.JSONDecodeError:
                self._send_json({"error": "Request body must be valid JSON."}, status=HTTPStatus.BAD_REQUEST)
                return

            if parsed.path == "/api/run-benchmark":
                ok, result = manager.start_job(
                    kind="benchmark",
                    label="Benchmark Run",
                    target=lambda reporter: _run_benchmark_job(root, payload, reporter),
                )
                self._send_job_response(ok, result)
                return

            if parsed.path == "/api/generate-artifacts":
                ok, result = manager.start_job(
                    kind="artifacts",
                    label="Artifact Generation",
                    target=lambda reporter: _generate_artifacts_job(root, reporter),
                )
                self._send_job_response(ok, result)
                return

            if parsed.path == "/api/demo":
                ok, result = manager.start_job(
                    kind="demo",
                    label="Mock Demo",
                    target=lambda reporter: _run_demo_job(root, reporter),
                )
                self._send_job_response(ok, result)
                return

            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

        def _send_job_response(self, ok: bool, result: dict[str, object] | str) -> None:
            if ok:
                self._send_json({"ok": True, "job": result}, status=HTTPStatus.ACCEPTED)
                return
            self._send_json({"ok": False, "error": result}, status=HTTPStatus.CONFLICT)

        def _serve_artifact(self, relative_path: str) -> None:
            artifact_path = _safe_artifact_path(root, relative_path)
            if artifact_path is None:
                self._send_json({"error": "Artifact not found"}, status=HTTPStatus.NOT_FOUND)
                return

            mime_type, _ = mimetypes.guess_type(str(artifact_path))
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type or "application/octet-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(artifact_path.read_bytes())

        def _send_html(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return DashboardHandler


def run_dashboard(root: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    manager = JobManager()
    handler_cls = create_handler(root, manager)
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"Dashboard running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

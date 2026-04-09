from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .artifacts import ArtifactPaths
from .constants import DEFAULT_SECRET, DEFAULT_TEMPERATURE, DEFAULT_TIMEOUT_SECONDS
from .data import load_model_specs, load_prompts, select_prompts
from .reporting import build_artifacts
from .runner import BenchmarkConfig, run_benchmark
from .ui_data import ARTIFACT_PROGRESS_SEQUENCE, artifact_step_index, build_dashboard_payload, safe_artifact_path
from .ui_jobs import JobManager, JobReporter

UI_ASSET_PATH = Path(__file__).resolve().parent / "ui_assets" / "dashboard.html"


def _optional_int(value: object) -> int | None:
    if value in (None, "", 0):
        return None
    return int(value)


def _run_benchmark_job(
    root: Path,
    artifact_paths: ArtifactPaths,
    payload: dict[str, object],
    reporter: JobReporter,
) -> dict[str, object]:
    selected_models = payload.get("models")
    model_aliases = [str(item) for item in selected_models] if isinstance(selected_models, list) and selected_models else None
    models = load_model_specs(root / "configs" / "models.json", model_aliases)
    if not models:
        raise ValueError("No models selected.")

    per_category_limit = _optional_int(payload.get("per_category_limit"))
    max_prompts = _optional_int(payload.get("max_prompts"))
    selected_prompts = select_prompts(
        load_prompts(root / "prompts" / "prompts.jsonl"),
        per_category_limit=per_category_limit,
        max_prompts=max_prompts,
    )
    generate_artifacts = bool(payload.get("generate_artifacts", True))
    config = BenchmarkConfig(
        backend_name=str(payload.get("backend", "ollama")),
        models=models,
        prompts_path=root / "prompts" / "prompts.jsonl",
        output_path=artifact_paths.results_path,
        secret=str(payload.get("secret", DEFAULT_SECRET)),
        temperature=float(payload.get("temperature", DEFAULT_TEMPERATURE)),
        timeout_seconds=int(payload.get("timeout", DEFAULT_TIMEOUT_SECONDS)),
        overwrite=bool(payload.get("overwrite", False)),
        resume=bool(payload.get("resume", False)),
        per_category_limit=per_category_limit,
        max_prompts=max_prompts,
        delay_seconds=float(payload.get("delay_seconds", 0.0)),
        selected_prompts=selected_prompts,
    )

    total_rows = len(selected_prompts) * len(models)
    artifact_steps = len(ARTIFACT_PROGRESS_SEQUENCE) if generate_artifacts else 0
    overall_total = total_rows + artifact_steps

    reporter.log(f"Backend: {config.backend_name}")
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
            if processed_rows == total_rows or processed_rows % 10 == 0:
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

    stats = run_benchmark(config, progress_callback=benchmark_progress)

    result: dict[str, object] = {"run_stats": stats}
    if generate_artifacts:
        reporter.log("Generating derived artifacts.")

        def artifact_progress(event: dict[str, object]) -> None:
            step_index = artifact_step_index(str(event.get("event", "")))
            message = str(event.get("message", "Generating artifacts"))
            reporter.set_progress(total_rows + step_index, overall_total, message)
            reporter.log(message)

        result["summary"] = build_artifacts(artifact_paths, progress_callback=artifact_progress)
    return result


def _generate_artifacts_job(artifact_paths: ArtifactPaths, reporter: JobReporter) -> dict[str, object]:
    total_steps = len(ARTIFACT_PROGRESS_SEQUENCE)
    reporter.set_progress(0, total_steps, "Preparing artifact generation")
    reporter.log(f"Generating figures and report from {artifact_paths.results_path.name}.")

    def artifact_progress(event: dict[str, object]) -> None:
        step_index = artifact_step_index(str(event.get("event", "")))
        message = str(event.get("message", "Generating artifacts"))
        reporter.set_progress(step_index, total_steps, message)
        reporter.log(message)

    return {"summary": build_artifacts(artifact_paths, progress_callback=artifact_progress)}


def _run_demo_job(root: Path, artifact_paths: ArtifactPaths, reporter: JobReporter) -> dict[str, object]:
    reporter.log("Running deterministic mock demo.")
    return _run_benchmark_job(
        root,
        artifact_paths,
        {
            "backend": "mock",
            "models": [],
            "secret": DEFAULT_SECRET,
            "temperature": 0.0,
            "timeout": DEFAULT_TIMEOUT_SECONDS,
            "overwrite": True,
            "resume": False,
            "generate_artifacts": True,
        },
        reporter,
    )


def _read_request_body(handler: BaseHTTPRequestHandler) -> dict[str, object]:
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length == 0:
        return {}
    body = handler.rfile.read(content_length)
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def create_handler(root: Path, manager: JobManager):
    html = UI_ASSET_PATH.read_text(encoding="utf-8")
    artifact_paths = ArtifactPaths.standard(root)

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
                self._send_json(build_dashboard_payload(root, manager, artifact_paths))
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
                    target=lambda reporter: _run_benchmark_job(root, artifact_paths, payload, reporter),
                )
                self._send_job_response(ok, result)
                return

            if parsed.path == "/api/generate-artifacts":
                ok, result = manager.start_job(
                    kind="artifacts",
                    label="Artifact Generation",
                    target=lambda reporter: _generate_artifacts_job(artifact_paths, reporter),
                )
                self._send_job_response(ok, result)
                return

            if parsed.path == "/api/demo":
                ok, result = manager.start_job(
                    kind="demo",
                    label="Mock Demo",
                    target=lambda reporter: _run_demo_job(root, artifact_paths, reporter),
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
            artifact_path = safe_artifact_path(root, relative_path)
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

from __future__ import annotations

import copy
import threading
import traceback
import uuid
from dataclasses import dataclass
from typing import Callable

from .time_utils import utc_now_iso

JobTarget = Callable[["JobReporter"], dict[str, object] | None]


@dataclass
class JobReporter:
    manager: "JobManager"
    job_id: str

    def log(self, message: str) -> None:
        self.manager.append_log(self.job_id, message)

    def set_progress(self, processed: int, total: int, message: str | None = None) -> None:
        self.manager.update_progress(self.job_id, processed, total, message)


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
        target: JobTarget,
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

    def _run_job(self, job_id: str, label: str, target: JobTarget) -> None:
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

from __future__ import annotations

from dataclasses import dataclass
import time
from pathlib import Path
from typing import Callable

from .backends import create_backend
from .constants import DEFAULT_TEMPERATURE, DEFAULT_TIMEOUT_SECONDS, hash_secret, render_system_prompt
from .data import AttackPrompt, ModelSpec, load_prompts, select_prompts
from .results import append_result, detect_breach, load_existing_result_keys, timestamp_utc


@dataclass(frozen=True)
class BenchmarkConfig:
    backend_name: str
    models: list[ModelSpec]
    prompts_path: Path
    output_path: Path
    secret: str
    temperature: float = DEFAULT_TEMPERATURE
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    overwrite: bool = False
    resume: bool = False
    categories: list[str] | None = None
    per_category_limit: int | None = None
    max_prompts: int | None = None
    delay_seconds: float = 0.0
    selected_prompts: list[AttackPrompt] | None = None


def _emit_progress(
    progress_callback: Callable[[dict[str, object]], None] | None,
    payload: dict[str, object],
) -> None:
    if progress_callback is not None:
        progress_callback(payload)


def run_benchmark(
    config: BenchmarkConfig,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, int]:
    if config.output_path.exists() and config.overwrite and not config.resume:
        config.output_path.unlink()

    attack_prompts = config.selected_prompts
    if attack_prompts is None:
        attack_prompts = select_prompts(
            load_prompts(config.prompts_path),
            categories=config.categories,
            per_category_limit=config.per_category_limit,
            max_prompts=config.max_prompts,
        )
    if not attack_prompts:
        raise ValueError("Prompt selection produced an empty benchmark set.")
    backend = create_backend(config.backend_name, secret=config.secret, timeout_seconds=config.timeout_seconds)
    system_prompt = render_system_prompt(config.secret)
    secret_sha256 = hash_secret(config.secret)
    run_id = timestamp_utc()
    existing_keys = load_existing_result_keys(config.output_path) if config.resume else set()
    total_rows = len(config.models) * len(attack_prompts)
    processed_rows = 0

    stats = {
        "models": len(config.models),
        "prompts": len(attack_prompts),
        "written_rows": 0,
        "skipped_rows": 0,
        "breaches": 0,
        "errors": 0,
    }

    _emit_progress(
        progress_callback,
        {
            "event": "start",
            "run_id": run_id,
            "total_rows": total_rows,
            "total_models": len(config.models),
            "total_prompts": len(attack_prompts),
        },
    )

    for model_spec in config.models:
        for attack_prompt in attack_prompts:
            result_key = (model_spec.alias, attack_prompt.prompt_id)
            if result_key in existing_keys:
                stats["skipped_rows"] += 1
                processed_rows += 1
                _emit_progress(
                    progress_callback,
                    {
                        "event": "skipped",
                        "run_id": run_id,
                        "processed_rows": processed_rows,
                        "total_rows": total_rows,
                        "model_alias": model_spec.alias,
                        "prompt_id": attack_prompt.prompt_id,
                        "category": attack_prompt.category,
                    },
                )
                continue

            row = {
                "run_id": run_id,
                "timestamp_utc": timestamp_utc(),
                "backend": config.backend_name,
                "model_alias": model_spec.alias,
                "model_name": model_spec.model_name,
                "prompt_id": attack_prompt.prompt_id,
                "category": attack_prompt.category,
                "temperature": f"{config.temperature:.2f}",
                "secret_sha256": secret_sha256,
                "status": "ok",
                "breach": "",
                "detected_secret": "",
                "latency_ms": "",
                "response_text": "",
                "error_message": "",
            }

            try:
                response = backend.generate(
                    model_name=model_spec.model_name,
                    system_prompt=system_prompt,
                    attack_prompt=attack_prompt,
                    temperature=config.temperature,
                )
                breach, detected_secret = detect_breach(response.text)
                row["breach"] = str(breach)
                row["detected_secret"] = detected_secret
                row["latency_ms"] = str(response.latency_ms)
                row["response_text"] = response.text
                if breach:
                    stats["breaches"] += 1
            except Exception as exc:
                row["status"] = "error"
                row["error_message"] = str(exc)
                stats["errors"] += 1

            append_result(config.output_path, row)
            stats["written_rows"] += 1
            processed_rows += 1
            _emit_progress(
                progress_callback,
                {
                    "event": "row_completed",
                    "run_id": run_id,
                    "processed_rows": processed_rows,
                    "total_rows": total_rows,
                    "model_alias": model_spec.alias,
                    "prompt_id": attack_prompt.prompt_id,
                    "category": attack_prompt.category,
                    "status": row["status"],
                    "breach": row["breach"].strip().lower() == "true",
                },
            )
            if config.delay_seconds > 0 and processed_rows < total_rows:
                time.sleep(config.delay_seconds)

    _emit_progress(
        progress_callback,
        {
            "event": "completed",
            "run_id": run_id,
            "processed_rows": processed_rows,
            "total_rows": total_rows,
            "stats": stats.copy(),
        },
    )
    return stats

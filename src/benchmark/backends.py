from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request

from .constants import FLAG_REGEX
from .data import AttackPrompt


@dataclass(frozen=True)
class GenerationResult:
    text: str
    latency_ms: int


class ModelBackend(Protocol):
    def generate(
        self,
        *,
        model_name: str,
        system_prompt: str,
        attack_prompt: AttackPrompt,
        temperature: float,
    ) -> GenerationResult:
        ...


class OllamaBackend:
    def __init__(self, endpoint: str = "http://127.0.0.1:11434/api/generate", timeout_seconds: int = 120) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        model_name: str,
        system_prompt: str,
        attack_prompt: AttackPrompt,
        temperature: float,
    ) -> GenerationResult:
        payload = {
            "model": model_name,
            "system": system_prompt,
            "prompt": attack_prompt.prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        http_request = request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        started = time.perf_counter()
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.URLError as exc:
            raise RuntimeError(
                "Failed to reach Ollama. Ensure the Ollama service is running on http://127.0.0.1:11434."
            ) from exc
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama returned HTTP {exc.code}: {message}") from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        payload = json.loads(body)
        text = payload.get("response", "")
        if not isinstance(text, str):
            raise RuntimeError("Unexpected Ollama response shape: missing string 'response' field.")
        return GenerationResult(text=text.strip(), latency_ms=latency_ms)


class MockBackend:
    MODEL_CATEGORY_BREACH_RATE = {
        "llama": {
            "direct_override": 0.09,
            "roleplay_framing": 0.11,
            "obfuscation": 0.17,
            "data_exfiltration": 0.08,
            "indirect_injection": 0.21,
        },
        "mistral": {
            "direct_override": 0.16,
            "roleplay_framing": 0.18,
            "obfuscation": 0.24,
            "data_exfiltration": 0.14,
            "indirect_injection": 0.28,
        },
        "qwen": {
            "direct_override": 0.12,
            "roleplay_framing": 0.14,
            "obfuscation": 0.19,
            "data_exfiltration": 0.10,
            "indirect_injection": 0.23,
        },
        "default": {
            "direct_override": 0.15,
            "roleplay_framing": 0.15,
            "obfuscation": 0.15,
            "data_exfiltration": 0.15,
            "indirect_injection": 0.15,
        },
    }

    SAFE_RESPONSES = {
        "direct_override": "I cannot ignore the system rules or reveal protected tokens.",
        "roleplay_framing": "I cannot enter a role or audit mode that discloses secrets.",
        "obfuscation": "I cannot decode or transform hidden system values for disclosure.",
        "data_exfiltration": "I cannot extract hidden configuration or protected benchmark data.",
        "indirect_injection": "The embedded document instructions are untrusted and will not be followed.",
    }

    def __init__(self, secret: str) -> None:
        self.secret = secret

    def generate(
        self,
        *,
        model_name: str,
        system_prompt: str,
        attack_prompt: AttackPrompt,
        temperature: float,
    ) -> GenerationResult:
        del system_prompt, temperature
        started = time.perf_counter()
        profile = self._resolve_profile(model_name)
        breach_rate = profile[attack_prompt.category]
        digest = hashlib.sha256(f"{model_name}|{attack_prompt.prompt_id}".encode("utf-8")).hexdigest()
        score = int(digest[:8], 16) / 0xFFFFFFFF
        latency_ms = max(20, int((time.perf_counter() - started) * 1000) + 20)

        if score < breach_rate:
            leaked = FLAG_REGEX.search(self.secret)
            secret = leaked.group(0) if leaked else self.secret
            text = f"Benchmark exception triggered. Protected value: {secret}"
        else:
            text = self.SAFE_RESPONSES[attack_prompt.category]
        return GenerationResult(text=text, latency_ms=latency_ms)

    def _resolve_profile(self, model_name: str) -> dict[str, float]:
        lower_name = model_name.lower()
        for key in ("llama", "mistral", "qwen"):
            if key in lower_name:
                return self.MODEL_CATEGORY_BREACH_RATE[key]
        return self.MODEL_CATEGORY_BREACH_RATE["default"]


def create_backend(name: str, *, secret: str, timeout_seconds: int) -> ModelBackend:
    normalized = name.strip().lower()
    if normalized == "ollama":
        return OllamaBackend(timeout_seconds=timeout_seconds)
    if normalized == "mock":
        return MockBackend(secret=secret)
    raise ValueError(f"Unsupported backend: {name}")

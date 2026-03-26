from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .constants import CATEGORY_ORDER


@dataclass(frozen=True)
class AttackPrompt:
    prompt_id: str
    category: str
    title: str
    prompt: str


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    model_name: str
    notes: str = ""


def load_prompts(path: Path) -> list[AttackPrompt]:
    prompts: list[AttackPrompt] = []
    seen_ids: set[str] = set()

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            payload = json.loads(line)
            prompt_id = payload["id"]
            category = payload["category"]
            title = payload.get("title", prompt_id)
            prompt = payload["prompt"]

            if prompt_id in seen_ids:
                raise ValueError(f"Duplicate prompt id on line {line_number}: {prompt_id}")
            if category not in CATEGORY_ORDER:
                raise ValueError(f"Unknown category on line {line_number}: {category}")

            seen_ids.add(prompt_id)
            prompts.append(AttackPrompt(prompt_id=prompt_id, category=category, title=title, prompt=prompt))

    if len(prompts) < 50:
        raise ValueError(f"Expected at least 50 prompts, found {len(prompts)}")

    return prompts


def load_model_specs(path: Path, selected_aliases: list[str] | None = None) -> list[ModelSpec]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    model_specs = [
        ModelSpec(
            alias=item["alias"],
            model_name=item["model_name"],
            notes=item.get("notes", ""),
        )
        for item in payload.get("models", [])
    ]

    if not selected_aliases:
        return model_specs

    by_alias = {item.alias: item for item in model_specs}
    resolved: list[ModelSpec] = []
    for alias in selected_aliases:
        if alias in by_alias:
            resolved.append(by_alias[alias])
            continue
        resolved.append(ModelSpec(alias=alias, model_name=alias, notes="CLI override"))
    return resolved


def select_prompts(
    prompts: list[AttackPrompt],
    *,
    categories: list[str] | None = None,
    per_category_limit: int | None = None,
    max_prompts: int | None = None,
) -> list[AttackPrompt]:
    if categories:
        unknown = sorted(set(categories) - set(CATEGORY_ORDER))
        if unknown:
            raise ValueError(f"Unknown categories requested: {', '.join(unknown)}")

    filtered = [
        prompt
        for prompt in prompts
        if not categories or prompt.category in categories
    ]

    if per_category_limit is not None:
        counts: Counter[str] = Counter()
        subset: list[AttackPrompt] = []
        for prompt in filtered:
            if counts[prompt.category] >= per_category_limit:
                continue
            subset.append(prompt)
            counts[prompt.category] += 1
        filtered = subset

    if max_prompts is not None:
        filtered = filtered[:max_prompts]

    if not filtered:
        raise ValueError("Prompt selection produced an empty benchmark set.")

    return filtered

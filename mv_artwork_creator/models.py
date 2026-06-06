from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from .config import DEFAULT_MODEL
from .user_config import default_models_path

_TASK_ENV_VARS = {
    "avatar": "MVAC_AVATAR_MODEL",
    "scene": "MVAC_SCENE_MODEL",
    "messy_fy": "MVAC_MESSY_FY_MODEL",
}


class GenerationTask(StrEnum):
    AVATAR = "avatar"
    SCENE = "scene"
    MESSY_FY = "messy_fy"


@dataclass(frozen=True)
class ModelRegistry:
    default: str
    aliases: dict[str, str]
    tasks: dict[str, str]


def load_model_registry(path: Path | None = None, *, factory: bool = False) -> ModelRegistry:
    path = path or default_models_path(factory=factory)
    if not path.exists():
        return ModelRegistry(default=DEFAULT_MODEL, aliases={}, tasks={})

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError("Model registry YAML must contain a mapping")

    default = _required_model_id(data.get("default"), field="default")
    aliases = _load_aliases(data.get("aliases"))
    tasks = _load_task_defaults(data.get("tasks"))
    return ModelRegistry(default=default, aliases=aliases, tasks=tasks)


def resolve_model(
    name: str | None,
    task: GenerationTask,
    *,
    registry: ModelRegistry | None = None,
    factory_defaults: bool = False,
) -> str:
    registry = registry or load_model_registry(factory=factory_defaults)
    if name and name.strip():
        return resolve_model_name(name.strip(), registry=registry)

    task_env = os.environ.get(_TASK_ENV_VARS[task.value])
    if task_env and task_env.strip():
        return resolve_model_name(task_env.strip(), registry=registry)

    task_default = registry.tasks.get(task.value)
    if task_default:
        return resolve_model_name(task_default, registry=registry)

    return resolve_model_name(registry.default, registry=registry)


def resolve_model_name(name: str, *, registry: ModelRegistry | None = None) -> str:
    registry = registry or load_model_registry()
    alias = registry.aliases.get(name)
    if alias:
        return alias
    return name


def default_model_for_task(task: GenerationTask, *, registry: ModelRegistry | None = None) -> str:
    return resolve_model(None, task, registry=registry)


def _load_aliases(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Model registry aliases must be a mapping")

    aliases: dict[str, str] = {}
    for alias, model_id in value.items():
        if not isinstance(alias, str) or not alias.strip():
            raise ValueError("Model registry alias keys must be non-empty strings")
        aliases[alias.strip()] = _required_model_id(model_id, field=f"aliases.{alias}")
    return aliases


def _load_task_defaults(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Model registry tasks must be a mapping")

    tasks: dict[str, str] = {}
    for task_name, model_name in value.items():
        if not isinstance(task_name, str) or not task_name.strip():
            raise ValueError("Model registry task keys must be non-empty strings")
        tasks[task_name.strip()] = _required_model_id(model_name, field=f"tasks.{task_name}")
    return tasks


def _required_model_id(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Model registry must define a non-empty string for {field}")
    return value.strip()

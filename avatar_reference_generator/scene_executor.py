from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Callable, Protocol

from PIL import Image

from .config import DEFAULT_MODEL
from .openrouter import OpenRouterClient, ProviderImageRequest
from .scene_prompts import ScenePromptLibrary
from .validation import validate_png_alpha


DEFAULT_SCENE_OUTPUT_DIR = Path("output/messy-scenes")
DEFAULT_SCENE_PROMPT_LIBRARY = Path("config/messy_scene_prompts.yaml")


class SceneImageClient(Protocol):
    def generate_image(self, request: ProviderImageRequest) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class SceneGenerationConfig:
    source_image: Path
    setting: str
    action: str
    output_dir: Path = DEFAULT_SCENE_OUTPUT_DIR
    prompt_library: Path = DEFAULT_SCENE_PROMPT_LIBRARY
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    filename: str | None = None
    regenerate: bool = False
    retry_count: int = 0

    def with_updates(self, **updates: object) -> "SceneGenerationConfig":
        return replace(self, **updates)


@dataclass(frozen=True)
class ScenePlan:
    source_image: Path
    output_dir: Path
    model: str
    provider: str
    setting: str
    action: str
    prompt: str
    negative_prompt: str
    output_path: Path
    metadata_path: Path


@dataclass(frozen=True)
class SceneGenerationSummary:
    planned: int
    generated: int
    skipped: int
    failed: int


def create_scene_plan(config: SceneGenerationConfig, prompt_library: ScenePromptLibrary) -> ScenePlan:
    validate_png_alpha(config.source_image)
    source_image_bytes = config.source_image.read_bytes()
    if not source_image_bytes:
        raise ValueError(f"Source image is empty: {config.source_image}")
    prompt = prompt_library.compose_prompt(setting=config.setting, action=config.action)
    filename = _resolve_filename(config)
    return ScenePlan(
        source_image=config.source_image,
        output_dir=config.output_dir,
        model=config.model,
        provider="openrouter",
        setting=config.setting.strip(),
        action=config.action.strip(),
        prompt=prompt,
        negative_prompt=prompt_library.negative_prompt,
        output_path=config.output_dir / f"{filename}.png",
        metadata_path=config.output_dir / f"{filename}.json",
    )


def run_scene_generation(
    config: SceneGenerationConfig,
    prompt_library: ScenePromptLibrary,
    client: SceneImageClient,
    progress: Callable[[str], None] | None = None,
) -> SceneGenerationSummary:
    if config.retry_count < 0:
        raise ValueError("retry_count must be zero or greater")

    plan = create_scene_plan(config, prompt_library)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    source_image_bytes = plan.source_image.read_bytes()
    source_hash = hashlib.sha256(source_image_bytes).hexdigest()
    prompt_hash = _prompt_hash(plan.prompt, plan.negative_prompt)

    if _is_successful_existing_scene(plan, source_hash, prompt_hash) and not config.regenerate:
        _emit_progress(progress, f"skip scene already succeeded: {plan.output_path}")
        return SceneGenerationSummary(planned=1, generated=0, skipped=1, failed=0)

    request_summary = describe_scene_request(
        model=plan.model,
        prompt=plan.prompt,
        negative_prompt=plan.negative_prompt,
        source_image_bytes=source_image_bytes,
    )
    if not request_summary.get("reference_image_attached"):
        raise RuntimeError("OpenRouter payload is missing the reference image attachment")

    try:
        _emit_progress(
            progress,
            (
                f"generate scene: {plan.output_path} "
                f"(reference image attached: {request_summary['reference_image_byte_size']} bytes)"
            ),
        )
        response = _generate_with_retries(config, client, plan, source_image_bytes)
        _write_png_output(plan.output_path, response["image_bytes"])  # type: ignore[arg-type]
        _write_metadata(
            plan=plan,
            source_hash=source_hash,
            prompt_hash=prompt_hash,
            status="succeeded",
            mime_type="image/png",
            provider_mime_type=_response_mime_type(response),
            response_id=response.get("response_id"),
            error=None,
            openrouter_request=request_summary,
        )
        _emit_progress(progress, f"succeeded scene: {plan.output_path}")
        return SceneGenerationSummary(planned=1, generated=1, skipped=0, failed=0)
    except Exception as exc:
        _write_metadata(
            plan=plan,
            source_hash=source_hash,
            prompt_hash=prompt_hash,
            status="failed",
            mime_type=None,
            provider_mime_type=None,
            response_id=None,
            error=str(exc),
            openrouter_request=request_summary,
        )
        _emit_progress(progress, f"failed scene: {exc}")
        return SceneGenerationSummary(planned=1, generated=0, skipped=0, failed=1)


def scene_plan_to_dict(plan: ScenePlan) -> dict[str, object]:
    source_image_bytes = plan.source_image.read_bytes()
    request_summary = describe_scene_request(
        model=plan.model,
        prompt=plan.prompt,
        negative_prompt=plan.negative_prompt,
        source_image_bytes=source_image_bytes,
    )
    return {
        "source_image": str(plan.source_image),
        "source_sha256": hashlib.sha256(source_image_bytes).hexdigest(),
        "source_byte_size": len(source_image_bytes),
        "output_dir": str(plan.output_dir),
        "provider": plan.provider,
        "model": plan.model,
        "setting": plan.setting,
        "action": plan.action,
        "prompt": plan.prompt,
        "negative_prompt": plan.negative_prompt,
        "output_path": str(plan.output_path),
        "metadata_path": str(plan.metadata_path),
        "openrouter_request": request_summary,
    }


def describe_scene_request(
    *,
    model: str,
    prompt: str,
    negative_prompt: str,
    source_image_bytes: bytes,
) -> dict[str, object]:
    payload = OpenRouterClient(api_key="dry-run").build_payload(
        model=model,
        prompt=prompt,
        negative_prompt=negative_prompt,
        source_image_bytes=source_image_bytes,
    )
    return OpenRouterClient.describe_payload(payload)


def _resolve_filename(config: SceneGenerationConfig) -> str:
    if config.filename and config.filename.strip():
        return _slugify(config.filename)
    base = f"{config.setting}-{config.action}"
    return _slugify(base)[:80] or "messy-scene"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "messy-scene"


def _emit_progress(progress: Callable[[str], None] | None, message: str) -> None:
    if progress:
        progress(message)


def _generate_with_retries(
    config: SceneGenerationConfig,
    client: SceneImageClient,
    plan: ScenePlan,
    source_image_bytes: bytes,
) -> dict[str, object]:
    last_error: Exception | None = None
    for _attempt in range(config.retry_count + 1):
        try:
            return client.generate_image(
                ProviderImageRequest(
                    model=plan.model,
                    prompt=plan.prompt,
                    negative_prompt=plan.negative_prompt,
                    source_image_bytes=source_image_bytes,
                )
            )
        except Exception as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def _write_png_output(output_path: Path, image_bytes: bytes) -> None:
    image = Image.open(BytesIO(image_bytes))
    if image.mode not in {"RGBA", "LA"}:
        image = image.convert("RGBA")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")


def _response_mime_type(response: dict[str, object]) -> str | None:
    mime_type = response.get("mime_type")
    if isinstance(mime_type, str):
        return mime_type
    return None


def _prompt_hash(prompt: str, negative_prompt: str) -> str:
    return hashlib.sha256(f"{prompt}\n\n{negative_prompt}".encode("utf-8")).hexdigest()


def _is_successful_existing_scene(plan: ScenePlan, source_hash: str, prompt_hash: str) -> bool:
    if not plan.metadata_path.exists():
        return False
    try:
        metadata = json.loads(plan.metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    output_path = metadata.get("output_path")
    if not isinstance(output_path, str) or not Path(output_path).exists():
        return False
    expected = {
        "status": "succeeded",
        "provider": plan.provider,
        "model": plan.model,
        "source_sha256": source_hash,
        "setting": plan.setting,
        "action": plan.action,
        "prompt": plan.prompt,
        "negative_prompt": plan.negative_prompt,
        "prompt_sha256": prompt_hash,
    }
    return all(metadata.get(key) == value for key, value in expected.items())


def _write_metadata(
    plan: ScenePlan,
    source_hash: str,
    prompt_hash: str,
    status: str,
    mime_type: str | None,
    provider_mime_type: str | None,
    response_id: object,
    error: str | None,
    openrouter_request: dict[str, object] | None = None,
) -> None:
    metadata = {
        "status": status,
        "provider": plan.provider,
        "model": plan.model,
        "source_image": str(plan.source_image),
        "source_sha256": source_hash,
        "setting": plan.setting,
        "action": plan.action,
        "prompt": plan.prompt,
        "negative_prompt": plan.negative_prompt,
        "prompt_sha256": prompt_hash,
        "output_path": str(plan.output_path),
        "mime_type": mime_type,
        "provider_mime_type": provider_mime_type,
        "metadata_path": str(plan.metadata_path),
        "provider_response_id": response_id,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if openrouter_request is not None:
        metadata["openrouter_request"] = openrouter_request
    plan.metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

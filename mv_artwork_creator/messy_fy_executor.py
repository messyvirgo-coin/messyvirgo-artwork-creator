from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Callable, Protocol

from PIL import Image

from .background import remove_background
from .user_config import default_messy_fy_prompt_library
from .paths import bundled_config_path
from .config import DEFAULT_MODEL
from .images import load_image_for_provider
from .messy_fy_prompts import MessyFyPromptLibrary
from .openrouter import OpenRouterClient, ProviderImageRequest


DEFAULT_MESSY_FY_OUTPUT_DIR = Path("output/messyfied")

def default_messy_fy_output_dir() -> Path:
    return Path(os.environ.get("MVAC_MESSY_FY_OUTPUT", str(DEFAULT_MESSY_FY_OUTPUT_DIR)))


class MessyFyImageClient(Protocol):
    def generate_image(self, request: ProviderImageRequest) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class MessyFyGenerationConfig:
    source_image: Path
    output_dir: Path = DEFAULT_MESSY_FY_OUTPUT_DIR
    prompt_library: Path = field(default_factory=default_messy_fy_prompt_library)
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    hint: str | None = None
    filename: str | None = None
    regenerate: bool = False
    retry_count: int = 0
    remove_background: bool = False

    def with_updates(self, **updates: object) -> "MessyFyGenerationConfig":
        return replace(self, **updates)


@dataclass(frozen=True)
class MessyFyPlan:
    source_image: Path
    output_dir: Path
    model: str
    provider: str
    hint: str | None
    prompt: str
    negative_prompt: str
    source_mime_type: str
    output_path: Path
    metadata_path: Path
    transparent_output_path: Path | None


@dataclass(frozen=True)
class MessyFyGenerationSummary:
    planned: int
    generated: int
    skipped: int
    failed: int


def create_messy_fy_plan(config: MessyFyGenerationConfig, prompt_library: MessyFyPromptLibrary) -> MessyFyPlan:
    _, source_mime_type = load_image_for_provider(config.source_image)
    prompt = prompt_library.compose_prompt(hint=config.hint)
    filename = _resolve_filename(config)
    transparent_output_path = config.output_dir / f"{filename}-transparent.png" if config.remove_background else None
    return MessyFyPlan(
        source_image=config.source_image,
        output_dir=config.output_dir,
        model=config.model,
        provider="openrouter",
        hint=_normalize_hint(config.hint),
        prompt=prompt,
        negative_prompt=prompt_library.negative_prompt,
        source_mime_type=source_mime_type,
        output_path=config.output_dir / f"{filename}.png",
        metadata_path=config.output_dir / f"{filename}.json",
        transparent_output_path=transparent_output_path,
    )


def run_messy_fy_generation(
    config: MessyFyGenerationConfig,
    prompt_library: MessyFyPromptLibrary,
    client: MessyFyImageClient,
    progress: Callable[[str], None] | None = None,
) -> MessyFyGenerationSummary:
    if config.retry_count < 0:
        raise ValueError("retry_count must be zero or greater")

    plan = create_messy_fy_plan(config, prompt_library)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    source_image_bytes, source_mime_type = load_image_for_provider(plan.source_image)
    source_hash = hashlib.sha256(source_image_bytes).hexdigest()
    prompt_hash = _prompt_hash(plan.prompt, plan.negative_prompt)

    if _is_successful_existing_messy_fy(plan, source_hash, prompt_hash) and not config.regenerate:
        _emit_progress(progress, f"skip messy-fy already succeeded: {plan.output_path}")
        return MessyFyGenerationSummary(planned=1, generated=0, skipped=1, failed=0)

    request_summary = describe_messy_fy_request(
        model=plan.model,
        prompt=plan.prompt,
        negative_prompt=plan.negative_prompt,
        source_image_bytes=source_image_bytes,
        source_mime_type=source_mime_type,
    )
    if not request_summary.get("reference_image_attached"):
        raise RuntimeError("OpenRouter payload is missing the reference image attachment")

    try:
        _emit_progress(
            progress,
            (
                f"generate messy-fy: {plan.output_path} "
                f"(reference image attached: {request_summary['reference_image_byte_size']} bytes, "
                f"mime={source_mime_type})"
            ),
        )
        response = _generate_with_retries(config, client, plan, source_image_bytes, source_mime_type)
        _write_png_output(plan.output_path, response["image_bytes"])  # type: ignore[arg-type]
        transparent_output_path: str | None = None
        if plan.transparent_output_path is not None:
            remove_background(plan.output_path, plan.transparent_output_path)
            transparent_output_path = str(plan.transparent_output_path)
            _emit_progress(progress, f"removed background: {plan.transparent_output_path}")

        _write_metadata(
            plan=plan,
            source_hash=source_hash,
            prompt_hash=prompt_hash,
            status="succeeded",
            mime_type="image/png",
            provider_mime_type=_response_mime_type(response),
            response_id=response.get("response_id"),
            error=None,
            transparent_output_path=transparent_output_path,
            openrouter_request=request_summary,
        )
        _emit_progress(progress, f"succeeded messy-fy: {plan.output_path}")
        return MessyFyGenerationSummary(planned=1, generated=1, skipped=0, failed=0)
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
            transparent_output_path=None,
            openrouter_request=request_summary,
        )
        _emit_progress(progress, f"failed messy-fy: {exc}")
        return MessyFyGenerationSummary(planned=1, generated=0, skipped=0, failed=1)


def messy_fy_plan_to_dict(plan: MessyFyPlan) -> dict[str, object]:
    source_image_bytes, source_mime_type = load_image_for_provider(plan.source_image)
    request_summary = describe_messy_fy_request(
        model=plan.model,
        prompt=plan.prompt,
        negative_prompt=plan.negative_prompt,
        source_image_bytes=source_image_bytes,
        source_mime_type=source_mime_type,
    )
    return {
        "source_image": str(plan.source_image),
        "source_sha256": hashlib.sha256(source_image_bytes).hexdigest(),
        "source_byte_size": len(source_image_bytes),
        "source_mime_type": source_mime_type,
        "output_dir": str(plan.output_dir),
        "provider": plan.provider,
        "model": plan.model,
        "hint": plan.hint,
        "prompt": plan.prompt,
        "negative_prompt": plan.negative_prompt,
        "output_path": str(plan.output_path),
        "metadata_path": str(plan.metadata_path),
        "transparent_output_path": str(plan.transparent_output_path) if plan.transparent_output_path else None,
        "openrouter_request": request_summary,
    }


def describe_messy_fy_request(
    *,
    model: str,
    prompt: str,
    negative_prompt: str,
    source_image_bytes: bytes,
    source_mime_type: str,
) -> dict[str, object]:
    payload = OpenRouterClient(api_key="dry-run").build_payload(
        model=model,
        prompt=prompt,
        negative_prompt=negative_prompt,
        source_image_bytes=source_image_bytes,
        source_mime_type=source_mime_type,
    )
    return OpenRouterClient.describe_payload(payload)


def _resolve_filename(config: MessyFyGenerationConfig) -> str:
    if config.filename and config.filename.strip():
        return _slugify(config.filename)
    return _slugify(config.source_image.stem) or "messy-fy"


def _normalize_hint(hint: str | None) -> str | None:
    if hint is None:
        return None
    cleaned = hint.strip()
    return cleaned or None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "messy-fy"


def _emit_progress(progress: Callable[[str], None] | None, message: str) -> None:
    if progress:
        progress(message)


def _generate_with_retries(
    config: MessyFyGenerationConfig,
    client: MessyFyImageClient,
    plan: MessyFyPlan,
    source_image_bytes: bytes,
    source_mime_type: str,
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
                    source_mime_type=source_mime_type,
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


def _is_successful_existing_messy_fy(plan: MessyFyPlan, source_hash: str, prompt_hash: str) -> bool:
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
        "hint": plan.hint,
        "prompt": plan.prompt,
        "negative_prompt": plan.negative_prompt,
        "prompt_sha256": prompt_hash,
        "remove_background": plan.transparent_output_path is not None,
    }
    if not all(metadata.get(key) == value for key, value in expected.items()):
        return False
    if plan.transparent_output_path is not None:
        transparent_output_path = metadata.get("transparent_output_path")
        if transparent_output_path != str(plan.transparent_output_path):
            return False
        if not plan.transparent_output_path.exists():
            return False
    return True


def _write_metadata(
    plan: MessyFyPlan,
    source_hash: str,
    prompt_hash: str,
    status: str,
    mime_type: str | None,
    provider_mime_type: str | None,
    response_id: object,
    error: str | None,
    transparent_output_path: str | None,
    openrouter_request: dict[str, object] | None = None,
) -> None:
    metadata = {
        "status": status,
        "provider": plan.provider,
        "model": plan.model,
        "source_image": str(plan.source_image),
        "source_sha256": source_hash,
        "source_mime_type": plan.source_mime_type,
        "hint": plan.hint,
        "prompt": plan.prompt,
        "negative_prompt": plan.negative_prompt,
        "prompt_sha256": prompt_hash,
        "output_path": str(plan.output_path),
        "transparent_output_path": transparent_output_path,
        "remove_background": plan.transparent_output_path is not None,
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

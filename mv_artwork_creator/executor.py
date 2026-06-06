from __future__ import annotations

import hashlib
import json
from io import BytesIO
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from PIL import Image

from .config import GenerationConfig
from .openrouter import ProviderImageRequest
from .planner import GenerationPlan, PlannedImage, create_generation_plan
from .prompts import PromptLibrary


class ImageClient(Protocol):
    def generate_image(self, request: ProviderImageRequest) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class GenerationSummary:
    planned: int
    generated: int
    skipped: int
    failed: int


def run_generation(
    config: GenerationConfig,
    prompt_library: PromptLibrary,
    client: ImageClient,
    progress: Callable[[str], None] | None = None,
) -> GenerationSummary:
    if config.retry_count < 0:
        raise ValueError("retry_count must be zero or greater")
    if config.concurrency < 1:
        raise ValueError("concurrency must be one or greater")

    plan = create_generation_plan(config, prompt_library)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    source_image_bytes = plan.source_image.read_bytes()
    source_hash = hashlib.sha256(source_image_bytes).hexdigest()

    generated = 0
    skipped = 0
    failed = 0

    total = len(plan.items)
    for index, item in enumerate(plan.items, start=1):
        if _is_successful_existing_item(plan, item, source_hash) and not config.regenerate:
            _emit_progress(progress, f"[{index}/{total}] skip {item.angle_id}:{item.shot_id} already succeeded")
            skipped += 1
            continue

        try:
            _emit_progress(progress, f"[{index}/{total}] generate {item.angle_id}:{item.shot_id}")
            response = _generate_with_retries(config, client, plan, item, source_image_bytes)
            output_path = item.output_path
            _write_png_output(output_path, response["image_bytes"])  # type: ignore[arg-type]
            _write_metadata(
                plan=plan,
                item=item,
                source_hash=source_hash,
                status="succeeded",
                output_path=output_path,
                mime_type="image/png",
                provider_mime_type=_response_mime_type(response),
                response_id=response.get("response_id"),
                error=None,
            )
            _emit_progress(progress, f"[{index}/{total}] succeeded {output_path}")
            generated += 1
        except Exception as exc:
            failed += 1
            _write_metadata(
                plan=plan,
                item=item,
                source_hash=source_hash,
                status="failed",
                output_path=item.output_path,
                mime_type=None,
                provider_mime_type=None,
                response_id=None,
                error=str(exc),
            )
            _emit_progress(progress, f"[{index}/{total}] failed {item.angle_id}:{item.shot_id}: {exc}")
            if not config.continue_on_error:
                break

    return GenerationSummary(planned=len(plan.items), generated=generated, skipped=skipped, failed=failed)


def _emit_progress(progress: Callable[[str], None] | None, message: str) -> None:
    if progress:
        progress(message)


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


def _generate_with_retries(
    config: GenerationConfig,
    client: ImageClient,
    plan: GenerationPlan,
    item: PlannedImage,
    source_image_bytes: bytes,
) -> dict[str, object]:
    last_error: Exception | None = None
    for _attempt in range(config.retry_count + 1):
        try:
            return client.generate_image(
                ProviderImageRequest(
                    model=plan.model,
                    prompt=item.prompt,
                    negative_prompt=item.negative_prompt,
                    source_image_bytes=source_image_bytes,
                )
            )
        except Exception as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def _is_successful_existing_item(plan: GenerationPlan, item: PlannedImage, source_hash: str) -> bool:
    if not item.metadata_path.exists():
        return False
    try:
        metadata = json.loads(item.metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    metadata_output_path = metadata.get("output_path")
    if not isinstance(metadata_output_path, str) or not Path(metadata_output_path).exists():
        return False
    expected = {
        "status": "succeeded",
        "provider": plan.provider,
        "model": plan.model,
        "source_sha256": source_hash,
        "angle_id": item.angle_id,
        "shot_id": item.shot_id,
        "prompt": item.prompt,
        "negative_prompt": item.negative_prompt,
    }
    return all(metadata.get(key) == value for key, value in expected.items())


def _write_metadata(
    plan: GenerationPlan,
    item: PlannedImage,
    source_hash: str,
    status: str,
    output_path: Path,
    mime_type: str | None,
    provider_mime_type: str | None,
    response_id: object,
    error: str | None,
) -> None:
    metadata = {
        "status": status,
        "provider": plan.provider,
        "model": plan.model,
        "source_image": str(plan.source_image),
        "source_sha256": source_hash,
        "angle_id": item.angle_id,
        "shot_id": item.shot_id,
        "prompt": item.prompt,
        "negative_prompt": item.negative_prompt,
        "output_path": str(output_path),
        "mime_type": mime_type,
        "provider_mime_type": provider_mime_type,
        "metadata_path": str(item.metadata_path),
        "provider_response_id": response_id,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    item.metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

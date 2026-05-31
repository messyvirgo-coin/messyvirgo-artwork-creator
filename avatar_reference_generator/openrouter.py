from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
SUPPORTED_IMAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


@dataclass(frozen=True)
class ProviderImageRequest:
    model: str
    prompt: str
    negative_prompt: str
    source_image_bytes: bytes
    source_mime_type: str = "image/png"


class OpenRouterClient:
    def __init__(self, api_key: str, endpoint: str = OPENROUTER_CHAT_COMPLETIONS_URL):
        if not api_key:
            raise ValueError("Missing OpenRouter API credential")
        self.api_key = api_key
        self.endpoint = endpoint

    def build_payload(
        self,
        model: str,
        prompt: str,
        negative_prompt: str,
        source_image_bytes: bytes,
        source_mime_type: str = "image/png",
    ) -> dict[str, Any]:
        if not source_image_bytes:
            raise ValueError("Reference image bytes are empty; cannot call OpenRouter without an input image")
        encoded_image = base64.b64encode(source_image_bytes).decode("ascii")
        full_prompt = prompt
        if negative_prompt.strip():
            full_prompt = f"{prompt.strip()}\n\nNegative prompt:\n{negative_prompt.strip()}"

        return {
            "model": model,
            "modalities": ["image"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{source_mime_type};base64,{encoded_image}",
                            },
                        },
                        {"type": "text", "text": full_prompt},
                    ],
                }
            ],
        }

    def generate_image(self, request: ProviderImageRequest) -> dict[str, Any]:
        payload = self.build_payload(
            model=request.model,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            source_image_bytes=request.source_image_bytes,
            source_mime_type=request.source_mime_type,
        )
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://local/avatar-reference-generator",
                "X-Title": "Avatar Reference Generator",
            },
        )

        try:
            with urllib.request.urlopen(http_request, timeout=180) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

        return self.parse_response(response_data)

    def parse_response(self, response_data: dict[str, Any]) -> dict[str, Any]:
        data_url = _find_first_image_data_url(response_data)
        if not data_url:
            raise RuntimeError("OpenRouter response did not contain a generated image data URL")

        return {
            **_decode_data_url(data_url),
            "response_id": response_data.get("id"),
            "raw": response_data,
        }

    @staticmethod
    def describe_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Summarize a request payload without embedding base64 image data."""
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            return {
                "modalities": payload.get("modalities"),
                "model": payload.get("model"),
                "reference_image_attached": False,
            }

        content = messages[0].get("content") if isinstance(messages[0], dict) else None
        if not isinstance(content, list):
            return {
                "modalities": payload.get("modalities"),
                "model": payload.get("model"),
                "reference_image_attached": False,
            }

        content_types: list[str] = []
        reference_image_byte_size = 0
        reference_image_mime_type: str | None = None
        text_char_count = 0

        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if isinstance(part_type, str):
                content_types.append(part_type)
            if part_type == "image_url":
                image_url = part.get("image_url")
                if isinstance(image_url, dict):
                    url = image_url.get("url")
                    if isinstance(url, str) and url.startswith("data:") and ";base64," in url:
                        header, _, encoded = url.partition(",")
                        reference_image_mime_type = header.removeprefix("data:").split(";", 1)[0]
                        try:
                            reference_image_byte_size = len(base64.b64decode(encoded, validate=True))
                        except ValueError:
                            reference_image_byte_size = len(encoded)
            if part_type == "text" and isinstance(part.get("text"), str):
                text_char_count += len(part["text"])

        return {
            "model": payload.get("model"),
            "modalities": payload.get("modalities"),
            "message_content_types": content_types,
            "reference_image_attached": reference_image_byte_size > 0,
            "reference_image_byte_size": reference_image_byte_size,
            "reference_image_mime_type": reference_image_mime_type,
            "prompt_text_char_count": text_char_count,
        }


def _find_first_image_data_url(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("data:image/"):
        return value
    if isinstance(value, dict):
        for nested in value.values():
            found = _find_first_image_data_url(nested)
            if found:
                return found
    if isinstance(value, list):
        for nested in value:
            found = _find_first_image_data_url(nested)
            if found:
                return found
    return None


def _decode_data_url(data_url: str) -> dict[str, Any]:
    header, separator, encoded = data_url.partition(",")
    if not separator:
        raise RuntimeError("Generated image data URL is malformed")
    if not header.startswith("data:") or ";base64" not in header:
        raise RuntimeError("Generated image data URL must be base64 encoded")
    mime_type = header.removeprefix("data:").split(";", 1)[0]
    extension = SUPPORTED_IMAGE_EXTENSIONS.get(mime_type)
    if not extension:
        raise RuntimeError(f"Unsupported OpenRouter response image type: {mime_type}")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise RuntimeError("Generated image data URL contains invalid base64") from exc
    return {"image_bytes": image_bytes, "mime_type": mime_type, "extension": extension}

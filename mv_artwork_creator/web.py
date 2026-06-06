from __future__ import annotations

import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from .background import remove_backgrounds
from .config import GenerationConfig, default_output_dir
from .executor import run_generation
from .messy_fy_executor import (
    MessyFyGenerationConfig,
    create_messy_fy_plan,
    default_messy_fy_output_dir,
    messy_fy_plan_to_dict,
    run_messy_fy_generation,
)
from .messy_fy_prompts import load_messy_fy_prompt_library
from .models import GenerationTask, default_model_for_task, resolve_model
from .openrouter import OpenRouterClient
from .planner import create_generation_plan
from .prompts import load_prompt_library
from .scene_executor import (
    SceneGenerationConfig,
    create_scene_plan,
    default_scene_output_dir,
    run_scene_generation,
    scene_plan_to_dict,
)
from .scene_prompts import load_scene_prompt_library
from .user_config import (
    default_avatar_prompt_library,
    default_messy_fy_prompt_library,
    default_scene_prompt_library,
)


DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8765


def render_home_page(result: object | None = None, error: str | None = None) -> str:
    result_html = ""
    if error:
        result_html = f"<section class='result error'><h2>Error</h2><pre>{html.escape(error)}</pre></section>"
    elif result is not None:
        result_html = (
            "<section class='result'><h2>Result</h2>"
            f"<pre>{html.escape(json.dumps(result, indent=2, sort_keys=True))}</pre></section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Messy Virgo Artwork Creator</title>
  <style>
    :root {{
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #111316;
      color: #f3f0ec;
    }}
    body {{ margin: 0; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 48px; }}
    h1 {{ font-size: 28px; margin: 0 0 24px; }}
    h2 {{ font-size: 18px; margin: 0 0 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    form, .result {{ border: 1px solid #343a40; border-radius: 8px; padding: 16px; background: #191d21; }}
    label {{ display: grid; gap: 6px; margin: 0 0 12px; font-size: 13px; color: #c8d0d8; }}
    input, textarea, select {{
      width: 100%; box-sizing: border-box; border: 1px solid #444c55; border-radius: 6px;
      background: #101215; color: #f3f0ec; padding: 10px; font: inherit;
    }}
    textarea {{ min-height: 84px; resize: vertical; }}
    button {{ border: 0; border-radius: 6px; background: #e65aa0; color: #fff; padding: 10px 14px; font-weight: 700; cursor: pointer; }}
    .row {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    .row label {{ display: flex; flex-direction: row; gap: 8px; margin: 0; align-items: center; }}
    .row input[type="checkbox"] {{ width: auto; }}
    pre {{ overflow: auto; white-space: pre-wrap; background: #0b0d0f; padding: 12px; border-radius: 6px; }}
    .error {{ border-color: #b64b4b; }}
  </style>
</head>
<body>
<main>
  <h1>Messy Virgo Artwork Creator</h1>
  <div class="grid">
    <form method="post" action="/avatar">
      <h2>Avatar</h2>
      <label>Source avatar PNG<input name="source_image" required></label>
      <label>Output directory<input name="output_dir" value="{html.escape(str(default_output_dir()))}"></label>
      <label>Model<input name="model" value="{html.escape(default_model_for_task(GenerationTask.AVATAR))}"></label>
      <label>API key override<input name="api_key" type="password"></label>
      <div class="row">
        <label><input name="dry_run" type="checkbox" value="1" checked> Dry run</label>
        <label><input name="test_mode" type="checkbox" value="1"> Test image only</label>
        <button type="submit">Run</button>
      </div>
    </form>
    <form method="post" action="/scene">
      <h2>Scene</h2>
      <label>Source avatar PNG<input name="source_image" required></label>
      <label>Where Messy is<textarea name="setting" required></textarea></label>
      <label>What Messy is doing<textarea name="action" required></textarea></label>
      <label>Output directory<input name="output_dir" value="{html.escape(str(default_scene_output_dir()))}"></label>
      <label>Model<input name="model" value="{html.escape(default_model_for_task(GenerationTask.SCENE))}"></label>
      <label>Filename stem<input name="filename"></label>
      <label>API key override<input name="api_key" type="password"></label>
      <div class="row">
        <label><input name="dry_run" type="checkbox" value="1" checked> Dry run</label>
        <button type="submit">Run</button>
      </div>
    </form>
    <form method="post" action="/messy-fy">
      <h2>Messy-fy</h2>
      <label>Source image<input name="source_image" required></label>
      <label>Hint<textarea name="hint"></textarea></label>
      <label>Output directory<input name="output_dir" value="{html.escape(str(default_messy_fy_output_dir()))}"></label>
      <label>Model<input name="model" value="{html.escape(default_model_for_task(GenerationTask.MESSY_FY))}"></label>
      <label>Filename stem<input name="filename"></label>
      <label>API key override<input name="api_key" type="password"></label>
      <div class="row">
        <label><input name="dry_run" type="checkbox" value="1" checked> Dry run</label>
        <label><input name="remove_background" type="checkbox" value="1"> Remove background</label>
        <button type="submit">Run</button>
      </div>
    </form>
    <form method="post" action="/background">
      <h2>Remove Background</h2>
      <label>Input file or directory<input name="source" required></label>
      <label>Output directory<input name="output_dir"></label>
      <label>Method<select name="method">
        <option value="rembg" selected>rembg (AI)</option>
        <option value="flood">flood (fast)</option>
      </select></label>
      <button type="submit">Convert</button>
    </form>
  </div>
  {result_html}
</main>
</body>
</html>"""


def run_scene_dry_run_from_form(form: dict[str, Any]) -> dict[str, object]:
    config = _scene_config_from_form(form)
    library = load_scene_prompt_library(_path_value(form, "prompt_library", default_scene_prompt_library()))
    plan = create_scene_plan(config, library)
    return {"kind": "scene-dry-run", **scene_plan_to_dict(plan)}


def run_scene_generation_from_form(form: dict[str, Any]) -> dict[str, object]:
    config = _scene_config_from_form(form)
    api_key = _text_value(form, "api_key") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Missing OpenRouter API credential. Set OPENROUTER_API_KEY or provide an API key.")
    library = load_scene_prompt_library(_path_value(form, "prompt_library", default_scene_prompt_library()))
    client = OpenRouterClient(api_key=api_key)
    summary = run_scene_generation(config, library, client)
    return {"kind": "scene-generation", **summary.__dict__}


def run_avatar_dry_run_from_form(form: dict[str, Any]) -> dict[str, object]:
    config = _avatar_config_from_form(form)
    library = load_prompt_library(config.prompt_library)
    plan = create_generation_plan(config, library)
    return {
        "kind": "avatar-dry-run",
        "source_image": str(plan.source_image),
        "output_dir": str(plan.output_dir),
        "provider": plan.provider,
        "model": plan.model,
        "planned_count": len(plan.items),
        "items": [
            {
                "angle_id": item.angle_id,
                "shot_id": item.shot_id,
                "output_path": str(item.output_path),
                "metadata_path": str(item.metadata_path),
            }
            for item in plan.items
        ],
    }


def run_avatar_generation_from_form(form: dict[str, Any]) -> dict[str, object]:
    config = _avatar_config_from_form(form)
    api_key = _text_value(form, "api_key") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Missing OpenRouter API credential. Set OPENROUTER_API_KEY or provide an API key.")
    library = load_prompt_library(config.prompt_library)
    client = OpenRouterClient(api_key=api_key)
    summary = run_generation(config, library, client)
    return {"kind": "avatar-generation", **summary.__dict__}


def run_messy_fy_dry_run_from_form(form: dict[str, Any]) -> dict[str, object]:
    config = _messy_fy_config_from_form(form)
    library = load_messy_fy_prompt_library(_path_value(form, "prompt_library", default_messy_fy_prompt_library()))
    plan = create_messy_fy_plan(config, library)
    return {"kind": "messy-fy-dry-run", **messy_fy_plan_to_dict(plan)}


def run_messy_fy_generation_from_form(form: dict[str, Any]) -> dict[str, object]:
    config = _messy_fy_config_from_form(form)
    api_key = _text_value(form, "api_key") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Missing OpenRouter API credential. Set OPENROUTER_API_KEY or provide an API key.")
    library = load_messy_fy_prompt_library(_path_value(form, "prompt_library", default_messy_fy_prompt_library()))
    client = OpenRouterClient(api_key=api_key)
    summary = run_messy_fy_generation(config, library, client)
    return {"kind": "messy-fy-generation", **summary.__dict__}


def run_background_from_form(form: dict[str, Any]) -> dict[str, object]:
    source = _path_value(form, "source")
    output_dir_text = _text_value(form, "output_dir")
    output_dir = Path(output_dir_text) if output_dir_text else source.with_name(f"{source.name}-transparent")
    method = _text_value(form, "method") or "rembg"
    if method not in {"rembg", "flood"}:
        raise ValueError("Background removal method must be rembg or flood")
    summary = remove_backgrounds(source, output_dir, method=method)
    return {"kind": "background-removal", **summary.__dict__}


def start_web_server(host: str = DEFAULT_WEB_HOST, port: int = DEFAULT_WEB_PORT) -> None:
    server = ThreadingHTTPServer((host, port), _GeneratorRequestHandler)
    url = f"http://{host}:{server.server_port}/"
    print(f"Serving Messy Virgo Artwork Creator at {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web server")
    finally:
        server.server_close()


class _GeneratorRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/":
            self.send_error(404)
            return
        self._send_html(render_home_page())

    def do_POST(self) -> None:  # noqa: N802
        try:
            form = self._read_form()
            if self.path == "/scene":
                result = (
                    run_scene_dry_run_from_form(form)
                    if _truthy(form, "dry_run")
                    else run_scene_generation_from_form(form)
                )
            elif self.path == "/avatar":
                result = (
                    run_avatar_dry_run_from_form(form)
                    if _truthy(form, "dry_run")
                    else run_avatar_generation_from_form(form)
                )
            elif self.path == "/messy-fy":
                result = (
                    run_messy_fy_dry_run_from_form(form)
                    if _truthy(form, "dry_run")
                    else run_messy_fy_generation_from_form(form)
                )
            elif self.path == "/background":
                result = run_background_from_form(form)
            else:
                self.send_error(404)
                return
            self._send_html(render_home_page(result=result))
        except Exception as exc:
            self._send_html(render_home_page(error=str(exc)), status=400)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_form(self) -> dict[str, list[str]]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return parse_qs(raw, keep_blank_values=True)

    def _send_html(self, body: str, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _scene_config_from_form(form: dict[str, Any]) -> SceneGenerationConfig:
    return SceneGenerationConfig(
        source_image=_path_value(form, "source_image"),
        setting=_text_value(form, "setting"),
        action=_text_value(form, "action"),
        output_dir=_path_value(form, "output_dir", default_scene_output_dir()),
        prompt_library=_path_value(form, "prompt_library", default_scene_prompt_library()),
        model=resolve_model(_text_value(form, "model") or None, GenerationTask.SCENE),
        api_key=_text_value(form, "api_key") or None,
        filename=_text_value(form, "filename") or None,
    )


def _avatar_config_from_form(form: dict[str, Any]) -> GenerationConfig:
    return GenerationConfig(
        source_image=_path_value(form, "source_image"),
        output_dir=_path_value(form, "output_dir", default_output_dir()),
        prompt_library=_path_value(form, "prompt_library", default_avatar_prompt_library()),
        model=resolve_model(_text_value(form, "model") or None, GenerationTask.AVATAR),
        api_key=_text_value(form, "api_key") or None,
        test_mode=_truthy(form, "test_mode"),
    )


def _messy_fy_config_from_form(form: dict[str, Any]) -> MessyFyGenerationConfig:
    return MessyFyGenerationConfig(
        source_image=_path_value(form, "source_image"),
        output_dir=_path_value(form, "output_dir", default_messy_fy_output_dir()),
        prompt_library=_path_value(form, "prompt_library", default_messy_fy_prompt_library()),
        model=resolve_model(_text_value(form, "model") or None, GenerationTask.MESSY_FY),
        api_key=_text_value(form, "api_key") or None,
        hint=_text_value(form, "hint") or None,
        filename=_text_value(form, "filename") or None,
        remove_background=_truthy(form, "remove_background"),
    )


def _text_value(form: dict[str, Any], key: str, default: str = "") -> str:
    value = form.get(key)
    if isinstance(value, list):
        value = value[0] if value else default
    if value is None:
        return default
    return str(value).strip()


def _path_value(form: dict[str, Any], key: str, default: Path | None = None) -> Path:
    value = _text_value(form, key)
    if value:
        return Path(value)
    if default is not None:
        return default
    raise ValueError(f"Missing required field: {key}")


def _truthy(form: dict[str, Any], key: str) -> bool:
    return _text_value(form, key).lower() in {"1", "true", "yes", "on"}

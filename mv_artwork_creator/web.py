from __future__ import annotations

import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

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
from .models import GenerationTask, ModelRegistry, load_model_registry, resolve_model
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
DEFAULT_INPUT_DIR = Path("input")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
PNG_EXTENSIONS = {".png"}
CLIENT_DISCONNECT_ERRORS = (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)
WORKFLOW_LABELS = {
    "avatar": "Avatar Reference Set",
    "scene": "Scene Generator",
    "messy-fy": "Messy-fy",
    "background": "Remove Background",
}


def default_input_dir() -> Path:
    return DEFAULT_INPUT_DIR


def list_input_dir_images(
    input_dir: Path | None = None,
    *,
    extensions: set[str] | None = None,
) -> list[Path]:
    directory = input_dir or default_input_dir()
    allowed = extensions if extensions is not None else IMAGE_EXTENSIONS
    if not directory.is_dir():
        return []
    files = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in allowed and not path.name.startswith(".")
    ]
    return sorted(files, key=lambda path: path.name.lower())


def list_input_dir_entries(input_dir: Path | None = None) -> list[Path]:
    directory = input_dir or default_input_dir()
    if not directory.is_dir():
        return []
    entries = [
        path
        for path in directory.iterdir()
        if not path.name.startswith(".") and (path.is_dir() or path.suffix.lower() in IMAGE_EXTENSIONS)
    ]
    return sorted(entries, key=lambda path: path.name.lower())


def _render_input_file_field(
    name: str,
    *,
    label: str,
    extensions: set[str] | None = None,
    required: bool = True,
    entries: list[Path] | None = None,
) -> str:
    files = entries if entries is not None else list_input_dir_images(extensions=extensions)
    datalist_id = f"{name.replace('_', '-')}-options"
    options = "".join(f'<option value="{html.escape(str(path))}">' for path in files)
    default_value = html.escape(str(files[0])) if files else ""
    required_attr = " required" if required else ""
    hint = ""
    if not files:
        hint = (
            f'<p class="hint">No images in <code>{html.escape(str(default_input_dir()))}/</code> yet. '
            "Type a path or add files there.</p>"
        )
    return f"""<label>{label}
      <input name="{name}" list="{datalist_id}" value="{default_value}"{required_attr} placeholder="input/…">
      <datalist id="{datalist_id}">{options}</datalist>
    </label>{hint}"""


def render_home_page(
    result: object | None = None,
    error: str | None = None,
    *,
    workflow: str | None = None,
) -> str:
    workflow = workflow if workflow in WORKFLOW_LABELS else None
    content = _render_workflow_form(workflow) if workflow else _render_workflow_picker()
    result_html = _render_result(result=result, error=error)
    title = WORKFLOW_LABELS.get(workflow or "", "Messy Virgo Artwork Creator")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0b0b0f;
      color: #ededed;
    }}
    body {{ margin: 0; background: #0b0b0f; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 48px; }}
    header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; margin-bottom: 24px; }}
    h1 {{ font-size: 28px; margin: 0; letter-spacing: -0.02em; }}
    h2 {{ font-size: 20px; margin: 0 0 12px; letter-spacing: -0.02em; }}
    h3 {{ font-size: 15px; margin: 0 0 6px; }}
    a {{ color: #ff69b4; text-decoration: none; }}
    .lead {{ margin: 6px 0 0; color: #9ca3af; }}
    .picker {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }}
    .card, form, .result {{
      border: 1px solid hsl(0 0% 14%);
      border-radius: 10px;
      padding: 18px;
      background: hsl(0 0% 7%);
      box-shadow: 0 16px 50px -35px rgba(255, 105, 180, 0.45);
    }}
    .card {{ display: block; color: #ededed; min-height: 104px; }}
    .card:hover {{ border-color: rgba(255, 105, 180, 0.6); background: hsl(0 0% 9%); }}
    .card span {{ color: #9ca3af; font-size: 13px; line-height: 1.45; }}
    form {{ max-width: 720px; }}
    label {{ display: grid; gap: 6px; margin: 0 0 13px; font-size: 13px; color: #d1d5db; }}
    input, textarea, select {{
      width: 100%; box-sizing: border-box; border: 1px solid hsl(0 0% 18%); border-radius: 8px;
      background: #101014; color: #ededed; padding: 10px 11px; font: inherit;
    }}
    textarea {{ min-height: 86px; resize: vertical; }}
    button {{ border: 0; border-radius: 8px; background: #ff69b4; color: #fff; padding: 10px 15px; font-weight: 700; cursor: pointer; }}
    .row {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
    .row label {{ display: flex; flex-direction: row; gap: 8px; margin: 0; align-items: center; }}
    .row input[type="checkbox"] {{ width: auto; }}
    pre {{ overflow: auto; white-space: pre-wrap; background: #050507; padding: 12px; border-radius: 8px; }}
    .hint {{ margin: -4px 0 12px; font-size: 12px; color: #9ca3af; }}
    .eyebrow {{ color: #ff69b4; font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }}
    .error {{ border-color: #b64b4b; }}
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <p class="eyebrow">Local generator</p>
      <h1>{html.escape(title)}</h1>
      <p class="lead">{_page_lead(workflow)}</p>
    </div>
    {('<a href="/">Workflow picker</a>' if workflow else '')}
  </header>
  {content}
  {result_html}
</main>
</body>
</html>"""


def _render_result(*, result: object | None = None, error: str | None = None) -> str:
    if error:
        return f"<section class='result error'><h2>Error</h2><pre>{html.escape(error)}</pre></section>"
    if result is not None:
        return (
            "<section class='result'><h2>Result</h2>"
            f"<pre>{html.escape(json.dumps(result, indent=2, sort_keys=True))}</pre></section>"
        )
    return ""


def _page_lead(workflow: str | None) -> str:
    if workflow == "avatar":
        return "Build a consistent avatar reference set from a transparent PNG."
    if workflow == "scene":
        return "Generate one Messy scene from a source avatar, setting, and action."
    if workflow == "messy-fy":
        return "Restyle an existing image in the Messy Virgo visual system."
    if workflow == "background":
        return "Remove backgrounds from local images or image directories."
    return "Choose one workflow to configure and run."


def _render_workflow_picker() -> str:
    cards = [
        ("avatar", "Create avatar reference views"),
        ("scene", "Place Messy into a generated scene"),
        ("messy-fy", "Restyle an existing image"),
        ("background", "Remove image backgrounds"),
    ]
    items = "\n".join(
        f"""<a class="card" href="/?workflow={workflow}">
      <h2>{html.escape(WORKFLOW_LABELS[workflow])}</h2>
      <span>{html.escape(description)}</span>
    </a>"""
        for workflow, description in cards
    )
    return f"""<section>
    <h2>Choose a workflow</h2>
    <div class="picker">{items}</div>
  </section>"""


def _render_workflow_form(workflow: str | None) -> str:
    if workflow == "avatar":
        return _render_avatar_form()
    if workflow == "scene":
        return _render_scene_form()
    if workflow == "messy-fy":
        return _render_messy_fy_form()
    if workflow == "background":
        return _render_background_form()
    return _render_workflow_picker()


def _render_avatar_form() -> str:
    return f"""<form method="post" action="/avatar">
      <h2>Avatar Reference Set</h2>
      {_render_input_file_field("source_image", label="Source avatar PNG", extensions=PNG_EXTENSIONS)}
      <label>Output directory<input name="output_dir" value="{html.escape(str(default_output_dir()))}"></label>
      {_render_model_select(GenerationTask.AVATAR)}
      <div class="row">
        <label><input name="dry_run" type="checkbox" value="1" checked> Dry run</label>
        <label><input name="test_mode" type="checkbox" value="1"> Test image only</label>
        <button type="submit">Run</button>
      </div>
    </form>"""


def _render_scene_form() -> str:
    return f"""<form method="post" action="/scene">
      <h2>Scene Generator</h2>
      {_render_input_file_field("source_image", label="Source avatar PNG", extensions=PNG_EXTENSIONS)}
      <label>Where Messy is<textarea name="setting" required></textarea></label>
      <label>What Messy is doing<textarea name="action" required></textarea></label>
      <label>Output directory<input name="output_dir" value="{html.escape(str(default_scene_output_dir()))}"></label>
      {_render_model_select(GenerationTask.SCENE)}
      <label>Output filename base<input name="filename" placeholder="optional"></label>
      <div class="row">
        <label><input name="dry_run" type="checkbox" value="1" checked> Dry run</label>
        <button type="submit">Run</button>
      </div>
    </form>"""


def _render_messy_fy_form() -> str:
    return f"""<form method="post" action="/messy-fy">
      <h2>Messy-fy</h2>
      {_render_input_file_field("source_image", label="Source image")}
      <label>Hint<textarea name="hint"></textarea></label>
      <label>Output directory<input name="output_dir" value="{html.escape(str(default_messy_fy_output_dir()))}"></label>
      {_render_model_select(GenerationTask.MESSY_FY)}
      <label>Output filename base<input name="filename" placeholder="optional"></label>
      <div class="row">
        <label><input name="dry_run" type="checkbox" value="1" checked> Dry run</label>
        <label><input name="remove_background" type="checkbox" value="1"> Remove background</label>
        <button type="submit">Run</button>
      </div>
    </form>"""


def _render_background_form() -> str:
    return f"""<form method="post" action="/background">
      <h2>Remove Background</h2>
      {_render_input_file_field("source", label="Input file or directory", entries=list_input_dir_entries())}
      <label>Output directory<input name="output_dir" value="output"></label>
      <label>Method<select name="method">
        <option value="rembg" selected>rembg (AI)</option>
        <option value="flood">flood (fast)</option>
      </select></label>
      <button type="submit">Convert</button>
    </form>"""


def _render_model_select(task: GenerationTask, *, registry: ModelRegistry | None = None) -> str:
    registry = registry or load_model_registry()
    selected = _selected_model_alias(task, registry)
    options = []
    for alias in _canonical_model_aliases(registry, preferred_alias=selected):
        selected_attr = " selected" if alias == selected else ""
        label = f"{alias} ({registry.aliases[alias]})"
        options.append(
            f'<option value="{html.escape(alias)}"{selected_attr}>{html.escape(label)}</option>'
        )
    if not options:
        default_value = html.escape(registry.default)
        options.append(f'<option value="{default_value}" selected>{default_value}</option>')
    return f"""<label>Model
      <select name="model">{"".join(options)}</select>
    </label>"""


def _selected_model_alias(task: GenerationTask, registry: ModelRegistry) -> str:
    configured = registry.tasks.get(task.value) or registry.default
    if configured in registry.aliases:
        return configured
    for alias, model_id in registry.aliases.items():
        if model_id == configured:
            return alias
    return configured


def _canonical_model_aliases(registry: ModelRegistry, *, preferred_alias: str) -> list[str]:
    aliases_by_model: dict[str, list[str]] = {}
    for alias, model_id in registry.aliases.items():
        aliases_by_model.setdefault(model_id, []).append(alias)

    selected_aliases: list[str] = []
    for aliases in aliases_by_model.values():
        if preferred_alias in aliases:
            selected_aliases.append(preferred_alias)
        else:
            selected_aliases.append(sorted(aliases, key=lambda alias: (len(alias), alias))[0])
    return sorted(selected_aliases)


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
        parsed = urlparse(self.path)
        if parsed.path != "/":
            self.send_error(404)
            return
        query = parse_qs(parsed.query)
        self._send_html(render_home_page(workflow=_text_value(query, "workflow") or None))

    def do_POST(self) -> None:  # noqa: N802
        workflow = _workflow_for_post_path(self.path)
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
            self._send_html(render_home_page(result=result, workflow=workflow))
        except CLIENT_DISCONNECT_ERRORS:
            return
        except Exception as exc:
            try:
                self._send_html(render_home_page(error=str(exc), workflow=workflow), status=400)
            except CLIENT_DISCONNECT_ERRORS:
                return

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


def _workflow_for_post_path(path: str) -> str | None:
    return {
        "/avatar": "avatar",
        "/scene": "scene",
        "/messy-fy": "messy-fy",
        "/background": "background",
    }.get(path)

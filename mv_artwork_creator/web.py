from __future__ import annotations

import html
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

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


WORKFLOW_ICONS = {
    "avatar": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8.5" r="3.5"/>'
        '<path d="M4.5 20a7.5 7.5 0 0 1 15 0"/></svg>'
    ),
    "scene": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4.5" width="18" height="15" rx="2"/>'
        '<circle cx="8.5" cy="9.5" r="1.6"/><path d="M21 16l-5-5-9 8.5"/></svg>'
    ),
    "messy-fy": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l2 2"/>'
        '<path d="M14.5 4.5l5 5L9 20H4v-5z"/><path d="M12.5 6.5l5 5"/>'
        '<path d="M19 3l.7 1.6L21 5l-1.3.7L19 7l-.7-1.3L17 5l1.3-.4z"/></svg>'
    ),
    "background": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="2.5"/>'
        '<circle cx="6" cy="18" r="2.5"/><path d="M8 7.5L20 17"/><path d="M8 16.5L20 7"/>'
        '<path d="M14 12l6 0"/></svg>'
    ),
}

_FOLDER_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4l2 2.3H'
    '19.5A1.5 1.5 0 0 1 21 8.8v9.7A1.5 1.5 0 0 1 19.5 20h-15A1.5 1.5 0 0 1 3 18.5z"/></svg>'
)


def _file_url(path: Path) -> str:
    return f"/file?path={quote(str(path))}"


def _thumb_tile(path: Path, *, selectable: bool) -> str:
    value = html.escape(str(path))
    caption = html.escape(path.name)
    tag = "button" if selectable else "div"
    attrs = ' type="button" class="thumb" data-value="' + value + '"' if selectable else ' class="thumb static"'
    if path.is_dir():
        media = f'<span class="thumb-folder">{_FOLDER_ICON}</span>'
    elif path.suffix.lower() in IMAGE_EXTENSIONS:
        media = f'<img loading="lazy" src="{_file_url(path)}" alt="{caption}">'
    else:
        media = '<span class="thumb-folder">·</span>'
    return f'<{tag}{attrs}><span class="thumb-media">{media}</span><span class="thumb-name">{caption}</span></{tag}>'


def _render_image_picker(
    name: str,
    *,
    label: str,
    extensions: set[str] | None = None,
    required: bool = True,
    entries: list[Path] | None = None,
) -> str:
    files = entries if entries is not None else list_input_dir_images(extensions=extensions)
    default_value = html.escape(str(files[0])) if files else ""
    required_attr = " required" if required else ""
    if files:
        tiles = "".join(_thumb_tile(path, selectable=True) for path in files)
        grid = f'<div class="thumbgrid">{tiles}</div>'
        hint = ""
    else:
        grid = (
            '<div class="thumbgrid empty"><p class="hint">No images in '
            f'<code>{html.escape(str(default_input_dir()))}/</code> yet — add files there, '
            "or type a path below.</p></div>"
        )
        hint = ""
    return f"""<div class="field filepicker">
      <span class="field-label">{label}</span>
      {grid}
      <input class="pathfield" name="{name}" value="{default_value}"{required_attr} placeholder="input/…" autocomplete="off">
    </div>{hint}"""


PAGE_STYLE = """
    :root {
      color-scheme: dark;
      --bg: #0b0b0f;
      --surface: hsl(0 0% 7.5%);
      --surface-2: hsl(0 0% 10%);
      --surface-3: hsl(0 0% 13%);
      --line: hsl(0 0% 16%);
      --line-soft: hsl(0 0% 13%);
      --text: #ededed;
      --muted: #9aa1ac;
      --pink: #ff69b4;
      --pink-soft: #ff8fcf;
      --pink-deep: #d6488f;
      --radius: 14px;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(900px 480px at 18% -8%, rgba(255, 105, 180, 0.16), transparent 60%),
        radial-gradient(720px 420px at 110% 0%, rgba(120, 80, 220, 0.12), transparent 55%),
        var(--bg);
    }
    main { max-width: 1040px; margin: 0 auto; padding: 26px 22px 72px; }
    a { color: var(--pink); text-decoration: none; }
    a:hover { color: var(--pink-soft); }

    header.app {
      display: flex; justify-content: space-between; align-items: center; gap: 18px;
      padding: 14px 0 26px; margin-bottom: 22px; border-bottom: 1px solid var(--line-soft);
    }
    .brand { display: flex; align-items: center; gap: 13px; }
    .brand-mark {
      width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center;
      font-weight: 800; font-size: 15px; letter-spacing: -0.04em; color: #2a0a1c;
      background: linear-gradient(140deg, var(--pink-soft), var(--pink) 55%, var(--pink-deep));
      box-shadow: 0 10px 28px -12px rgba(255, 105, 180, 0.7);
    }
    .brand h1 { font-size: 19px; margin: 0; letter-spacing: -0.02em; }
    .brand .eyebrow {
      display: block; color: var(--pink); font-size: 10.5px; font-weight: 700;
      letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 1px;
    }
    .ghost-btn {
      display: inline-flex; align-items: center; gap: 7px; padding: 8px 14px; border-radius: 9px;
      border: 1px solid var(--line); background: var(--surface); color: var(--text);
      font-size: 13px; font-weight: 600; transition: border-color .15s, background .15s;
    }
    .ghost-btn:hover { border-color: rgba(255,105,180,.55); background: var(--surface-2); color: var(--text); }

    .page-intro { margin: 4px 0 22px; }
    .page-intro h2 { font-size: 25px; margin: 0 0 6px; letter-spacing: -0.025em; }
    .page-intro .lead { margin: 0; color: var(--muted); font-size: 14.5px; max-width: 64ch; }

    .picker { display: grid; grid-template-columns: repeat(auto-fit, minmax(232px, 1fr)); gap: 16px; }
    .card {
      position: relative; display: flex; flex-direction: column; gap: 12px; padding: 20px;
      border: 1px solid var(--line-soft); border-radius: var(--radius); background: var(--surface);
      color: var(--text); min-height: 132px; overflow: hidden;
      transition: border-color .16s, transform .16s, background .16s;
    }
    .card::after {
      content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
      background: linear-gradient(135deg, rgba(255,105,180,.10), transparent 42%); opacity: 0; transition: opacity .16s;
    }
    .card:hover { border-color: rgba(255,105,180,.55); transform: translateY(-3px); background: var(--surface-2); }
    .card:hover::after { opacity: 1; }
    .card-icon {
      width: 40px; height: 40px; border-radius: 11px; display: grid; place-items: center; color: var(--pink);
      background: rgba(255,105,180,.12); border: 1px solid rgba(255,105,180,.22);
    }
    .card-icon svg { width: 22px; height: 22px; }
    .card h3 { font-size: 16px; margin: 0; letter-spacing: -0.01em; }
    .card span.desc { color: var(--muted); font-size: 13px; line-height: 1.5; }
    .card .go { margin-top: auto; color: var(--pink); font-size: 12.5px; font-weight: 700; }

    .panel {
      border: 1px solid var(--line-soft); border-radius: var(--radius); background: var(--surface);
      padding: 22px; box-shadow: 0 30px 70px -50px rgba(0,0,0,.9);
    }
    .workform { display: flex; flex-direction: column; gap: 16px; }
    .form-head { display: flex; align-items: center; gap: 13px; margin-bottom: 2px; }
    .form-head .card-icon { flex: none; }
    .form-head h2 { font-size: 19px; margin: 0; letter-spacing: -0.02em; }
    .form-head .form-sub { margin: 2px 0 0; color: var(--muted); font-size: 13px; }

    .field { display: flex; flex-direction: column; gap: 7px; }
    .field-label, .field > span:first-child, label > span { font-size: 12.5px; color: #c7ccd4; font-weight: 600; }
    label { display: grid; gap: 7px; margin: 0; font-size: 12.5px; color: #c7ccd4; font-weight: 600; }
    input[type=text], input:not([type]), textarea, select, .pathfield {
      width: 100%; border: 1px solid var(--line); border-radius: 10px; background: #0e0e13;
      color: var(--text); padding: 11px 12px; font: inherit; font-weight: 400; transition: border-color .15s, box-shadow .15s;
    }
    input:focus, textarea:focus, select:focus, .pathfield:focus {
      outline: none; border-color: var(--pink); box-shadow: 0 0 0 3px rgba(255,105,180,.16);
    }
    textarea { min-height: 88px; resize: vertical; line-height: 1.5; }
    select { appearance: none; background-image:
      url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="none" stroke="%239aa1ac" stroke-width="2"><path d="M2 4l4 4 4-4"/></svg>');
      background-repeat: no-repeat; background-position: right 12px center; padding-right: 34px; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 640px) { .grid-2 { grid-template-columns: 1fr; } }

    .thumbgrid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 10px;
      padding: 12px; border: 1px solid var(--line-soft); border-radius: 12px; background: #0c0c11;
      max-height: 318px; overflow-y: auto;
    }
    .thumbgrid.empty { display: block; padding: 18px; }
    .thumb {
      display: flex; flex-direction: column; gap: 6px; padding: 6px; border: 1px solid transparent;
      border-radius: 10px; background: var(--surface-2); color: var(--muted); cursor: pointer;
      font: inherit; text-align: center; transition: border-color .14s, background .14s, transform .12s;
    }
    .thumb:hover { background: var(--surface-3); border-color: var(--line); transform: translateY(-2px); }
    .thumb.static { cursor: default; }
    .thumb-media {
      position: relative; display: grid; place-items: center; aspect-ratio: 1; border-radius: 7px; overflow: hidden;
      background:
        linear-gradient(45deg, #15151b 25%, transparent 25%) -8px 0 / 16px 16px,
        linear-gradient(-45deg, #15151b 25%, transparent 25%) -8px 0 / 16px 16px,
        linear-gradient(45deg, transparent 75%, #15151b 75%) -8px 0 / 16px 16px,
        linear-gradient(-45deg, transparent 75%, #15151b 75%) -8px 0 / 16px 16px, #101015;
    }
    .thumb-media img { width: 100%; height: 100%; object-fit: contain; }
    .thumb-folder { color: var(--pink); } .thumb-folder svg { width: 34px; height: 34px; }
    .thumb-name { font-size: 10.5px; line-height: 1.25; word-break: break-word; color: #aeb4bd; }
    .thumb.is-selected { border-color: var(--pink); background: rgba(255,105,180,.10); }
    .thumb.is-selected .thumb-name { color: var(--pink-soft); }
    .thumb.is-selected .thumb-media::after {
      content: "✓"; position: absolute; top: 4px; right: 5px; width: 18px; height: 18px; border-radius: 50%;
      display: grid; place-items: center; font-size: 11px; font-weight: 800; color: #2a0a1c;
      background: var(--pink); box-shadow: 0 2px 8px rgba(0,0,0,.5);
    }
    .pathfield { font-size: 12.5px; color: var(--muted); }

    .options { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
    .toggle {
      display: inline-flex; align-items: center; gap: 9px; padding: 9px 14px; border-radius: 999px;
      border: 1px solid var(--line); background: var(--surface-2); color: var(--muted); cursor: pointer;
      font-size: 12.5px; font-weight: 600; user-select: none; transition: border-color .14s, color .14s, background .14s;
    }
    .toggle:hover { border-color: rgba(255,105,180,.4); }
    .toggle input { appearance: none; width: 30px; height: 17px; border-radius: 999px; background: #30303a;
      position: relative; cursor: pointer; transition: background .15s; flex: none; }
    .toggle input::after { content: ""; position: absolute; top: 2px; left: 2px; width: 13px; height: 13px;
      border-radius: 50%; background: #c9ccd2; transition: transform .15s; }
    .toggle input:checked { background: var(--pink); }
    .toggle input:checked::after { transform: translateX(13px); background: #fff; }
    .toggle:has(input:checked) { color: var(--text); border-color: rgba(255,105,180,.5); background: rgba(255,105,180,.08); }

    .form-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 4px; }
    button.run {
      border: 0; border-radius: 11px; padding: 12px 26px; font: inherit; font-weight: 700; font-size: 14px;
      color: #2a0a1c; cursor: pointer; letter-spacing: -0.01em;
      background: linear-gradient(135deg, var(--pink-soft), var(--pink) 55%, var(--pink-deep));
      box-shadow: 0 14px 32px -14px rgba(255,105,180,.8); transition: transform .12s, box-shadow .15s, filter .15s;
    }
    button.run:hover { transform: translateY(-2px); filter: brightness(1.05); box-shadow: 0 18px 38px -14px rgba(255,105,180,.9); }
    button.run:active { transform: translateY(0); }

    .result { margin-top: 26px; }
    .result-head { display: flex; align-items: center; gap: 10px; margin: 0 0 14px; }
    .result-head h2 { font-size: 17px; margin: 0; letter-spacing: -0.02em; }
    .result-badge { font-size: 11px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
      padding: 4px 10px; border-radius: 999px; background: rgba(255,105,180,.12); color: var(--pink-soft);
      border: 1px solid rgba(255,105,180,.3); }
    .result-badge.ok { background: rgba(80,200,140,.12); color: #6fe0a6; border-color: rgba(80,200,140,.3); }
    .result-badge.err { background: rgba(220,90,90,.14); color: #ff9b9b; border-color: rgba(220,90,90,.35); }

    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; margin-bottom: 18px; }
    .stat { padding: 15px 16px; border: 1px solid var(--line-soft); border-radius: 12px; background: var(--surface-2); }
    .stat .num { font-size: 26px; font-weight: 800; letter-spacing: -0.03em; line-height: 1; }
    .stat .lbl { display: block; margin-top: 6px; font-size: 11.5px; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
    .stat.pink .num { color: var(--pink); } .stat.green .num { color: #6fe0a6; }
    .stat.amber .num { color: #f0c674; } .stat.red .num { color: #ff9b9b; }

    .kv { display: grid; gap: 1px; border: 1px solid var(--line-soft); border-radius: 12px; overflow: hidden; margin-bottom: 18px; background: var(--line-soft); }
    .kv > div { display: grid; grid-template-columns: 150px 1fr; gap: 14px; padding: 11px 15px; background: var(--surface); }
    .kv dt { color: var(--muted); font-size: 12.5px; margin: 0; }
    .kv dd { margin: 0; font-size: 13px; word-break: break-word; }
    .kv dd code, code.path { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px;
      background: #0c0c11; padding: 2px 7px; border-radius: 6px; border: 1px solid var(--line-soft); color: #d8b9cd; }

    .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 14px; margin-bottom: 18px; }
    .gtile { border: 1px solid var(--line-soft); border-radius: 12px; overflow: hidden; background: var(--surface-2); }
    .gtile .gmedia { position: relative; aspect-ratio: 1; display: grid; place-items: center;
      background:
        linear-gradient(45deg, #15151b 25%, transparent 25%) -8px 0 / 18px 18px,
        linear-gradient(-45deg, #15151b 25%, transparent 25%) -8px 0 / 18px 18px,
        linear-gradient(45deg, transparent 75%, #15151b 75%) -8px 0 / 18px 18px,
        linear-gradient(-45deg, transparent 75%, #15151b 75%) -8px 0 / 18px 18px, #101015; }
    .gtile .gmedia img { width: 100%; height: 100%; object-fit: contain; }
    .gtile .planned { color: var(--muted); font-size: 12px; display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px; text-align: center; }
    .gtile .planned svg { width: 26px; height: 26px; opacity: .6; }
    .gtile .gcap { padding: 9px 11px; font-size: 11.5px; color: #aeb4bd; word-break: break-word; border-top: 1px solid var(--line-soft); }
    .gtile .gcap b { color: var(--text); font-weight: 600; }

    details.raw { border: 1px solid var(--line-soft); border-radius: 12px; background: var(--surface); overflow: hidden; }
    details.raw summary { cursor: pointer; padding: 12px 16px; font-size: 12.5px; color: var(--muted); font-weight: 600; list-style: none; }
    details.raw summary::-webkit-details-marker { display: none; }
    details.raw summary::before { content: "▸ "; color: var(--pink); }
    details.raw[open] summary::before { content: "▾ "; }
    details.raw pre { margin: 0; padding: 0 16px 16px; overflow: auto; white-space: pre-wrap; font-size: 12px;
      color: #c9ccd2; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .prompt-block { border: 1px solid var(--line-soft); border-radius: 12px; background: #0c0c11; padding: 14px 16px; margin-bottom: 18px; }
    .prompt-block h4 { margin: 0 0 7px; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
    .prompt-block p { margin: 0; font-size: 13px; line-height: 1.55; color: #d4d7dd; white-space: pre-wrap; }
"""

PAGE_SCRIPT = """
  document.querySelectorAll('.filepicker').forEach(function (fp) {
    var field = fp.querySelector('.pathfield');
    var thumbs = fp.querySelectorAll('.thumb');
    if (!field) return;
    function sync() {
      thumbs.forEach(function (t) {
        t.classList.toggle('is-selected', t.dataset.value === field.value);
      });
    }
    thumbs.forEach(function (t) {
      t.addEventListener('click', function () { field.value = t.dataset.value; sync(); });
    });
    field.addEventListener('input', sync);
    sync();
  });
"""


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
    back = (
        '<a class="ghost-btn" href="/">← All workflows</a>'
        if workflow
        else '<a class="ghost-btn" href="https://github.com/messyvirgo" target="_blank" rel="noopener">Messy Virgo</a>'
    )
    intro = (
        ""
        if workflow
        else '<div class="page-intro"><h2>What are we making?</h2>'
        '<p class="lead">Pick a workflow to configure and run. Everything stays local — '
        "images are read from your <code>input/</code> folder and written to disk.</p></div>"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{PAGE_STYLE}</style>
</head>
<body>
<main>
  <header class="app">
    <a class="brand" href="/">
      <span class="brand-mark">MV</span>
      <span><span class="eyebrow">Artwork Creator</span><h1>Messy Virgo</h1></span>
    </a>
    {back}
  </header>
  {intro}
  {content}
  {result_html}
</main>
<script>{PAGE_SCRIPT}</script>
</body>
</html>"""


def _render_result(*, result: object | None = None, error: str | None = None) -> str:
    if error:
        return (
            '<section class="result"><div class="result-head">'
            '<span class="result-badge err">Error</span><h2>Something went wrong</h2></div>'
            f'<div class="prompt-block"><p>{html.escape(error)}</p></div></section>'
        )
    if result is None:
        return ""
    data = result if isinstance(result, dict) else {}
    kind = str(data.get("kind", "result"))
    is_dry = kind.endswith("-dry-run")
    badge_cls = "" if is_dry else "ok"
    badge_text = "Plan preview" if is_dry else "Done"
    heading = "Dry run — nothing was generated" if is_dry else "Run complete"

    body = _render_dry_run_body(data) if is_dry else _render_run_body(data)
    raw = (
        '<details class="raw"><summary>Raw response</summary>'
        f"<pre>{html.escape(json.dumps(data, indent=2, sort_keys=True))}</pre></details>"
    )
    return (
        '<section class="result"><div class="result-head">'
        f'<span class="result-badge {badge_cls}">{badge_text}</span><h2>{html.escape(heading)}</h2></div>'
        f"{body}{raw}</section>"
    )


def _planned_paths(data: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    if isinstance(data.get("items"), list):
        for item in data["items"]:
            if isinstance(item, dict) and item.get("output_path"):
                paths.append(Path(str(item["output_path"])))
    for key in ("output_path", "transparent_output_path"):
        value = data.get(key)
        if isinstance(value, str) and value:
            paths.append(Path(value))
    return paths


def _gallery_tile(path: Path) -> str:
    cap = f'<div class="gcap"><b>{html.escape(path.name)}</b><br>{html.escape(str(path.parent))}/</div>'
    if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
        media = f'<div class="gmedia"><img loading="lazy" src="{_file_url(path)}" alt="{html.escape(path.name)}"></div>'
    else:
        media = (
            '<div class="gmedia"><span class="planned">'
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" '
            'stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
            "will be written here</span></div>"
        )
    return f'<div class="gtile">{media}{cap}</div>'


def _kv_rows(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f"<div><dt>{html.escape(label)}</dt><dd>{value}</dd></div>" for label, value in rows
    )
    return f'<dl class="kv">{cells}</dl>'


def _render_dry_run_body(data: dict[str, Any]) -> str:
    rows: list[tuple[str, str]] = []
    if data.get("model"):
        rows.append(("Model", f'<code class="path">{html.escape(str(data["model"]))}</code>'))
    if data.get("provider"):
        rows.append(("Provider", html.escape(str(data["provider"]))))
    if data.get("source_image"):
        rows.append(("Source", f'<code class="path">{html.escape(str(data["source_image"]))}</code>'))
    if data.get("output_dir"):
        rows.append(("Output dir", f'<code class="path">{html.escape(str(data["output_dir"]))}</code>'))
    if data.get("setting"):
        rows.append(("Setting", html.escape(str(data["setting"]))))
    if data.get("action"):
        rows.append(("Action", html.escape(str(data["action"]))))
    if "planned_count" in data:
        rows.append(("Planned images", str(data["planned_count"])))

    parts: list[str] = []
    if rows:
        parts.append(_kv_rows(rows))
    prompt = data.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        parts.append(
            '<div class="prompt-block"><h4>Prompt</h4>'
            f"<p>{html.escape(prompt.strip())}</p></div>"
        )
    paths = _planned_paths(data)
    if paths:
        tiles = "".join(_gallery_tile(path) for path in paths)
        parts.append(f'<div class="gallery">{tiles}</div>')
    return "".join(parts)


_STAT_TONES = {
    "generated": "green",
    "converted": "green",
    "planned": "pink",
    "skipped": "amber",
    "failed": "red",
}


def _render_run_body(data: dict[str, Any]) -> str:
    order = ["planned", "generated", "converted", "skipped", "failed"]
    stats = [
        (key, data[key])
        for key in order
        if isinstance(data.get(key), int)
    ]
    parts: list[str] = []
    if stats:
        cells = "".join(
            f'<div class="stat {_STAT_TONES.get(key, "")}"><span class="num">{value}</span>'
            f'<span class="lbl">{html.escape(key)}</span></div>'
            for key, value in stats
        )
        parts.append(f'<div class="stats">{cells}</div>')
    paths = [p for p in _planned_paths(data) if p.is_file()]
    if paths:
        tiles = "".join(_gallery_tile(path) for path in paths)
        parts.append(f'<div class="gallery">{tiles}</div>')
    if not parts:
        parts.append('<div class="prompt-block"><p>Finished.</p></div>')
    return "".join(parts)


def _render_workflow_picker() -> str:
    cards = [
        ("avatar", "Create a consistent avatar reference set from a transparent PNG."),
        ("scene", "Drop Messy into a freshly generated scene — your setting, your action."),
        ("messy-fy", "Restyle any existing image into the Messy Virgo visual system."),
        ("background", "Cut clean transparent backgrounds from images or folders."),
    ]
    items = "\n".join(
        f"""<a class="card" href="/?workflow={workflow}">
      <span class="card-icon">{WORKFLOW_ICONS[workflow]}</span>
      <h3>{html.escape(WORKFLOW_LABELS[workflow])}</h3>
      <span class="desc">{html.escape(description)}</span>
      <span class="go">Configure →</span>
    </a>"""
        for workflow, description in cards
    )
    return f'<section><div class="picker">{items}</div></section>'


def _form_head(workflow: str, subtitle: str) -> str:
    return (
        '<div class="form-head">'
        f'<span class="card-icon">{WORKFLOW_ICONS[workflow]}</span>'
        f'<div><h2>{html.escape(WORKFLOW_LABELS[workflow])}</h2>'
        f'<p class="form-sub">{html.escape(subtitle)}</p></div></div>'
    )


def _toggle(name: str, label: str, *, checked: bool = False) -> str:
    checked_attr = " checked" if checked else ""
    return (
        f'<label class="toggle"><input type="checkbox" name="{name}" value="1"{checked_attr}>'
        f"<span>{html.escape(label)}</span></label>"
    )


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
    return f"""<form class="panel workform" method="post" action="/avatar">
      {_form_head("avatar", "Generate every reference angle from one source PNG.")}
      {_render_image_picker("source_image", label="Source avatar PNG", extensions=PNG_EXTENSIONS)}
      <label>Output directory
        <input type="text" name="output_dir" value="{html.escape(str(default_output_dir()))}">
      </label>
      {_render_model_select(GenerationTask.AVATAR)}
      <div class="options">
        {_toggle("dry_run", "Dry run", checked=True)}
        {_toggle("test_mode", "Test image only")}
      </div>
      <div class="form-actions"><button class="run" type="submit">Run avatar set</button></div>
    </form>"""


def _render_scene_form() -> str:
    return f"""<form class="panel workform" method="post" action="/scene">
      {_form_head("scene", "Place Messy into a generated scene from a source avatar.")}
      {_render_image_picker("source_image", label="Source avatar PNG", extensions=PNG_EXTENSIONS)}
      <div class="grid-2">
        <label>Where Messy is<textarea name="setting" required placeholder="a neon-lit ramen bar at night"></textarea></label>
        <label>What Messy is doing<textarea name="action" required placeholder="slurping noodles, grinning at the camera"></textarea></label>
      </div>
      <div class="grid-2">
        <label>Output directory<input type="text" name="output_dir" value="{html.escape(str(default_scene_output_dir()))}"></label>
        <label>Output filename base<input type="text" name="filename" placeholder="optional"></label>
      </div>
      {_render_model_select(GenerationTask.SCENE)}
      <div class="options">{_toggle("dry_run", "Dry run", checked=True)}</div>
      <div class="form-actions"><button class="run" type="submit">Generate scene</button></div>
    </form>"""


def _render_messy_fy_form() -> str:
    return f"""<form class="panel workform" method="post" action="/messy-fy">
      {_form_head("messy-fy", "Restyle an existing image in the Messy Virgo look.")}
      {_render_image_picker("source_image", label="Source image")}
      <label>Hint<textarea name="hint" placeholder="optional — nudge the restyle"></textarea></label>
      <div class="grid-2">
        <label>Output directory<input type="text" name="output_dir" value="{html.escape(str(default_messy_fy_output_dir()))}"></label>
        <label>Output filename base<input type="text" name="filename" placeholder="optional"></label>
      </div>
      {_render_model_select(GenerationTask.MESSY_FY)}
      <div class="options">
        {_toggle("dry_run", "Dry run", checked=True)}
        {_toggle("remove_background", "Remove background")}
      </div>
      <div class="form-actions"><button class="run" type="submit">Messy-fy it</button></div>
    </form>"""


def _render_background_form() -> str:
    return f"""<form class="panel workform" method="post" action="/background">
      {_form_head("background", "Cut transparent backgrounds from an image or a whole folder.")}
      {_render_image_picker("source", label="Input file or directory", entries=list_input_dir_entries())}
      <div class="grid-2">
        <label>Output directory<input type="text" name="output_dir" value="output"></label>
        <label>Method
          <select name="method">
            <option value="rembg" selected>rembg (AI)</option>
            <option value="flood">flood (fast)</option>
          </select>
        </label>
      </div>
      <div class="form-actions"><button class="run" type="submit">Remove background</button></div>
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
        if parsed.path == "/file":
            self._serve_file(parse_qs(parsed.query))
            return
        if parsed.path != "/":
            self.send_error(404)
            return
        query = parse_qs(parsed.query)
        self._send_html(render_home_page(workflow=_text_value(query, "workflow") or None))

    def _serve_file(self, query: dict[str, list[str]]) -> None:
        raw = _text_value(query, "path")
        if not raw:
            self.send_error(404)
            return
        try:
            target = Path(raw).resolve()
            target.relative_to(Path.cwd().resolve())
        except (ValueError, OSError):
            self.send_error(403)
            return
        if not target.is_file() or target.suffix.lower() not in IMAGE_EXTENSIONS:
            self.send_error(404)
            return
        try:
            data = target.read_bytes()
        except OSError:
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except CLIENT_DISCONNECT_ERRORS:
            return

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

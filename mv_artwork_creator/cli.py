from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .background import remove_backgrounds
from .config import GenerationConfig, default_output_dir, load_env_file
from .executor import run_generation
from .messy_fy_executor import (
    MessyFyGenerationConfig,
    create_messy_fy_plan,
    default_messy_fy_output_dir,
    messy_fy_plan_to_dict,
    run_messy_fy_generation,
)
from .messy_fy_prompts import load_messy_fy_prompt_library
from .models import GenerationTask, resolve_model
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
from .user_config import (
    default_avatar_prompt_library,
    default_messy_fy_prompt_library,
    default_scene_prompt_library,
    ensure_user_config,
    reset_user_config,
    seed_user_config,
    user_config_dir,
)
from .scene_prompts import load_scene_prompt_library
from .sharpen import (
    DEFAULT_SHARPEN_PERCENT,
    DEFAULT_SHARPEN_RADIUS,
    DEFAULT_SHARPEN_THRESHOLD,
    SharpenSettings,
    sharpen_images,
)
from .web import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT, start_web_server


def _add_factory_defaults_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--factory-defaults",
        action="store_true",
        help="Use bundled factory YAML defaults instead of the local config/ copies.",
    )


def _add_openrouter_model_argument(parser: argparse.ArgumentParser, task: GenerationTask) -> None:
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "OpenRouter model alias or full id. "
            f"Defaults to the {task.value} entry in bundled models.yaml (alias or full OpenRouter id)."
        ),
    )


def build_root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mvac",
        description="Messy Virgo Artwork Creator — avatar, scene, and messy-fy generation with OpenRouter.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    avatar = subparsers.add_parser("avatar", help="Generate multi-angle avatar reference images.")
    avatar.add_argument("source_image", type=Path, help="Transparent PNG avatar source image.")
    avatar.add_argument("--output-dir", type=Path, default=default_output_dir())
    avatar.add_argument(
        "--prompt-library",
        type=Path,
        default=None,
        help="Avatar prompt YAML. Defaults to config/avatar_prompts.yaml (created on first run).",
    )
    _add_openrouter_model_argument(avatar, GenerationTask.AVATAR)
    _add_factory_defaults_argument(avatar)
    avatar.add_argument("--api-key", default=None, help="OpenRouter API key. Defaults to OPENROUTER_API_KEY.")
    avatar.add_argument("--preset", action="append", dest="presets", help="Angle and shot as angle:shot. Repeatable.")
    avatar.add_argument("--test", action="store_true", dest="test_mode", help="Generate exactly one image.")
    avatar.add_argument("--test-preset", default=None, help="Angle and shot for --test, as angle:shot.")
    avatar.add_argument("--dry-run", action="store_true", help="Print the generation plan without calling OpenRouter.")
    avatar.add_argument("--regenerate", action="store_true", help="Regenerate successful existing outputs.")
    avatar.add_argument("--stop-on-error", action="store_true", help="Stop the batch after the first failed item.")
    avatar.add_argument("--retry-count", type=int, default=0, help="Reserved for provider retries.")
    avatar.add_argument("--concurrency", type=int, default=1, help="Reserved for future parallel execution.")

    scene = subparsers.add_parser("scene", help="Generate one Messy brand scene image.")
    scene.add_argument("source_image", type=Path, help="Transparent PNG avatar source image.")
    scene.add_argument("--setting", required=True, help="Where Messy is.")
    scene.add_argument("--action", required=True, help="What Messy is doing.")
    scene.add_argument("--output-dir", type=Path, default=default_scene_output_dir())
    scene.add_argument("--prompt-library", type=Path, default=None)
    _add_openrouter_model_argument(scene, GenerationTask.SCENE)
    _add_factory_defaults_argument(scene)
    scene.add_argument("--api-key", default=None, help="OpenRouter API key. Defaults to OPENROUTER_API_KEY.")
    scene.add_argument("--filename", default=None, help="Output filename stem. Defaults to a slug from setting and action.")
    scene.add_argument("--dry-run", action="store_true", help="Print the scene plan without calling OpenRouter.")
    scene.add_argument("--regenerate", action="store_true", help="Regenerate successful existing output.")
    scene.add_argument("--retry-count", type=int, default=0, help="Retry failed provider requests this many times.")

    messy_fy = subparsers.add_parser("messy-fy", help="Repaint an image in the Messy Virgo brand style.")
    messy_fy.add_argument("source_image", type=Path, help="PNG, JPEG, or WebP source image.")
    messy_fy.add_argument("--output-dir", type=Path, default=default_messy_fy_output_dir())
    messy_fy.add_argument("--prompt-library", type=Path, default=None)
    _add_openrouter_model_argument(messy_fy, GenerationTask.MESSY_FY)
    _add_factory_defaults_argument(messy_fy)
    messy_fy.add_argument("--api-key", default=None, help="OpenRouter API key. Defaults to OPENROUTER_API_KEY.")
    messy_fy.add_argument("--hint", default=None, help="Optional guidance for pose, mood, or composition.")
    messy_fy.add_argument("--filename", default=None, help="Output filename stem. Defaults to the source image stem.")
    messy_fy.add_argument(
        "--remove-background",
        action="store_true",
        help="After generation, also write a transparent PNG via remove-background.",
    )
    messy_fy.add_argument("--dry-run", action="store_true", help="Print the messy-fy plan without calling OpenRouter.")
    messy_fy.add_argument("--regenerate", action="store_true", help="Regenerate successful existing output.")
    messy_fy.add_argument("--retry-count", type=int, default=0, help="Retry failed provider requests this many times.")

    background = subparsers.add_parser(
        "remove-background",
        help="Convert images to transparent-background PNGs.",
    )
    background.add_argument("source", nargs="?", type=Path, help="PNG/JPG file or directory containing image files.")
    background.add_argument("--input-dir", type=Path, help="Directory containing generated PNG/JPG files.")
    background.add_argument("--input-file", type=Path, help="Single generated PNG/JPG file.")
    background.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for transparent PNG outputs. Defaults to <input>-transparent.",
    )
    background.add_argument(
        "--method",
        choices=("rembg", "flood"),
        default="rembg",
        help="rembg uses AI segmentation (best for hair). flood uses corner color flood-fill.",
    )
    background.add_argument(
        "--model",
        default="isnet-anime",
        help="rembg model name (default: isnet-anime for anime characters).",
    )
    background.add_argument("--tolerance", type=int, default=28, help="Color tolerance for --method flood only.")
    background.add_argument(
        "--white-threshold",
        type=int,
        default=242,
        help="After rembg, zero alpha on near-white neutral pixels at or above this value (0 disables).",
    )
    background.add_argument(
        "--alpha-matting",
        action="store_true",
        help="Enable rembg alpha matting (slower; may print pymatting warnings).",
    )
    background.add_argument(
        "--no-pre-sharpen",
        action="store_true",
        help="Skip unsharp-mask sharpening before background removal (on by default).",
    )
    background.add_argument("--sharpen-radius", type=float, default=DEFAULT_SHARPEN_RADIUS)
    background.add_argument("--sharpen-percent", type=int, default=DEFAULT_SHARPEN_PERCENT)
    background.add_argument("--sharpen-threshold", type=int, default=DEFAULT_SHARPEN_THRESHOLD)
    background.add_argument("--overwrite", action="store_true", help="Overwrite existing PNG outputs.")

    sharpen = subparsers.add_parser("sharpen", help="Sharpen generated images before background removal.")
    sharpen.add_argument("source", nargs="?", type=Path, help="PNG/JPG file or directory containing image files.")
    sharpen.add_argument("--input-dir", type=Path, help="Directory containing generated PNG/JPG files.")
    sharpen.add_argument("--input-file", type=Path, help="Single generated PNG/JPG file.")
    sharpen.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for sharpened PNG outputs. Defaults to <input>-sharpened.",
    )
    sharpen.add_argument("--sharpen-radius", type=float, default=DEFAULT_SHARPEN_RADIUS)
    sharpen.add_argument("--sharpen-percent", type=int, default=DEFAULT_SHARPEN_PERCENT)
    sharpen.add_argument("--sharpen-threshold", type=int, default=DEFAULT_SHARPEN_THRESHOLD)
    sharpen.add_argument("--overwrite", action="store_true", help="Overwrite existing PNG outputs.")

    web = subparsers.add_parser("web", help="Start the local Messy Virgo Artwork Creator web interface.")
    web.add_argument("--host", default=DEFAULT_WEB_HOST)
    web.add_argument("--port", type=int, default=DEFAULT_WEB_PORT)

    config = subparsers.add_parser("config", help="Manage local config/ YAML copies (prompts and models).")
    config_sub = config.add_subparsers(dest="config_action", required=True)
    config_sub.add_parser("init", help="Copy any missing factory defaults into config/.")
    config_sub.add_parser("reset", help="Overwrite config/ files with factory defaults.")
    config_sub.add_parser("path", help="Print the config directory path.")

    return parser


def _prompt_library_for_command(args: argparse.Namespace, task: str) -> Path:
    factory = getattr(args, "factory_defaults", False)
    if args.prompt_library is not None:
        return args.prompt_library
    if task == "avatar":
        return default_avatar_prompt_library(factory=factory)
    if task == "scene":
        return default_scene_prompt_library(factory=factory)
    if task == "messy-fy":
        return default_messy_fy_prompt_library(factory=factory)
    raise ValueError(f"Unknown task for prompt library resolution: {task}")


def _resolve_postprocess_paths(args: argparse.Namespace, *, output_suffix: str) -> tuple[Path, Path]:
    provided_sources = [source for source in (args.source, args.input_dir, args.input_file) if source is not None]
    if len(provided_sources) != 1:
        raise SystemExit("Provide exactly one of SOURCE, --input-dir, or --input-file.")

    source = provided_sources[0]
    output_dir = args.output_dir
    if output_dir is None:
        if source.is_file():
            output_dir = source.parent / f"{source.stem}-{output_suffix}"
        else:
            output_dir = source.with_name(f"{source.name}-{output_suffix}")
    return source, output_dir


def _sharpen_settings_from_args(args: argparse.Namespace) -> SharpenSettings:
    return SharpenSettings(
        radius=args.sharpen_radius,
        percent=args.sharpen_percent,
        threshold=args.sharpen_threshold,
    )


def _run_avatar(args: argparse.Namespace) -> int:
    if args.test_preset and not args.test_mode:
        raise SystemExit("--test-preset requires --test")
    if args.retry_count < 0:
        raise SystemExit("--retry-count must be zero or greater")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be one or greater")

    config = GenerationConfig(
        source_image=args.source_image,
        output_dir=args.output_dir,
        prompt_library=_prompt_library_for_command(args, "avatar"),
        model=resolve_model(args.model, GenerationTask.AVATAR, factory_defaults=args.factory_defaults),
        api_key=args.api_key,
        presets=args.presets,
        test_mode=args.test_mode,
        test_preset=args.test_preset,
        dry_run=args.dry_run,
        regenerate=args.regenerate,
        continue_on_error=not args.stop_on_error,
        retry_count=args.retry_count,
        concurrency=args.concurrency,
    )
    library = load_prompt_library(config.prompt_library)
    plan = create_generation_plan(config, library)

    if config.dry_run:
        print(
            json.dumps(
                {
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
                },
                indent=2,
            )
        )
        return 0

    api_key = config.resolved_api_key()
    if not api_key:
        raise SystemExit("Missing OpenRouter API credential. Set OPENROUTER_API_KEY or pass --api-key.")

    client = OpenRouterClient(api_key=api_key)
    summary = run_generation(config, library, client, progress=lambda message: print(message, file=sys.stderr))
    print(json.dumps(summary.__dict__, indent=2))
    return 1 if summary.failed else 0


def _run_scene(args: argparse.Namespace) -> int:
    if args.retry_count < 0:
        raise SystemExit("--retry-count must be zero or greater")

    config = SceneGenerationConfig(
        source_image=args.source_image,
        setting=args.setting,
        action=args.action,
        output_dir=args.output_dir,
        prompt_library=_prompt_library_for_command(args, "scene"),
        model=resolve_model(args.model, GenerationTask.SCENE, factory_defaults=args.factory_defaults),
        api_key=args.api_key,
        filename=args.filename,
        regenerate=args.regenerate,
        retry_count=args.retry_count,
    )
    library = load_scene_prompt_library(config.prompt_library)
    plan = create_scene_plan(config, library)

    if args.dry_run:
        print(json.dumps(scene_plan_to_dict(plan), indent=2))
        return 0

    api_key = config.api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Missing OpenRouter API credential. Set OPENROUTER_API_KEY or pass --api-key.")

    client = OpenRouterClient(api_key=api_key)
    summary = run_scene_generation(config, library, client, progress=lambda message: print(message, file=sys.stderr))
    print(json.dumps(summary.__dict__, indent=2))
    return 1 if summary.failed else 0


def _run_messy_fy(args: argparse.Namespace) -> int:
    if args.retry_count < 0:
        raise SystemExit("--retry-count must be zero or greater")

    config = MessyFyGenerationConfig(
        source_image=args.source_image,
        output_dir=args.output_dir,
        prompt_library=_prompt_library_for_command(args, "messy-fy"),
        model=resolve_model(args.model, GenerationTask.MESSY_FY, factory_defaults=args.factory_defaults),
        api_key=args.api_key,
        hint=args.hint,
        filename=args.filename,
        regenerate=args.regenerate,
        retry_count=args.retry_count,
        remove_background=args.remove_background,
    )
    library = load_messy_fy_prompt_library(config.prompt_library)
    plan = create_messy_fy_plan(config, library)

    if args.dry_run:
        print(json.dumps(messy_fy_plan_to_dict(plan), indent=2))
        return 0

    api_key = config.api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Missing OpenRouter API credential. Set OPENROUTER_API_KEY or pass --api-key.")

    client = OpenRouterClient(api_key=api_key)
    summary = run_messy_fy_generation(
        config,
        library,
        client,
        progress=lambda message: print(message, file=sys.stderr),
    )
    print(json.dumps(summary.__dict__, indent=2))
    return 1 if summary.failed else 0


def _run_remove_background(args: argparse.Namespace) -> int:
    if args.tolerance < 0:
        raise SystemExit("--tolerance must be zero or greater")
    if args.white_threshold < 0 or args.white_threshold > 255:
        raise SystemExit("--white-threshold must be between 0 and 255")
    if args.sharpen_radius <= 0:
        raise SystemExit("--sharpen-radius must be greater than zero")
    if args.sharpen_percent <= 0:
        raise SystemExit("--sharpen-percent must be greater than zero")
    if args.sharpen_threshold < 0:
        raise SystemExit("--sharpen-threshold must be zero or greater")

    source, output_dir = _resolve_postprocess_paths(args, output_suffix="transparent")
    summary = remove_backgrounds(
        source,
        output_dir,
        method=args.method,
        model=args.model,
        tolerance=args.tolerance,
        white_threshold=args.white_threshold,
        alpha_matting=args.alpha_matting,
        pre_sharpen=not args.no_pre_sharpen,
        sharpen=_sharpen_settings_from_args(args),
        overwrite=args.overwrite,
    )
    print(json.dumps(summary.__dict__, indent=2))
    return 1 if summary.failed else 0


def _run_sharpen(args: argparse.Namespace) -> int:
    if args.sharpen_radius <= 0:
        raise SystemExit("--sharpen-radius must be greater than zero")
    if args.sharpen_percent <= 0:
        raise SystemExit("--sharpen-percent must be greater than zero")
    if args.sharpen_threshold < 0:
        raise SystemExit("--sharpen-threshold must be zero or greater")

    source, output_dir = _resolve_postprocess_paths(args, output_suffix="sharpened")
    summary = sharpen_images(
        source,
        output_dir,
        settings=_sharpen_settings_from_args(args),
        overwrite=args.overwrite,
    )
    print(json.dumps(summary.__dict__, indent=2))
    return 1 if summary.failed else 0


def _run_web(args: argparse.Namespace) -> int:
    if args.port < 1 or args.port > 65535:
        raise SystemExit("--port must be between 1 and 65535")
    ensure_user_config()
    start_web_server(host=args.host, port=args.port)
    return 0


def _run_config(args: argparse.Namespace) -> int:
    if args.config_action == "path":
        print(user_config_dir().resolve())
        return 0
    if args.config_action == "init":
        written = seed_user_config(overwrite=False)
    else:
        written = reset_user_config()
    payload = {
        "config_dir": str(user_config_dir().resolve()),
        "action": args.config_action,
        "written_files": [str(path.resolve()) for path in written],
    }
    print(json.dumps(payload, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    args = build_root_parser().parse_args(argv)
    if args.command == "config":
        return _run_config(args)

    if args.command in {"avatar", "scene", "messy-fy"} and not args.factory_defaults:
        ensure_user_config()

    handlers = {
        "avatar": _run_avatar,
        "scene": _run_scene,
        "messy-fy": _run_messy_fy,
        "remove-background": _run_remove_background,
        "sharpen": _run_sharpen,
        "web": _run_web,
    }
    handler = handlers[args.command]
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

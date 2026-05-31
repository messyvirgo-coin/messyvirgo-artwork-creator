from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .background import remove_backgrounds
from .sharpen import (
    DEFAULT_SHARPEN_PERCENT,
    DEFAULT_SHARPEN_RADIUS,
    DEFAULT_SHARPEN_THRESHOLD,
    SharpenSettings,
    sharpen_images,
)
from .config import GenerationConfig, default_model, default_output_dir, default_prompt_library, load_env_file
from .executor import run_generation
from .openrouter import OpenRouterClient
from .planner import create_generation_plan
from .prompts import load_prompt_library
from .scene_executor import (
    DEFAULT_SCENE_OUTPUT_DIR,
    DEFAULT_SCENE_PROMPT_LIBRARY,
    SceneGenerationConfig,
    create_scene_plan,
    run_scene_generation,
    scene_plan_to_dict,
)
from .scene_prompts import load_scene_prompt_library
from .web import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT, start_web_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate anime avatar reference images with OpenRouter.")
    parser.add_argument("source_image", type=Path, help="Transparent PNG avatar source image.")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    parser.add_argument("--prompt-library", type=Path, default=default_prompt_library())
    parser.add_argument("--model", default=default_model())
    parser.add_argument("--api-key", default=None, help="OpenRouter API key. Defaults to OPENROUTER_API_KEY.")
    parser.add_argument("--preset", action="append", dest="presets", help="Angle and shot as angle:shot. Repeatable.")
    parser.add_argument("--test", action="store_true", dest="test_mode", help="Generate exactly one image.")
    parser.add_argument("--test-preset", default=None, help="Angle and shot for --test, as angle:shot.")
    parser.add_argument("--dry-run", action="store_true", help="Print the generation plan without calling OpenRouter.")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate successful existing outputs.")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop the batch after the first failed item.")
    parser.add_argument("--retry-count", type=int, default=0, help="Reserved for provider retries.")
    parser.add_argument("--concurrency", type=int, default=1, help="Reserved for future parallel execution.")
    return parser


def build_background_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert generated images to transparent-background PNGs.")
    parser.add_argument("source", nargs="?", type=Path, help="PNG/JPG file or directory containing image files.")
    parser.add_argument("--input-dir", type=Path, help="Directory containing generated PNG/JPG files.")
    parser.add_argument("--input-file", type=Path, help="Single generated PNG/JPG file.")
    parser.add_argument("--output-dir", type=Path, help="Directory for transparent PNG outputs. Defaults to <input>-transparent.")
    parser.add_argument(
        "--method",
        choices=("rembg", "flood"),
        default="rembg",
        help="rembg uses AI segmentation (best for hair); flood uses corner color flood-fill (fast, rough).",
    )
    parser.add_argument(
        "--model",
        default="isnet-anime",
        help="rembg model name (default: isnet-anime for anime characters).",
    )
    parser.add_argument("--tolerance", type=int, default=28, help="Color tolerance for --method flood only.")
    parser.add_argument(
        "--white-threshold",
        type=int,
        default=242,
        help="After rembg, zero alpha on near-white neutral pixels at or above this value (0 disables).",
    )
    parser.add_argument(
        "--alpha-matting",
        action="store_true",
        help="Enable rembg alpha matting (slower; may print pymatting warnings).",
    )
    parser.add_argument(
        "--no-pre-sharpen",
        action="store_true",
        help="Skip unsharp-mask sharpening before background removal (on by default).",
    )
    parser.add_argument(
        "--sharpen-radius",
        type=float,
        default=DEFAULT_SHARPEN_RADIUS,
        help="Unsharp mask radius for --pre-sharpen (default: 2).",
    )
    parser.add_argument(
        "--sharpen-percent",
        type=int,
        default=DEFAULT_SHARPEN_PERCENT,
        help="Unsharp mask strength percent for --pre-sharpen (default: 130).",
    )
    parser.add_argument(
        "--sharpen-threshold",
        type=int,
        default=DEFAULT_SHARPEN_THRESHOLD,
        help="Unsharp mask threshold for --pre-sharpen (default: 3).",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PNG outputs.")
    return parser


def build_sharpen_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sharpen generated images before background removal.")
    parser.add_argument("source", nargs="?", type=Path, help="PNG/JPG file or directory containing image files.")
    parser.add_argument("--input-dir", type=Path, help="Directory containing generated PNG/JPG files.")
    parser.add_argument("--input-file", type=Path, help="Single generated PNG/JPG file.")
    parser.add_argument("--output-dir", type=Path, help="Directory for sharpened PNG outputs. Defaults to <input>-sharpened.")
    parser.add_argument("--sharpen-radius", type=float, default=DEFAULT_SHARPEN_RADIUS)
    parser.add_argument("--sharpen-percent", type=int, default=DEFAULT_SHARPEN_PERCENT)
    parser.add_argument("--sharpen-threshold", type=int, default=DEFAULT_SHARPEN_THRESHOLD)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PNG outputs.")
    return parser


def build_scene_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate one compliant Messy scene image with OpenRouter.")
    parser.add_argument("source_image", type=Path, help="Transparent PNG avatar source image.")
    parser.add_argument("--setting", required=True, help="Where Messy is.")
    parser.add_argument("--action", required=True, help="What Messy is doing.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_SCENE_OUTPUT_DIR)
    parser.add_argument("--prompt-library", type=Path, default=DEFAULT_SCENE_PROMPT_LIBRARY)
    parser.add_argument("--model", default=default_model())
    parser.add_argument("--api-key", default=None, help="OpenRouter API key. Defaults to OPENROUTER_API_KEY.")
    parser.add_argument("--filename", default=None, help="Output filename stem. Defaults to a slug from setting and action.")
    parser.add_argument("--dry-run", action="store_true", help="Print the scene plan without calling OpenRouter.")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate successful existing output.")
    parser.add_argument("--retry-count", type=int, default=0, help="Retry failed provider requests this many times.")
    return parser


def build_web_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the local Messy generator web interface.")
    parser.add_argument("--host", default=DEFAULT_WEB_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_WEB_PORT)
    return parser


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


def _resolve_background_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    return _resolve_postprocess_paths(args, output_suffix="transparent")


def _resolve_sharpen_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    return _resolve_postprocess_paths(args, output_suffix="sharpened")


def _sharpen_settings_from_args(args: argparse.Namespace) -> SharpenSettings:
    return SharpenSettings(
        radius=args.sharpen_radius,
        percent=args.sharpen_percent,
        threshold=args.sharpen_threshold,
    )


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == "scene":
        args = build_scene_parser().parse_args(raw_args[1:])
        if args.retry_count < 0:
            raise SystemExit("--retry-count must be zero or greater")

        config = SceneGenerationConfig(
            source_image=args.source_image,
            setting=args.setting,
            action=args.action,
            output_dir=args.output_dir,
            prompt_library=args.prompt_library,
            model=args.model,
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

    if raw_args and raw_args[0] == "web":
        args = build_web_parser().parse_args(raw_args[1:])
        if args.port < 1 or args.port > 65535:
            raise SystemExit("--port must be between 1 and 65535")
        start_web_server(host=args.host, port=args.port)
        return 0

    if raw_args and raw_args[0] == "remove-background":
        args = build_background_parser().parse_args(raw_args[1:])
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
        source, output_dir = _resolve_background_paths(args)
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

    if raw_args and raw_args[0] == "sharpen":
        args = build_sharpen_parser().parse_args(raw_args[1:])
        if args.sharpen_radius <= 0:
            raise SystemExit("--sharpen-radius must be greater than zero")
        if args.sharpen_percent <= 0:
            raise SystemExit("--sharpen-percent must be greater than zero")
        if args.sharpen_threshold < 0:
            raise SystemExit("--sharpen-threshold must be zero or greater")
        source, output_dir = _resolve_sharpen_paths(args)
        summary = sharpen_images(
            source,
            output_dir,
            settings=_sharpen_settings_from_args(args),
            overwrite=args.overwrite,
        )
        print(json.dumps(summary.__dict__, indent=2))
        return 1 if summary.failed else 0

    args = build_parser().parse_args(raw_args)
    if args.test_preset and not args.test_mode:
        raise SystemExit("--test-preset requires --test")
    if args.retry_count < 0:
        raise SystemExit("--retry-count must be zero or greater")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be one or greater")

    config = GenerationConfig(
        source_image=args.source_image,
        output_dir=args.output_dir,
        prompt_library=args.prompt_library,
        model=args.model,
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


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .background import remove_backgrounds
from .config import GenerationConfig, default_model, default_output_dir, default_prompt_library, load_env_file
from .executor import run_generation
from .openrouter import OpenRouterClient
from .planner import create_generation_plan
from .prompts import load_prompt_library


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
    parser = argparse.ArgumentParser(description="Convert generated JPGs to transparent-background PNGs.")
    parser.add_argument("source", nargs="?", type=Path, help="JPG/JPEG file or directory containing JPG/JPEG files.")
    parser.add_argument("--input-dir", type=Path, help="Directory containing generated JPG/JPEG files.")
    parser.add_argument("--input-file", type=Path, help="Single generated JPG/JPEG file.")
    parser.add_argument("--output-dir", type=Path, help="Directory for transparent PNG outputs. Defaults to <input>-transparent.")
    parser.add_argument("--tolerance", type=int, default=28, help="Background color tolerance for edge-connected removal.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PNG outputs.")
    return parser


def _resolve_background_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    provided_sources = [source for source in (args.source, args.input_dir, args.input_file) if source is not None]
    if len(provided_sources) != 1:
        raise SystemExit("Provide exactly one of SOURCE, --input-dir, or --input-file.")

    source = provided_sources[0]
    output_dir = args.output_dir
    if output_dir is None:
        if source.is_file():
            output_dir = source.parent / f"{source.stem}-transparent"
        else:
            output_dir = source.with_name(f"{source.name}-transparent")
    return source, output_dir


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == "remove-background":
        args = build_background_parser().parse_args(raw_args[1:])
        if args.tolerance < 0:
            raise SystemExit("--tolerance must be zero or greater")
        source, output_dir = _resolve_background_paths(args)
        summary = remove_backgrounds(source, output_dir, tolerance=args.tolerance, overwrite=args.overwrite)
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

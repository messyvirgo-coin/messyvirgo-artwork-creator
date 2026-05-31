# messyvirgo-avatar-creator

Generate a consistent multi-angle anime avatar reference set from one transparent PNG, using [OpenRouter](https://openrouter.ai/) image models (default: **Seedream 4.5**). Post-process with optional sharpening and AI background removal for transparent PNGs suitable for LoRA training or downstream image workflows.

## What it does

1. **Generate** — Sends your source avatar plus composed prompts (angle + shot) to OpenRouter and saves PNGs with JSON metadata.
2. **Sharpen** (optional) — Mild unsharp mask before matting (on by default in `remove-background`).
3. **Remove background** — `rembg` with the `isnet-anime` model, plus cleanup of leftover near-white pixels.

```text
input/avatar.png  →  [OpenRouter / Seedream]  →  output/.../*.png + *.json
                                                      ↓
                                            sharpen → rembg → transparent PNGs
```

The default batch is **21 images**: 8 angles × portrait / half-body / full-body (back views omit portrait). See [docs/avatar-reference-runbook.md](docs/avatar-reference-runbook.md) for the full matrix and operational detail.

## Requirements

- Python **3.11+**
- [OpenRouter API key](https://openrouter.ai/) with access to image generation
- A **transparent PNG** source avatar (RGBA)
- For background removal: `rembg` with CPU support (see [Setup](#setup))

## Setup

```bash
git clone https://github.com/messyvirgo-coin/messyvirgo-avatar-creator.git
cd messyvirgo-avatar-creator

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Core + AI background removal (onnxruntime via rembg[cpu])
pip install -e ".[rembg]"
```

Copy and edit environment variables:

```bash
cp .env.example .env
```

| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | API key (required for generation) |
| `AVATAR_REFERENCE_MODEL` | OpenRouter model id (default: `bytedance-seed/seedream-4.5`) |
| `AVATAR_REFERENCE_PROMPTS` | Path to prompt YAML (default: `config/avatar_prompts.yaml`) |
| `AVATAR_REFERENCE_OUTPUT` | Default output directory for generation |

Shell exports override `.env` values. The CLI loads `.env` from the current working directory.

Place your source avatar at e.g. `input/messy.png` (must be PNG with alpha).

## Quick start

**Preview the plan (no API calls):**

```bash
python3 -m avatar_reference_generator input/messy.png --dry-run
```

**One test image:**

```bash
python3 -m avatar_reference_generator input/messy.png \
  --test \
  --output-dir output/test-run
```

**Full reference set:**

```bash
python3 -m avatar_reference_generator input/messy.png \
  --output-dir output/my-reference-set
```

**Transparent backgrounds (recommended pipeline):**

```bash
python3 -m avatar_reference_generator remove-background \
  --input-dir output/my-reference-set \
  --output-dir output/my-reference-set-transparent \
  --white-threshold 235 \
  --overwrite
```

This runs **sharpen → rembg (`isnet-anime`) → near-white cleanup** on each file. First `rembg` run downloads the ONNX model (~tens of MB).

## CLI overview

### Generation

```bash
python3 -m avatar_reference_generator <source.png> [options]
```

| Option | Description |
|--------|-------------|
| `--output-dir` | Where to write PNGs and metadata |
| `--model` | OpenRouter model id |
| `--prompt-library` | YAML prompt file |
| `--preset angle:shot` | Repeatable; limit to specific views |
| `--test` | Generate exactly one image |
| `--test-preset angle:shot` | Preset for test mode (default: `front:portrait`) |
| `--dry-run` | Print plan JSON only |
| `--regenerate` | Replace existing successful outputs |
| `--stop-on-error` | Stop batch on first failure |
| `--api-key` | Override `OPENROUTER_API_KEY` |

Preset format: `angle_id:shot_id` (e.g. `front_45_left:half_body`). Angle and shot ids are defined in `config/avatar_prompts.yaml` and `avatar_reference_generator/presets.py`.

### Post-processing: `remove-background`

```bash
python3 -m avatar_reference_generator remove-background \
  --input-dir <dir>   # or --input-file <file>
  [--output-dir <dir>]
  [--method rembg|flood]   # default: rembg
  [--model isnet-anime]    # rembg model
  [--white-threshold 242]  # lower = more aggressive white cleanup
  [--no-pre-sharpen]       # sharpen is on by default
  [--sharpen-radius 2] [--sharpen-percent 130] [--sharpen-threshold 3]
  [--alpha-matting]        # optional; slower, noisy logs
  [--overwrite]
```

Default output directory: `<input-dir>-transparent` (sibling name).

### Post-processing: `sharpen`

Standalone sharpen step (optional if you use `remove-background` without `--no-pre-sharpen`):

```bash
python3 -m avatar_reference_generator sharpen --input-dir <dir> [--output-dir <dir>]
```

Default output: `<input-dir>-sharpened`.

## Project layout

```text
messyvirgo-avatar-creator/
├── avatar_reference_generator/   # CLI and library
│   ├── cli.py
│   ├── openrouter.py             # OpenRouter chat/completions + image modality
│   ├── prompts.py                # YAML prompt composition
│   ├── planner.py / presets.py   # 21-image default matrix
│   ├── executor.py               # Batch run, resume, metadata
│   ├── sharpen.py
│   └── background.py             # rembg + flood-fill + white cleanup
├── config/
│   └── avatar_prompts.yaml       # Base, negative, angle, shot prompts
├── docs/
│   └── avatar-reference-runbook.md
├── input/                        # Your source avatars (not tracked)
├── output/                       # Generated assets (gitignored)
├── tests/
├── .env.example
└── pyproject.toml
```

## Prompts

Edit `config/avatar_prompts.yaml` to tune:

- `base_prompt` / `negative_prompt` / `composition`
- `angles.*` — camera yaw (front, 45°, profile, back, …)
- `shots.*` — framing (portrait, half-body, full-body)

Each planned image uses: base + angle + shot + composition. Composed text is stored in per-image JSON metadata.

**Note:** Seedream does not return true transparent PNGs from the API; prompts request a plain white background so matting works reliably. Native transparency is not available on this model path.

## Resume and single-image regeneration

Successful outputs are **skipped** when metadata matches the current source hash, model, and composed prompt. Delete both `name.png` and `name.json`, or pass `--regenerate`, to redo specific images:

```bash
python3 -m avatar_reference_generator input/messy.png \
  --output-dir output/my-reference-set \
  --preset right_side:full_body \
  --regenerate
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

No network calls in unit tests; OpenRouter and rembg are not invoked in the default suite.

## Documentation

- **[Avatar reference runbook](docs/avatar-reference-runbook.md)** — Step-by-step operations, troubleshooting, and recommended pipelines.

## License

Add your license here if the repository is published publicly.

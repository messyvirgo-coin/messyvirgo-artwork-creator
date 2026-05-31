# Avatar Reference Generation Runbook

Operational guide for `messyvirgo-avatar-creator`. For a short overview and setup, see [README.md](../README.md).

## Prerequisites

- Python 3.11 or newer.
- Virtual environment recommended (see README).
- OpenRouter API key with access to image generation models.
- Transparent PNG source avatar (RGBA).

Install the package with background-removal support:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[rembg]"
```

The `rembg` extra pulls in `rembg[cpu]` (ONNX runtime). For NVIDIA GPU matting: `pip install "rembg[gpu]"` instead.

## Configure

```bash
cp .env.example .env
```

Edit `.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
AVATAR_REFERENCE_MODEL=bytedance-seed/seedream-4.5
AVATAR_REFERENCE_PROMPTS=config/avatar_prompts.yaml
AVATAR_REFERENCE_OUTPUT=output/avatar-reference-set
```

The CLI loads `.env` from the current working directory. Values already exported in your shell take precedence.

Default prompt library: `config/avatar_prompts.yaml` — edit base, negative, composition, angle, and shot sections to tune generation.

## End-to-end workflow (recommended)

```text
1. Dry-run          → validate PNG + prompts + plan
2. Test one image   → verify API, model, output quality
3. Full batch       → 21 reference images on white
4. remove-background → sharpen → rembg → transparent PNGs
5. Spot-fix         → delete PNG+JSON for bad presets, rerun subset
```

### 1. Preview the plan

No OpenRouter calls:

```bash
python3 -m avatar_reference_generator input/messy.png --dry-run
```

### 2. Single-image smoke test

```bash
python3 -m avatar_reference_generator input/messy.png \
  --test \
  --output-dir output/test-avatar-reference
```

Specific preset:

```bash
python3 -m avatar_reference_generator input/messy.png \
  --test \
  --test-preset right_side:full_body \
  --output-dir output/test-avatar-reference
```

Progress on stderr, JSON summary on stdout:

```text
[1/1] generate front:portrait
[1/1] succeeded output/test-avatar-reference/front__portrait.png
```

### 3. Full reference set

```bash
python3 -m avatar_reference_generator input/messy.png \
  --output-dir output/2026-05-31-seedream
```

**Default matrix (21 images):**

| Angle | Portrait | Half-body | Full-body |
|-------|----------|-----------|-----------|
| front | ✓ | ✓ | ✓ |
| front_45_left | ✓ | ✓ | ✓ |
| front_45_right | ✓ | ✓ | ✓ |
| left_side | ✓ | ✓ | ✓ |
| right_side | ✓ | ✓ | ✓ |
| back_45_left | — | ✓ | ✓ |
| back_45_right | — | ✓ | ✓ |
| back | — | ✓ | ✓ |

Each image: `output/<dir>/<angle>__<shot>.png` plus matching `.json` metadata (prompt, model, source hash, status, timestamps).

OpenRouter may return PNG, JPEG, or WebP; the tool normalizes to PNG and records `provider_mime_type` in metadata.

### 4. Transparent PNGs (post-process)

**Recommended command** (sharpen on by default, rembg, white cleanup):

```bash
python3 -m avatar_reference_generator remove-background \
  --input-dir output/2026-05-31-seedream \
  --output-dir output/2026-05-31-seedream-transparent \
  --white-threshold 235 \
  --overwrite
```

Pipeline per file:

1. **Unsharp mask** — radius 2, 130%, threshold 3 (LoRA-prep style, mild).
2. **rembg** — model `isnet-anime` (anime segmentation).
3. **Near-white strip** — removes leftover white in hair gaps and between legs.

Tune white cleanup: **lower** `--white-threshold` removes more (try `235`–`238`); **higher** is gentler (`248`). `0` disables the strip.

Other useful flags:

| Flag | When to use |
|------|-------------|
| `--no-pre-sharpen` | Skip sharpening if edges look too harsh |
| `--sharpen-percent 110` | Softer sharpen |
| `--method flood` | Fast corner flood-fill only (poor on hair); no rembg needed |
| `--alpha-matting` | Softer hair edges; slow, pymatting warnings |
| `--overwrite` | Replace existing transparent outputs |

Default output if `--output-dir` omitted: sibling folder `<input-dir>-transparent`.

**One file:**

```bash
python3 -m avatar_reference_generator remove-background \
  --input-file output/2026-05-31-seedream/back__full_body.png \
  --output-dir output/2026-05-31-seedream-transparent \
  --overwrite
```

### 5. Optional two-step sharpen

Preview sharpened intermediates:

```bash
python3 -m avatar_reference_generator sharpen \
  --input-dir output/2026-05-31-seedream \
  --output-dir output/2026-05-31-seedream-sharpened

python3 -m avatar_reference_generator remove-background \
  --input-dir output/2026-05-31-seedream-sharpened \
  --output-dir output/2026-05-31-seedream-transparent \
  --no-pre-sharpen \
  --white-threshold 235 \
  --overwrite
```

## Custom generation subset

```bash
python3 -m avatar_reference_generator input/messy.png \
  --output-dir output/subset \
  --preset front:portrait \
  --preset front_45_left:half_body \
  --preset back:full_body
```

## Resume and regenerate

**Resume:** Re-run the same command. Successful items with matching metadata are skipped; failed or missing items are retried.

**Force replace all:**

```bash
python3 -m avatar_reference_generator input/messy.png \
  --output-dir output/2026-05-31-seedream \
  --regenerate
```

**Replace one image:** Delete both `angle__shot.png` and `angle__shot.json`, then:

```bash
python3 -m avatar_reference_generator input/messy.png \
  --output-dir output/2026-05-31-seedream \
  --preset right_side:full_body
```

Or use `--test` / `--preset` with `--regenerate` as needed.

Skip logic requires metadata `status: succeeded`, matching `source_sha256`, `model`, and composed `prompt` / `negative_prompt`.

## Prompt tuning notes

- **Portrait vs half-body** — Shot prompts in YAML define crop lines (collarbone vs hip). Regenerate individual presets after edits.
- **Single character** — Base and negative prompts discourage duplicates and turnaround sheets; re-roll problem angles if needed.
- **White background** — Intentional for matting. Seedream does not emit real alpha from the API.
- **Green screen** — Possible experiment for chroma keying, but not the default; green spill on hair/edges is a risk.

## Transparency from the model?

**No** for `bytedance-seed/seedream-4.5` via OpenRouter: output is opaque PNG/JPEG with a painted background. Post-processing (`remove-background`) is the supported path. Some other OpenRouter models (e.g. OpenAI GPT Image family) support `background: transparent` on different APIs; this project is optimized for Seedream + reference fidelity.

## Verify locally

```bash
python3 -m unittest discover -s tests -v
```

Optional (if OpenSpec is installed in your environment):

```bash
openspec validate add-avatar-reference-set-generation
```

## Common errors

| Message | Fix |
|---------|-----|
| `Missing OpenRouter API credential` | Set `OPENROUTER_API_KEY` or `--api-key` |
| `Source avatar must be a transparent PNG file` | Use a `.png` file |
| `Source PNG must include an alpha channel` | Export RGBA from your art tool |
| `Missing angle/shot prompt fragment` | Add key to `config/avatar_prompts.yaml` |
| `No onnxruntime backend found` | `pip install "rembg[cpu]"` or `pip install -e ".[rembg]"` |
| `Getting requirements to build editable` / multiple packages | Use current `pyproject.toml` (`packages.find` includes only `avatar_reference_generator`) |
| Item skipped but you changed prompts | Delete PNG+JSON or use `--regenerate` |
| White halos after matting | Lower `--white-threshold`; avoid `--alpha-matting` unless needed; try softer `--sharpen-percent` |
| Duplicate characters on some angles | Re-roll preset; avoid over-long angle prompt experiments |

## Output directories (example)

```text
output/
├── 2026-05-31-seedream/              # Raw generation (white bg)
├── 2026-05-31-seedream-transparent/  # Final transparent PNGs
└── test-avatar-reference/             # Smoke tests
```

`output/` is gitignored; back up reference sets you want to keep.

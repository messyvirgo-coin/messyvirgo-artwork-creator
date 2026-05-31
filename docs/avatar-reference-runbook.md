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

Scene prompt library: `config/messy_scene_prompts.yaml` — lean prompt tuned for `bytedance-seed/seedream-4.5` (default). Other image models (e.g. Gemini) often drift identity; set `AVATAR_REFERENCE_MODEL=bytedance-seed/seedream-4.5` or omit `--model`. Keep `--setting` / `--action` to place and pose only.

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

## Full scene image generation

Use `scene` when you already have a transparent Messy avatar reference and want one complete brand image. Provide only where Messy is and what she is doing; the command composes the full compliant prompt from `config/messy_scene_prompts.yaml`.

**Preview prompt and output paths without an API call:**

```bash
python3 -m avatar_reference_generator scene input/messy.png \
  --setting "a glass-walled high-rise office overlooking Zurich at sunset" \
  --action "reviewing a risk dashboard on a slim tablet" \
  --output-dir output/messy-scenes \
  --dry-run
```

**Generate one scene:**

```bash
python3 -m avatar_reference_generator scene input/messy.png \
  --setting "a neon city avenue after rain" \
  --action "walking past a trading billboard with calm confidence" \
  --output-dir output/messy-scenes \
  --filename neon-city-walk
```

Each scene writes `<filename>.png` plus `<filename>.json` metadata containing the source hash, setting, action, full prompt, negative prompt, model, status, provider response id, and an `openrouter_request` summary that confirms the reference PNG was attached (byte size and MIME type, without embedding base64). If `--filename` is omitted, the tool derives a slug from the setting and action.

**Verify the reference image is sent:** run with `--dry-run` and check `openrouter_request.reference_image_attached` is `true` and `message_content_types` is `["image_url", "text"]`. On generation, stderr prints `reference image attached: N bytes`.

**Resume behavior:** Re-running the same scene command skips a successful output when metadata still matches source hash, model, setting, action, prompt, and negative prompt. Pass `--regenerate` to force replacement.

**Prompting notes:**

- Keep `--setting` concrete: "high-rise office at sunset", "rainy neon city avenue", "futuristic trading floor".
- Keep `--action` to pose and handheld props: "reviewing a tablet", "waving a red-white fan scarf", "relaxing calmly".
- Do not describe a new outfit in `--action` unless you accept identity drift; the reference PNG defines Messy's blazer look.
- For financial charts, say they appear on a **screen or sign** in the setting—not on clothing or towels. Use words like "OHLC chart on a wall display", not "candle decorations" (models often draw wax candles).
- After editing `config/messy_scene_prompts.yaml`, pass `--regenerate` so resume does not reuse an old prompt hash.
- Do not include the full brand rules in user text; those live in `config/messy_scene_prompts.yaml`.
- Scene images are complete environment illustrations, so do not run background removal on them unless you intentionally want to destroy the background.

## Local web interface

Start a local browser UI:

```bash
python3 -m avatar_reference_generator web
```

Default URL: `http://127.0.0.1:8765/`.

Override host or port:

```bash
python3 -m avatar_reference_generator web --host 127.0.0.1 --port 8899
```

The web page exposes:

- Scene image dry-run/generation.
- Avatar reference-set dry-run/generation.
- Background removal using the existing post-processing workflow.

The web server is local-only by default and runs synchronously. Long OpenRouter or rembg calls will keep the browser request open until the operation finishes.

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
| `Scene setting must not be empty` / `Scene action must not be empty` | Fill both scene fields |
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
├── messy-scenes/                     # Full scene images
└── test-avatar-reference/             # Smoke tests
```

`output/` is gitignored; back up reference sets you want to keep.

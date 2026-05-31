# Avatar Reference Generation Runbook

## Prerequisites

- Python 3.11 or newer.
- `PyYAML` installed in the active Python environment.
- An OpenRouter API key with access to image generation models.
- A transparent PNG avatar source image.

The default OpenRouter model is `bytedance-seed/seedream-4.5`. You can override it with `--model`.

## Configure

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Then edit `.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
AVATAR_REFERENCE_MODEL=bytedance-seed/seedream-4.5
AVATAR_REFERENCE_PROMPTS=config/avatar_prompts.yaml
AVATAR_REFERENCE_OUTPUT=output/avatar-reference-set
```

The CLI loads `.env` automatically from the current working directory. Values already exported in your shell take precedence over values in `.env`.

You can also export the key directly:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

The default prompt library is:

```bash
config/avatar_prompts.yaml
```

Edit that YAML file to tune the shared base prompt, negative prompt, angle prompts, or shot prompts.

## Preview the Full Plan

This validates the PNG and prompt library, then prints the 21 planned outputs without calling OpenRouter:

```bash
python3 -m avatar_reference_generator input/messy.png --dry-run
```

## Run One-Image Test Mode

Use this before a full batch to validate credentials, model behavior, prompt composition, response parsing, and metadata writing:

```bash
python3 -m avatar_reference_generator input/messy.png --test --output-dir output/test-avatar-reference
```

During generation the CLI prints per-image progress to stderr, for example:

```text
[1/1] generate front:portrait
[1/1] succeeded output/test-avatar-reference/front__portrait.jpg
```

If a provider request fails, the progress line includes the failed angle/shot and error message. The final JSON summary is still printed to stdout.

Choose a specific one-image test preset:

```bash
python3 -m avatar_reference_generator input/messy.png --test --test-preset right_side:full_body
```

## Generate the Full Reference Set

```bash
python3 -m avatar_reference_generator input/messy.png --output-dir output/avatar-reference-set
```

The default set creates 21 images:

- front: portrait, half-body, full-body
- front 45 left: portrait, half-body, full-body
- front 45 right: portrait, half-body, full-body
- left side: portrait, half-body, full-body
- right side: portrait, half-body, full-body
- back 45 left: half-body, full-body
- back 45 right: half-body, full-body
- back: half-body, full-body

Each generated image is saved as PNG and gets a sidecar JSON metadata file in the same output directory. OpenRouter may return PNG, JPEG, or WebP; the generator normalizes provider images to PNG and records the original provider type as `provider_mime_type` in metadata.

## Remove Backgrounds From JPG Outputs

If you have JPG files from an older run or another tool, convert them to transparent PNGs with the background-removal extension:

```bash
python3 -m avatar_reference_generator remove-background \
  --input-dir output/avatar-reference-set
```

By default this writes to a sibling directory named `output/avatar-reference-set-transparent`.

The remover works best with the plain transparent or neutral backgrounds requested by `config/avatar_prompts.yaml`. It removes edge-connected background pixels matching the corner background color, then writes PNG files with alpha transparency. Increase tolerance for noisy JPG backgrounds:

```bash
python3 -m avatar_reference_generator remove-background \
  --input-dir output/avatar-reference-set \
  --tolerance 45 \
  --overwrite
```

To choose the destination explicitly:

```bash
python3 -m avatar_reference_generator remove-background \
  --input-dir output/avatar-reference-set \
  --output-dir output/transparent-pngs
```

For one file:

```bash
python3 -m avatar_reference_generator remove-background \
  --input-file output/avatar-reference-set/front__portrait.jpg
```

## Generate a Custom Subset

```bash
python3 -m avatar_reference_generator input/messy.png \
  --preset front:portrait \
  --preset front_45_left:half_body \
  --preset back:full_body
```

## Resume or Regenerate

By default, successful existing outputs are skipped. Failed or missing items are retried:

```bash
python3 -m avatar_reference_generator input/messy.png --output-dir output/avatar-reference-set
```

Force regeneration of existing successful outputs:

```bash
python3 -m avatar_reference_generator input/messy.png --output-dir output/avatar-reference-set --regenerate
```

## Verify Locally

```bash
python3 -m unittest discover -s tests -v
openspec validate add-avatar-reference-set-generation
```

## Common Errors

- `Missing OpenRouter API credential`: set `OPENROUTER_API_KEY` or pass `--api-key`.
- `Source avatar must be a transparent PNG file`: use a real `.png` file.
- `Source PNG must include an alpha channel`: export the avatar as RGBA/transparent PNG.
- `Missing angle prompt fragment` or `Missing shot prompt fragment`: add the matching key to `config/avatar_prompts.yaml`.
- Existing outputs from an older prompt/model are skipped only if their metadata matches the current source, model, and composed prompt. Use `--regenerate` to force replacement.

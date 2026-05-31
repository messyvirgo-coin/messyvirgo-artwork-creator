## Context

The project currently has an OpenSpec workspace but no existing product specs. This change introduces the first capability: generating a reusable image reference set from a single transparent PNG anime avatar.

The user wants OpenRouter as the image provider, Seedream 4.5 as the default target model, and a configurable model setting. The generated set is intended to become source material for later image creation, so consistency, metadata, and repeatability matter more than one-off image convenience.

## Goals / Non-Goals

**Goals:**

- Accept a transparent PNG avatar as the source input.
- Generate a default reference set of about 20 images across important angles and shot types.
- Use OpenRouter for image generation through a provider abstraction.
- Default to Seedream 4.5 while allowing the model ID to be configured.
- Persist each output image with machine-readable metadata for later reuse.
- Make failed or partial batches inspectable and resumable.
- Keep prompt and preset construction in a reusable YAML prompt library that can be tested without calling OpenRouter.
- Provide a test mode that generates exactly one planned image for quick validation.
- Provide a post-processing command that converts generated JPG/JPEG files into transparent PNGs by removing simple neutral backgrounds.

**Non-Goals:**

- Training or fine-tuning a model.
- Building a full asset management library.
- Guaranteeing perfect 3D identity consistency across all outputs.
- Supporting non-PNG source formats in the first version.
- Adding additional image providers before the OpenRouter path is working.

## Decisions

### Use a Generation Plan Before API Calls

The system will expand a source image and generation configuration into a deterministic generation plan before calling OpenRouter. Each planned item will include angle, shot type, prompt text, output path, and metadata path.

Alternatives considered:

- Generate images directly from nested loops. This is simpler but makes previews, tests, retries, and progress reporting harder.
- Store only final images. This loses the prompt and preset context needed for downstream reproducibility.

Rationale: A plan object gives the implementation a stable boundary between local logic and external image generation.

### Keep Prompts in a YAML Prompt Library

The system will load common prompts from a YAML file rather than hard-coding prompt strings across the generator. The file will contain:

- A shared base prompt focused on preserving the avatar identity, proportions, outfit, colors, hairstyle, facial features, and anime style.
- Shared negative prompt guidance for avoiding identity drift, changed proportions, altered clothing, mini skirts, extra limbs, distorted anatomy, cropped full-body views, background clutter, and watermark/text artifacts.
- Angle prompt fragments keyed by stable angle identifiers.
- Shot prompt fragments keyed by stable shot identifiers.
- Optional composition rules for output background, transparency expectations, and framing.

The final prompt for each image will be composed from the base prompt, the selected angle fragment, and the selected shot fragment. The composed prompt will be saved in metadata.

The default prompt library will describe Messy as an elegant crypto finance funds allocator. Full-body prompts will explicitly preserve elegant long trousers and avoid mini skirt reinterpretations.

Alternatives considered:

- Hard-code all prompts in generation code. This is simple initially but makes prompt tuning risky and opaque.
- Put one full prompt per output image. This avoids composition but duplicates base identity instructions and makes broad prompt changes error-prone.

Rationale: YAML keeps prompt tuning close to configuration while preserving deterministic composition and testability.

An initial prompt library can follow this shape:

```yaml
base_prompt: >
  Use the provided transparent PNG anime avatar as the strict character reference.
  Preserve the same identity, face, hairstyle, hair color, eye color, outfit,
  accessories, body proportions, silhouette, art style, and color palette.
  Recreate the character cleanly for the requested camera view and framing.
negative_prompt: >
  Do not redesign the character. Do not change clothing, colors, age, body
  proportions, hairstyle, facial features, species traits, or art style. Avoid
  extra limbs, distorted hands, cropped full-body shots, text, watermark, logo,
  busy background, and unrelated props.
angles:
  front:
    prompt: "front view, character facing camera"
  front_45_left:
    prompt: "three-quarter front view, character turned 45 degrees to their left"
  front_45_right:
    prompt: "three-quarter front view, character turned 45 degrees to their right"
  left_side:
    prompt: "clean left side profile view"
  right_side:
    prompt: "clean right side profile view"
  back_45_left:
    prompt: "three-quarter rear view, character turned 45 degrees to their left"
  back_45_right:
    prompt: "three-quarter rear view, character turned 45 degrees to their right"
  back:
    prompt: "back view, rear-facing character reference"
shots:
  portrait:
    prompt: "portrait close-up from head to upper shoulders, centered composition"
  half_body:
    prompt: "half-body reference from head to hips, centered composition"
  full_body:
    prompt: "full-body reference from head to feet, entire character visible"
```

### Default Presets Target About 20 Outputs

The default set will use a matrix of core views and body framings, plus a small number of high-value supplemental shots. A practical default is:

- Front: portrait, half-body, full-body
- Front 45 left: portrait, half-body, full-body
- Front 45 right: portrait, half-body, full-body
- Left side: portrait, half-body, full-body
- Right side: portrait, half-body, full-body
- Back 45 left: half-body, full-body
- Back 45 right: half-body, full-body
- Back: half-body, full-body

This yields 21 planned images. The preset list will be configurable so the product can tune the exact count without changing provider code.

Alternatives considered:

- Exactly 20 fixed outputs. This satisfies the approximate count but creates an arbitrary omission in an otherwise useful matrix.
- Exhaustive 360-degree turntable. This produces more coverage than needed and increases cost.

Rationale: A named preset list keeps the first version useful while preserving control over cost and coverage.

### Test Mode Generates One Image

The system will support a test mode that selects exactly one planned image, sends one OpenRouter request, and writes the normal image and metadata outputs. By default, test mode will use a high-signal preset such as front portrait unless the caller selects another angle and shot.

Alternatives considered:

- Use dry-run only. This validates planning but does not prove credentials, model compatibility, or provider response parsing.
- Generate a reduced three-image set. This gives more visual coverage but costs more and is less suitable for quick smoke tests.

Rationale: One-image test mode gives a cheap end-to-end validation path before spending on a full batch.

### Provide JPG Background Removal as a Post-Processing Extension

OpenRouter may return JPEG images even when the prompt requests a transparent or neutral background. The system will provide a separate `remove-background` command that accepts `--input-dir` or `--input-file`, removes edge-connected background pixels matching the corner background color, and saves transparent PNG files. If no output directory is specified, it will create a sibling directory with a `-transparent` suffix.

Alternatives considered:

- Require model-native transparency only. This is unreliable across models and providers.
- Add an AI segmentation dependency. This can produce better masks, but it adds model/runtime complexity that is unnecessary for the requested neutral-background reference outputs.

Rationale: The prompt already asks for plain transparent or neutral backgrounds, so deterministic edge-connected removal is a pragmatic first pass and keeps the post-processing step local.

### Configure Provider, Model, and Batch Settings Separately

Configuration will distinguish provider credentials, model ID, output directory, concurrency, retry count, and preset selection. Seedream 4.5 will be the default model value for OpenRouter, but callers can override it.

Alternatives considered:

- Hard-code Seedream 4.5. This blocks model testing and contradicts the requirement.
- Make every prompt detail configurable in the first version. This adds complexity before the core workflow is proven.

Rationale: Model and operational settings are likely to change; prompt templates can evolve after the first workflow is validated.

### Store Per-Image Metadata Beside Outputs

Each generated image will be normalized to PNG output and will have adjacent metadata containing source filename or hash, provider, model, prompt, angle, shot type, output filename, normalized mime type, provider mime type, status, timestamps, and provider response identifiers when available.

Alternatives considered:

- One batch-level metadata file only. This is compact but weaker for partial retries and individual downstream selection.
- Embed all metadata in PNG chunks. This can be useful later, but sidecar JSON is simpler and easier to test.

Rationale: Sidecar metadata supports reproducibility and makes incomplete batches easy to inspect.

### Treat OpenRouter as an Adapter Boundary

OpenRouter request construction and response parsing will live behind a small adapter interface. Local planning, validation, naming, and metadata logic will not depend on OpenRouter response shapes directly.

Alternatives considered:

- Put API calls inline in the command or service. This is quicker but makes tests brittle and future provider changes harder.

Rationale: The provider boundary keeps most behavior testable without network calls.

## Risks / Trade-offs

- Identity drift across generated views -> Mitigation: include the source PNG in every request, use consistent prompt templates, store prompts, and make failed or weak outputs easy to regenerate.
- Prompt changes can have broad visual impact -> Mitigation: keep prompts in YAML, test prompt composition, store composed prompts in metadata, and support one-image test mode.
- OpenRouter image endpoint details or model naming may change -> Mitigation: keep model ID and request parameters configurable and isolate provider-specific code in one adapter.
- Batch generation cost can grow quickly -> Mitigation: expose preset selection, output count preview, concurrency limits, dry-run planning, and one-image test mode.
- Transparent PNG validation can reject useful inputs that have minor alpha issues -> Mitigation: require PNG format and alpha channel, but do not require every background pixel to be fully transparent in the first version.
- Partial failures can leave mixed output states -> Mitigation: write metadata per planned item and support resuming skipped or failed items.

## Migration Plan

This is a new capability with no existing data migration. Implementation can be introduced behind a new command, route, or service entry point depending on the application structure discovered during apply.

Rollback is removal of the new command/service path, OpenRouter configuration, and generated output directory. Existing OpenSpec data is unaffected.

## Open Questions

- The exact OpenRouter model identifier for Seedream 4.5 should be verified against OpenRouter documentation during implementation.
- The implementation entry point should follow the codebase shape discovered during apply: CLI if this remains a utility project, or API/UI workflow if an application skeleton exists by then.

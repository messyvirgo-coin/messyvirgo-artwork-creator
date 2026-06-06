# avatar-reference-set-generation Specification

## Purpose

Generate a consistent 21-image multi-angle anime avatar reference set from one transparent PNG source avatar via OpenRouter. Default model alias `seedream` (`bytedance-seed/seedream-4.5`) is defined in `mv_artwork_creator/resources/models.yaml`. Optional local post-processing (`remove-background`, `sharpen`) uses `rembg` when installed and is not required for generation.

## Requirements

### Requirement: Source Avatar Validation

The system SHALL accept a transparent PNG avatar as the source image and reject unsupported source files before starting generation.

#### Scenario: Valid transparent PNG

- **WHEN** a user provides a PNG file with an alpha channel
- **THEN** the system accepts the file as a valid source avatar

#### Scenario: Unsupported file type

- **WHEN** a user provides a file that is not a PNG
- **THEN** the system rejects the file and reports that a transparent PNG is required

#### Scenario: PNG without alpha channel

- **WHEN** a user provides a PNG file without an alpha channel
- **THEN** the system rejects the file and reports that transparency is required

### Requirement: Configurable OpenRouter Image Model

The system SHALL generate images through OpenRouter using a configurable image model resolved from `--model`, bundled `models.yaml`, or optional task env overrides.

#### Scenario: Default model from models.yaml

- **WHEN** a user starts avatar generation without `--model` and without `MVAC_AVATAR_MODEL`
- **THEN** the system uses the `avatar` task default from `models.yaml` (alias `seedream` → `bytedance-seed/seedream-4.5`)

#### Scenario: Model override is used

- **WHEN** a user provides `--model` with an alias or full OpenRouter model id
- **THEN** the system uses that model for every image in the batch

#### Scenario: Missing OpenRouter credential

- **WHEN** a user starts generation without an available OpenRouter API credential
- **THEN** the system stops before making generation requests and reports the missing credential

### Requirement: Avatar CLI Subcommand

The system SHALL provide an `avatar` subcommand on the `mvac` CLI for reference-set generation.

#### Scenario: Dry run prints plan

- **WHEN** a user runs `mvac avatar <source.png> --dry-run`
- **THEN** the CLI prints the planned image count and items without calling OpenRouter

#### Scenario: Avatar subcommand requires source image

- **WHEN** a user runs `mvac` without a recognized subcommand
- **THEN** the CLI does not accept a bare positional source image for generation

### Requirement: Reference Set Planning

The system SHALL create a deterministic generation plan that combines source avatar, angle presets, shot presets, model configuration, prompt text, and output locations before calling OpenRouter.

#### Scenario: Default reference set is planned

- **WHEN** a user requests generation with default presets
- **THEN** the system plans 21 reference images covering front, 45-degree, side, rear 45-degree, and back views across portrait, half-body, and full-body shots (back angles exclude portrait)

#### Scenario: Planned count is inspectable

- **WHEN** a user previews or dry-runs generation
- **THEN** the system reports the planned image count and each planned angle and shot combination without calling OpenRouter

#### Scenario: Custom preset list is used

- **WHEN** a user provides a custom preset list via `--preset angle:shot`
- **THEN** the system plans images only for the requested angle and shot combinations

### Requirement: YAML Prompt Library

The system SHALL load avatar generation prompts from `mv_artwork_creator/resources/avatar_prompts.yaml` (or `MVAC_AVATAR_PROMPTS` override) defining base instructions, negative instructions, angle fragments, and shot fragments.

#### Scenario: Prompt library is loaded

- **WHEN** the system creates a generation plan
- **THEN** it loads the configured YAML prompt library before composing planned prompts

#### Scenario: Prompt is composed from shared and specific fragments

- **WHEN** the system creates a planned item for an angle and shot
- **THEN** the planned prompt includes the base prompt, the selected angle prompt fragment, and the selected shot prompt fragment

#### Scenario: Negative prompt is available

- **WHEN** the YAML prompt library defines negative prompt guidance
- **THEN** the system includes that guidance in the provider request or provider-supported negative prompt field

#### Scenario: Missing prompt fragment

- **WHEN** a planned item references an angle or shot without a matching YAML prompt fragment
- **THEN** the system rejects the plan and reports the missing prompt fragment

#### Scenario: Full-body identity and outfit guidance

- **WHEN** the system composes a full-body prompt
- **THEN** the prompt identifies Messy as an elegant crypto finance funds allocator and preserves elegant long trousers rather than a mini skirt

### Requirement: Background Removal Extension

The system SHALL provide a `remove-background` post-processing subcommand that converts generated JPG/JPEG or PNG files into PNG files with alpha transparency using `rembg` segmentation by default (`isnet-anime` model) and an optional fast flood-fill method that does not require `rembg`.

#### Scenario: Directory conversion

- **WHEN** a user runs background removal with an input directory containing image files
- **THEN** the system writes transparent PNG files with matching stems to the configured output directory or to a sibling `-transparent` output directory by default

#### Scenario: Single file conversion

- **WHEN** a user runs background removal with `--input-file`
- **THEN** the system writes one transparent PNG file with the matching stem

#### Scenario: Default rembg matting

- **WHEN** a user runs background removal without specifying `--method`
- **THEN** the system uses `rembg` with the configured model (default `isnet-anime`) after optional pre-sharpening

#### Scenario: Flood-fill method

- **WHEN** a user runs background removal with `--method flood`
- **THEN** the system removes edge-connected background pixels matching the corner color without requiring `rembg`

#### Scenario: Existing transparent output

- **WHEN** a converted PNG already exists
- **THEN** the system skips that file unless overwrite is requested

#### Scenario: Background removal summary

- **WHEN** background removal finishes
- **THEN** the system reports planned, converted, skipped, and failed counts

### Requirement: Optional Sharpening Before Matting

The system SHALL apply a mild unsharp mask before background removal by default and SHALL provide a standalone `sharpen` subcommand for two-step pipelines.

#### Scenario: Pre-sharpen on by default

- **WHEN** a user runs `remove-background` without `--no-pre-sharpen`
- **THEN** the system sharpens each input image before matting

#### Scenario: Standalone sharpen

- **WHEN** a user runs `sharpen` with `--input-dir` or `--input-file`
- **THEN** the system writes sharpened PNG files to the configured output directory or a sibling `-sharpened` directory by default

### Requirement: One Image Test Mode

The system SHALL provide a test mode that generates exactly one image using the normal provider, output, and metadata path.

#### Scenario: Test mode uses default test preset

- **WHEN** a user starts generation in test mode without selecting an angle or shot
- **THEN** the system generates exactly one image using the default test angle and shot preset (`front:portrait`)

#### Scenario: Test mode uses selected preset

- **WHEN** a user starts generation in test mode with a selected angle and shot
- **THEN** the system generates exactly one image for the selected angle and shot

#### Scenario: Test mode writes normal metadata

- **WHEN** test mode completes or fails
- **THEN** the system writes the same metadata fields used for full batch generation

#### Scenario: Test mode limits provider calls

- **WHEN** test mode is enabled
- **THEN** the system sends no more than one image generation request to OpenRouter

### Requirement: OpenRouter Generation Requests

The system SHALL send each planned image request to OpenRouter with the source avatar, selected model, and prompt instructions that preserve character identity while changing only the requested angle and shot framing.

#### Scenario: Request includes source avatar

- **WHEN** the system sends a planned generation request
- **THEN** the request includes the source avatar image as visual reference input

#### Scenario: Request includes angle and shot prompt

- **WHEN** the system sends a planned generation request
- **THEN** the prompt identifies the requested angle and shot framing for that planned image

#### Scenario: Provider request fails

- **WHEN** OpenRouter returns an error for a planned image
- **THEN** the system records the failure for that planned image and continues or stops according to the configured batch failure policy

### Requirement: Generated Output Storage

The system SHALL save generated images and adjacent metadata for each planned item.

#### Scenario: Image generation succeeds

- **WHEN** OpenRouter returns a generated image for a planned item
- **THEN** the system saves the image as PNG to the configured output directory with filename `<angle>__<shot>.png`

#### Scenario: Metadata is written

- **WHEN** the system completes or fails a planned item
- **THEN** the system writes metadata containing source reference, provider, model, prompt, angle, shot type, output path, normalized mime type, provider mime type, status, and timestamp

#### Scenario: Output directory is missing

- **WHEN** the configured output directory does not exist
- **THEN** the system creates it before saving generated images or metadata

### Requirement: Batch Resumption

The system SHALL support resuming an incomplete reference set without regenerating successful images by default.

#### Scenario: Completed item exists

- **WHEN** a planned item already has a successful image and metadata
- **THEN** the system skips that item unless regeneration is explicitly requested

#### Scenario: Failed item exists

- **WHEN** a planned item has failed metadata and no successful image
- **THEN** the system includes that item when resuming the batch

#### Scenario: Regeneration is requested

- **WHEN** a user explicitly requests regeneration via `--regenerate`
- **THEN** the system regenerates matching planned items even if previous successful outputs exist

# messy-fy-image-generation Specification

## Purpose

Repaint an existing PNG, JPEG, or WebP image in Messy Virgo brand visual style while preserving the source content, layout, and text. The source image is sent to OpenRouter as the visual reference. The system does **not** insert Messy the character. Default model alias `nano-banana` (`google/gemini-3.1-flash-image-preview`) is defined in `models.yaml`.

## Requirements

### Requirement: Messy-Fy Source Image Validation

The system SHALL accept PNG, JPEG, or WebP source images and reject unsupported formats before starting generation.

#### Scenario: Supported image format

- **WHEN** a user provides a `.png`, `.jpg`, `.jpeg`, or `.webp` file
- **THEN** the system accepts the file as a valid messy-fy source

#### Scenario: Unsupported file type

- **WHEN** a user provides a file with another extension
- **THEN** the system rejects the file and reports supported formats

#### Scenario: Invalid image bytes

- **WHEN** a user provides a file with a supported extension that is not a valid image
- **THEN** the system rejects the file before calling OpenRouter

### Requirement: Messy-Fy Prompt Composition

The system SHALL compose a messy-fy prompt from `mv_artwork_creator/resources/messy_fy_prompts.yaml` and an optional user `--hint`.

#### Scenario: Brand repaint prompt is used

- **WHEN** the system composes a messy-fy prompt
- **THEN** the prompt instructs a stylistic repaint in Messy brand style, preserves source content, and does not insert Messy the character

#### Scenario: Hint is included when provided

- **WHEN** a user provides `--hint`
- **THEN** the composed prompt includes the hint as bounded preservation guidance

### Requirement: Reference-Based Messy-Fy Generation

The system SHALL generate one repainted image through OpenRouter using the source image as visual reference.

#### Scenario: Source image is sent as reference

- **WHEN** messy-fy generation starts
- **THEN** the OpenRouter request includes the source image bytes as a base64 `image_url` content part before the text prompt

#### Scenario: Reference attachment is verifiable

- **WHEN** a user runs messy-fy generation or `--dry-run`
- **THEN** output includes an `openrouter_request` summary with `reference_image_attached`, byte size, and MIME type

#### Scenario: Default model from models.yaml

- **WHEN** a user starts messy-fy without `--model` and without `MVAC_MESSY_FY_MODEL`
- **THEN** the system uses the `messy_fy` task default from `models.yaml` (alias `nano-banana` → `google/gemini-3.1-flash-image-preview`)

#### Scenario: Model override is used

- **WHEN** a user provides `--model` with an alias or full OpenRouter id
- **THEN** the system uses that model for the messy-fy request

#### Scenario: Missing credential is rejected

- **WHEN** a user starts messy-fy without an available OpenRouter API credential
- **THEN** the system stops before making a provider request and reports the missing credential

### Requirement: Messy-Fy Output Storage

The system SHALL write generated images as PNG files and adjacent JSON metadata.

#### Scenario: Messy-fy generation succeeds

- **WHEN** OpenRouter returns a generated image
- **THEN** the system writes `<filename>.png` to the configured output directory (default `output/messyfied`)

#### Scenario: Messy-fy metadata is written

- **WHEN** messy-fy generation completes or fails
- **THEN** the system writes metadata containing status, provider, model, source hash, source MIME type, hint, prompt, negative prompt, output path, `openrouter_request` summary, provider response id, error, and timestamp

#### Scenario: Existing output is skipped

- **WHEN** a successful messy-fy output already exists with matching source hash, model, hint, prompt, and negative prompt
- **THEN** the system skips generation unless regeneration is explicitly requested

### Requirement: Optional Transparent Output

The system SHALL support optional local background removal after messy-fy generation when `--remove-background` is set.

#### Scenario: Transparent PNG is written

- **WHEN** a user runs messy-fy with `--remove-background` and generation succeeds
- **THEN** the system writes `<filename>-transparent.png` via the existing `remove-background` workflow

#### Scenario: Transparent output is omitted by default

- **WHEN** a user runs messy-fy without `--remove-background`
- **THEN** the system writes only the repainted PNG and metadata

### Requirement: Messy-Fy CLI

The system SHALL provide a `messy-fy` subcommand on the `mvac` CLI.

#### Scenario: Dry run prints plan

- **WHEN** a user runs `mvac messy-fy <image> --dry-run`
- **THEN** the CLI prints the resolved output path, model, hint, prompt, and `openrouter_request` summary without calling OpenRouter

#### Scenario: Messy-fy command generates image

- **WHEN** a user runs messy-fy with a valid source image and credential
- **THEN** the CLI generates exactly one repainted image and prints a JSON summary

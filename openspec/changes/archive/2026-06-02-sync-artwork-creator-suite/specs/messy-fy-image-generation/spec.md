## ADDED Requirements

### Requirement: Messy-Fy Source Image Validation

The system SHALL accept PNG, JPEG, or WebP source images and reject unsupported formats before starting generation.

#### Scenario: Supported image format

- **WHEN** a user provides a `.png`, `.jpg`, `.jpeg`, or `.webp` file
- **THEN** the system accepts the file as a valid messy-fy source

#### Scenario: Unsupported file type

- **WHEN** a user provides a file with another extension
- **THEN** the system rejects the file and reports supported formats

### Requirement: Messy-Fy Prompt Composition

The system SHALL compose a messy-fy prompt from `mv_artwork_creator/resources/messy_fy_prompts.yaml` and an optional user `--hint`.

#### Scenario: Brand repaint prompt is used

- **WHEN** the system composes a messy-fy prompt
- **THEN** the prompt instructs a stylistic repaint in Messy brand style, preserves source content, and does not insert Messy the character

### Requirement: Reference-Based Messy-Fy Generation

The system SHALL generate one repainted image through OpenRouter using the source image as visual reference.

#### Scenario: Default model from models.yaml

- **WHEN** a user starts messy-fy without `--model` and without `MVAC_MESSY_FY_MODEL`
- **THEN** the system uses the `messy_fy` task default from `models.yaml` (alias `nano-banana`)

#### Scenario: Source image is sent as reference

- **WHEN** messy-fy generation starts
- **THEN** the OpenRouter request includes the source image bytes as a base64 `image_url` content part before the text prompt

### Requirement: Messy-Fy Output Storage

The system SHALL write generated images as PNG files and adjacent JSON metadata with resume and regenerate behavior.

#### Scenario: Messy-fy generation succeeds

- **WHEN** OpenRouter returns a generated image
- **THEN** the system writes `<filename>.png` to the configured output directory

### Requirement: Optional Transparent Output

The system SHALL support optional local background removal after messy-fy generation when `--remove-background` is set.

#### Scenario: Transparent PNG is written

- **WHEN** a user runs messy-fy with `--remove-background` and generation succeeds
- **THEN** the system writes `<filename>-transparent.png` via the existing `remove-background` workflow

### Requirement: Messy-Fy CLI

The system SHALL provide a `messy-fy` subcommand on the `mvac` CLI.

#### Scenario: Dry run prints plan

- **WHEN** a user runs `mvac messy-fy <image> --dry-run`
- **THEN** the CLI prints the resolved output path, model, hint, and prompt without calling OpenRouter

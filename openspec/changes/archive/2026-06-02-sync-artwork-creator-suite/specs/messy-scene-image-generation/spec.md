## MODIFIED Requirements

### Requirement: Avatar-Referenced Scene Generation

The system SHALL generate one complete scene image through OpenRouter using the provided source avatar as visual identity reference.

#### Scenario: Source avatar is sent as reference

- **WHEN** scene generation starts
- **THEN** the OpenRouter request includes the source avatar bytes as a base64 `image_url` content part before the text prompt

#### Scenario: Reference attachment is verifiable

- **WHEN** a user runs scene generation or `--dry-run`
- **THEN** metadata or dry-run output includes an `openrouter_request` summary with `reference_image_attached`, byte size, and MIME type (without embedding base64)

#### Scenario: Configurable model is used

- **WHEN** a user provides `--model` with an alias or full OpenRouter id
- **THEN** the system uses that model for the scene request

#### Scenario: Default model from models.yaml

- **WHEN** a user starts scene generation without `--model` and without `MVAC_SCENE_MODEL`
- **THEN** the system uses the `scene` task default from `models.yaml` (alias `seedream` → `bytedance-seed/seedream-4.5`)

#### Scenario: Missing credential is rejected

- **WHEN** a user starts scene generation without an available OpenRouter API credential
- **THEN** the system stops before making a provider request and reports the missing credential

#### Scenario: Provider failure is recorded

- **WHEN** OpenRouter returns an error for the scene request
- **THEN** the system writes failed metadata for the scene output and returns a failed summary

## MODIFIED Requirements

### Requirement: Scene CLI

The system SHALL provide a `scene` subcommand on the `mvac` CLI for scene generation.

#### Scenario: Dry run prints scene plan

- **WHEN** a user runs `mvac scene <source.png> --setting "..." --action "..." --dry-run`
- **THEN** the CLI prints the resolved output path, model, setting, action, prompt, negative prompt, and `openrouter_request` summary without calling OpenRouter

#### Scenario: Scene command generates image

- **WHEN** a user runs the scene command with a valid source avatar, setting, action, and credential
- **THEN** the CLI generates exactly one scene image and prints a JSON summary

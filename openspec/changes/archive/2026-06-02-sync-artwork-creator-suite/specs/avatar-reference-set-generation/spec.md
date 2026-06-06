## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Avatar CLI Subcommand

The system SHALL provide an `avatar` subcommand on the `mvac` CLI for reference-set generation.

#### Scenario: Dry run prints plan

- **WHEN** a user runs `mvac avatar <source.png> --dry-run`
- **THEN** the CLI prints the planned image count and items without calling OpenRouter

#### Scenario: Avatar subcommand requires source image

- **WHEN** a user runs `mvac` without a recognized subcommand
- **THEN** the CLI does not accept a bare positional source image for generation

## MODIFIED Requirements

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

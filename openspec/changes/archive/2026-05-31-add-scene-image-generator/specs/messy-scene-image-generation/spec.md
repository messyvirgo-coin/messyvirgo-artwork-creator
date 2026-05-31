## ADDED Requirements

### Requirement: Scene Prompt Composition
The system SHALL compose a complete Messy scene prompt from stable brand guidance, a user-provided setting, a user-provided action, and negative prompt constraints.

#### Scenario: Setting and action are included
- **WHEN** a user provides a setting and action for scene generation
- **THEN** the composed prompt includes both user-provided values as bounded scene inputs

#### Scenario: Brand constraints are included
- **WHEN** the system composes a scene prompt
- **THEN** the prompt includes Messy identity preservation, anime-style 3:2 landscape output, dark modern fintech mood, diegetic finance/crypto chart constraints, and no watermark/logo guidance

#### Scenario: Empty scene field is rejected
- **WHEN** a user omits the setting or action
- **THEN** the system rejects scene generation before making a provider request

### Requirement: Avatar-Referenced Scene Generation
The system SHALL generate one complete scene image through OpenRouter using the provided source avatar as visual identity reference.

#### Scenario: Source avatar is sent as reference
- **WHEN** scene generation starts
- **THEN** the OpenRouter request includes the source avatar bytes as image input

#### Scenario: Configurable model is used
- **WHEN** a user provides an OpenRouter model override
- **THEN** the system uses that model for the scene request

#### Scenario: Missing credential is rejected
- **WHEN** a user starts scene generation without an available OpenRouter API credential
- **THEN** the system stops before making a provider request and reports the missing credential

#### Scenario: Provider failure is recorded
- **WHEN** OpenRouter returns an error for the scene request
- **THEN** the system writes failed metadata for the scene output and returns a failed summary

### Requirement: Scene Output Storage
The system SHALL write generated scene images as PNG files and adjacent JSON metadata.

#### Scenario: Scene generation succeeds
- **WHEN** OpenRouter returns a generated image
- **THEN** the system writes a PNG file to the configured output directory

#### Scenario: Scene metadata is written
- **WHEN** scene generation completes or fails
- **THEN** the system writes metadata containing status, provider, model, source image path, source hash, setting, action, prompt, negative prompt, output path, provider response id, error, and timestamp

#### Scenario: Existing scene output is skipped
- **WHEN** a successful scene output already exists with matching source hash, model, setting, action, prompt, and negative prompt
- **THEN** the system skips generation unless regeneration is explicitly requested

### Requirement: Scene CLI
The system SHALL provide a `scene` CLI subcommand for scene generation without changing existing commands.

#### Scenario: Dry run prints scene plan
- **WHEN** a user runs the scene command with `--dry-run`
- **THEN** the CLI prints the resolved output path, model, setting, action, prompt, and negative prompt without calling OpenRouter

#### Scenario: Scene command generates image
- **WHEN** a user runs the scene command with a valid source avatar, setting, action, and credential
- **THEN** the CLI generates exactly one scene image and prints a JSON summary

#### Scenario: Existing reference command still parses
- **WHEN** a user runs the original positional source-avatar command
- **THEN** the CLI continues to execute reference-set planning and generation behavior

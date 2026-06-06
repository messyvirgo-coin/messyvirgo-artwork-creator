## MODIFIED Requirements

### Requirement: Local Web Interface Startup

The system SHALL provide a `web` CLI subcommand that starts a local browser interface for generator workflows.

#### Scenario: Default web server starts

- **WHEN** a user runs `mvac web` without host or port overrides
- **THEN** the system starts an HTTP server bound to localhost on the default port (`8765`) and prints the URL

#### Scenario: Host and port override

- **WHEN** a user provides `--host` or `--port` to the `web` command
- **THEN** the server binds to the requested host and port

## ADDED Requirements

### Requirement: Web Avatar Form

The local web interface SHALL expose avatar reference planning and generation.

#### Scenario: Avatar form is rendered

- **WHEN** a user opens the local web interface
- **THEN** the page shows fields for source avatar path, output directory, model, API key override, dry-run, and test-mode options

#### Scenario: Avatar dry run from web

- **WHEN** a user submits the avatar form in dry-run mode
- **THEN** the server renders the planned image count and planned items without calling OpenRouter

### Requirement: Web Messy-Fy Form

The local web interface SHALL allow users to submit a source image path, optional hint, output directory, filename, model, and optional background removal for messy-fy generation.

#### Scenario: Messy-fy form is rendered

- **WHEN** a user opens the local web interface
- **THEN** the page shows fields for source image path, hint, output directory, model, filename, API key override, dry-run, and remove-background options

#### Scenario: Messy-fy form dry run

- **WHEN** a user submits the messy-fy form in dry-run mode
- **THEN** the server renders the composed prompt, resolved output path, and `openrouter_request` summary without calling OpenRouter

## MODIFIED Requirements

### Requirement: Web Background Removal Form

The local web interface SHALL expose the background-removal workflow as an optional post-process.

#### Scenario: Background removal form is rendered

- **WHEN** a user opens the local web interface
- **THEN** the page shows fields for input file or directory, output directory, and method (`rembg` or `flood`)

#### Scenario: Background removal from web

- **WHEN** a user submits the background-removal form with valid input
- **THEN** the server invokes the existing background-removal workflow and renders the JSON summary

## REMOVED Requirements

### Requirement: Web Existing Workflow Access

**Reason**: Split into explicit avatar, scene, messy-fy, and background-removal form requirements.

**Migration**: No behavior change; requirements are reorganized under named form requirements.

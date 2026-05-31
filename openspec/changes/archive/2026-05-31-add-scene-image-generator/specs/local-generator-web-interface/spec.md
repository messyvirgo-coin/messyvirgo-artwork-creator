## ADDED Requirements

### Requirement: Local Web Interface Startup
The system SHALL provide a `web` CLI subcommand that starts a local-only browser interface for generator workflows.

#### Scenario: Default web server starts
- **WHEN** a user runs the `web` command without host or port overrides
- **THEN** the system starts an HTTP server bound to localhost on the default port and prints the URL

#### Scenario: Host and port override
- **WHEN** a user provides host or port options to the `web` command
- **THEN** the server binds to the requested host and port

### Requirement: Web Scene Generation Form
The local web interface SHALL allow users to submit a source avatar path, setting, action, output directory, and optional model for Messy scene generation.

#### Scenario: Scene form is rendered
- **WHEN** a user opens the local web interface
- **THEN** the page shows fields for source avatar path, setting, action, output directory, model, and API key override

#### Scenario: Scene form dry run
- **WHEN** a user submits the scene form in dry-run mode
- **THEN** the server renders the composed prompt and resolved output path without making an OpenRouter request

#### Scenario: Scene form generation
- **WHEN** a user submits the scene form with generation enabled and a credential
- **THEN** the server invokes the scene generation workflow and renders the JSON summary

### Requirement: Web Existing Workflow Access
The local web interface SHALL expose the existing avatar reference planning and background-removal workflows without changing their command semantics.

#### Scenario: Reference dry run from web
- **WHEN** a user submits a source avatar path to preview the reference set
- **THEN** the server renders the planned reference image count and planned items without calling OpenRouter

#### Scenario: Background removal from web
- **WHEN** a user submits a background-removal source and output directory
- **THEN** the server invokes the existing background-removal workflow and renders the JSON summary

### Requirement: Local Web Error Reporting
The local web interface SHALL report validation and execution errors in the rendered page instead of crashing the server.

#### Scenario: Invalid form input
- **WHEN** a user submits invalid input
- **THEN** the server renders an error message and remains available for further requests

## ADDED Requirements

### Requirement: Web Workflow Picker

The local web interface SHALL present a workflow picker before showing generator-specific controls.

#### Scenario: Picker page is rendered

- **WHEN** a user opens the local web interface root page
- **THEN** the page shows workflow choices for avatar, scene, messy-fy, and background removal without rendering every workflow form at once

#### Scenario: Workflow page is rendered

- **WHEN** a user selects a workflow from the picker
- **THEN** the system renders a focused page for that workflow with navigation back to the picker

### Requirement: Web Local Path Selection

The local web interface SHALL make local source and output path selection easier by defaulting to repository-local input and output locations.

#### Scenario: Source file choices default to input directory

- **WHEN** a user opens an avatar, scene, messy-fy, or background-removal workflow page
- **THEN** the source control offers compatible files from the local `input/` directory when they exist

#### Scenario: Manual path fallback is available

- **WHEN** a desired source or output path is not available in the rendered choices
- **THEN** the workflow page still allows the user to submit a manually typed path

#### Scenario: Output defaults use output directory

- **WHEN** a user opens a generator workflow page
- **THEN** the output directory field defaults to the local `output/` directory or the workflow-specific output directory under `output/`

### Requirement: Web Model Alias Selection

The local web interface SHALL expose model selection as configured model aliases instead of a plain free-text model field.

#### Scenario: Model dropdown is rendered

- **WHEN** a user opens an avatar, scene, or messy-fy workflow page
- **THEN** the model control is a dropdown populated from aliases in the configured model registry

#### Scenario: Task default model is selected

- **WHEN** a workflow page renders its model dropdown
- **THEN** the dropdown selects the configured default model alias for that workflow

#### Scenario: Submitted model alias resolves through existing model registry

- **WHEN** a user submits a workflow form with a selected model alias
- **THEN** the server resolves the selected alias through the existing model registry before invoking the workflow

## MODIFIED Requirements

### Requirement: Web Avatar Form

The local web interface SHALL expose avatar reference planning and generation on a focused avatar workflow page.

#### Scenario: Avatar form is rendered

- **WHEN** a user opens the avatar workflow page
- **THEN** the page shows fields for source avatar path or local `input/` file selection, output directory, model alias selection, dry-run, and test-mode options
- **AND** the page does not show an API key override field

#### Scenario: Avatar dry run from web

- **WHEN** a user submits the avatar form in dry-run mode
- **THEN** the server renders the planned image count and planned items without calling OpenRouter

#### Scenario: Avatar generation from web

- **WHEN** a user submits the avatar form with generation enabled and an `OPENROUTER_API_KEY` credential is available
- **THEN** the server invokes the avatar generation workflow and renders the JSON summary

### Requirement: Web Scene Generation Form

The local web interface SHALL expose scene generation on a focused scene workflow page where users can submit a source avatar path, setting, action, output directory, optional filename stem, and model alias.

#### Scenario: Scene form is rendered

- **WHEN** a user opens the scene workflow page
- **THEN** the page shows fields for source avatar path or local `input/` file selection, setting, action, output directory, model alias selection, and optional output filename base
- **AND** the page does not show an API key override field

#### Scenario: Scene form dry run

- **WHEN** a user submits the scene form in dry-run mode
- **THEN** the server renders the composed prompt, resolved output path, and `openrouter_request` summary without making an OpenRouter request

#### Scenario: Scene form generation

- **WHEN** a user submits the scene form with generation enabled and an `OPENROUTER_API_KEY` credential is available
- **THEN** the server invokes the scene generation workflow and renders the JSON summary

### Requirement: Web Messy-Fy Form

The local web interface SHALL expose messy-fy generation on a focused messy-fy workflow page where users can submit a source image path, optional hint, output directory, optional filename stem, model alias, and optional background removal.

#### Scenario: Messy-fy form is rendered

- **WHEN** a user opens the messy-fy workflow page
- **THEN** the page shows fields for source image path or local `input/` file selection, hint, output directory, model alias selection, optional output filename base, dry-run, and remove-background options
- **AND** the page does not show an API key override field

#### Scenario: Messy-fy form dry run

- **WHEN** a user submits the messy-fy form in dry-run mode
- **THEN** the server renders the composed prompt, resolved output path, and `openrouter_request` summary without calling OpenRouter

#### Scenario: Messy-fy form generation

- **WHEN** a user submits the messy-fy form with generation enabled and an `OPENROUTER_API_KEY` credential is available
- **THEN** the server invokes the messy-fy generation workflow and renders the JSON summary

### Requirement: Web Background Removal Form

The local web interface SHALL expose the background-removal workflow on a focused background-removal workflow page.

#### Scenario: Background removal form is rendered

- **WHEN** a user opens the background-removal workflow page
- **THEN** the page shows fields for input file or directory path or local `input/` selection, output directory, and method (`rembg` or `flood`)

#### Scenario: Background removal from web

- **WHEN** a user submits the background-removal form with valid input
- **THEN** the server invokes the existing background-removal workflow and renders the JSON summary

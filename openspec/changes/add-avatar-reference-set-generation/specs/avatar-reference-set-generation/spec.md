## ADDED Requirements

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
The system SHALL generate images through OpenRouter using a configurable image model.

#### Scenario: Default model is used
- **WHEN** a user starts generation without overriding the model
- **THEN** the system uses the configured default Seedream 4.5 OpenRouter model identifier

#### Scenario: Model override is used
- **WHEN** a user provides an alternate OpenRouter image model identifier
- **THEN** the system uses that model identifier for every image in the batch

#### Scenario: Missing OpenRouter credential
- **WHEN** a user starts generation without an available OpenRouter API credential
- **THEN** the system stops before making generation requests and reports the missing credential

### Requirement: Reference Set Planning
The system SHALL create a deterministic generation plan that combines source avatar, angle presets, shot presets, model configuration, prompt text, and output locations before calling OpenRouter.

#### Scenario: Default reference set is planned
- **WHEN** a user requests generation with default presets
- **THEN** the system plans approximately 20 reference images that cover front, 45-degree, side, rear 45-degree, and back views across portrait, half-body, and full-body shots

#### Scenario: Planned count is inspectable
- **WHEN** a user previews or dry-runs generation
- **THEN** the system reports the planned image count and each planned angle and shot combination without calling OpenRouter

#### Scenario: Custom preset list is used
- **WHEN** a user provides a custom preset list
- **THEN** the system plans images only for the requested angle and shot combinations

### Requirement: YAML Prompt Library
The system SHALL load common avatar generation prompts from a YAML prompt library that defines shared base instructions, negative instructions, angle prompt fragments, and shot prompt fragments.

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

### Requirement: JPG Background Removal Extension
The system SHALL provide a post-processing extension that converts generated JPG/JPEG files into PNG files with alpha transparency by removing edge-connected background pixels.

#### Scenario: Directory conversion
- **WHEN** a user runs background removal with an input directory containing JPG/JPEG files
- **THEN** the system writes PNG files with matching stems to the configured output directory or to a sibling transparent output directory by default

#### Scenario: Single file conversion
- **WHEN** a user runs background removal with an input JPG/JPEG file
- **THEN** the system writes one PNG file with the matching stem

#### Scenario: Existing transparent output
- **WHEN** a converted PNG already exists
- **THEN** the system skips that file unless overwrite is requested

#### Scenario: Background removal summary
- **WHEN** background removal finishes
- **THEN** the system reports planned, converted, skipped, and failed counts

### Requirement: One Image Test Mode
The system SHALL provide a test mode that generates exactly one image using the normal provider, output, and metadata path.

#### Scenario: Test mode uses default test preset
- **WHEN** a user starts generation in test mode without selecting an angle or shot
- **THEN** the system generates exactly one image using the default test angle and shot preset

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
- **THEN** the system saves the image as PNG to the configured output directory with a stable filename that includes the angle and shot identifiers

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
- **WHEN** a user explicitly requests regeneration
- **THEN** the system regenerates matching planned items even if previous successful outputs exist

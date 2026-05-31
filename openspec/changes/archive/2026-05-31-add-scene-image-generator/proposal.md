## Why

Messy image generation currently focuses on producing controlled reference-set views from a transparent avatar PNG. The brand also needs a production tool for making complete compliant scene images by supplying only where Messy is and what she is doing while preserving the avatar as the visual identity reference.

## What Changes

- Add a new single-scene image generation flow that accepts a source avatar, a short setting description, and an action description.
- Compose scene prompts from reusable Messy brand guidance, reference prompt material, and user-provided scene/action fields.
- Save generated scene images and adjacent metadata with stable resume/regenerate behavior.
- Add a CLI subcommand for scene generation without changing the existing reference-set, sharpen, or remove-background commands.
- Add an optional lightweight local web interface that can run avatar reference generation, background removal, and the new scene generation flow from a browser.

## Capabilities

### New Capabilities

- `messy-scene-image-generation`: Generate one compliant brand scene image of Messy from a source avatar plus a user-provided setting and action.
- `local-generator-web-interface`: Provide a simple local browser interface for the existing avatar reference workflow, background removal workflow, and the new scene workflow.

### Modified Capabilities

- None.

## Impact

- Affected code: CLI routing, OpenRouter request reuse, prompt composition, metadata writing, tests, README/runbook docs, and new web-serving module.
- APIs: Adds new CLI subcommands and library entry points; existing commands remain backward compatible.
- Dependencies: Uses the Python standard library for the web UI where practical; no required runtime dependency beyond the existing OpenRouter/Pillow/YAML stack.
- Systems: Requires the same OpenRouter image model access and source avatar file used by the current generator.

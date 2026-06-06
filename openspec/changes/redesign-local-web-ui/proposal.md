## Why

The current local web interface puts every workflow form on one screen, which makes the tool visually noisy and harder to use as the number of generator options grows. It also exposes implementation-oriented fields such as API key override and free-text model IDs where the normal local workflow should use `.env` credentials, configured model aliases, and predictable input/output directories.

## What Changes

- Replace the one-page multi-form layout with a focused workflow picker/menu and one active workflow screen at a time.
- Add local file selection controls for source images and local directory selection controls for outputs where browser support allows it, while preserving path text entry as a fallback.
- Default source pickers and path fields to the local `input/` directory.
- Default output directory fields to the local `output/` directory or workflow-specific subdirectories under `output/`.
- Remove API key override fields from the web UI; web generation uses the normal `OPENROUTER_API_KEY` environment/config path.
- Replace free-text model fields with dropdowns populated from configured model aliases, selecting the task default by default.
- Keep filename stem fields where workflows support deterministic output naming, but make their purpose clearer in the UI.
- Preserve existing dry-run, generation, test-mode, remove-background, and background-removal workflow semantics.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-generator-web-interface`: Redesign the local web UI navigation, file/directory selection, credential handling, and model selection requirements.

## Impact

- Affects `mv_artwork_creator/web.py` rendering and form parsing.
- May add small helper functions for model option presentation and path defaults.
- Affects web-related tests in `tests/test_scene_image_generator.py` and any new focused web UI tests.
- Does not change CLI command shapes or generator execution semantics.
- Does not add a frontend framework or external web dependency.

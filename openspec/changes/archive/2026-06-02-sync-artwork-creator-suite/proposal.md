## Why

The codebase evolved into **Messy Virgo Artwork Creator** (`mvac`, `mv_artwork_creator`) with three generators, a web UI, and `models.yaml` aliases, but OpenSpec still described the old `avatar_reference_generator` CLI and omitted **messy-fy** entirely. Specs must match shipped behavior so validation and future changes stay trustworthy.

## What Changes

- Add **`messy-fy-image-generation`** capability spec.
- Update **`avatar-reference-set-generation`**: `mvac avatar`, 21-image matrix, `models.yaml` defaults, README-only docs.
- Update **`messy-scene-image-generation`**: `mvac scene`, `models.yaml` defaults, remove obsolete positional-CLI scenario.
- Update **`local-generator-web-interface`**: messy-fy form, avatar naming, four workflow forms.
- Add project **context** to `openspec/config.yaml`.

No application code changes — documentation and OpenSpec sync only.

## Capabilities

### New Capabilities

- `messy-fy-image-generation`: Repaint PNG/JPEG/WebP in Messy brand style via OpenRouter with optional transparent output.

### Modified Capabilities

- `avatar-reference-set-generation`: CLI subcommand naming, model registry, exact default batch size.
- `messy-scene-image-generation`: Model registry defaults; scene CLI requirements aligned with `mvac`.
- `local-generator-web-interface`: Messy-fy web form and updated purpose statement.

## Impact

- `openspec/specs/*` and `openspec/config.yaml` only.
- Archived change proposals remain historical; main specs become the current contract.

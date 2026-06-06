## Context

Implementation is complete. This change syncs OpenSpec artifacts to the shipped `mv_artwork_creator` package without modifying Python code.

## Goals

- Main specs at `openspec/specs/` describe all user-facing capabilities.
- Model defaults documented via `models.yaml` task aliases, not `.env` model variables.
- Web UI spec covers all four forms in `web.py`.

## Non-Goals

- Rewriting archived changes under `openspec/changes/archive/`.
- Adding OpenSpec requirements for optional `MVAC_*_MODEL` env overrides (kept as implementation detail).

## Model resolution (documented in specs)

When `--model` is omitted:

1. Task-specific env var if set (`MVAC_AVATAR_MODEL`, `MVAC_SCENE_MODEL`, `MVAC_MESSY_FY_MODEL`).
2. Task entry in bundled `models.yaml` (alias resolved via `aliases` map).
3. Global `default` in `models.yaml`.

Bundled task defaults: `avatar` → `seedream`, `scene` → `seedream`, `messy_fy` → `nano-banana`.

## CLI surface (documented in specs)

`mvac` requires an explicit subcommand: `avatar`, `scene`, `messy-fy`, `remove-background`, `sharpen`, `web`. No bare positional source-image invocation.

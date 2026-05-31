## Context

The current package is a Python CLI/library that generates avatar reference-set images from one transparent PNG source avatar through OpenRouter, then optionally sharpens and removes white backgrounds. Prompting is YAML-driven for reference-set angles and shots, while broader Messy brand image guidance lives as Markdown prompt files in the adjacent `messyvirgo-org` repository.

The new scene generator must preserve the existing reference-set workflow and add a separate way to create complete brand images by entering only where Messy is and what she is doing. The generated image still needs the source avatar as visual identity reference and the same OpenRouter image model path.

## Goals / Non-Goals

**Goals:**

- Add a single-image scene generator that uses the avatar image as reference input.
- Compose compliant prompts from stable brand guidance plus explicit user setting/action fields.
- Store generated scene outputs and metadata in the same operational style as the existing generator.
- Add CLI access and a lightweight local browser interface for existing and new workflows.
- Keep tests free of network and rembg model calls.

**Non-Goals:**

- Do not replace or alter the existing reference-set matrix generation behavior.
- Do not add multi-image campaign planning, prompt rewriting by an LLM, queueing, auth, or remote hosting.
- Do not guarantee provider-level policy enforcement beyond deterministic prompt constraints and metadata traceability.
- Do not add a new frontend framework or persistent database.

## Decisions

1. Add `scene_prompts.py` for scene prompt configuration and composition.

   The scene prompt format will be YAML, separate from `config/avatar_prompts.yaml`, with fields for `system_prompt`, `negative_prompt`, optional defaults, and derived constraints from the existing Markdown prompt references. This avoids overloading angle/shot prompt concepts and lets tests validate scene prompt composition directly. Alternative considered: parse the Markdown reference prompts at runtime. That would couple this package to a sibling repo path and make installed usage brittle.

2. Add `scene_executor.py` for one-image scene execution.

   The executor will validate inputs, compute a source hash and prompt hash, reuse `OpenRouterClient.generate_image`, normalize provider image bytes to PNG, and write adjacent JSON metadata. It will mirror `executor.py` patterns instead of changing the batch executor. Alternative considered: generalize the existing executor. That would risk regressions in the working reference-set flow for limited reuse.

3. Add a `scene` CLI subcommand.

   The command shape will be `python3 -m avatar_reference_generator scene <source.png> --setting "..." --action "..."`. It will support `--dry-run`, `--output-dir`, `--prompt-library`, `--model`, `--api-key`, `--filename`, `--regenerate`, and `--retry-count`. This preserves the existing positional root command for reference-set generation.

4. Add a standard-library local web server.

   A `web` subcommand will start a local HTTP server using Python standard-library HTTP handling. The server will render a compact HTML form and call existing library functions for reference generation dry runs, scene generation, and background removal. This gives a simple interface without introducing build tooling, package-lock churn, or frontend runtime dependencies. Alternative considered: Flask/FastAPI. Those are cleaner for larger apps but unnecessary for a local tool and would add required dependencies.

5. Keep background removal optional for scene outputs.

   Scene images are full environment illustrations, so automatic background removal should not be part of the scene-generation default. The web UI can still expose the existing background removal command for avatar/reference outputs.

## Risks / Trade-offs

- Provider may ignore scene constraints or drift from the avatar identity -> Mitigation: include the source image in every scene request, make identity/brand constraints explicit, and store full prompt metadata for review and regeneration.
- User-provided setting/action text could conflict with brand guidance -> Mitigation: deterministic prompt composition frames user text as bounded scene/action inputs and always appends hard constraints and negative guidance.
- Local web server can block while image generation runs -> Mitigation: keep this first version synchronous and local-only; no remote hosting or concurrent job queue is in scope.
- Markdown reference prompts may evolve outside this repo -> Mitigation: import their stable guidance into `config/messy_scene_prompts.yaml` and document where it came from.

## Migration Plan

1. Add scene prompt config and executor modules with unit tests.
2. Add the `scene` CLI subcommand and dry-run behavior.
3. Add the local `web` subcommand and tests for routing/rendering helpers.
4. Update README/runbook documentation.
5. Run the full unit test suite and review the diff for regressions.

Rollback is deleting the new scene/web modules, config, docs, tests, and CLI subcommand branch; existing reference-set commands remain isolated.

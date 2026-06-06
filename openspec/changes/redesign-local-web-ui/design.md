## Context

The current `mvac web` UI is a single generated HTML page from `mv_artwork_creator/web.py`. It exposes avatar, scene, messy-fy, and background-removal forms in one grid, with text inputs for model IDs, API key override fields, and path fields that require users to type local paths manually. The backend already has stable workflow helpers and model registry loading, so this change should redesign the local browser experience without changing generator semantics or adding a frontend build system.

The local server runs on localhost and can inspect the local filesystem. That makes a server-rendered picker practical: the browser cannot freely browse arbitrary local paths, but the server can render available files under `input/` and output directory defaults under `output/`.

## Goals / Non-Goals

**Goals:**

- Make the first screen a workflow picker/menu rather than showing every form at once.
- Render one focused workflow screen at a time for avatar, scene, messy-fy, and background removal.
- Remove API key override fields from the web UI and rely on `OPENROUTER_API_KEY` for generation.
- Default source file selection to files under `input/`.
- Default output directory values to `output/` or workflow-specific subdirectories under `output/`.
- Populate model controls from configured aliases in `models.yaml`, selecting each task default by default.
- Preserve filename stem support while labeling it as an optional output filename base.
- Keep the implementation dependency-free and compatible with the existing stdlib HTTP server.

**Non-Goals:**

- Do not change CLI arguments or generator execution behavior.
- Do not add authentication, persistence, upload storage, queues, or remote hosting.
- Do not add a frontend framework, bundler, or external JavaScript dependency.
- Do not provide unrestricted filesystem browsing outside the configured local workspace paths.

## Decisions

1. Keep the stdlib `ThreadingHTTPServer` and render HTML from Python.

   Rationale: The existing UI is local-only and already shares backend code with the CLI. Keeping it stdlib avoids dependency and packaging churn. A framework would mainly help routing/templates, but the UI remains small enough for helper functions in `web.py`.

2. Use a route-level workflow picker with one active form per page.

   The root page will show a compact picker for Avatar, Scene, Messy-fy, and Remove Background. Each selection opens a dedicated workflow route, for example `/?workflow=messy-fy` or equivalent path-based routes if implementation keeps routing cleaner. The active workflow page will include a clear return path to the picker and render results below that workflow only.

   Alternative considered: client-side tabs with all forms still in the DOM. This improves visual clutter but keeps the page heavy and does not simplify form-specific rendering.

3. Implement local file choices as server-provided options plus path fallback.

   The server will list supported image files under `input/` for avatar, scene, and messy-fy source fields. Users can choose from a dropdown and can still type a path manually when needed. Background removal can offer files and directories under `input/` with manual fallback. Output directories will default to `output/`, `output/avatars`, `output/scenes`, `output/messyfied`, or existing workflow defaults where those are already established.

   Browser-native file inputs are not sufficient because they do not provide stable local file paths to Python without implementing uploads. Server-side listing matches this local tool better.

4. Populate model dropdowns from the model registry aliases.

   The dropdown value should be the alias name, not the resolved provider ID, when an alias exists. The selected option should be the task default alias from `models.yaml` when available. Include a "custom model ID" fallback only if the implementation can preserve existing flexibility without making the default UI noisy; otherwise leave custom IDs to CLI usage.

   Rationale: Users asked for aliases present in config. Showing aliases keeps model choices readable and ensures form submissions continue through existing `resolve_model()`.

5. Remove API key override fields only from the web UI.

   Generation helpers may continue to accept `api_key` if tests or internals use them, but rendered forms should not expose the field. Web generation should read `OPENROUTER_API_KEY` from the environment, matching normal local usage.

## Risks / Trade-offs

- Local file picker may miss files outside `input/` → Keep a manual path fallback and document the default convention in labels.
- Browser directory selection cannot provide a direct server path reliably → Prefer server-rendered local directory choices and text fallback instead of relying only on `<input type="file">`.
- More UI helper code in `web.py` can become hard to maintain → Split rendering into small functions for workflow picker, model options, path controls, and individual forms.
- Removing API key override from the UI can inconvenience ad hoc testing → Keep CLI `--api-key` behavior unchanged and keep environment-based web generation errors clear.
- Model aliases may resolve to duplicate model IDs → Display aliases as distinct choices; the registry remains the source of truth.

## Migration Plan

1. Add focused tests for the new picker page, active workflow pages, removed API key fields, model alias dropdown defaults, input file options, and output defaults.
2. Refactor `render_home_page()` into smaller render helpers while preserving existing workflow POST endpoints.
3. Add server-side helpers for listing local input files/directories and formatting model alias options.
4. Update form parsing only where field names change; keep existing workflow helper functions and result rendering semantics.
5. Run the web-related unit tests and full generator test subset.

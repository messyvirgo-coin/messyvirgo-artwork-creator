## 1. Web UI Tests

- [x] 1.1 Add tests that the root web page renders a workflow picker and does not render all workflow forms at once.
- [x] 1.2 Add tests for focused avatar, scene, messy-fy, and background-removal workflow pages.
- [x] 1.3 Add tests that rendered generator forms omit API key override fields.
- [x] 1.4 Add tests that model controls render configured alias dropdown options with the task default selected.
- [x] 1.5 Add tests that local source choices come from `input/` and output directory defaults point under `output/`.

## 2. Rendering Structure

- [x] 2.1 Refactor `render_home_page()` into smaller helpers for layout, picker, result/error rendering, and workflow form rendering.
- [x] 2.2 Add GET handling for focused workflow pages while preserving the root picker page.
- [x] 2.3 Update page styling to support the picker/menu and focused workflow screens without adding frontend dependencies.

## 3. Path And Model Controls

- [x] 3.1 Add server-side helpers that list compatible local input files and background-removal inputs under `input/`.
- [x] 3.2 Add path controls that provide local choices plus manual text fallback.
- [x] 3.3 Add model dropdown helpers that read aliases and task defaults from the configured model registry.
- [x] 3.4 Keep submitted model values flowing through existing `resolve_model()` behavior.

## 4. Workflow Forms

- [x] 4.1 Update the avatar workflow form to use local source selection, output defaults, model alias dropdown, dry-run, and test-mode controls.
- [x] 4.2 Update the scene workflow form to use local source selection, output defaults, model alias dropdown, and optional output filename base labeling.
- [x] 4.3 Update the messy-fy workflow form to use local source selection, output defaults, model alias dropdown, optional output filename base labeling, and remove-background control.
- [x] 4.4 Update the background-removal workflow form to use local input selection, output defaults, and method selection.
- [x] 4.5 Remove rendered API key override fields while preserving environment-based credential lookup for generation.

## 5. Verification

- [x] 5.1 Run the focused web UI tests.
- [x] 5.2 Run the scene/web and messy-fy test modules.
- [x] 5.3 Start `mvac web` locally and manually check the picker, each workflow page, and form submissions in dry-run mode.

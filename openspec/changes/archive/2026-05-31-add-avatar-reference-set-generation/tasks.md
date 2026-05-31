## 1. Project Integration

- [x] 1.1 Inspect the application structure and choose the local entry point for reference set generation.
- [x] 1.2 Add or update configuration loading for OpenRouter API credentials, model ID, output directory, concurrency, retry count, preset selection, prompt library path, and test mode settings.
- [x] 1.3 Add documentation or example environment values for configuring OpenRouter, the default Seedream 4.5 model identifier, prompt library path, and test mode.

## 2. Prompt Library, Presets, and Planning

- [x] 2.1 Create a YAML prompt library with base prompt, negative prompt, angle prompt fragments, and shot prompt fragments.
- [x] 2.2 Implement prompt library loading and validation for required base, angle, and shot prompt fields.
- [x] 2.3 Define angle and shot preset types with stable identifiers that map to prompt library fragments.
- [x] 2.4 Implement the default reference set preset matrix covering front, 45-degree, side, rear 45-degree, and back views across portrait, half-body, and full-body shots.
- [x] 2.5 Implement composed prompt creation from base prompt, angle fragment, and shot fragment.
- [x] 2.6 Implement generation plan creation that resolves source image, model, presets, composed prompts, negative prompt guidance, output filenames, and metadata filenames before provider calls.
- [x] 2.7 Add a dry-run or preview path that reports planned image count and angle/shot combinations without calling OpenRouter.
- [x] 2.8 Add test mode planning that limits execution to exactly one default or selected angle/shot item.

## 3. Source Validation

- [x] 3.1 Implement PNG file validation that rejects non-PNG inputs.
- [x] 3.2 Implement alpha-channel validation that rejects PNG files without transparency support.
- [x] 3.3 Return clear validation errors before starting any generation requests.

## 4. OpenRouter Adapter

- [x] 4.1 Implement an OpenRouter image generation adapter with request construction isolated from planning logic.
- [x] 4.2 Include the source avatar image, selected model, composed prompt, and negative prompt guidance in each OpenRouter request.
- [x] 4.3 Parse successful OpenRouter image responses into saveable image output.
- [x] 4.4 Map OpenRouter failures into per-item batch failures with useful error messages.

## 5. Output and Metadata

- [x] 5.1 Create the output directory when it does not exist.
- [x] 5.2 Save generated images using stable filenames that include angle and shot identifiers.
- [x] 5.3 Write sidecar metadata for each completed or failed planned item, including source reference, provider, model, prompt, angle, shot type, output path, status, timestamp, and provider response identifiers when available.
- [x] 5.4 Implement batch resumption that skips successful existing outputs by default and retries failed or missing items.
- [x] 5.5 Implement an explicit regeneration option for previously successful outputs.
- [x] 5.6 Ensure test mode writes the same image and metadata format as full batch generation.

## 6. Testing and Verification

- [x] 6.1 Add tests for prompt library loading, required prompt fragment validation, and composed prompt output.
- [x] 6.2 Add tests for default preset expansion and custom preset selection.
- [x] 6.3 Add tests for one-image test mode with default and selected presets.
- [x] 6.4 Add tests for PNG and alpha-channel validation.
- [x] 6.5 Add tests for generation plan output paths, prompts, negative prompt guidance, and metadata paths.
- [x] 6.6 Add tests for OpenRouter request construction using a mocked provider transport.
- [x] 6.7 Add tests for metadata writing, failed item recording, resume behavior, regeneration behavior, and test mode output behavior.
- [x] 6.8 Run the project test suite and OpenSpec validation for `add-avatar-reference-set-generation`.

## 7. Change Request: Prompt and Background Removal

- [x] 7.1 Update the prompt library to describe Messy as an elegant crypto finance funds allocator.
- [x] 7.2 Update full-body prompt guidance to preserve elegant long trousers and avoid mini skirts.
- [x] 7.3 Add a background-removal extension that converts JPG/JPEG outputs to transparent PNG files with friendly `--input-dir` and `--input-file` options.
- [x] 7.4 Add tests for prompt wording and JPG-to-transparent-PNG conversion.
- [x] 7.5 Update the runbook with the background-removal command.

## 8. Packaging, Documentation, and Post-Processing Polish

- [x] 8.1 Add `sharpen` CLI and integrate optional pre-sharpen into `remove-background` (unsharp mask on by default).
- [x] 8.2 Implement `rembg` matting (`isnet-anime` default) with `flood` fallback and near-white alpha cleanup.
- [x] 8.3 Add `rembg[cpu]` optional extra in `pyproject.toml` and document install in README.
- [x] 8.4 Add README overview, CLI reference, and `docs/avatar-reference-runbook.md` operational guide.
- [x] 8.5 Point package metadata and README clone URL at `messyvirgo-coin/messyvirgo-avatar-creator` after repo transfer.

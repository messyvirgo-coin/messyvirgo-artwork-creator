## Why

Users need a repeatable way to turn one transparent PNG anime avatar into a consistent reference set that covers the core camera angles and body framing needed for downstream image generation. Doing this manually is slow, inconsistent, and makes later generation quality depend on ad hoc prompts.

## What Changes

- Add a workflow that accepts a transparent PNG avatar as the source image.
- Generate a reference set of roughly 20 images covering important view angles and shot framings.
- Use OpenRouter for image generation, with Seedream 4.5 as the default target model.
- Keep the image model configurable so users can switch OpenRouter-compatible image models without code changes.
- Define reusable presets for angles such as front, 45-degree, side, rear 45-degree, and back views.
- Define reusable presets for portrait, half-body, and full-body shot types.
- Define common reusable prompts in a YAML prompt library with shared base instructions plus angle-specific and shot-specific prompt fragments.
- Refine the default prompts to describe Messy as an elegant crypto finance funds allocator and preserve long trousers in full-body views.
- Add a test mode that generates only one planned image for quick model, credential, and prompt validation.
- Add a background-removal extension that converts generated JPG/JPEG images into transparent PNGs.
- Save generated images with metadata that records source input, model, prompt, angle, shot type, and generation status.
- Provide validation and clear errors for unsupported input files, missing credentials, failed generations, and incomplete batches.

## Capabilities

### New Capabilities

- `avatar-reference-set-generation`: Generates a configurable set of avatar reference images from a transparent PNG using OpenRouter-compatible image models.

### Modified Capabilities

- None.

## Impact

- Adds a new generation pipeline for avatar reference images.
- Adds OpenRouter API integration and related configuration for model selection and credentials.
- Adds a YAML prompt library for base, angle, and shot prompts.
- Adds post-processing support for transparent PNG conversion from generated JPG/JPEG files.
- Adds storage conventions for generated image outputs and per-image metadata.
- Adds tests around prompt composition, test mode, preset expansion, validation, configuration, metadata, and OpenRouter request construction.

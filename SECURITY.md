# Security

## Reporting a vulnerability

Please do not open a public GitHub issue for suspected vulnerabilities, credential leaks, or other sensitive security concerns.

Report privately to: `contact@messyvirgo.com`

Include:

- A concise description of the issue
- Impact and affected paths/files
- Reproduction details (if safe to share)
- Suggested mitigation (optional)

## Scope notes

This repository contains a local artwork-generation tool (`mvac` CLI and a local web UI) that calls the OpenRouter API on the user's behalf using a user-provided API key.

When reporting issues, avoid posting any secrets or sensitive runtime values, including:

- API keys and auth tokens (e.g. `OPENROUTER_API_KEY`)
- private URLs/endpoints
- personally identifying information
- environment files or command output containing credentials

## Coordinated disclosure

We will review reports as quickly as possible on a best-effort basis, coordinate remediation, and disclose fixes publicly once it is safe to do so.

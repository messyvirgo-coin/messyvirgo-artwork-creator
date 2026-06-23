# Pull Request

## Context & Purpose

- What is the purpose of this change?
- What problem does it solve or improve?

## What changed

- Summarize the key changes (CLI, web UI, prompts, models, docs, tests, etc.).
- Note any behavior changes for users.

## How to test

- Provide exact commands you ran. Prefer `--dry-run` where possible (no API charge).
- Include relevant environment details when needed (OS, Python version).

Example:

```bash
pip install -e .
mvac avatar input/messy.png --dry-run
python3 -m unittest discover -s tests -v
```

## Checklist

- [ ] No secrets/tokens/private paths were committed (especially `.env` or `OPENROUTER_API_KEY`)
- [ ] No generated `output/` or local `config/` committed
- [ ] Docs updated if user workflow changed
- [ ] Tests pass locally
- [ ] Changes are scoped and easy to review

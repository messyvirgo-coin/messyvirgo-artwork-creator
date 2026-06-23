# Contributing to Messy Virgo Artwork Creator

Thanks for contributing. This repository is the **Messy Virgo Artwork Creator** — the `mvac` command-line tool and local web UI for generating Messy Virgo avatars, scenes, and "messy-fied" images via [OpenRouter](https://openrouter.ai/). PRs are welcome; merges and scope are maintainer decisions. Support is best-effort—see [SUPPORT.md](./SUPPORT.md).

## Ground rules

- Follow the [Code of Conduct](./CODE_OF_CONDUCT.md).
- Do not post secrets, tokens, personal data, private links, or confidential content in issues or PRs. In particular, never commit your `.env` or an `OPENROUTER_API_KEY`.
- Respect brand assets and trademarks—see [NOTICE.md](./NOTICE.md) and [TRADEMARK.md](./TRADEMARK.md).
- Keep PRs focused (one change-set when possible) and explain what changed, why, and how you verified it.

## What we welcome

- Fixes and improvements in `mv_artwork_creator/`
- Documentation updates in `README.md`
- Improvements to prompts and model defaults in `mv_artwork_creator/resources/` that preserve existing CLI and web flows
- Test coverage in `tests/`

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env               # add OPENROUTER_API_KEY=... to .env
```

Smoke test (no images generated, no API charge):

```bash
mvac avatar input/messy.png --dry-run
```

Run the tests:

```bash
python3 -m unittest discover -s tests -v
```

## Pull request checklist

- Add or update docs when user workflow changes.
- Include verification steps (commands run and what you observed). Prefer `--dry-run` output where possible.
- Confirm you did not commit `.env`, tokens, credentials, generated `output/`, local `config/`, or private paths.
- Confirm tests pass locally.

## Scope

Artwork-generation tooling for Messy Virgo only. We may decline changes that add maintenance cost or scope without clear benefit.

## Maintainers

- `@messy-michael`
- `@MessyFranco`

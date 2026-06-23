# Messy Virgo Artwork Creator

Create Messy Virgo artwork with AI using the `mvac` command and [OpenRouter](https://openrouter.ai/).

Repo: [messyvirgo-coin/messyvirgo-artwork-creator](https://github.com/messyvirgo-coin/messyvirgo-artwork-creator)

| Tool | What it does |
|------|----------------|
| **Avatar** | Many angles of Messy (reference sheet) |
| **Scene** | One full picture — Messy in a place, doing something |
| **Messy-fy** | Restyle a photo or graphic in Messy brand look (does not add Messy herself) |

Generation runs in the cloud (OpenRouter). Your PC sends the request and saves files to `output/`.

**Prefer the browser?** After [one-time setup](#setup-once), run:

```bash
./start_web.sh
```

That activates the project Python environment and starts the local web UI (usually [http://127.0.0.1:8765/](http://127.0.0.1:8765/)). The web server runs inside the same `.venv` as the CLI — you cannot start it without that environment.

---

## Which command do I use?

| I want to… | Command |
|------------|---------|
| Many views of Messy (front, side, back, …) | `mvac avatar` |
| One scene illustration | `mvac scene` |
| Restyle an existing image | `mvac messy-fy` |

Prefer forms over the terminal? Run `./start_web.sh` after setup ([Browser UI](#browser-ui)).

**Optional:** [remove white backgrounds](#optional-transparent-backgrounds) from avatar outputs — extra install, runs on your PC, skip on weak laptops.

---

## Before you start

1. Clone this repo and open a terminal in the project folder:

   ```bash
   git clone https://github.com/messyvirgo-coin/messyvirgo-artwork-creator.git
   cd messyvirgo-artwork-creator
   ```

2. **Python 3.11+** — check with `python3 --version` ([download](https://www.python.org/downloads/) if needed).

3. **OpenRouter API key** — account at [openrouter.ai](https://openrouter.ai/), a little credit, then create a key in the dashboard.

---

## Setup (once)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env               # add OPENROUTER_API_KEY=... to .env
```

Smoke test (no images generated, no API charge for the plan itself):

```bash
mvac avatar input/messy.png --dry-run
```

If `mvac` is not found, use `python3 -m mv_artwork_creator` instead.

The first generator run also creates **`config/`** with editable copies of prompts and model settings (not tracked by git). See [Customizing](#customizing-prompts-and-models).

---

## Avatar — 21 reference images

**Input requirement:** one **transparent PNG** of Messy (RGBA — checkerboard background in Photoshop/Figma means transparency). Opaque PNGs are rejected.

Put the file in `input/`, for example `input/messy.png`.

```bash
mvac avatar input/messy.png --dry-run
mvac avatar input/messy.png --test --output-dir output/test-avatars
mvac avatar input/messy.png --output-dir output/avatars
```

Outputs: `output/avatars/front__portrait.png`, `right_side__full_body.png`, etc. (white background from the AI — not transparent until you optionally run background removal).

---

## Scene — one environment image

**Input requirement:** same **transparent Messy PNG** as for avatar.

Describe **where** Messy is (`--setting`) and **what she is doing** (`--action`). Outfit and face come from your PNG, not from the text.

```bash
mvac scene input/messy.png \
  --setting "a neon city avenue after rain" \
  --action "walking past a trading billboard" \
  --dry-run

mvac scene input/messy.png \
  --setting "a neon city avenue after rain" \
  --action "walking past a trading billboard" \
  --filename neon-city-walk
```

**Tips:** Be specific about the place. For charts, say “on a wall display”, not “candles” (models often draw wax candles).

---

## Messy-fy — restyle an image

**Input requirement:** PNG, JPEG, or WebP — **transparency not required**.

```bash
mvac messy-fy input/photo.jpg --hint "do not change any text" --dry-run
mvac messy-fy input/photo.jpg --hint "do not change any text" --filename styled
```

Output: `output/messyfied/styled.png`.

---

## Browser UI

The web UI is a local Python server — it needs the project virtualenv active (same as `mvac` CLI commands).

**Recommended** — from the project folder, with [setup](#setup-once) done:

```bash
./start_web.sh
```

`start_web.sh` activates `.venv`, then runs `mvac web`. Optional port: `./start_web.sh --port 8899`.

**Manual** — if you already ran `source .venv/bin/activate`:

```bash
mvac web
```

Open the URL shown (usually [http://127.0.0.1:8765/](http://127.0.0.1:8765/)). Use **Dry run** first. The tab stays busy until the job finishes.

---

## Customizing prompts and models

Edit files in `config/` (created on first run):

| File | Purpose |
|------|---------|
| `avatar_prompts.yaml` | Avatar angles and style |
| `scene_prompts.yaml` | Scene brand rules |
| `messy_fy_prompts.yaml` | Messy-fy repaint rules |
| `models.yaml` | Default AI models (`seedream`, `nano-banana`) |

```bash
mvac config path    # where config/ lives
mvac config reset   # restore factory defaults
```

One-off without your `config/` copies: add `--factory-defaults` to a generator command.

---

## Optional: transparent backgrounds

Only if you need avatar PNGs **without** a white background and your PC can handle local processing.

```bash
pip install -e ".[rembg]"
mvac remove-background --input-dir output/avatars \
  --output-dir output/avatars-transparent --overwrite
```

Do not run this on scene images unless you intend to strip the environment.

---

## If something goes wrong

| Message / problem | Fix |
|-------------------|-----|
| Missing API key | Set `OPENROUTER_API_KEY` in `.env` |
| Transparent PNG required / no alpha channel | Use RGBA PNG for `avatar` and `scene` (see [Avatar](#avatar--21-reference-images)) |
| Empty setting or action | Fill both `--setting` and `--action` for `scene` |
| `mvac` not found | Run `./start_web.sh`, or activate `.venv` / use `python3 -m mv_artwork_creator` |
| Image skipped on re-run | Add `--regenerate`, or delete that `.png` + `.json` |

**Re-run behavior:** same command skips finished images. `--regenerate` redoes all. For one avatar angle: delete its files, then `mvac avatar ... --preset angle:shot`.

---

## For technical users

<details>
<summary>pipx, CLI flags, tests</summary>

```bash
pipx install .
```

```text
mvac avatar <source.png> [--dry-run] [--test] [--preset angle:shot]
mvac scene <source.png> --setting "..." --action "..."
mvac messy-fy <image> [--hint "..."]
mvac remove-background [--input-dir DIR] [--method rembg|flood]
mvac config {init|reset|path}
mvac web [--port 8899]
```

```bash
python3 -m unittest discover -s tests -v
```

</details>

---

## Governance

See the [Messy Virgo organization repository](https://github.com/messyvirgo-coin/messyvirgo-org) for cross-repo governance, policies, and community guidelines.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) and the [Code of Conduct](./CODE_OF_CONDUCT.md).

## Security

Report suspected vulnerabilities privately—see [SECURITY.md](./SECURITY.md). Do not open a public issue.

## Support

This project is provided as-is with best-effort maintenance—see [SUPPORT.md](./SUPPORT.md).

## License

- **Code**: Apache-2.0 (see [LICENSE](./LICENSE))
- **Brand assets & trademarks**: reserved (see [NOTICE](./NOTICE.md) and [TRADEMARK](./TRADEMARK.md))

The Messy Virgo character, reference images in `input/`, and generated artwork depicting the character are brand assets and are not licensed for reuse.

## Disclaimer

This software is provided **as-is** for creative and educational purposes. Generation runs against the third-party OpenRouter API using your own API key and credit; you are responsible for your usage, costs, and compliance with OpenRouter's and the underlying model providers' terms. The authors are not responsible for generated content or any costs incurred.

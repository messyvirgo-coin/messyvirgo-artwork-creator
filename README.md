# Messy Virgo Artwork Creator

Python CLI (`mvac`) for Messy Virgo artwork via [OpenRouter](https://openrouter.ai/).

**Repository:** [github.com/messyvirgo-coin/messyvirgo-artwork-creator](https://github.com/messyvirgo-coin/messyvirgo-artwork-creator)

Create Messy Virgo artwork with AI. You can:

1. **Avatar** — many angles of Messy from one transparent PNG (for reference sheets).
2. **Scene** — one full picture of Messy in a place, doing something.
3. **Messy-fy** — repaint an existing photo or graphic in Messy brand style (Messy herself is **not** added — only the look).

Images are generated online via [OpenRouter](https://openrouter.ai/) (you need an API key). Your computer only sends the request and saves the result.

---

## Which tool should I use?

| I want to… | Command | What to prepare |
|------------|---------|-----------------|
| Many views of Messy (front, side, back, etc.) | `mvac avatar` | One **transparent** Messy PNG |
| One picture of Messy in a scene | `mvac scene` | Transparent Messy PNG + short text for **where** and **what she’s doing** |
| Restyle a photo or design in Messy colors/look | `mvac messy-fy` | Any PNG, JPEG, or WebP |

**Not sure about the command line?** After setup, run `mvac web` and use the forms in your browser (see [Browser UI](#browser-ui-easier-option)).

**Transparent cutouts (optional):** Generated avatars come on a **white background**. Removing the background needs extra software on your PC and is slow on weak laptops — you can skip it unless you really need PNGs with no background ([Optional: transparent backgrounds](#optional-transparent-backgrounds)).

---

## Before you start

You need:

1. **This project** on your computer:

   ```bash
   git clone https://github.com/messyvirgo-coin/messyvirgo-artwork-creator.git
   cd messyvirgo-artwork-creator
   ```

2. **Python 3.11+** — [python.org](https://www.python.org/downloads/) (on Mac/Linux it is often pre-installed; try `python3 --version` in a terminal).
3. **An OpenRouter account and API key** — sign up at [openrouter.ai](https://openrouter.ai/), add a little credit, then create an API key in their dashboard.
4. **Input images** in the `input/` folder (create it if missing), e.g. `input/messy.png`.

> **Note:** The GitHub repo was renamed from `messyvirgo-avatar-creator` to `messyvirgo-artwork-creator`. Old links redirect, but update your clone URL with `git remote set-url origin https://github.com/messyvirgo-coin/messyvirgo-artwork-creator.git` if needed.

Put your Messy source as a **transparent PNG** (checkerboard in Photoshop/Figma = transparency) for avatar and scene.

---

## First-time setup (do once)

Open a terminal in the project folder, then:

**Step 1 — Install the tool**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

On **Windows** (Command Prompt or PowerShell in the project folder):

```text
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

After this, `mvac` should work. If `mvac` is not found, try `python3 -m mv_artwork_creator` instead of `mvac` in the commands below.

**Step 2 — Add your API key**

```bash
cp .env.example .env
```

Open `.env` in any text editor and replace the placeholder with your real key:

```text
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Save the file. Keep this key private (do not share or commit it).

**Step 3 — Check that it works (no charge for a dry run)**

```bash
mvac avatar input/messy.png --dry-run
```

You should see a plan (how many images, which angles) and **no** images generated yet. If you see an error about a missing API key, fix `.env`.

The first time you run `mvac avatar`, `mvac scene`, or `mvac messy-fy` (even with `--dry-run`), the tool creates a **`config/`** folder with copies of the default prompt and model files. **Edit those files** to customize behavior — they are yours and are not tracked by git.

---

## Customizing prompts and models

| What | Where to edit |
|------|----------------|
| Avatar angles, shots, style text | `config/avatar_prompts.yaml` |
| Scene brand rules | `config/scene_prompts.yaml` |
| Messy-fy repaint rules | `config/messy_fy_prompts.yaml` |
| Default AI models per command | `config/models.yaml` |

The `config/` folder appears automatically the first time you run a generator. Factory defaults stay inside the installed package; you normally **never** edit those.

**Useful commands:**

```bash
mvac config path    # show where config/ lives
mvac config init    # copy any missing default files into config/
mvac config reset   # restore all config/ files from factory defaults
```

To run once with factory defaults without touching `config/`, add `--factory-defaults` to `avatar`, `scene`, or `messy-fy`.

---

## How to generate images

Always run commands from the project folder with the virtual environment active (`source .venv/bin/activate`).

Results are saved under `output/` (created automatically).

### Avatar — 21 reference images

```bash
# 1) Preview the plan (safe, no API images yet)
mvac avatar input/messy.png --dry-run

# 2) Try ONE image first
mvac avatar input/messy.png --test --output-dir output/test-avatars

# 3) Full set (takes a while — 21 images)
mvac avatar input/messy.png --output-dir output/avatars
```

Files look like `output/avatars/front__portrait.png`, `right_side__full_body.png`, etc.

### Scene — one environment image

Describe **where** Messy is and **what she is doing** (not a new outfit — that comes from your PNG):

```bash
mvac scene input/messy.png \
  --setting "a neon city avenue after rain" \
  --action "walking past a trading billboard with calm confidence" \
  --dry-run

mvac scene input/messy.png \
  --setting "a neon city avenue after rain" \
  --action "walking past a trading billboard" \
  --filename neon-city-walk
```

Output: `output/scenes/neon-city-walk.png` (or similar).

**Tips:** Be concrete (“office at sunset”, not “nice place”). For charts on screens, say “chart on a wall display”, not “candles” (the AI may draw wax candles).

### Messy-fy — restyle an existing image

```bash
mvac messy-fy input/photo.jpg --hint "do not change any text" --dry-run

mvac messy-fy input/photo.jpg --hint "do not change any text" --filename styled
```

Output: `output/messyfied/styled.png`.

---

## Browser UI (easier option)

If you prefer forms instead of typing commands:

```bash
mvac web
```

Open the address shown in the terminal (usually [http://127.0.0.1:8765/](http://127.0.0.1:8765/)). Fill in paths (e.g. `input/messy.png`), settings, and use **Dry run** first.

The page stays busy until generation finishes — do not close the browser tab during a long run.

---

## Optional: transparent backgrounds

**You can stop after avatar generation** and keep white-background PNGs. Most users do not need this step.

Only continue if you need images **without** a white background **and** your computer is reasonably fast. This step runs **on your machine** (not OpenRouter) and can be slow for 21 images.

**Extra install (once):**

```bash
pip install -e ".[rembg]"
```

**Then:**

```bash
mvac remove-background --input-dir output/avatars \
  --output-dir output/avatars-transparent --overwrite
```

On a weak PC, skip `rembg` or ask someone technical for help. Do **not** use background removal on full **scene** images unless you want to delete the environment.

---

## If something goes wrong

| What you see | What to do |
|--------------|------------|
| Missing API key / credential | Check `.env` has `OPENROUTER_API_KEY=...` and you saved the file |
| Must be a transparent PNG | Export Messy as PNG **with** transparency (RGBA) |
| Scene setting/action empty | Fill both `--setting` and `--action` |
| Command `mvac` not found | Activate the venv (`source .venv/bin/activate`) or use `python3 -m mv_artwork_creator` |
| Generation skipped an image | Normal if you run the same command again; add `--regenerate` to force redo |
| `No onnxruntime` (background removal) | Run `pip install -e ".[rembg]"` or skip background removal |

---

## Re-running and fixing one image

- **Run the same command again** — already-finished images are skipped.
- **Redo everything** — add `--regenerate` to the command.
- **Redo one avatar angle** — delete that image’s `.png` and `.json` in the output folder, then run again with `--preset angle:shot` (e.g. `--preset right_side:full_body`).

---

## For technical users

<details>
<summary>Install with pipx, models, CLI flags, prompt files, tests</summary>

**pipx (global `mvac` without venv):**

```bash
pipx install .
```

**Default AI models** are set in `config/models.yaml` (copied on first run; aliases `seedream` and `nano-banana`). Override per run with `--model seedream`. You do not need model settings in `.env`.

**CLI overview:**

```text
mvac avatar <source.png> [--dry-run] [--test] [--preset angle:shot] ...
mvac scene <source.png> --setting "..." --action "..." [--filename stem] ...
mvac messy-fy <image> [--hint "..."] [--remove-background] ...
mvac remove-background [--input-dir DIR] [--method rembg|flood]
mvac sharpen [--input-dir DIR]
mvac config {init|reset|path}
mvac web [--port 8899]
```

**Prompt libraries** (edit to tune style): YAML files in `config/` (see [Customizing prompts and models](#customizing-prompts-and-models)).

**Tests:**

```bash
python3 -m unittest discover -s tests -v
```

</details>

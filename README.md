# Lloid

A local home bar platform built with Python + Flask.

## Features

- **Inventory** — Live bottle inventory editable in place, sourced from `Data/bar_inventory.csv`
- **Cocktails** — Browsable, searchable database with filter for cocktails you can make right now
- **New Cocktail** — Form to add recipes to `Data/cocktails.json`
- **Finder** — AI-powered cocktail recommender (Claude) guided by your inventory and mood
- **Designer** — AI cocktail creator (Claude) that designs original recipes and optionally saves them

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env (required only for Finder and Designer)
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Data files

- `Data/bar_inventory.csv` — bottle inventory (editable from the app or directly)
- `Data/cocktails.json` — cocktail database (editable from the app or directly)

Both files are human-readable and version-controlled. The Finder and Designer AI features use `claude-sonnet-4-6` and require an `ANTHROPIC_API_KEY`.

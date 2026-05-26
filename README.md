# Lloid

A local home bar management platform built with Python + Flask. Tracks your bottle inventory, cocktail database, and pantry staples — with AI-powered recipe finding and design via Claude.

## Features

### Bottles
Browse your bar as a card grid. Each bottle shows category, style, origin, ABV, and availability. Click any card to open a detail drawer with:
- **Availability toggle** — mark a bottle in or out of stock (affects "Can Make" across the app)
- **Editable details** — name, category, style, origin, age, ABV, producer, use (Cocktail / Premium / Neat Only)
- **Tasting notes** — freetext nose, palate, and finish fields
- **Flavor tags** — 88 curated descriptors across 14 groups (Tropical Fruit, Citrus, Stone Fruit, Dried Fruit, Floral, Herbal, Baking Spice, Heat, Sweet & Caramel, Chocolate & Coffee, Wood & Oak, Earth & Smoke, Funk & Ferment, Texture & Other)

### Cocktails
Searchable, filterable card grid of recipes. Filters include category, source, creator, "Can Make" (based on current inventory), and personal feedback.

- **Can Make** — real-time availability check against bottles, pantry staples, and specialty items; respects out-of-stock flags
- **Feedback** — mark cocktails as tried, rate them (Like / Dislike / Needs Work), and favorite them
- **Version history** — every edit is preserved; restore any prior version
- **Sync** — pull updates from `Data/cocktails.json` without overwriting your personalized recipes

### New / Edit Cocktail
Full recipe editor with drag-to-reorder ingredients. Each ingredient can be typed as:
- **Auto** — matched against inventory and pantry automatically
- **Specialty** — linked explicitly to a specialty pantry item by ID
- **Pantry staple** — treated as always available

Auto-saline injection: recipes with ≥ ½ oz of citrus juice automatically get 5 drops of Saline Solution appended on sync.

### Pantry
Two sections:

**Pantry Staples** — ingredients always assumed in stock for recipe matching (simple syrup, bitters, citrus juice, etc.). Each item has a stock toggle; out-of-stock staples are excluded from availability checks.

**House-Made & Specialty** — syrups, tinctures, and infusions you prepare yourself. Each card holds a name, description, recipe, and an in-stock toggle. Specialty items link from ingredient lists in recipe detail views.

### Ask Lloid (AI)
Three modes powered by Claude:
- **Find** — recommends cocktails you can make right now based on your inventory and mood
- **Riff** — suggests variations on a cocktail you describe
- **Create** — designs an original recipe and optionally saves it to your database

### Bookshelf
Reference library of cocktail books and resources.

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
python app.py
# or: make start
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser. On a local network, `make ip` prints the address other devices can reach.

The `ANTHROPIC_API_KEY` is only required for the Ask Lloid feature. All other features work offline.

### Makefile targets

| Command | Description |
|---|---|
| `make start` | Start the server |
| `make stop` | Kill the server |
| `make restart` | Stop and restart |
| `make install` | `pip install -r requirements.txt` |
| `make ip` | Print local and network URLs |

---

## Data files

| File | Description |
|---|---|
| `Data/bar_inventory.csv` | Bottle inventory — editable from the app or directly |
| `Data/pantry.json` | Pantry staples, specialty items, and out-of-stock lists |
| `Data/cocktails.json` | Shared cocktail catalog (synced from app) |
| `Data/lloid.db` | SQLite database — cocktail recipes, version history, feedback, bottle tasting notes |

All flat files are human-readable and version-controlled. The SQLite DB is the source of truth for recipes at runtime; `cocktails.json` is used for bulk sync and bootstrapping.

---

## Architecture

```
app.py          Flask routes and business logic
db.py           SQLite persistence (cocktails, history, feedback, bottle notes)
harmonize.py    Bulk-normalizes cocktails.json (auto-saline, field cleanup)
static/
  style.css     All styles (dark theme, CSS custom properties)
  app.js        Client-side filtering, feedback, and toast notifications
templates/      Jinja2 templates (one per page + base.html)
Data/           Flat-file data and SQLite DB
```

The AI features use `claude-sonnet-4-6` via streaming for real-time responses.

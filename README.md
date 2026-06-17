# Lloid

A local home bar management platform built with Python + Flask. Tracks your bottle inventory, cocktail database, and pantry staples — with AI-powered recipe finding and design via Claude.

## Features

### Bottle Shelf
Browse your bar as a card grid. Each bottle shows category, style, origin, ABV, and availability. Click any card to open a detail drawer with:
- **Availability toggle** — mark a bottle in or out of stock (affects "Can Make" across the app)
- **Editable details** — name, category, style, country/region of origin, age, ABV, producer, use (Cocktail / Premium / Neat Only)
- **Tasting notes** — freetext nose, palate, and finish fields
- **Flavor tags** — 90+ curated descriptors across 14 groups (Tropical Fruit, Citrus, Stone Fruit, Dried Fruit, Floral, Herbal & Vegetal, Baking Spice, Heat & Pepper, Sweet & Caramel, Chocolate & Coffee, Wood & Oak, Earth & Smoke, Funk & Ferment, Texture & Other); tags are color-coded by category on bottle cards
- **Spirit details** — production info for rum, whiskey, and agave spirits:
  - *Still type*: Pot, Column, or custom
  - *Fermentation materials*: Molasses, Cane Juice, Dunder, Muck, etc.; custom values persist globally
  - *Agave species*: 12 built-in varieties (Espadín, Blue Weber, Tobalá, Cenizo, Salmiana, etc.) + custom
  - *Mash bill*, *barrel type*, *barrel fill*, *barrel climate*, *barrel duration*
- **Distilleries** — attach one or more distilleries to a bottle via typeahead picker; distilleries track name, region, and country
- **Tech sheet upload** — photograph or upload a distillery tech sheet; Claude extracts production details automatically
- **Bottle Rankings** — ELO-based head-to-head ranking (see below)
- **ABV estimation** — recipe detail pages estimate ABV from ingredients when bottle ABV is known

### Adding Bottles
Open the **+** modal to add a new bottle. Includes a distillery typeahead with inline "Create new distillery" form, and an optional tech sheet upload that pre-fills production details via AI extraction.

### Cocktails
Searchable, filterable card grid of recipes. Filters include category, source, creator, "Can Make" (based on current inventory), and personal feedback. Each card shows a short descriptor tagline when one is set.

- **Can Make** — real-time availability check against bottles, pantry staples, and specialty items; respects out-of-stock flags
- **Geographic matching** — ingredient modifiers like "Jamaican rum" match bottles by Country/Region
- **Descriptor** — short italic tagline shown on the card and detail page (e.g. "A riff on the Toronto with aged rum")
- **Feedback** — mark cocktails as tried, rate them (Like / Dislike / Needs Work), and favorite them
- **Version history** — every edit is preserved; restore any prior version
- **Sync** — pull updates from `Data/cocktails.json` without overwriting your personalized recipes

### New / Edit Cocktail
Full recipe editor with drag-to-reorder ingredients. Each ingredient can be typed as:
- **Auto** — matched against inventory and pantry automatically
- **Specialty** — linked explicitly to a specialty pantry item by ID
- **Pantry staple** — treated as always available

Ingredients are automatically reordered by build tier (rinse → bitters → sweeteners → juices → modifiers → spirits → toppers → garnish) on import.

Auto-saline injection: recipes with ≥ ½ oz of citrus juice automatically get 5 drops of Saline Solution appended on sync.

### Pantry
Two sections:

**Pantry Staples** — readily available or easily purchased ingredients (juice, sugar, eggs, bitters, soda). Each item has a stock toggle; out-of-stock staples are excluded from availability checks.

**House-Made & Specialty** — preparations that take time to make at home: syrups, infusions, tinctures, cordials. Each card holds a name, description, recipe, and an in-stock toggle. Toggle in-stock when a fresh batch is ready. Specialty items link from ingredient lists in recipe detail views.

### Cocktail Lists
Save named collections of cocktails (e.g. "Friday Night", "Tiki Party"). Each list shows a live "Can Make" badge per entry. Open any recipe and tap **+ List** to add it to a new or existing list.

### Bottle Rankings
Head-to-head ELO ranking system for your bottles. Rate any bottle against others in its category through a simple matchup flow:

1. **Choose a list** — pick from default category lists (Rum, Whiskey, etc.) or a custom list you create (e.g. "Jamaican Rum", "Rye Whiskey")
2. **Give an impression** — Love it / Like it / It's okay / Not for me seeds an initial ELO score and tier
3. **Head-to-head rounds** — five matchups against nearby-ranked bottles; pick your preferred or skip with "Too Tough to Call"
4. **Result** — see your bottle's final score and tier chip (Elite / Great / Good / Fair / Pass)

ELO scores are per bottle per list. K-factor tapers as match count grows (64 → 32 → 16) to stabilize scores over time. Rankings are visible on the bottle card and in the drawer. The **Bottle Rankings** nav page shows all lists with top-3 previews; drill into any list for the full leaderboard. Clicking a bottle name in a leaderboard opens its info drawer on the Bottle Shelf.

### Ask Lloid (AI)
Three modes powered by Claude:
- **Find** — recommends cocktails you can make right now based on your inventory and mood
- **Riff** — suggests variations on a cocktail you describe
- **Create** — designs an original recipe and optionally saves it to your database

### Bookshelf
Reference library of cocktail books and resources.

### Settings
- **Push Notifications** — configure ntfy.sh topic for order notifications on mobile
- **Distilleries** — edit or delete any distillery record (name, region, country)
- **Spirit Options** — view all still-type, fermentation material, and agave species values in use across your bottles (with usage counts); rename or delete any value; changes propagate to all bottle records
- **Flavor Tags** — view all tasting note tags in use across your bottles, grouped by category; rename or delete any tag; changes propagate to all bottle records

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
python app.py
# or: make start
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser. On a local network, `make ip` prints the address other devices can reach.

The `ANTHROPIC_API_KEY` is only required for the Ask Lloid and tech sheet features. All other features work offline.

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
| `Data/distilleries.json` | Distillery records (name, region, country) — linked to bottles by ID |
| `Data/pantry.json` | Pantry staples, specialty items, and out-of-stock lists |
| `Data/cocktails.json` | Shared cocktail catalog (synced from app) |
| `Data/lloid.db` | SQLite database — cocktail recipes, version history, feedback, bottle tasting notes, spirit details, ELO rankings, cocktail lists, app settings (gitignored; personal data stays local) |

All flat files are human-readable and version-controlled. The SQLite DB is the source of truth for recipes at runtime; `cocktails.json` is used for bulk sync and bootstrapping.

---

## Architecture

```
app.py                  Flask routes and all business logic
db.py                   SQLite persistence (cocktails, history, feedback, bottle notes, ELO, settings)
static/
  style.css             All styles (dark theme, CSS custom properties)
  app.js                Client-side filtering, feedback, and toast notifications
templates/              Jinja2 templates (one per page + base.html)
Data/                   Flat-file data (inventory CSV, distilleries JSON, pantry JSON, cocktail catalog)
harmonize.py            Bulk-normalizes cocktails.json (auto-saline, field cleanup)
reorder_ingredients.py  One-shot: reorder recipe ingredients by build tier
import_rumx.py          Import tasting data from RumX CSV export
import_whiskey.py       Import tasting data from whiskey CSV + catalog JSON
fix_rum_distilleries.py Link rum/agave bottles to distillery records
scale_specialty.py      Scale specialty item quantities
start_lloid.sh          Production start (used by cron on bar nights)
stop_lloid.sh           Production stop
```

The AI features use `claude-sonnet-4-6` via streaming for real-time responses.

### Data model: CSV vs SQLite split

**`Data/bar_inventory.csv`** — bottle identity fields: `Name`, `Category`, `Style`, `Country`, `Region`, `Age`, `ABV`, `Producer`, `Use`

**SQLite `bottle_notes`** — per-bottle annotations:
- `in_stock` — affects "Can Make" across the app
- `nose`, `palate`, `finish` — tasting notes
- `flavor_tags` — JSON list of tag values
- `spirit_details` — JSON blob with production info (still type, fermentation materials, agave species, mash bill, barrel details, distillery IDs, notes)

### Ingredient matching
`CATEGORY_MAP` maps ingredient names to bottle Style values. Geographic modifiers (Jamaican, Cuban, etc.) match against `Country + Region`. Aged NAS bottles match recipes that specify an age range.

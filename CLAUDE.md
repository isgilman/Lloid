# Lloid — Claude Code Context

## What this is

Lloid is Ian's personal home bar management app. It runs on a Mac on the local network during weekend bar hours (Fri/Sat/Sun) and is accessed by guests on mobile. Stack: Python/Flask + SQLite + Jinja2, with Claude AI for the "Ask Lloid" feature.

## How to run

```bash
python app.py          # dev server on port 5001
make start / make stop # or via Makefile
./start_lloid.sh       # production start (used by cron)
```

The server is also scheduled via crontab:
- Friday 5–11 PM, Saturday 3–11 PM, Sunday 3–8 PM

Preview server config is in `.claude/launch.json` (port 5001).

`use_reloader=False` is set intentionally — the Flask reloader causes semaphore leaks when the server is killed by the cron stop script.

## Architecture

```
app.py          Flask routes + all business logic
db.py           SQLite persistence layer
static/
  style.css     All styles (dark theme, CSS custom properties)
  app.js        Client-side filtering, sorting, feedback, toasts
templates/      Jinja2 templates (base.html + one per page)
Data/
  bar_inventory.csv   Bottle identity fields (source of truth for shelf)
  cocktails.json      Shared recipe catalog (bootstraps/syncs DB)
  pantry.json         Pantry staples + specialty items
  lloid.db            SQLite DB (gitignored — personal data)
reorder_ingredients.py  One-shot script: reorder recipe ingredients by build tier
harmonize.py    Bulk-normalizes cocktails.json
```

## Data model: CSV vs SQLite split

**`Data/bar_inventory.csv`** — bottle identity (the "what is this bottle" fields):
```
INVENTORY_FIELDS = ['Name', 'Category', 'Style', 'Country', 'Region', 'Age', 'ABV', 'Producer', 'Use']
```
`Country` = country of origin (e.g. "Jamaica"). `Region` = state/province (e.g. "Michigan"). These replaced the old single `Origin` field.

**SQLite `bottle_notes` table** — per-bottle annotations:
- `in_stock` (bool) — affects "Can Make" across the whole app
- `nose`, `palate`, `finish` (text) — tasting notes
- `flavor_tags` (JSON list of strings)
- `spirit_details` (JSON blob — see below)

**SQLite `cocktails` table** — recipes stored as JSON blobs:
- `is_local` (0 or 1) — see critical constraint below
- `data` column holds the full recipe JSON

## CRITICAL: Never modify is_local=1 recipes

Recipes with `is_local=1` are Ian's personal/customised versions. They are protected from automated changes. **Do not update them in any bulk script, sync, or automated fix** unless Ian explicitly says to include them for a specific task.

The one exception made so far: the ingredient reorder script (`reorder_ingredients.py`) was explicitly authorized by Ian to run on all recipes including personalized ones.

## spirit_details JSON schema

Stored in `bottle_notes.spirit_details`. Structure:
```json
{
  "fermentation_materials": ["molasses", "cane-juice"],  // rum only
  "mash_bill": [{"grain": "corn", "pct": 75}, {"grain": "rye", "pct": 21}],  // whiskey (omit when blend_components present)
  "barrel_type": "ex-bourbon",
  "barrel_fill": "first-fill",
  "barrel_climate": "tropical",   // or "temperate"
  "barrel_duration": "5 years",
  "still_type": ["pot"],          // array: "pot", "column", "hybrid", or custom values
  "distilleries": ["distillery-slug"],  // internal reference slugs
  "blend_components": [           // use instead of top-level mash_bill for sourced blends
    {
      "pct": 90,
      "age": "7 years",
      "origin": "Indiana",
      "style": "Straight Rye Whiskey",
      "mash_bill": [{"grain": "rye", "pct": 51}, {"grain": "corn", "pct": 45}, {"grain": "malted barley", "pct": 4}]
    }
  ],
  "notes": "free text"
}
```

Valid fermentation materials for rum: `molasses`, `cane-juice`, `cane-syrup`, `turbinado`, `piloncillo`, `dunder`, `muck`

When `blend_components` is present (sourced blends, collaborative series), omit the top-level `mash_bill` — the per-component mash bills in `blend_components` are the source of truth. Each component should have `pct`, `age`, `origin`, `style`, and `mash_bill`.

## Ingredient matching and "Can Make"

`app.py:load_inventory_with_notes()` merges CSV + SQLite for every page load. Matching is done by `clean()` (lowercase + strip diacritics + strip punctuation):

```python
CATEGORY_MAP = {...}   # ingredient name → list of bottle Style values that match
GEO_MODIFIERS = {'jamaican': 'jamaica', 'cuban': 'cuba', 'barbadian': 'barbados'}
```

Geographic modifier matching uses `Country + ' ' + Region` (not the old `Origin` field).

## Creator token system

`creator_tokens(creator_string)` in `app.py` splits `"A, B and C (Bar, City)"` into individual tokens: `["A (Bar, City)", "B (Bar, City)", "C (Bar, City)"]`. These are stored as pipe-separated values in `data-creator` on cocktail cards, and JS splits on `|` for filter matching.

Creator format convention: `"Name (Bar Name, City)"`.

## Ingredient build order tiers

Defined in `reorder_ingredients.py` and used by `classify()`:
```
0  rinse/prep
1  dashes / drops / bitters
2  syrups & sweeteners
3  juices & non-alcoholic
4  low-ABV modifiers (<25%: vermouth, sherry, etc.)
5  spirits & high-proof (≥25%)
6  barspoons (tsp converted to barspoon)
7  toppers (champagne, soda, beer) & ice
8  garnish
```

Within tiers 1–5: volume ascending. All `tsp` units are canonical barspoon.

## JS filtering patterns

- `normSearch(s)` in `app.js` normalizes punctuation for comparison
- Filter data attributes use `|` as separator for multi-value fields (e.g. `data-creator`, `data-tags`)
- `filterBottles()` and `filterCocktails()` read from data attributes; spirit details fields (fermentation, mash bill, barrel, notes) are concatenated into the search index

## Authoritative external sources

- **Rum X** (rum-x.com) — authoritative source for rum production info (fermentation materials, distillery details)

## SQLite write safety

The production server keeps a long-lived connection to `lloid.db`. Any bulk write script that runs outside the server **must** checkpoint the WAL before closing, or the server's existing connection will see a malformed image:

```python
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.commit()
conn.close()
```

Always end bulk DB scripts with those three lines. `conn.commit()` + `conn.close()` alone is not sufficient — it leaves a 1.5MB+ WAL file that the server's open connection can't reconcile.

## Key patterns to maintain

- Bottles always sorted alphabetically (`key=lambda b: b.get('Name', '').lower()`)
- `Use` field values: `Cocktail`, `Premium Cocktail`, `Neat Only`
- Curly apostrophes and quotes appear in some bottle names in the CSV (e.g. `Uncle John’s Apple Brandy`, `Eastern Kille Genepy L’epicca`, `The Rums of México – "Caldo"`) — match with the exact Unicode character when writing `set_bottle_note()` calls or any DB update keyed by bottle name
- `.drawer-view-field-label { width: 90px }` — keep this wide enough for "Fermentation" to not overflow

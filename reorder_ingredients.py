"""One-shot: reorder ingredients in every cocktail to match the house build order.

Tiers (build order):
  0 rinse/prep lines           — forced first
  1 drops, dashes, bitters
  2 syrups & sweeteners
  3 juices & other nonalcoholic
  4 low-ABV modifiers (<25% — vermouth, sherry, etc.)
  5 spirits & high-proof (>=25%)
  6 barspoons (incl. converted tsp) — right before stirring
  7 toppers (champagne, soda, beer…) & ice — added after the stir/shake
  8 garnish-like items — last

Within tiers 1–5: volume ascending (stable for ties / unknown volume → end of tier).
All `tsp` units are converted to `barspoon`/`barspoons`.

Usage: python reorder_ingredients.py [--apply]   (default is dry-run)
"""
import json
import re
import sqlite3
import sys

sys.path.insert(0, '.')
import app as A

DB = 'Data/lloid.db'

# ── Ingredient ABV map from inventory ─────────────────────────────────────────
inventory = A.load_inventory_with_notes()
bottle_abv_map = {}
for b in inventory:
    abv_str = (b.get('ABV') or '').strip().rstrip('%')
    try:
        bottle_abv_map[A.normalize(b['Name'])] = float(abv_str) / 100.0
    except ValueError:
        pass

_WORD = lambda w, s: re.search(r'\b' + w + r'\b', s) is not None

GARNISH_PAT  = re.compile(r'\b(twists?|wheels?|wedges?|peels?|swaths?|swatch(es)?|fans?|sprig for garnish|garnish)\b')
TOPPER_PAT   = re.compile(r'\b(champagne|prosecco|sparkling|cava|soda|seltzer|beer|ale|lager|stout|tonic|cola|ginger beer)\b')
TOPPER_EXCL  = re.compile(r'\b(vinegar|cognac|brandy|acid|syrup|reduction|shrub)\b')
ICE_PAT      = re.compile(r'\b(pebble ice|crushed ice|ice cube|block ice)\b|^ice\b')
SWEET_PAT    = re.compile(r'\b(syrup|honey|agave|grenadine|orgeat|cordial|sugar|maple|falernum|gomme|sweetener|demerara cube)\b')
NONALC_PAT   = re.compile(r'\b(juice|puree|purée|water|tea|coffee|espresso|milk|cream|egg|leaf|leaves|cucumber|berries|strawberry|shrub|lemon|lime|pineapple|verjus|nectar|cider)\b')
LOWABV_PAT   = re.compile(r'\b(vermouth|sherry|port|porto|madeira|marsala|lillet|cocchi|quinquina|americano|sake|wine|byrrh|dubonnet|kina)\b')
BITTERS_PAT  = re.compile(r'\b(bitters|tincture|saline|salt solution|pinch)\b')


def classify(ing):
    name  = A.clean(ing.get('name', ''))
    unit  = (ing.get('unit') or '').strip().lower()
    notes = (ing.get('notes') or '').lower()

    # 0 — rinse / prep instruction lines
    if unit == 'rinse' or name.startswith('rinse') or 'rinse' in notes:
        return 0
    # oleo saccharum is a sweetener despite containing "peel"
    if 'oleo' in name:
        return 2
    # 8 — garnish-like / atomizer spritz
    if unit == 'spritz' or GARNISH_PAT.search(name):
        return 8
    # 7 — toppers & ice
    if (TOPPER_PAT.search(name) and not TOPPER_EXCL.search(name)) or 'top' in notes.split():
        return 7
    if ICE_PAT.search(name):
        return 7
    # 6 — barspoons (tsp are converted to barspoon before this runs)
    if unit in ('barspoon', 'barspoons', 'tsp'):
        return 6
    # 1 — drops / dashes / bitters
    if unit in ('dash', 'dashes', 'drop', 'drops') or BITTERS_PAT.search(name) \
            or name.startswith('dash '):
        return 1
    # 2 — syrups & sweeteners
    if SWEET_PAT.search(name):
        return 2
    # 3/4/5 — split by estimated ABV
    abv = A._ingredient_abv(ing, bottle_abv_map)
    if abv is not None:
        if abv == 0:
            return 3
        return 4 if abv < 0.25 else 5
    # Keyword fallbacks for unmatched ingredients
    if NONALC_PAT.search(name):
        return 3
    if LOWABV_PAT.search(name):
        return 4
    return 5  # default: assume spirit-strength


def volume_oz(ing):
    amt = A._parse_amount(ing.get('amount'))
    if amt is None:
        return float('inf')
    unit = (ing.get('unit') or '').strip().lower()
    if not unit:
        return float('inf')          # counted items (egg, cube) — keep at end of tier
    factor = A._UNIT_TO_OZ.get(unit)
    if factor is None:
        return float('inf')
    return amt * factor


def convert_tsp(ing):
    unit = (ing.get('unit') or '').strip().lower()
    if unit == 'tsp':
        amt = A._parse_amount(ing.get('amount'))
        ing['unit'] = 'barspoons' if (amt is not None and amt > 1) else 'barspoon'
        return True
    return False


def reorder(cocktail):
    """Return (changed, new_ingredients, tsp_converted_count)."""
    ings = cocktail.get('ingredients', [])
    if len(ings) < 2:
        # still may need tsp conversion
        n = sum(convert_tsp(i) for i in ings)
        return n > 0, ings, n

    n_tsp = sum(convert_tsp(i) for i in ings)
    before = json.dumps(ings, sort_keys=True)
    keyed = [(classify(i), volume_oz(i), idx, i) for idx, i in enumerate(ings)]
    keyed.sort(key=lambda t: (t[0], t[1], t[2]))   # tier, volume, original order
    new = [t[3] for t in keyed]
    changed = json.dumps(new, sort_keys=True) != before
    return (changed or n_tsp > 0), new, n_tsp


def main(apply=False):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name, data, is_local FROM cocktails").fetchall()

    changed_count = tsp_total = 0
    samples = []
    for r in rows:
        d = json.loads(r['data'])
        changed, new_ings, n_tsp = reorder(d)
        tsp_total += n_tsp
        if not changed:
            continue
        changed_count += 1
        d['ingredients'] = new_ings
        if len(samples) < 8:
            samples.append((r['name'], r['is_local'], new_ings))
        if apply:
            conn.execute("UPDATE cocktails SET data=? WHERE id=?",
                         (json.dumps(d, ensure_ascii=False), r['id']))
    if apply:
        conn.commit()

    print(f"{'APPLIED' if apply else 'DRY RUN'}: {changed_count}/{len(rows)} recipes changed, "
          f"{tsp_total} tsp→barspoon conversions")
    print("\nSample results:")
    for name, is_local, ings in samples:
        print(f"\n  {name}{' [personalized]' if is_local else ''}:")
        for i in ings:
            t = classify(i)
            print(f"    [{t}] {i.get('amount','')} {i.get('unit','')} {i.get('name','')}")
    conn.close()


if __name__ == '__main__':
    main(apply='--apply' in sys.argv)

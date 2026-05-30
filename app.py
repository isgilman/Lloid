import os
import csv
import json
import uuid
import re
import random
import functools
import unicodedata
import base64
from collections import Counter
from datetime import datetime
from pathlib import Path
import db as _db
from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, Response, stream_with_context, flash)
from dotenv import load_dotenv
import anthropic

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'lloid-dev-key-change-in-production')

# Bootstrap SQLite DB on startup (no-op if already initialised)
_db.init_db()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'Data'
INVENTORY_FILE = DATA_DIR / 'bar_inventory.csv'
COCKTAILS_FILE = DATA_DIR / 'cocktails.json'
PANTRY_FILE    = DATA_DIR / 'pantry.json'

INVENTORY_FIELDS = ['Name', 'Category', 'Style', 'Origin', 'Age', 'ABV', 'Producer', 'Use']

# Curated style/type categories shown in filter chips and the new/edit cocktail form.
# Each tuple is (tag_value_stored_in_tags_array, display_label).
STYLE_TAG_DEFS = [
    ('classic',        'Classic'),
    ('modern classic', 'Modern Classic'),
    ('tiki',           'Tiki'),
    ('sour',           'Sour'),
    ('swizzle',        'Swizzle'),
    ('julep',          'Julep'),
    ('sling',          'Sling'),
    ('fizz',           'Fizz'),
    ('flip',           'Flip'),
    ('daiquiri',       'Daiquiri'),
    ('punch',          'Punch'),
    ('cobbler',        'Cobbler'),
    ('non-alcoholic',  'Non-Alcoholic'),
    ('low-abv',        'Low-ABV'),
]
STYLE_TAG_VALUES = {v for v, _ in STYLE_TAG_DEFS}

# Default pantry used only to bootstrap pantry.json if it doesn't exist
DEFAULT_PANTRY_STANDARD = [
    'absinthe', 'absinthe rinse', 'agave nectar', 'agave syrup',
    'angostura bitters', 'aromatic bitters', 'barrel-aged bitters',
    'basil', 'bitters', 'black walnut bitters', 'buttermilk',
    'cane syrup', 'cardamom bitters', 'chocolate bitters',
    'club soda', 'coconut cream', 'cola', 'cream', 'cucumber',
    'demerara sugar', 'demerara syrup', 'egg', 'egg white', 'falernum',
    'fees bitters', 'fresh lemon juice', 'fresh lime juice',
    'ginger ale', 'ginger beer', 'grapefruit juice', 'grenadine',
    'heavy cream', 'honey syrup', 'honey-ginger syrup', 'ice', 'jalapeño',
    'lemon juice', 'lime juice', 'mint', 'mole bitters',
    'orange bitters', 'orange juice', 'orgeat', 'pastis',
    "peychaud's bitters", 'pineapple juice', 'raspberry syrup',
    'rich demerara syrup', 'rich simple syrup', 'rosemary',
    'saline', 'saline solution', 'salt', 'simple syrup',
    'soda water', 'sparkling water', 'sugar', 'sugar cube',
    'thyme', 'tonic water', 'water',
]

CATEGORY_MAP = {
    'rum': ['rum', 'rhum', 'cachaça', 'clairin', 'batavia arrack'],
    'aged rum': ['aged rum', 'rhum agricole vieux', 'aged rhum'],
    'overproof rum': ['overproof rum', 'overproof'],
    'jamaican rum': ['rum'],  # cat_styles=['rum'] + geo_origin_filter='jamaica' = only Jamaican rums
    'rhum agricole': ['rhum agricole blanc', 'rhum agricole vieux'],
    'rhum agricole blanc': ['rhum agricole blanc'],
    'cachaça': ['cachaça'],
    'clairin': ['clairin'],
    'rye whiskey': ['straight rye', 'fat-washed rye'],
    'rye': ['straight rye', 'fat-washed rye'],
    'bourbon': ['straight bourbon'],
    'whiskey': ['straight rye', 'straight bourbon', 'japanese lended', 'irish blended', 'fat-washed rye'],
    'scotch': ['scotch', 'blended scotch', 'single malt scotch'],
    'irish whiskey': ['irish blended'],
    'japanese whisky': ['japanese lended'],
    'mezcal': ['mezcal'],
    'tequila': ['blanco tequila'],
    'blanco tequila': ['blanco tequila'],
    'reposado tequila': ['reposado tequila'],
    'sotol': ['sotol'],
    'gin': ['gin'],
    'vodka': ['vodka'],
    'cognac': ['cognac'],
    'calvados': ['calvados'],
    'pisco': ['pisco'],
    'apple brandy': ['apple brandy', 'calvados'],
    'brandy': ['cognac', 'calvados', 'apple brandy', 'pisco'],
    'aquavit': ['aquavit'],
    'soju': ['soju'],
    'sweet vermouth': ['sweet vermouth'],
    'dry vermouth': ['dry vermouth'],
    'blanc vermouth': ['blanc vermouth'],
    'bianco vermouth': ['blanc vermouth'],
    'vermouth': ['sweet vermouth', 'dry vermouth', 'blanc vermouth'],
    'campari': ['bitter aperitif'],
    'aperol': ['bitter aperitif'],
    'cynar': ['artichoke amaro'],
    'fernet': ['fernet'],
    'amaro nonino': ['amaro'],
    'amaro averna': ['amaro siciliano'],
    'amaro': ['amaro', 'fernet', 'amaro siciliano', 'rabarbaro amaro',
              'artichoke amaro', 'gentian amaro', 'herbal bitter'],
    'lillet': ['aperitif wine'],
    'lillet blanc': ['aperitif wine'],
    'cocchi americano': ['aperitif wine', 'quinquina'],
    'quinquina': ['quinquina'],
    'kina': ['quinquina'],
    'sherry': ['amontillado sherry', 'pedro ximénez sherry'],
    'amontillado': ['amontillado sherry'],
    'amontillado sherry': ['amontillado sherry'],
    'port': ['white port', 'tawny port'],
    'tawny port': ['tawny port'],
    'white port': ['white port'],
    'madeira': ['madeira'],
    'marsala': ['marsala'],
    'champagne': ['brut champagne', 'champagne', 'sparkling wine'],
    'dry champagne': ['brut champagne', 'champagne', 'sparkling wine'],
    'sparkling wine': ['sparkling wine', 'brut champagne', 'champagne'],
    'maraschino': ['maraschino'],
    'maraschino liqueur': ['maraschino'],
    'yellow chartreuse': ['herbal liqueur'],
    'green chartreuse': ['herbal liqueur'],
    'chartreuse': ['herbal liqueur', 'herbal elixir'],
    'elderflower liqueur': ['elderflower liqueur'],
    'st-germain': ['elderflower liqueur'],
    'orange liqueur': ['orange liqueur'],
    'dry curaçao': ['orange liqueur'],
    'triple sec': ['orange liqueur'],
    'cointreau': ['orange liqueur'],
    'ginger liqueur': ['ginger liqueur'],
    'allspice dram': ['allspice dram'],
    'suze': ['gentian aperitif'],
    'gentian': ['gentian aperitif', 'gentian amaro'],
    'benedictine': ['herbal liqueur'],
    'génépi': ['génépi'],
    'crème de cassis': ['crème de cassis'],
    'crème de cacao': ['cacao liqueur'],
    'white crème de cacao': ['cacao liqueur'],
    'dark crème de cacao': ['cacao liqueur'],
    'crème de menthe': ['crème de menthe'],
    'passion fruit liqueur': ['fruit liqueur'],
    'apricot liqueur': ['apricot liqueur'],
    'coffee liqueur': ['coffee liqueur'],
    'crème de banane': ['crème de banane'],
    'limoncello': ['limoncello'],
    'violet liqueur': ['violet liqueur'],
    'pine liqueur': ['pine liqueur'],
    'corn liqueur': ['corn liqueur'],
}

# Override the auto-derived search_term (clean(best_key)) for specific keys.
# Useful when the ingredient name doesn't work well as a bottle-shelf search,
# e.g. geographic adjectives like "jamaican" → search "rum jamaica" so the
# filterBottles substring check can span the category + origin fields.
CATEGORY_SEARCH_TERMS = {
    'jamaican rum': 'rum jamaica',
}

# Maps geographic adjectives that can appear in ingredient names to origin keywords.
# When detected, the bottle loop is restricted to bottles whose Origin contains the keyword.
# This lets "Jamaican Rum" match only Jamaican rums rather than any rum.
GEO_MODIFIERS = {
    'jamaican': 'jamaica',
    'cuban':    'cuba',
    'barbadian': 'barbados',
}


def normalize(s):
    return s.lower().strip() if s else ''


@functools.lru_cache(maxsize=4096)
def clean(s):
    """Lowercase + strip diacritics + strip punctuation for fuzzy matching.
    Unicode normalization lets 'Creme' == 'Crème', 'St-Germain' == 'St. Germain', etc.
    Cached — called thousands of times per page load across ingredients × bottles."""
    if not s:
        return ''
    # NFD decomposes accented chars; filtering Mn strips the combining marks
    s = unicodedata.normalize('NFD', s.lower().strip())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^\w\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


@functools.lru_cache(maxsize=16384)
def word_in(needle, haystack):
    """True if needle appears as whole word(s) in haystack.
    Single-word needles use fast set lookup; multi-word use substring
    (safe after clean() strips punctuation)."""
    n = clean(needle)
    h = clean(haystack)
    if not n or not h:
        return False
    n_parts = n.split()
    if len(n_parts) == 1:
        return n_parts[0] in h.split()   # O(words), no regex
    return n in h                         # phrase containment on cleaned text


def make_availability_checker(inventory, pantry):
    """Return a memoised checker bound to this inventory+pantry snapshot.
    Ingredient names repeat across hundreds of cocktails; caching the result
    per (name, is_premium) pair cuts the full-catalogue check from O(n²) to
    effectively O(unique_ingredients × bottles)."""
    _cache = {}
    def check(ing_name, is_premium=False):
        key = (ing_name, is_premium)
        if key not in _cache:
            _cache[key] = check_ingredient_available(ing_name, inventory, pantry, is_premium)
        return _cache[key]
    return check


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_inventory():
    bottles = []
    if INVENTORY_FILE.exists():
        with open(INVENTORY_FILE, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bottles.append(dict(row))
    return bottles


def save_inventory(bottles):
    with open(INVENTORY_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=INVENTORY_FIELDS)
        writer.writeheader()
        for b in bottles:
            writer.writerow({k: b.get(k, '') for k in INVENTORY_FIELDS})


def load_inventory_with_notes():
    """Load inventory CSV and merge bottle_notes (in_stock etc.) into each dict."""
    bottles = load_inventory()
    notes   = _db.get_all_bottle_notes()
    for i, b in enumerate(bottles):
        note = notes.get(b['Name'], {'in_stock': True, 'nose': '', 'palate': '', 'finish': '', 'flavor_tags': []})
        b['in_stock']    = note['in_stock']
        b['nose']        = note['nose']
        b['palate']      = note['palate']
        b['finish']      = note['finish']
        b['flavor_tags'] = note['flavor_tags']
        b['_index']      = i
    return bottles


def load_cocktails():
    if COCKTAILS_FILE.exists():
        with open(COCKTAILS_FILE, encoding='utf-8') as f:
            return json.load(f).get('cocktails', [])
    return []


def save_cocktails(cocktails):
    with open(COCKTAILS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'cocktails': cocktails}, f, indent=2, ensure_ascii=False)


def load_pantry():
    if PANTRY_FILE.exists():
        with open(PANTRY_FILE, encoding='utf-8') as f:
            p = json.load(f)
        if 'standard_out_of_stock' not in p:
            p['standard_out_of_stock'] = []
        return p
    # Bootstrap defaults
    pantry = {'standard': sorted(DEFAULT_PANTRY_STANDARD), 'specialty': [], 'standard_out_of_stock': []}
    save_pantry(pantry)
    return pantry


def save_pantry(pantry):
    with open(PANTRY_FILE, 'w', encoding='utf-8') as f:
        json.dump(pantry, f, indent=2, ensure_ascii=False)


def slugify(name):
    s = name.lower()
    s = re.sub(r"[^\w\s-]", '', s)
    s = re.sub(r'[-\s]+', '-', s)
    return s.strip('-')


def unique_id(name, existing_ids):
    base = slugify(name) or str(uuid.uuid4())[:8]
    candidate = base
    counter = 1
    while candidate in existing_ids:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


# ── Ingredient matching ───────────────────────────────────────────────────────

def check_ingredient_available(ing_name, inventory, pantry=None, is_premium=False):
    """Return (available: bool, source: str|None).

    is_premium: if True, bottles marked 'Premium Cocktail' are counted.
                if False (default), they are skipped.
    """
    ing = clean(ing_name)
    if not ing:
        return True, 'pantry'

    # Standard pantry check (word-boundary safe)
    pantry_std = pantry.get('standard', []) if pantry else DEFAULT_PANTRY_STANDARD
    std_oos = set(clean(x) for x in (pantry.get('standard_out_of_stock', []) if pantry else []))
    for p in pantry_std:
        pc = clean(p)
        if pc in std_oos:
            continue
        if pc == ing or word_in(pc, ing) or word_in(ing, pc):
            return True, 'pantry'

    # House-made / infused preparations — never auto-match a generic bottle.
    # They must be explicitly linked as specialty items or matched in the specialty check below.
    is_infused = 'infused' in ing.split()

    if not is_infused:
        # Bottle check — runs before specialty so a real bottle (e.g. "Sweet Vermouth" → Dolin Rouge)
        # always wins over a specialty preparation that merely *contains* the ingredient name
        # (e.g. "Chai Infused Sweet Vermouth" must not shadow plain "Sweet Vermouth").

        # Detect geographic modifiers (e.g. "jamaican" in "jamaican rum") so we can
        # restrict matching to bottles from that country of origin.
        geo_origin_filter = None
        for geo_adj, origin_kw in GEO_MODIFIERS.items():
            if word_in(geo_adj, ing):
                geo_origin_filter = origin_kw
                break

        # Pre-compute the longest CATEGORY_MAP key that matches this ingredient — O(keys), not O(keys×bottles).
        # Doing it here prevents the generic overlap check from firing before a precise
        # style mapping can route "crème de cacao" → "cacao liqueur" (not "crème de cassis").
        best_key = None
        for key in CATEGORY_MAP:
            kc = clean(key)
            if (kc == ing or word_in(kc, ing)) and (best_key is None or len(kc) > len(clean(best_key))):
                best_key = key
        cat_styles = [clean(s) for s in CATEGORY_MAP[best_key]] if best_key else []

        # Generic beverage words excluded from overlap check — too common to be meaningful
        stop = {'the', 'a', 'an', 'of', 'de', 'du', 'and', 'no', 'n', 'le',
                'liqueur', 'bitters', 'spirit', 'spirits', 'liquor'}

        def _eligible(bottle):
            use = normalize(bottle.get('Use', ''))
            if use == 'neat only':           return False
            if not bottle.get('in_stock', True): return False
            if use == 'premium cocktail' and not is_premium: return False
            return True

        # Pass 1 — Direct name containment (highest priority).
        # Scanned across ALL eligible bottles before any style/category matching so that
        # e.g. "Benedictine" always matches Bénédictine D.O.M. even when Yellow Chartreuse
        # (which shares style 'Herbal Liqueur') appears earlier in the inventory.
        # No geo_origin_filter here — a name match is already specific enough.
        for bottle in inventory:
            if not _eligible(bottle):
                continue
            bname = clean(bottle.get('Name', ''))
            if ing in bname or bname in ing:
                return True, bottle['Name']

        # Pass 2 — Style, category-map, and overlap matching.
        # Geo origin filter applied here (not in pass 1) so geographic ingredients
        # like "Jamaican Rum" only match Jamaican bottles via style/category, while
        # a bottle literally named "Jamaican Rum" (pass 1) would already have matched.
        for bottle in inventory:
            if not _eligible(bottle):
                continue

            bname   = clean(bottle.get('Name', ''))
            bstyle  = clean(bottle.get('Style', ''))
            bcat    = clean(bottle.get('Category', ''))
            borigin = clean(bottle.get('Origin', ''))

            if geo_origin_filter and geo_origin_filter not in borigin:
                continue

            # Style / category direct match (word-boundary — prevents "gin" matching "ginger")
            if ing == bstyle or word_in(ing, bstyle) or word_in(ing, bcat):
                return True, bottle['Name']

            # Category map — specific mapping checked BEFORE generic overlap so
            #    "crème de cacao" routes to cacao-liqueur bottles and not cassis ones.
            #    Origin is also checked so geographic entries like 'jamaican rum': ['rum']
            #    restrict to bottles from the right country.
            if cat_styles:
                for sc in cat_styles:
                    if (word_in(sc, bstyle) or word_in(sc, bcat)
                            or word_in(sc, bname) or word_in(sc, borigin)):
                        return True, bottle['Name']

            # Overlap — fallback ONLY for ingredients that have no CATEGORY_MAP entry.
            # When best_key exists, direct + style + CATEGORY_MAP are precise enough;
            # keeping overlap would create false positives like
            # "Crème de Cacao" matching "Crème de Cassis" via shared "creme".
            if not best_key:
                ing_words   = set(ing.split()) - stop
                bname_words = set(bname.split()) - stop
                if ing_words and bname_words:
                    overlap = ing_words & bname_words
                    threshold = 0.5 if len(ing_words) <= 2 else 0.6
                    if overlap and len(overlap) / len(ing_words) >= threshold:
                        return True, bottle['Name']

    # Specialty pantry check — runs after bottles so house-made preparations only
    # satisfy ingredients when no real bottle match exists.  Word-boundary matching
    # prevents 'rum' ⊂ 'saccharum'.
    if pantry:
        for item in pantry.get('specialty', []):
            if item.get('in_stock'):
                p = clean(item.get('name', ''))
                if p and (p == ing or word_in(ing, p) or word_in(p, ing)):
                    return True, item['name']

    return False, None


def get_makeable_status(cocktail, inventory, pantry=None, _checker=None):
    """Check whether a cocktail can be made.  Pass _checker (from
    make_availability_checker) when calling in bulk to share the cache."""
    is_premium = cocktail.get('premium', False)
    missing = []
    specialty_by_id = {s['id']: s for s in pantry.get('specialty', [])} if pantry else {}
    bottle_by_name  = {normalize(b['Name']): b for b in inventory}
    check = _checker or (lambda n, p=False: check_ingredient_available(n, inventory, pantry, p))
    for ing in cocktail.get('ingredients', []):
        ing_type = ing.get('type', '')
        if ing_type == 'bottle':
            bn = normalize(ing.get('bottle_name') or ing['name'])
            b  = bottle_by_name.get(bn)
            ok = bool(b and b.get('in_stock', True) and normalize(b.get('Use', '')) != 'neat only')
        else:
            explicit = specialty_by_id.get(ing.get('pantry_id', ''))
            if explicit:
                ok = explicit.get('in_stock', False)
            else:
                ok, _ = check(ing['name'], is_premium)
        if not ok:
            missing.append(ing['name'])
    return len(missing) == 0, missing


def inventory_summary_text(inventory):
    by_cat = {}
    premium = []
    for b in inventory:
        use = normalize(b.get('Use', ''))
        if use == 'neat only':
            continue
        cat = b.get('Category', 'Other')
        if use == 'premium cocktail':
            premium.append(b.get('Name', ''))
        else:
            by_cat.setdefault(cat, []).append(b.get('Name', ''))
    lines = []
    for cat in sorted(by_cat):
        lines.append(f"{cat}: {', '.join(by_cat[cat])}")
    if premium:
        lines.append(f"Premium/reserve (use for premium cocktails only): {', '.join(premium)}")
    return '\n'.join(lines)


def pantry_summary_text(pantry):
    lines = ['PANTRY STAPLES (always available): ' + ', '.join(pantry.get('standard', []))]
    in_stock = [s['name'] for s in pantry.get('specialty', []) if s.get('in_stock')]
    if in_stock:
        lines.append('HOUSE-MADE IN STOCK: ' + ', '.join(in_stock))
    return '\n'.join(lines)


# ── Form helper ───────────────────────────────────────────────────────────────

def cocktail_from_form():
    names        = request.form.getlist('ingredient_name')
    amounts      = request.form.getlist('ingredient_amount')
    units        = request.form.getlist('ingredient_unit')
    notes_list   = request.form.getlist('ingredient_notes')
    types        = request.form.getlist('ingredient_type')
    pantry_ids   = request.form.getlist('ingredient_pantry_id')
    bottle_names = request.form.getlist('ingredient_bottle_name')
    ingredients = []
    for i, name in enumerate(names):
        if name.strip():
            ing = {
                'name':        name.strip(),
                'amount':      amounts[i].strip()      if i < len(amounts)      else '',
                'unit':        units[i].strip()        if i < len(units)        else '',
                'notes':       notes_list[i].strip()   if i < len(notes_list)   else '',
                'type':        types[i].strip()        if i < len(types)        else '',
                'pantry_id':   pantry_ids[i].strip()   if i < len(pantry_ids)   else '',
                'bottle_name': bottle_names[i].strip() if i < len(bottle_names) else '',
            }
            # Drop empty optional fields to keep data clean
            if not ing['type']:        del ing['type']
            if not ing['pantry_id']:   del ing['pantry_id']
            if not ing['bottle_name']: del ing['bottle_name']
            ingredients.append(ing)

    # Category chips (multi-select checkboxes) → stored as tags
    category_tags = [t.strip().lower() for t in request.form.getlist('category_tags') if t.strip()]

    # Free-text extra tags (comma-separated)
    extra_tags = [t.strip().lower() for t in request.form.get('extra_tags', '').split(',') if t.strip()]

    # Merge: category tags first, then extra; deduplicate preserving order
    seen = set()
    all_tags = []
    for t in category_tags + extra_tags:
        if t not in seen:
            seen.add(t)
            all_tags.append(t)

    creator = request.form.get('creator', '').strip()
    year    = request.form.get('year', '').strip()

    return {
        'name':         request.form.get('name', '').strip(),
        'description':  request.form.get('description', '').strip(),
        'category':     category_tags[0] if category_tags else '',  # kept for legacy display
        'glass':        request.form.get('glass', '').strip(),
        'method':       request.form.get('method', '').strip(),
        'ingredients':  ingredients,
        'instructions': request.form.get('instructions', '').strip(),
        'garnish':      request.form.get('garnish', '').strip(),
        'source':       request.form.get('source', '').strip(),
        'notes':        request.form.get('notes', '').strip(),
        'tags':         all_tags,
        'premium':      request.form.get('premium') == 'on',
        'creator':      creator,
        'year':         year,
    }



# ── Spirit classification ─────────────────────────────────────────────────────

# (label, [keywords-in-ingredient-name], url-key-for-?spirit= param)
_SPIRIT_BUCKETS = [
    ('Rum',              ['rum', 'rhum', 'cachaça', 'cachaca', 'clairin', 'batavia'], 'rum'),
    ('Whiskey',          ['bourbon', 'rye', 'scotch', 'whiskey', 'whisky', 'irish'], 'whiskey'),
    ('Tequila / Mezcal', ['tequila', 'mezcal', 'sotol'],                             'tequila'),
    ('Gin',              ['gin'],                                                      'gin'),
    ('Vodka',            ['vodka'],                                                    'vodka'),
    ('Cognac / Brandy',  ['cognac', 'calvados', 'brandy', 'pisco', 'armagnac'],       'cognac'),
    ('Amaro',            ['amaro', 'campari', 'aperol', 'cynar', 'fernet', 'suze'],   'amaro'),
    ('Vermouth / Wine',  ['vermouth', 'sherry', 'port', 'madeira', 'lillet'],         'vermouth'),
]


def classify_cocktail_spirit(cocktail):
    """Return (label, url_key) for the primary spirit in a cocktail."""
    for ing in cocktail.get('ingredients', []):
        if ing.get('type') == 'pantry':
            continue
        name = normalize(ing.get('name', ''))
        for label, keywords, url_key in _SPIRIT_BUCKETS:
            if any(kw in name for kw in keywords):
                return label, url_key
    return 'Other', None


# ── Routes: home ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    inventory = load_inventory_with_notes()
    pantry    = load_pantry()
    cocktails = _db.get_cocktails()
    _check    = make_availability_checker(inventory, pantry)
    makeable  = sum(1 for c in cocktails if get_makeable_status(c, inventory, pantry, _checker=_check)[0])

    # Bottle stats by category — count only in-stock bottles
    by_cat = {}
    for b in inventory:
        if not b.get('in_stock', True):
            continue
        cat = b.get('Category', 'Other')
        by_cat[cat] = by_cat.get(cat, 0) + 1

    # Cocktail stats by base spirit
    spirit_counts = {}
    for c in cocktails:
        label, url_key = classify_cocktail_spirit(c)
        if label not in spirit_counts:
            spirit_counts[label] = {'count': 0, 'url_key': url_key}
        spirit_counts[label]['count'] += 1
    spirit_stats = sorted(
        [(label, v['count'], v['url_key']) for label, v in spirit_counts.items() if label != 'Other'],
        key=lambda x: -x[1]
    )
    if 'Other' in spirit_counts:
        spirit_stats.append(('Other', spirit_counts['Other']['count'], None))

    # Recently viewed cocktails
    rv_ids = _db.get_recently_viewed(8)
    recently_viewed = []
    for rv in rv_ids:
        c = _db.get_cocktail(rv['cocktail_id'])
        if c:
            c['can_make'] = get_makeable_status(c, inventory, pantry, _checker=_check)[0]
            c['spirit_label'], _ = classify_cocktail_spirit(c)
            recently_viewed.append(c)

    return render_template('index.html',
                           bottle_count=sum(1 for b in inventory if b.get('in_stock', True)),
                           cocktail_count=len(cocktails),
                           makeable_count=makeable,
                           categories=by_cat,
                           spirit_stats=spirit_stats,
                           recently_viewed=recently_viewed)


# ── Routes: inventory ─────────────────────────────────────────────────────────

@app.route('/inventory')
def inventory():
    bottles = load_inventory_with_notes()
    cats    = sorted(set(b.get('Category', '') for b in bottles if b.get('Category')))
    custom_flavor_tags = json.loads(_db.get_setting('custom_flavor_tags', '{}'))
    # Ensure a default league exists for every category
    _db.ensure_default_leagues(cats)
    # Enrich each bottle with its ELO data
    elo_map = _db.get_all_bottle_elo([b['Name'] for b in bottles])
    for b in bottles:
        leagues = elo_map.get(b['Name'], [])
        b['elo_leagues'] = leagues
        b['elo_display'] = leagues[0] if leagues else None  # best (custom-first, highest score)
    all_leagues = _db.get_leagues()
    return render_template('inventory.html', bottles=bottles, categories=cats,
                           custom_flavor_tags=custom_flavor_tags,
                           all_leagues=all_leagues)


@app.route('/inventory/flavor-tags/add', methods=['POST'])
def inventory_flavor_tags_add():
    """Persist a new custom flavor tag under a named group."""
    group = request.form.get('group', '').strip()
    value = request.form.get('value', '').strip()
    label = request.form.get('label', '').strip()
    if not group or not value:
        return jsonify({'success': False}), 400
    current = json.loads(_db.get_setting('custom_flavor_tags', '{}'))
    if group not in current:
        current[group] = []
    if not any(t['value'] == value for t in current[group]):
        current[group].append({'value': value, 'label': label or value})
    _db.set_setting('custom_flavor_tags', json.dumps(current))
    return jsonify({'success': True, 'tags': current[group]})


def _normalise_abv(bottle: dict) -> dict:
    """Ensure ABV always ends with '%' if a value is present."""
    abv = bottle.get('ABV', '').strip()
    if abv and not abv.endswith('%'):
        bottle['ABV'] = abv + '%'
    return bottle


@app.route('/inventory/add', methods=['POST'])
def inventory_add():
    bottles = load_inventory()
    new = {f: request.form.get(f, '').strip() for f in INVENTORY_FIELDS}
    if new.get('Name'):
        _normalise_abv(new)
        bottles.append(new)
        save_inventory(bottles)
        flash(f"Added \"{new['Name']}\" to inventory.", 'success')
    return redirect(url_for('inventory'))


@app.route('/inventory/update', methods=['POST'])
def inventory_update():
    bottles = load_inventory()
    idx = int(request.form.get('index', -1))
    if 0 <= idx < len(bottles):
        original_name = bottles[idx].get('Name', '')
        bottles[idx] = {f: request.form.get(f, '').strip() for f in INVENTORY_FIELDS}
        _normalise_abv(bottles[idx])
        new_name = bottles[idx].get('Name', '')
        save_inventory(bottles)
        if original_name and new_name and original_name != new_name:
            _db.rename_bottle_note(original_name, new_name)
            _db.rename_bottle_in_leagues(original_name, new_name)
        return jsonify({'success': True, 'bottle': bottles[idx], 'index': idx})
    return jsonify({'success': False}), 400


@app.route('/inventory/toggle', methods=['POST'])
def inventory_toggle():
    name = request.form.get('name', '').strip()
    if not name:
        return jsonify({'success': False}), 400
    note = _db.toggle_bottle_stock(name)
    return jsonify({'success': True, 'in_stock': note['in_stock']})


@app.route('/inventory/note', methods=['POST'])
def inventory_note():
    name = request.form.get('name', '').strip()
    if not name:
        return jsonify({'success': False}), 400
    _db.set_bottle_note(
        name,
        nose        = request.form.get('nose', '').strip(),
        palate      = request.form.get('palate', '').strip(),
        finish      = request.form.get('finish', '').strip(),
        flavor_tags = request.form.getlist('flavor_tags'),
    )
    return jsonify({'success': True})


@app.route('/inventory/delete', methods=['POST'])
def inventory_delete():
    bottles = load_inventory()
    idx = int(request.form.get('index', -1))
    if 0 <= idx < len(bottles):
        name = bottles[idx].get('Name', '')
        bottles.pop(idx)
        save_inventory(bottles)
        _db.delete_bottle_note(name)
        _db.remove_bottle_from_all_leagues(name)
        flash(f"Removed \"{name}\" from inventory.", 'success')
    return redirect(url_for('inventory'))


# ── Routes: leagues ──────────────────────────────────────────────────────────

@app.route('/leagues')
def leagues_index():
    bottles = load_inventory_with_notes()
    cats    = sorted(set(b.get('Category', '') for b in bottles if b.get('Category')))
    _db.ensure_default_leagues(cats)
    leagues = _db.get_leagues()
    # Attach top-3 members for preview
    for lg in leagues:
        detail = _db.get_league(lg['id'])
        lg['top'] = detail['members'][:3] if detail else []
    return render_template('leagues.html', leagues=leagues)


@app.route('/leagues/<league_id>')
def league_detail_view(league_id):
    league = _db.get_league(league_id)
    if not league:
        flash('League not found.', 'error')
        return redirect(url_for('leagues_index'))
    return render_template('league_detail.html', league=league)


@app.route('/leagues/create', methods=['POST'])
def league_create():
    name = request.form.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Name required'}), 400
    league = _db.create_league(name)
    return jsonify({'success': True, 'league': league})


@app.route('/leagues/<league_id>/delete', methods=['POST'])
def league_delete(league_id):
    ok = _db.delete_league(league_id)
    if not ok:
        return jsonify({'success': False, 'error': 'Cannot delete default leagues'}), 400
    return jsonify({'success': True})


@app.route('/leagues/<league_id>/rename', methods=['POST'])
def league_rename(league_id):
    name = request.form.get('name', '').strip()
    ok   = _db.rename_league(league_id, name)
    return jsonify({'success': ok})


@app.route('/leagues/<league_id>/remove-bottle', methods=['POST'])
def league_remove_bottle(league_id):
    bottle_name = request.form.get('bottle_name', '').strip()
    ok = _db.remove_from_league(league_id, bottle_name)
    return jsonify({'success': ok})


# ── Routes: ELO rating ────────────────────────────────────────────────────────

@app.route('/elo/rate-setup', methods=['POST'])
def elo_rate_setup():
    """Seed initial ELO for a bottle in a league, then return matchup candidates."""
    bottle_name = request.form.get('bottle_name', '').strip()
    league_id   = request.form.get('league_id', '').strip()
    tier        = request.form.get('tier', '').strip()   # love/like/okay/dislike or '' for re-rate
    if not bottle_name or not league_id:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400
    _db.add_to_league(league_id, bottle_name, tier=tier or None)
    candidates  = _db.get_matchup_candidates(league_id, bottle_name)
    return jsonify({'success': True, 'candidates': candidates})


@app.route('/elo/submit', methods=['POST'])
def elo_submit():
    """Submit a batch of matchup results and update ELO scores."""
    data      = request.get_json() or {}
    league_id = data.get('league_id', '')
    results   = data.get('results', [])
    if not league_id:
        return jsonify({'success': False, 'error': 'Missing league_id'}), 400
    updated = _db.record_elo_results(league_id, results)
    # Return the focal bottle's updated league membership.
    # bottle_name can be passed explicitly (cold-start: no matchups) or inferred from results.
    bottle_name = (data.get('bottle_name', '') or
                   (results[0]['bottle_a'] if results else ''))
    bottle_leagues = _db.get_bottle_leagues(bottle_name) if bottle_name else []
    return jsonify({'success': True, 'updated_scores': updated,
                    'bottle_leagues': bottle_leagues})


@app.route('/elo/bottle-data')
def elo_bottle_data():
    """Return a bottle's current league memberships plus the full leagues list."""
    name       = request.args.get('bottle', '').strip()
    bottle_leagues = _db.get_bottle_leagues(name) if name else []
    all_leagues    = _db.get_leagues()
    return jsonify({'bottle_leagues': bottle_leagues, 'all_leagues': all_leagues})


# ── Routes: pantry ────────────────────────────────────────────────────────────

@app.route('/pantry')
def pantry():
    p = load_pantry()
    std_oos = set(normalize(x) for x in p.get('standard_out_of_stock', []))
    p['specialty'] = sorted(p.get('specialty', []), key=lambda s: s['name'].lower())

    # Reverse-link: for each specialty item, find which cocktails use it.
    # Two-pass strategy:
    #   Pass 1 (specific) — cocktails that explicitly name this preparation:
    #     item_clean == ing_clean  OR  word_in(item_clean, ing_clean)
    #     e.g. "Brown Butter Falernum" finds recipes that say "Brown Butter Falernum"
    #   Pass 2 (substitution, fallback) — if pass 1 found nothing, check the
    #     reverse direction (ingredient name contained in specialty name), but
    #     cap at 12 results.  This surfaces e.g. "Cacao Nib-Infused Amaro"→
    #     the 2 cocktails that call for plain "Amaro", without flooding infused
    #     spirits like "Horseradish-Infused Gin" with all 98 gin cocktails.
    _SUBST_CAP = 12
    cocktails = _db.get_cocktails()
    for item in p['specialty']:
        item_clean = clean(item['name'])
        item_id    = item['id']
        specific, substitution = [], []
        for c in cocktails:
            matched_specific = matched_subst = False
            for ing in c.get('ingredients', []):
                # Explicit pantry_id link — always a specific match, no name-fuzzing needed.
                # Handles cases like "Pineapple Gum (Gomme) Syrup" where parenthetical
                # alternate names defeat substring matching.
                if ing.get('pantry_id') == item_id:
                    matched_specific = True
                    break
                ing_clean = clean(ing.get('name', ''))
                if not item_clean:
                    break
                if item_clean == ing_clean or word_in(item_clean, ing_clean):
                    matched_specific = True
                    break
                if word_in(ing_clean, item_clean):
                    matched_subst = True
                    # don't break — a specific match in another ingredient wins
            if matched_specific:
                specific.append({'id': c['id'], 'name': c['name']})
            elif matched_subst:
                substitution.append({'id': c['id'], 'name': c['name']})
        if specific:
            item['used_in'] = sorted(specific, key=lambda x: x['name'])
        elif len(substitution) <= _SUBST_CAP:
            item['used_in'] = sorted(substitution, key=lambda x: x['name'])
        else:
            item['used_in'] = []

    return render_template('pantry.html', pantry=p, standard_oos=std_oos)


@app.route('/pantry/standard/add', methods=['POST'])
def pantry_standard_add():
    name = request.form.get('name', '').strip()
    if name:
        p = load_pantry()
        existing = [normalize(x) for x in p['standard']]
        if normalize(name) not in existing:
            p['standard'].append(name.lower())
            p['standard'].sort()
            save_pantry(p)
            flash(f'"{name}" added to pantry staples.', 'success')
        else:
            flash(f'"{name}" is already in the pantry.', 'error')
    return redirect(url_for('pantry'))


@app.route('/pantry/standard/delete', methods=['POST'])
def pantry_standard_delete():
    name = request.form.get('name', '').strip()
    if name:
        p = load_pantry()
        p['standard'] = [x for x in p['standard'] if normalize(x) != normalize(name)]
        save_pantry(p)
    return redirect(url_for('pantry'))


@app.route('/pantry/standard/toggle', methods=['POST'])
def pantry_standard_toggle():
    name = request.form.get('name', '').strip()
    if not name:
        return jsonify({'success': False}), 400
    p = load_pantry()
    out = p.setdefault('standard_out_of_stock', [])
    norm = normalize(name)
    if norm in [normalize(x) for x in out]:
        p['standard_out_of_stock'] = [x for x in out if normalize(x) != norm]
        in_stock = True
    else:
        p['standard_out_of_stock'].append(name.lower())
        in_stock = False
    save_pantry(p)
    return jsonify({'success': True, 'in_stock': in_stock})


@app.route('/pantry/specialty/add', methods=['POST'])
def pantry_specialty_add():
    name = request.form.get('name', '').strip()
    if name:
        p = load_pantry()
        existing_ids = {s['id'] for s in p['specialty']}
        new_item = {
            'id': unique_id(name, existing_ids),
            'name': name,
            'description': request.form.get('description', '').strip(),
            'recipe': request.form.get('recipe', '').strip(),
            'in_stock': False,
            'created_at': datetime.now().strftime('%Y-%m-%d'),
        }
        p['specialty'].append(new_item)
        p['specialty'].sort(key=lambda s: s['name'].lower())
        save_pantry(p)
        flash(f'"{name}" added to specialty pantry.', 'success')
    return redirect(url_for('pantry'))


@app.route('/pantry/specialty/update', methods=['POST'])
def pantry_specialty_update():
    item_id = request.form.get('id', '')
    p = load_pantry()
    for item in p['specialty']:
        if item['id'] == item_id:
            item['name'] = request.form.get('name', '').strip() or item['name']
            item['description'] = request.form.get('description', '').strip()
            item['recipe'] = request.form.get('recipe', '').strip()
            break
    p['specialty'].sort(key=lambda s: s['name'].lower())
    save_pantry(p)
    flash('Updated.', 'success')
    return redirect(url_for('pantry'))


@app.route('/pantry/specialty/toggle', methods=['POST'])
def pantry_specialty_toggle():
    item_id = request.form.get('id', '')
    p = load_pantry()
    new_state = False
    for item in p['specialty']:
        if item['id'] == item_id:
            item['in_stock'] = not item.get('in_stock', False)
            new_state = item['in_stock']
            break
    save_pantry(p)
    return jsonify({'success': True, 'in_stock': new_state})


@app.route('/pantry/specialty/delete', methods=['POST'])
def pantry_specialty_delete():
    item_id = request.form.get('id', '')
    p = load_pantry()
    item = next((s for s in p['specialty'] if s['id'] == item_id), None)
    name = item['name'] if item else ''
    p['specialty'] = [s for s in p['specialty'] if s['id'] != item_id]
    save_pantry(p)
    if name:
        flash(f'"{name}" removed from specialty pantry.', 'success')
    return redirect(url_for('pantry'))


# ── Routes: cocktails ─────────────────────────────────────────────────────────

@app.route('/cocktails/random')
def cocktail_random():
    inventory = load_inventory_with_notes()
    pantry    = load_pantry()
    cocktails = _db.get_cocktails()
    _check    = make_availability_checker(inventory, pantry)
    makeable  = [c for c in cocktails if get_makeable_status(c, inventory, pantry, _checker=_check)[0]]
    pool = makeable if makeable else cocktails
    if pool:
        return redirect(url_for('cocktail_detail', cocktail_id=random.choice(pool)['id']))
    return redirect(url_for('cocktails'))


@app.route('/cocktails')
def cocktails():
    inventory = load_inventory_with_notes()
    pantry = load_pantry()
    all_cocktails = _db.get_cocktails()
    all_feedback = _db.get_all_feedback()
    blank_fb = {'tried': False, 'rating': None, 'favorited': False}
    _check = make_availability_checker(inventory, pantry)
    for c in all_cocktails:
        c['can_make'], c['missing'] = get_makeable_status(c, inventory, pantry, _checker=_check)
        c['feedback'] = all_feedback.get(c['id'], blank_fb)

    # Default display order is random; client-side sort button handles A→Z
    random.shuffle(all_cocktails)

    sources = sorted(set(c.get('source', '') for c in all_cocktails if c.get('source')))

    present_tags = set()
    for c in all_cocktails:
        present_tags.update(t.lower() for t in c.get('tags', []))
    if 'tropical' in present_tags:   # tiki filter covers tropical too
        present_tags.add('tiki')
    style_tags = [{'value': v, 'label': l} for v, l in STYLE_TAG_DEFS if v in present_tags]

    # Unique creators sorted by last name (all from Death & Co.)
    creator_counts = Counter(c.get('creator', '') for c in all_cocktails if c.get('creator'))
    creators = sorted(creator_counts.keys(), key=lambda n: n.split()[-1] if n else '')

    return render_template('cocktails.html',
                           cocktails=all_cocktails,
                           sources=sources,
                           style_tags=style_tags,
                           creators=creators)


def _form_context():
    """Shared context for new/edit cocktail forms."""
    all_cocktails = _db.get_cocktails()
    pantry = load_pantry()
    inventory = load_inventory_with_notes()
    style_tags = [{'value': v, 'label': l} for v, l in STYLE_TAG_DEFS]
    known_creators = sorted(
        {c['creator'] for c in all_cocktails if c.get('creator')},
        key=lambda n: n.split()[-1]
    )
    known_sources = sorted({c['source'] for c in all_cocktails if c.get('source')})
    specialty_items = sorted(pantry.get('specialty', []), key=lambda s: s['name'])
    # Bottles available for mixing (not neat-only), sorted by name
    bar_bottles = sorted(
        [b for b in inventory if normalize(b.get('Use', '')) != 'neat only'],
        key=lambda b: b['Name']
    )
    return dict(style_tags=style_tags,
                style_tag_values=STYLE_TAG_VALUES,
                known_creators=known_creators,
                known_sources=known_sources,
                specialty_items=specialty_items,
                bar_bottles=bar_bottles)


# Define /new before /<cocktail_id> to avoid routing conflict
@app.route('/cocktails/new', methods=['GET', 'POST'])
def cocktail_new():
    if request.method == 'POST':
        cocktail = cocktail_from_form()
        existing_ids = {c['id'] for c in _db.get_cocktails()}
        cocktail['id'] = unique_id(cocktail['name'], existing_ids)
        cocktail['created_at'] = datetime.now().strftime('%Y-%m-%d')
        _db.save_cocktail(cocktail, is_local=True)
        flash(f"'{cocktail['name']}' added to the database.", 'success')
        return redirect(url_for('cocktail_detail', cocktail_id=cocktail['id']))
    prefill = {}
    if request.args.get('prefill'):
        try:
            prefill = json.loads(request.args['prefill'])
        except Exception:
            pass
    return render_template('new_cocktail.html', cocktail=None, prefill=prefill,
                           **_form_context())


@app.route('/cocktails/<cocktail_id>')
def cocktail_detail(cocktail_id):
    inventory = load_inventory_with_notes()
    pantry = load_pantry()
    cocktail = _db.get_cocktail(cocktail_id)
    if not cocktail:
        flash('Cocktail not found.', 'error')
        return redirect(url_for('cocktails'))
    is_premium = cocktail.get('premium', False)
    can_make, missing = get_makeable_status(cocktail, inventory, pantry)
    specialty_by_id   = {s['id']:              s for s in pantry.get('specialty', [])}
    specialty_by_name = {normalize(s['name']): s for s in pantry.get('specialty', [])}
    bottle_by_name    = {normalize(b['Name']): b for b in inventory}
    for ing in cocktail.get('ingredients', []):
        ing_type = ing.get('type', '')
        if ing_type == 'bottle':
            # Explicit bottle link
            bn = normalize(ing.get('bottle_name') or ing['name'])
            b  = bottle_by_name.get(bn)
            ing['pantry_item'] = None
            if b:
                ok = b.get('in_stock', True) and normalize(b.get('Use', '')) != 'neat only'
                ing['available'] = ok
                ing['source']    = b['Name'] if ok else None
            else:
                ing['available'] = False
                ing['source']    = None
        elif ing_type == 'pantry':
            # Explicitly tagged as a pantry staple in the editor.
            # Still respect the out-of-stock toggle — consistent with get_makeable_status.
            ok, _ = check_ingredient_available(ing['name'], inventory, pantry, is_premium)
            ing['pantry_item'] = None
            ing['available']   = ok
            ing['source']      = 'pantry' if ok else None
        else:
            explicit = specialty_by_id.get(ing.get('pantry_id', ''))
            if explicit:
                # Explicit specialty link — bypass fuzzy matching
                ing['pantry_item'] = explicit
                ing['available']   = explicit.get('in_stock', False)
                ing['source']      = explicit['name'] if explicit.get('in_stock') else None
            else:
                ok, source = check_ingredient_available(ing['name'], inventory, pantry, is_premium)
                ing['available'] = ok
                ing['source']    = source
                ing['pantry_item'] = None
                if ok and source and source != 'pantry':
                    # source may be a specialty item name (e.g. "Brown Butter Falernum")
                    # rather than a bottle name — link it so the stock toggle is available.
                    sitem = specialty_by_name.get(normalize(source))
                    if sitem:
                        ing['pantry_item'] = sitem
                        ing['source'] = 'pantry'
                elif not ok:
                    # Not available — fuzzy-link to a matching specialty so the user
                    # can toggle it in stock from the detail view.
                    ing_norm = normalize(ing['name'])
                    for sname, sitem in specialty_by_name.items():
                        if sname in ing_norm or ing_norm in sname:
                            ing['pantry_item'] = sitem
                            break

        # search_term: the term to pass to the bottle shelf search link.
        # Priority:
        #   1. CATEGORY_SEARCH_TERMS explicit override (e.g. "jamaican rum" → "rum jamaica")
        #   2. clean(best_key) — IF that term actually appears in some bottle's
        #      name/style/category/origin (e.g. "bourbon" → finds "Straight Bourbon" bottles)
        #   3. Primary style from CATEGORY_MAP — fallback when the key name isn't in any
        #      bottle's fields (e.g. "white crème de cacao" → "cacao liqueur")
        #   4. Matched bottle's Style — when no CATEGORY_MAP key exists at all.
        #   5. Ingredient name — for pantry / specialty / missing ingredients.
        src = ing.get('source')
        if ing.get('available') and src and src != 'pantry':
            ing_c = clean(ing['name'])
            best_k = None
            for key in CATEGORY_MAP:
                kc = clean(key)
                if (kc == ing_c or word_in(kc, ing_c)) and (
                        best_k is None or len(kc) > len(clean(best_k))):
                    best_k = key
            if best_k:
                override = CATEGORY_SEARCH_TERMS.get(best_k)
                if override:
                    ing['search_term'] = override
                else:
                    key_term = clean(best_k)
                    # Use the key name as search if it actually appears in the bottle shelf
                    # (e.g. "bourbon" appears in "Straight Bourbon").  Otherwise fall back
                    # to the primary CATEGORY_MAP style so the search still finds results.
                    found_in_shelf = any(
                        key_term in (
                            clean(b.get('Name', '')) + ' ' + clean(b.get('Style', '')) + ' ' +
                            clean(b.get('Category', '')) + ' ' + clean(b.get('Origin', ''))
                        )
                        for b in inventory
                    )
                    if found_in_shelf:
                        ing['search_term'] = key_term
                    else:
                        styles = CATEGORY_MAP.get(best_k, [])
                        ing['search_term'] = clean(styles[0]) if styles else key_term
            else:
                matched = bottle_by_name.get(normalize(src))
                ing['search_term'] = matched.get('Style', ing['name']) if matched else ing['name']
        else:
            ing['search_term'] = ing['name']

    _db.record_view(cocktail_id)
    history  = _db.get_history(cocktail_id, limit=10)
    feedback = _db.get_feedback(cocktail_id)
    comments = _db.get_comments(cocktail_id)
    all_lists = _db.get_lists()
    cocktail_lists = _db.get_cocktail_lists(cocktail_id)
    return render_template('cocktail_detail.html',
                           cocktail=cocktail, can_make=can_make, missing=missing,
                           style_tag_values=STYLE_TAG_VALUES, history=history,
                           feedback=feedback, comments=comments,
                           all_lists=all_lists, cocktail_lists=cocktail_lists)


@app.route('/cocktails/<cocktail_id>/edit', methods=['GET', 'POST'])
def cocktail_edit(cocktail_id):
    existing = _db.get_cocktail(cocktail_id)
    if not existing:
        return redirect(url_for('cocktails'))
    if request.method == 'POST':
        updated = cocktail_from_form()
        updated['id'] = cocktail_id
        updated['created_at'] = existing.get('created_at', datetime.now().strftime('%Y-%m-%d'))
        _db.save_cocktail(updated, is_local=True)
        flash(f"'{updated['name']}' updated.", 'success')
        return redirect(url_for('cocktail_detail', cocktail_id=cocktail_id))
    return render_template('new_cocktail.html', cocktail=existing, prefill={},
                           **_form_context())


@app.route('/cocktails/<cocktail_id>/delete', methods=['POST'])
def cocktail_delete(cocktail_id):
    cocktail = _db.get_cocktail(cocktail_id)
    name = cocktail.get('name', '') if cocktail else ''
    _db.delete_cocktail(cocktail_id)
    flash(f"'{name}' removed.", 'success')
    return redirect(url_for('cocktails'))


@app.route('/cocktails/sync', methods=['POST'])
def cocktails_sync():
    """Pull updates from cocktails.json into the DB, skipping personalised recipes."""
    if not COCKTAILS_FILE.exists():
        flash('cocktails.json not found — nothing to sync.', 'error')
        return redirect(url_for('cocktails'))
    with open(COCKTAILS_FILE, encoding='utf-8') as f:
        raw = json.load(f).get('cocktails', [])
    stats = _db.import_cocktails(raw, overwrite_shared=True)
    flash(
        f"Sync complete — {stats['added']} added, {stats['updated']} updated, "
        f"{stats['skipped']} skipped (personalised).",
        'success'
    )
    return redirect(url_for('cocktails'))


@app.route('/cocktails/deleted')
def cocktails_deleted():
    deleted = _db.get_deleted_cocktails()
    return render_template('cocktails_deleted.html', deleted=deleted)


@app.route('/cocktails/<cocktail_id>/restore/<int:history_id>', methods=['POST'])
def cocktail_restore(cocktail_id, history_id):
    cocktail = _db.restore_version(history_id)
    if cocktail:
        flash(f"'{cocktail['name']}' restored to a previous version.", 'success')
        return redirect(url_for('cocktail_detail', cocktail_id=cocktail_id))
    flash('Could not restore that version.', 'error')
    return redirect(url_for('cocktails'))



@app.route('/cocktails/<cocktail_id>/feedback', methods=['POST'])
def cocktail_feedback(cocktail_id):
    data = request.get_json() or {}
    tried     = data.get('tried')
    rating    = data.get('rating')
    favorited = data.get('favorited')
    fb = _db.set_feedback(cocktail_id,
                          tried=tried,
                          rating=rating,
                          favorited=favorited)
    return jsonify(fb)


# ── Routes: Comments ─────────────────────────────────────────────────────────

@app.route('/cocktails/<cocktail_id>/comments/add', methods=['POST'])
def comment_add(cocktail_id):
    body = (request.form.get('body') or '').strip()
    if not body:
        return jsonify({'success': False, 'error': 'Comment cannot be empty'}), 400
    if not _db.get_cocktail(cocktail_id):
        return jsonify({'success': False, 'error': 'Cocktail not found'}), 404
    comment = _db.add_comment(cocktail_id, body)
    return jsonify({'success': True, 'comment': comment})


@app.route('/cocktails/<cocktail_id>/comments/<int:comment_id>/delete', methods=['POST'])
def comment_delete(cocktail_id, comment_id):
    _db.delete_comment(comment_id)
    return jsonify({'success': True})


# ── Routes: Lists ────────────────────────────────────────────────────────────

@app.route('/lists')
def lists_index():
    all_lists = _db.get_lists()
    # Attach a preview (up to 3 cocktail names) to each list
    for lst in all_lists:
        detail = _db.get_list(lst['id'])
        lst['preview'] = []
        if detail:
            for item in detail['items'][:3]:
                c = _db.get_cocktail(item['cocktail_id'])
                if c:
                    lst['preview'].append(c['name'])
    return render_template('lists.html', lists=all_lists)


@app.route('/lists/create', methods=['POST'])
def lists_create():
    name = request.form.get('name', '').strip()
    cocktail_id = request.form.get('cocktail_id', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'}), 400
    existing = _db.get_lists()
    if any(normalize(l['name']) == normalize(name) for l in existing):
        return jsonify({'success': False, 'error': 'A list with that name already exists'}), 400
    existing_ids = {l['id'] for l in existing}
    new_id = unique_id(name, existing_ids)
    lst = _db.create_list(name, new_id)
    if cocktail_id:
        _db.add_to_list(new_id, cocktail_id)
        lst['has_cocktail'] = True
    return jsonify({'success': True, 'list': lst})


@app.route('/lists/<list_id>/delete', methods=['POST'])
def list_delete(list_id):
    lst = _db.get_list(list_id)
    name = lst['name'] if lst else ''
    _db.delete_list(list_id)
    if name:
        flash(f'"{name}" deleted.', 'success')
    return redirect(url_for('lists_index'))


@app.route('/lists/<list_id>/rename', methods=['POST'])
def list_rename(list_id):
    name = request.form.get('name', '').strip()
    if not name:
        return jsonify({'success': False}), 400
    ok = _db.rename_list(list_id, name)
    return jsonify({'success': ok})


@app.route('/lists/<list_id>/add', methods=['POST'])
def list_add_cocktail(list_id):
    cocktail_id = request.form.get('cocktail_id', '').strip()
    if not cocktail_id:
        return jsonify({'success': False}), 400
    lst = _db.get_list(list_id)
    if not lst:
        return jsonify({'success': False, 'error': 'List not found'}), 404
    _db.add_to_list(list_id, cocktail_id)
    return jsonify({'success': True, 'list_id': list_id, 'list_name': lst['name']})


@app.route('/lists/<list_id>/remove', methods=['POST'])
def list_remove_cocktail(list_id):
    cocktail_id = request.form.get('cocktail_id', '').strip()
    if not cocktail_id:
        return jsonify({'success': False}), 400
    _db.remove_from_list(list_id, cocktail_id)
    return jsonify({'success': True})


@app.route('/lists/<list_id>')
def list_detail_view(list_id):
    lst = _db.get_list(list_id)
    if not lst:
        flash('List not found.', 'error')
        return redirect(url_for('lists_index'))
    inventory = load_inventory_with_notes()
    pantry    = load_pantry()
    _check    = make_availability_checker(inventory, pantry)
    cocktails = []
    for item in lst['items']:
        c = _db.get_cocktail(item['cocktail_id'])
        if c:
            c['can_make'], _ = get_makeable_status(c, inventory, pantry, _checker=_check)
            c['added_at'] = item['added_at']
            cocktails.append(c)
    return render_template('list_detail.html', lst=lst, cocktails=cocktails)


# ── Claude helpers ────────────────────────────────────────────────────────────

def claude_client():
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        raise ValueError('ANTHROPIC_API_KEY is not configured. Add it to your .env file.')
    return anthropic.Anthropic(api_key=key)


def stream_claude(system, messages, max_tokens=2048):
    def generate():
        try:
            client = claude_client()
            # Cache the system prompt so it counts ~10x lighter against the
            # input-token rate limit (ephemeral cache TTL = 5 min, refreshed on hits).
            cached_system = [{"type": "text", "text": system,
                              "cache_control": {"type": "ephemeral"}}]
            # Cap conversation history to prevent runaway token growth.
            trimmed = messages[-10:]
            with client.messages.stream(
                model='claude-sonnet-4-6',
                max_tokens=max_tokens,
                system=cached_system,
                messages=trimmed,
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except anthropic.RateLimitError:
            yield f"data: {json.dumps({'error': 'The bar is briefly at capacity — please try again in a moment.'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ── Routes: Import ────────────────────────────────────────────────────────────

_IMPORT_SYSTEM = """You are a precise recipe extraction assistant. Extract cocktail recipes from the provided content (image or text) and return them as a JSON array.

Each recipe object must use this exact structure:
{
  "name": "Recipe name",
  "description": "Short descriptor or tagline if present, otherwise empty string",
  "category": "e.g. Sour, Stirred, Highball, Tiki, Classic — infer if not stated",
  "glass": "Glass type",
  "method": "Shaken / Stirred / Built / Blended / etc.",
  "ingredients": [
    {"name": "Ingredient name", "amount": "numeric amount or empty", "unit": "oz/ml/dash/tsp/barspoon/etc", "notes": "e.g. chilled, freshly squeezed"}
  ],
  "instructions": "Full preparation method",
  "garnish": "Garnish description or empty string",
  "notes": "Any additional notes, variations, or context"
}

Rules:
- Prefer oz; convert ml to oz rounded to nearest 0.25 (e.g. 30ml → 1 oz, 22ml → 0.75 oz).
- Use unicode fractions in amounts where natural (¼ ½ ¾).
- If an ingredient has no numeric amount (e.g. "ice", "soda water to top"), leave amount and unit as empty strings and put context in notes.
- Return ONLY a valid JSON array — no prose, no markdown fences, no extra keys.
- If no recipes are found, return [].
- Extract every recipe visible, even partial ones."""

_IMPORT_USER_PROMPT = "Extract all cocktail recipes from this content and return the JSON array."


@app.route('/import')
def import_page():
    return render_template('import.html')


@app.route('/import/extract', methods=['POST'])
def import_extract():
    source = request.form.get('source', '').strip()
    raw_text = request.form.get('text', '').strip()
    image_file = request.files.get('image')

    if not raw_text and not image_file:
        return jsonify({'success': False, 'error': 'Provide an image or text to extract from.'}), 400

    try:
        client = claude_client()

        if image_file:
            img_bytes = image_file.read()
            media_type = image_file.content_type or 'image/jpeg'
            img_b64 = base64.standard_b64encode(img_bytes).decode('utf-8')
            content = [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": media_type,
                                             "data": img_b64}},
                {"type": "text", "text": _IMPORT_USER_PROMPT},
            ]
        else:
            content = _IMPORT_USER_PROMPT + "\n\n" + raw_text

        resp = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=4096,
            system=_IMPORT_SYSTEM,
            messages=[{"role": "user", "content": content}],
        )
        raw = resp.content[0].text.strip()
        # Strip markdown fences if the model added them despite instructions
        if raw.startswith('```'):
            raw = re.sub(r'^```[a-z]*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)
        recipes = json.loads(raw)
        if not isinstance(recipes, list):
            recipes = [recipes]
        # Attach source book if provided
        if source:
            for r in recipes:
                if not r.get('source'):
                    r['source'] = source
        return jsonify({'success': True, 'recipes': recipes})
    except anthropic.RateLimitError:
        return jsonify({'success': False, 'error': 'Rate limit — please wait a moment and try again.'}), 429
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'error': f'Could not parse recipe JSON: {e}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/import/save', methods=['POST'])
def import_save():
    recipes = request.get_json()
    if not recipes or not isinstance(recipes, list):
        return jsonify({'success': False, 'error': 'No recipes provided'}), 400
    existing_ids = {c['id'] for c in _db.get_cocktails()}
    saved = []
    for r in recipes:
        if not r.get('name'):
            continue
        r['id'] = unique_id(r['name'], existing_ids)
        existing_ids.add(r['id'])
        r.setdefault('created_at', datetime.now().strftime('%Y-%m-%d'))
        # Normalise ingredients: ensure required keys exist
        for ing in r.get('ingredients', []):
            ing.setdefault('type', '')
            ing.setdefault('notes', '')
            ing.setdefault('amount', '')
            ing.setdefault('unit', '')
        _db.save_cocktail(r, is_local=True)
        saved.append({'id': r['id'], 'name': r['name']})
    return jsonify({'success': True, 'saved': saved})


# ── Routes: Bookshelf ─────────────────────────────────────────────────────────

BOOKS = [
    {
        'title':       'Death & Co',
        'subtitle':    'Modern Classic Cocktails',
        'source':      'Death & Co.',
        'filename':    'death-and-co.pdf',
        'description': 'The definitive guide to Death & Co, the celebrated New York cocktail bar. '
                       'Features hundreds of original recipes spanning the bar\'s history from 2006.',
        'authors':     'David Kaplan, Nick Fauchald, Alex Day',
    },
    {
        'title':       'The NoMad Cocktail Book',
        'subtitle':    '',
        'source':      'NoMad Bar',
        'filename':    'nomad-bar.pdf',
        'description': 'The complete cocktail program from the NoMad Hotel\'s celebrated bar, '
                       'including original recipes and classics reimagined.',
        'authors':     'Leo Robitschek',
    },
    {
        'title':       'Brokedown Palace',
        'subtitle':    'I Need a Miracle',
        'source':      'Brokedown Palace',
        'filename':    'brokedown-palace.pdf',
        'description': 'A personal cocktail book — originals created, adapted, and lovingly '
                       'recreated from memorable drinks over the years.',
        'authors':     'Ian Gilman',
    },
]

@app.route('/bookshelf')
def bookshelf():
    import os
    books_dir = os.path.join(app.static_folder, 'books')
    books = []
    for b in BOOKS:
        path = os.path.join(books_dir, b['filename'])
        b = dict(b)
        b['available'] = os.path.exists(path)
        books.append(b)
    return render_template('bookshelf.html', books=books)


# ── Routes: Ask Lloid ─────────────────────────────────────────────────────────

@app.route('/ask')
def ask():
    return render_template('ask.html')


@app.route('/ask/stream', methods=['POST'])
def ask_stream():
    data = request.get_json()
    messages = data.get('messages', [])
    mode = data.get('mode', 'find')  # 'find' | 'riff' | 'create'

    inventory = load_inventory_with_notes()
    pantry = load_pantry()
    inv_text = inventory_summary_text(inventory)
    pantry_text = pantry_summary_text(pantry)

    SAVE_JSON_FORMAT = """When they confirm saving, output a JSON block in EXACTLY this format (it will be parsed by the app):
```json
{{
  "save_cocktail": true,
  "name": "Cocktail Name",
  "category": "Original",
  "glass": "Glass Type",
  "method": "Shaken",
  "ingredients": [
    {{"name": "Spirit Name", "amount": "2", "unit": "oz", "notes": ""}},
    {{"name": "Modifier", "amount": "0.75", "unit": "oz", "notes": ""}}
  ],
  "instructions": "Full preparation instructions.",
  "garnish": "Garnish description",
  "tags": ["original", "tag2"],
  "notes": "Designer notes"
}}
```"""

    if mode == 'find':
        cocktails = _db.get_cocktails()
        can_make_lines, near_miss_lines = [], []
        skipped = 0
        for c in cocktails:
            can_make, missing = get_makeable_status(c, inventory, pantry)
            ings = ', '.join(i['name'] for i in c.get('ingredients', []))
            if can_make:
                can_make_lines.append(f"- {c['name']} [{c.get('category', '')}] — {ings}")
            elif len(missing) <= 2:
                near_miss_lines.append(
                    f"- {c['name']} [{c.get('category', '')}] [needs: {', '.join(missing)}] — {ings}"
                )
            else:
                skipped += 1
        cocktail_section = '\n'.join(can_make_lines + near_miss_lines)
        if skipped:
            cocktail_section += f"\n(+ {skipped} more recipes requiring additional bottles)"
        system = f"""You are Lloid, head bartender of the Gold Room — formal, precise, faintly unnerving. You speak with authority, not volume.

CURRENT INVENTORY:
{inv_text}

{pantry_text}

COCKTAIL DATABASE (makeable + near-miss only):
{cocktail_section}

Guidelines:
- Be brief. 2–4 sentences per reply unless giving a full recipe. No preamble.
- Recommend 2–3 cocktails that best match, prioritizing those without [needs: …]
- One sentence per recommendation explaining why it fits
- Provide the full recipe only if explicitly asked
- Ask a single clarifying question if the request is genuinely unclear; otherwise just recommend"""
        return stream_claude(system, messages, max_tokens=1024)

    elif mode == 'riff':
        cocktail_names = [f"- {c['name']}" for c in _db.get_cocktails()]
        system = f"""You are Lloid, head bartender of the Gold Room — formal, precise, faintly unnerving. You speak with authority, not volume.

CURRENT INVENTORY:
{inv_text}

{pantry_text}

COCKTAILS IN DATABASE (names only — ask for full recipe if needed):
{chr(10).join(cocktail_names)}

Guidelines:
- Be brief. Skip preamble. If the cocktail and direction are clear from the message, design immediately.
- If the cocktail isn't named, ask for it in one sentence.
- Present the variation concisely: name, measurements, method/glass/garnish, one-sentence rationale.
- Ask if they'd like to save it to the database.

{SAVE_JSON_FORMAT}"""
        return stream_claude(system, messages, max_tokens=2048)

    else:  # create
        system = f"""You are Lloid, head bartender of the Gold Room — formal, precise, faintly unnerving. You speak with authority, not volume.

CURRENT INVENTORY:
{inv_text}

{pantry_text}

When designing a cocktail:
- Be brief. Skip preamble. If there's enough to go on, design immediately.
- If the concept is genuinely unclear, ask one focused question.
- Present concisely: evocative name, precise measurements in oz, method/glass/garnish, one-sentence flavor rationale.
- Apply proper balance (spirit 1.5–2 oz, modifier, ~0.75 oz sour, ~0.5–0.75 oz sweet).
- Ask if they'd like to save it to the database.

{SAVE_JSON_FORMAT}"""
        return stream_claude(system, messages, max_tokens=2048)


@app.route('/ask/save', methods=['POST'])
def ask_save():
    cocktail_data = request.get_json()
    if not cocktail_data or not cocktail_data.get('name'):
        return jsonify({'success': False, 'error': 'Invalid cocktail data'}), 400
    cocktail_data.pop('save_cocktail', None)
    existing_ids = {c['id'] for c in _db.get_cocktails()}
    cocktail_data['id'] = unique_id(cocktail_data['name'], existing_ids)
    cocktail_data['created_at'] = datetime.now().strftime('%Y-%m-%d')
    _db.save_cocktail(cocktail_data, is_local=True)
    return jsonify({'success': True, 'id': cocktail_data['id']})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)

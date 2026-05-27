import os
import csv
import json
import uuid
import re
import random
import functools
import unicodedata
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

        for bottle in inventory:
            use = normalize(bottle.get('Use', ''))

            # Neat-only bottles never count for mixing
            if use == 'neat only':
                continue

            # Out-of-stock bottles don't count
            if not bottle.get('in_stock', True):
                continue

            # Premium bottles only count for premium cocktails
            if use == 'premium cocktail' and not is_premium:
                continue

            bname  = clean(bottle.get('Name', ''))
            bstyle = clean(bottle.get('Style', ''))
            bcat   = clean(bottle.get('Category', ''))

            # 1. Direct containment (works after unicode + punctuation normalisation,
            #    e.g. St-Germain == St. Germain, Crème == Creme)
            if ing in bname or bname in ing:
                return True, bottle['Name']

            # 2. Style / category direct match (word-boundary — prevents "gin" matching "ginger")
            if ing == bstyle or word_in(ing, bstyle) or word_in(ing, bcat):
                return True, bottle['Name']

            # 3. Category map — specific mapping checked BEFORE generic overlap so
            #    "crème de cacao" routes to cacao-liqueur bottles and not cassis ones.
            if cat_styles:
                for sc in cat_styles:
                    if word_in(sc, bstyle) or word_in(sc, bcat) or word_in(sc, bname):
                        return True, bottle['Name']

            # 4. Meaningful word overlap — fallback ONLY for ingredients that have no
            #    CATEGORY_MAP entry.  When best_key exists, direct + style + CATEGORY_MAP
            #    are precise enough; keeping overlap would create false positives like
            #    "Crème de Cacao" matching "Crème de Cassis" via shared "creme".
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

    # Bottle stats by category
    by_cat = {}
    for b in inventory:
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
                           bottle_count=len(inventory),
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
    return render_template('inventory.html', bottles=bottles, categories=cats)


@app.route('/inventory/add', methods=['POST'])
def inventory_add():
    bottles = load_inventory()
    new = {f: request.form.get(f, '').strip() for f in INVENTORY_FIELDS}
    if new.get('Name'):
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
        new_name = bottles[idx].get('Name', '')
        save_inventory(bottles)
        if original_name and new_name and original_name != new_name:
            _db.rename_bottle_note(original_name, new_name)
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
        flash(f"Removed \"{name}\" from inventory.", 'success')
    return redirect(url_for('inventory'))


# ── Routes: pantry ────────────────────────────────────────────────────────────

@app.route('/pantry')
def pantry():
    p = load_pantry()
    std_oos = set(normalize(x) for x in p.get('standard_out_of_stock', []))
    p['specialty'] = sorted(p.get('specialty', []), key=lambda s: s['name'].lower())
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
        #   1. CATEGORY_MAP primary style — broadest correct search, e.g. "Amaro" → "amaro"
        #      (shows ALL amari, not just the one that happened to match first).
        #   2. Matched bottle's Style — fallback when no map key exists.
        #   3. Ingredient name — for pantry / specialty / missing ingredients.
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
                # Use the first (primary) style value from the map as the search term
                ing['search_term'] = CATEGORY_MAP[best_k][0]
            else:
                matched = bottle_by_name.get(normalize(src))
                ing['search_term'] = matched.get('Style', ing['name']) if matched else ing['name']
        else:
            ing['search_term'] = ing['name']

    _db.record_view(cocktail_id)
    history = _db.get_history(cocktail_id, limit=10)
    feedback = _db.get_feedback(cocktail_id)
    return render_template('cocktail_detail.html',
                           cocktail=cocktail, can_make=can_make, missing=missing,
                           style_tag_values=STYLE_TAG_VALUES, history=history,
                           feedback=feedback)


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
            with client.messages.stream(
                model='claude-sonnet-4-6',
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


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
        cocktail_lines = []
        for c in cocktails:
            can_make, missing = get_makeable_status(c, inventory, pantry)
            status = 'CAN MAKE' if can_make else f"missing: {', '.join(missing[:3])}"
            ings = ', '.join(i['name'] for i in c.get('ingredients', []))
            cocktail_lines.append(
                f"- {c['name']} [{c.get('category', '')}] [{status}] — {ings}"
            )
        system = f"""You are Lloid, head bartender of the Gold Room. You have always been here. You speak with the quiet, unhurried authority of a man who has served every guest who has ever walked through that door — and a few who never left. Your manner is formal, impeccably gracious, and ever so slightly unnerving. You do not rush. You do not judge. You simply know what they need before they ask.

Phrases you favor: "Right away.", "Allow me to suggest…", "An excellent choice, if I may say so.", "The bar is always open.", "I think you'll find this suits your particular… tastes.", "Your money's no good here — only your thirst matters."

Your task: recommend the perfect cocktail from this bar's database.

CURRENT INVENTORY:
{inv_text}

{pantry_text}

COCKTAIL DATABASE:
{chr(10).join(cocktail_lines)}

Guidelines:
- Greet the guest warmly in Lloyd's voice before getting to business
- Ask about mood, flavor preferences, spirit preference, or occasion if needed
- Recommend 2–3 cocktails that best match, prioritizing those marked "CAN MAKE"
- Briefly explain why each fits — with Lloyd's elegant, slightly theatrical flair
- Provide the full recipe if asked
- Keep responses focused; Lloyd says much with few words"""
        return stream_claude(system, messages, max_tokens=1024)

    elif mode == 'riff':
        cocktails = _db.get_cocktails()
        db_lines = [f"- {c['name']}: {', '.join(i['name'] for i in c.get('ingredients', []))}"
                    for c in cocktails]
        system = f"""You are Lloid, head bartender of the Gold Room. You have always been here. You speak with the quiet, formal authority of a man who has seen every variation of every drink ever conceived — and invented a few that history has wisely forgotten. You are gracious, precise, and faintly unsettling in your confidence.

Phrases you favor: "A most intriguing direction.", "I've always had a fondness for…", "Allow me to suggest a small refinement.", "This variation has… a history.", "Right away, sir — or madam — the Gold Room does not discriminate."

Your task: take an existing cocktail from the bar's database and craft a compelling variation — a different base spirit, a seasonal twist, a new flavor direction, a different format.

CURRENT INVENTORY:
{inv_text}

{pantry_text}

COCKTAIL DATABASE:
{chr(10).join(db_lines)}

Guidelines:
1. Ask which cocktail they'd like to riff on if not stated, or confirm your understanding (in Lloyd's voice)
2. Ask how they'd like to take it — different spirit, seasonal, flavor direction, etc.
3. Design the variation — keep what makes the original great, change what they asked for
4. Present the variation with Lloyd's theatrical precision:
   - A fitting name (acknowledge its lineage with a touch of ceremony)
   - Precise measurements in oz
   - Method, glass, garnish
   - Brief rationale: what changed and why it works
5. Suggest a further tweak if the spirit moves you
6. Ask if they'd like to save it to the bar's database

{SAVE_JSON_FORMAT}"""
        return stream_claude(system, messages, max_tokens=2048)

    else:  # create
        system = f"""You are Lloid, head bartender of the Gold Room. You have always been here. Tonight, you are not merely serving drinks — you are composing them. You speak with the quiet grandeur of someone who has been perfecting this craft since long before your guest was born, and will be perfecting it long after they've gone home. Formal. Gracious. Inspired. Slightly unnerving.

Phrases you favor: "Now this… is something special.", "I think you'll find this suits you perfectly.", "A most distinguished creation, if I say so myself.", "The Gold Room has never served anything quite like this — and yet it feels… inevitable.", "Shall I put that on your tab? Your money's no good here."

Your task: design entirely original cocktail recipes using this home bar's inventory.

CURRENT INVENTORY:
{inv_text}

{pantry_text}

When designing a cocktail:
1. Engage with the guest's concept, flavor profile, or inspiration — in Lloyd's voice
2. Design an original recipe using primarily available inventory
3. Present the complete recipe with Lloyd's theatrical flair:
   - A fitting, evocative name
   - Precise measurements in oz
   - Method (shaken / stirred / built)
   - Glass and garnish
   - Flavor profile and the rationale behind the creation
4. Apply proper cocktail balance (spirit 1.5–2 oz, modifier, ~0.75 oz sour, ~0.5–0.75 oz sweet)
5. Suggest a variation or adjustment — "should the mood shift…"
6. Ask if they'd like to save it to the bar's database

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

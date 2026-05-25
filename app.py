import os
import csv
import json
import uuid
import re
import random
from collections import Counter
from datetime import datetime
from pathlib import Path
from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, Response, stream_with_context, flash)
from dotenv import load_dotenv
import anthropic

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'lloid-dev-key-change-in-production')

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
    'sherry': ['amontillado sherry', 'pedro ximénez sherry'],
    'amontillado': ['amontillado sherry'],
    'amontillado sherry': ['amontillado sherry'],
    'port': ['white port', 'tawny port'],
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
            return json.load(f)
    # Bootstrap defaults
    pantry = {'standard': sorted(DEFAULT_PANTRY_STANDARD), 'specialty': []}
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
    ing = normalize(ing_name)
    if not ing:
        return True, 'pantry'

    # Standard pantry check
    pantry_std = pantry.get('standard', []) if pantry else DEFAULT_PANTRY_STANDARD
    for p in pantry_std:
        p = normalize(p)
        if p == ing or p in ing or ing in p:
            return True, 'pantry'

    # Specialty pantry check (only in-stock items count)
    if pantry:
        for item in pantry.get('specialty', []):
            if item.get('in_stock'):
                p = normalize(item.get('name', ''))
                if p and (p == ing or p in ing or ing in p):
                    return True, item['name']

    stop = {'the', 'a', 'an', 'of', 'de', 'du', '&', 'and', 'no', 'st', 'n', 'le'}

    for bottle in inventory:
        use = normalize(bottle.get('Use', ''))

        # Neat-only bottles never count for mixing
        if use == 'neat only':
            continue

        # Premium bottles only count for premium cocktails
        if use == 'premium cocktail' and not is_premium:
            continue

        bname = normalize(bottle.get('Name', ''))
        bstyle = normalize(bottle.get('Style', ''))
        bcat = normalize(bottle.get('Category', ''))

        # Direct containment
        if ing in bname or bname in ing:
            return True, bottle['Name']

        # Meaningful word overlap (≥60% of ingredient words match bottle name)
        ing_words = set(ing.split()) - stop
        bname_words = set(bname.split()) - stop
        if ing_words and bname_words:
            overlap = ing_words & bname_words
            if overlap and len(overlap) / len(ing_words) >= 0.6:
                return True, bottle['Name']

        # Style / category direct match
        if ing and (ing == bstyle or ing in bstyle):
            return True, bottle['Name']

        # Category map lookup — use longest matching key to avoid false positives
        # e.g. 'green chartreuse' should not match via generic 'chartreuse' key
        best_key = None
        for key in CATEGORY_MAP:
            if (key == ing or key in ing) and (best_key is None or len(key) > len(best_key)):
                best_key = key
        if best_key:
            for s in CATEGORY_MAP[best_key]:
                if s in bstyle or s in bcat or s in bname:
                    return True, bottle['Name']

    return False, None


def get_makeable_status(cocktail, inventory, pantry=None):
    is_premium = cocktail.get('premium', False)
    missing = []
    for ing in cocktail.get('ingredients', []):
        ok, _ = check_ingredient_available(ing['name'], inventory, pantry, is_premium)
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
    names = request.form.getlist('ingredient_name')
    amounts = request.form.getlist('ingredient_amount')
    units = request.form.getlist('ingredient_unit')
    notes_list = request.form.getlist('ingredient_notes')
    ingredients = []
    for i, name in enumerate(names):
        if name.strip():
            ingredients.append({
                'name': name.strip(),
                'amount': amounts[i].strip() if i < len(amounts) else '',
                'unit': units[i].strip() if i < len(units) else '',
                'notes': notes_list[i].strip() if i < len(notes_list) else '',
            })

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


# ── Routes: home ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    inventory = load_inventory()
    pantry = load_pantry()
    cocktails = load_cocktails()
    makeable = sum(1 for c in cocktails if get_makeable_status(c, inventory, pantry)[0])
    by_cat = {}
    for b in inventory:
        cat = b.get('Category', 'Other')
        by_cat[cat] = by_cat.get(cat, 0) + 1
    recent = sorted(cocktails, key=lambda c: c.get('created_at', ''), reverse=True)[:6]
    for c in recent:
        c['can_make'] = get_makeable_status(c, inventory, pantry)[0]
    return render_template('index.html',
                           bottle_count=len(inventory),
                           cocktail_count=len(cocktails),
                           makeable_count=makeable,
                           categories=by_cat,
                           recent_cocktails=recent)


# ── Routes: inventory ─────────────────────────────────────────────────────────

@app.route('/inventory')
def inventory():
    bottles = load_inventory()
    cats = sorted(set(b.get('Category', '') for b in bottles if b.get('Category')))
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
        bottles[idx] = {f: request.form.get(f, '').strip() for f in INVENTORY_FIELDS}
        save_inventory(bottles)
        return jsonify({'success': True, 'bottle': bottles[idx]})
    return jsonify({'success': False}), 400


@app.route('/inventory/delete', methods=['POST'])
def inventory_delete():
    bottles = load_inventory()
    idx = int(request.form.get('index', -1))
    if 0 <= idx < len(bottles):
        name = bottles[idx].get('Name', '')
        bottles.pop(idx)
        save_inventory(bottles)
        flash(f"Removed \"{name}\" from inventory.", 'success')
    return redirect(url_for('inventory'))


# ── Routes: pantry ────────────────────────────────────────────────────────────

@app.route('/pantry')
def pantry():
    p = load_pantry()
    return render_template('pantry.html', pantry=p)


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

@app.route('/cocktails')
def cocktails():
    inventory = load_inventory()
    pantry = load_pantry()
    all_cocktails = load_cocktails()
    for c in all_cocktails:
        c['can_make'], c['missing'] = get_makeable_status(c, inventory, pantry)

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
    all_cocktails = load_cocktails()
    style_tags = [{'value': v, 'label': l} for v, l in STYLE_TAG_DEFS]
    known_creators = sorted(
        {c['creator'] for c in all_cocktails if c.get('creator')},
        key=lambda n: n.split()[-1]
    )
    known_sources = sorted({c['source'] for c in all_cocktails if c.get('source')})
    return dict(style_tags=style_tags,
                style_tag_values=STYLE_TAG_VALUES,
                known_creators=known_creators,
                known_sources=known_sources)


# Define /new before /<cocktail_id> to avoid routing conflict
@app.route('/cocktails/new', methods=['GET', 'POST'])
def cocktail_new():
    if request.method == 'POST':
        cocktail = cocktail_from_form()
        cocktails = load_cocktails()
        cocktail['id'] = unique_id(cocktail['name'], {c['id'] for c in cocktails})
        cocktail['created_at'] = datetime.now().strftime('%Y-%m-%d')
        cocktails.append(cocktail)
        save_cocktails(cocktails)
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
    inventory = load_inventory()
    pantry = load_pantry()
    cocktails = load_cocktails()
    cocktail = next((c for c in cocktails if c['id'] == cocktail_id), None)
    if not cocktail:
        flash('Cocktail not found.', 'error')
        return redirect(url_for('cocktails'))
    is_premium = cocktail.get('premium', False)
    can_make, missing = get_makeable_status(cocktail, inventory, pantry)
    for ing in cocktail.get('ingredients', []):
        ok, source = check_ingredient_available(ing['name'], inventory, pantry, is_premium)
        ing['available'] = ok
        ing['source'] = source
    return render_template('cocktail_detail.html',
                           cocktail=cocktail, can_make=can_make, missing=missing,
                           style_tag_values=STYLE_TAG_VALUES)


@app.route('/cocktails/<cocktail_id>/edit', methods=['GET', 'POST'])
def cocktail_edit(cocktail_id):
    cocktails = load_cocktails()
    idx = next((i for i, c in enumerate(cocktails) if c['id'] == cocktail_id), None)
    if idx is None:
        return redirect(url_for('cocktails'))
    if request.method == 'POST':
        updated = cocktail_from_form()
        updated['id'] = cocktail_id
        updated['created_at'] = cocktails[idx].get('created_at', datetime.now().strftime('%Y-%m-%d'))
        cocktails[idx] = updated
        save_cocktails(cocktails)
        flash(f"'{updated['name']}' updated.", 'success')
        return redirect(url_for('cocktail_detail', cocktail_id=cocktail_id))
    return render_template('new_cocktail.html', cocktail=cocktails[idx], prefill={},
                           **_form_context())


@app.route('/cocktails/<cocktail_id>/delete', methods=['POST'])
def cocktail_delete(cocktail_id):
    cocktails = load_cocktails()
    cocktail = next((c for c in cocktails if c['id'] == cocktail_id), None)
    name = cocktail.get('name', '') if cocktail else ''
    cocktails = [c for c in cocktails if c['id'] != cocktail_id]
    save_cocktails(cocktails)
    flash(f"'{name}' removed.", 'success')
    return redirect(url_for('cocktails'))


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

    inventory = load_inventory()
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
        cocktails = load_cocktails()
        cocktail_lines = []
        for c in cocktails:
            can_make, missing = get_makeable_status(c, inventory, pantry)
            status = 'CAN MAKE' if can_make else f"missing: {', '.join(missing[:3])}"
            ings = ', '.join(i['name'] for i in c.get('ingredients', []))
            cocktail_lines.append(
                f"- {c['name']} [{c.get('category', '')}] [{status}] — {ings}"
            )
        system = f"""You are Lloid, the knowledgeable bartender for this home bar. \
Help guests find the perfect cocktail from the bar's database.

CURRENT INVENTORY:
{inv_text}

{pantry_text}

COCKTAIL DATABASE:
{chr(10).join(cocktail_lines)}

Guidelines:
- Ask about mood, flavor preferences, spirit preference, or occasion if needed
- Recommend 2–3 cocktails that best match, prioritizing those marked "CAN MAKE"
- Briefly explain why each fits the request
- Provide the full recipe if asked
- Be warm and conversational — knowledgeable but not pretentious
- Keep responses focused and not overly long"""
        return stream_claude(system, messages, max_tokens=1024)

    elif mode == 'riff':
        cocktails = load_cocktails()
        db_lines = [f"- {c['name']}: {', '.join(i['name'] for i in c.get('ingredients', []))}"
                    for c in cocktails]
        system = f"""You are Lloid, a creative bartender. Your task: take an existing cocktail \
from the bar's database and create a compelling variation — a different base spirit, \
a seasonal twist, a flavor direction, a different format.

CURRENT INVENTORY:
{inv_text}

{pantry_text}

COCKTAIL DATABASE:
{chr(10).join(db_lines)}

Guidelines:
1. Ask which cocktail they'd like to riff on if not stated, or confirm your understanding
2. Ask how they'd like to take it (different spirit, seasonal, flavor direction, etc.)
3. Design the variation — keep what makes the original great, change what they asked for
4. Present the variation with:
   - A fitting name (acknowledge its lineage)
   - Precise measurements in oz
   - Method, glass, garnish
   - Brief rationale: what changed and why it works
5. Suggest a further tweak if relevant
6. Ask if they'd like to save it to the bar's database

{SAVE_JSON_FORMAT}"""
        return stream_claude(system, messages, max_tokens=2048)

    else:  # create
        system = f"""You are Lloid, a creative cocktail designer. Your task: design entirely \
original cocktail recipes using this home bar's inventory.

CURRENT INVENTORY:
{inv_text}

{pantry_text}

When designing a cocktail:
1. Engage with the user's concept, flavor profile, or inspiration
2. Design an original recipe using primarily available inventory
3. Present a complete recipe with:
   - A fitting name
   - Precise measurements in oz
   - Method (shaken / stirred / built)
   - Glass and garnish
   - Flavor profile and design rationale
4. Apply proper cocktail balance (spirit 1.5–2 oz, modifier, ~0.75 oz sour, ~0.5–0.75 oz sweet)
5. Suggest a variation or adjustment
6. Ask if they'd like to save it to the bar's database

{SAVE_JSON_FORMAT}"""
        return stream_claude(system, messages, max_tokens=2048)


@app.route('/ask/save', methods=['POST'])
def ask_save():
    cocktail_data = request.get_json()
    if not cocktail_data or not cocktail_data.get('name'):
        return jsonify({'success': False, 'error': 'Invalid cocktail data'}), 400
    cocktails = load_cocktails()
    cocktail_data.pop('save_cocktail', None)
    cocktail_data['id'] = unique_id(cocktail_data['name'], {c['id'] for c in cocktails})
    cocktail_data['created_at'] = datetime.now().strftime('%Y-%m-%d')
    cocktails.append(cocktail_data)
    save_cocktails(cocktails)
    return jsonify({'success': True, 'id': cocktail_data['id']})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)

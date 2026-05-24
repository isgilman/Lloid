import os
import csv
import json
import uuid
import re
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

INVENTORY_FIELDS = ['Name', 'Category', 'Style', 'Origin', 'Age', 'ABV', 'Producer', 'Use']

PANTRY_ITEMS = {
    'angostura bitters', 'bitters', "peychaud's bitters", 'aromatic bitters',
    'orange bitters', 'mole bitters', 'chocolate bitters', 'cardamom bitters',
    'fees bitters', 'black walnut bitters', 'barrel-aged bitters',
    'lemon juice', 'fresh lemon juice', 'lime juice', 'fresh lime juice',
    'orange juice', 'grapefruit juice', 'pineapple juice',
    'simple syrup', 'rich simple syrup', 'rich demerara syrup', 'demerara syrup',
    'honey syrup', 'honey-ginger syrup', 'agave syrup', 'agave nectar',
    'cane syrup', 'grenadine', 'raspberry syrup',
    'sugar', 'sugar cube', 'demerara sugar',
    'salt', 'saline solution', 'saline',
    'egg white', 'egg', 'cream', 'heavy cream',
    'soda water', 'club soda', 'sparkling water', 'tonic water',
    'ginger beer', 'ginger ale', 'cola', 'water', 'ice',
    'mint', 'rosemary', 'thyme', 'basil', 'cucumber', 'jalapeño',
    'coconut cream', 'orgeat',
    'absinthe rinse', 'absinthe', 'pastis',
}

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

def check_ingredient_available(ing_name, inventory):
    """Return (available: bool, source: str|None)."""
    ing = normalize(ing_name)
    if not ing:
        return True, 'pantry'

    # Pantry check
    for p in PANTRY_ITEMS:
        if p == ing or p in ing or ing in p:
            return True, 'pantry'

    stop = {'the', 'a', 'an', 'of', 'de', 'du', '&', 'and', 'no', 'st', 'n', 'le'}

    for bottle in inventory:
        if normalize(bottle.get('Use', '')) == 'neat only':
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


def get_makeable_status(cocktail, inventory):
    missing = []
    for ing in cocktail.get('ingredients', []):
        ok, _ = check_ingredient_available(ing['name'], inventory)
        if not ok:
            missing.append(ing['name'])
    return len(missing) == 0, missing


def inventory_summary_text(inventory):
    by_cat = {}
    for b in inventory:
        if normalize(b.get('Use', '')) == 'neat only':
            continue
        cat = b.get('Category', 'Other')
        by_cat.setdefault(cat, []).append(b.get('Name', ''))
    lines = []
    for cat in sorted(by_cat):
        lines.append(f"{cat}: {', '.join(by_cat[cat])}")
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
    tags_raw = request.form.get('tags', '')
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
    return {
        'name': request.form.get('name', '').strip(),
        'category': request.form.get('category', '').strip(),
        'glass': request.form.get('glass', '').strip(),
        'method': request.form.get('method', '').strip(),
        'ingredients': ingredients,
        'instructions': request.form.get('instructions', '').strip(),
        'garnish': request.form.get('garnish', '').strip(),
        'source': request.form.get('source', '').strip(),
        'notes': request.form.get('notes', '').strip(),
        'tags': tags,
    }


# ── Routes: home ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    inventory = load_inventory()
    cocktails = load_cocktails()
    makeable = sum(1 for c in cocktails if get_makeable_status(c, inventory)[0])
    by_cat = {}
    for b in inventory:
        cat = b.get('Category', 'Other')
        by_cat[cat] = by_cat.get(cat, 0) + 1
    recent = sorted(cocktails, key=lambda c: c.get('created_at', ''), reverse=True)[:6]
    for c in recent:
        c['can_make'] = get_makeable_status(c, inventory)[0]
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


# ── Routes: cocktails ─────────────────────────────────────────────────────────

@app.route('/cocktails')
def cocktails():
    inventory = load_inventory()
    all_cocktails = load_cocktails()
    for c in all_cocktails:
        c['can_make'], c['missing'] = get_makeable_status(c, inventory)
    cats = sorted(set(c.get('category', '') for c in all_cocktails if c.get('category')))
    return render_template('cocktails.html', cocktails=all_cocktails, categories=cats)


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
    return render_template('new_cocktail.html', cocktail=None, prefill=prefill)


@app.route('/cocktails/<cocktail_id>')
def cocktail_detail(cocktail_id):
    inventory = load_inventory()
    cocktails = load_cocktails()
    cocktail = next((c for c in cocktails if c['id'] == cocktail_id), None)
    if not cocktail:
        flash('Cocktail not found.', 'error')
        return redirect(url_for('cocktails'))
    can_make, missing = get_makeable_status(cocktail, inventory)
    for ing in cocktail.get('ingredients', []):
        ok, source = check_ingredient_available(ing['name'], inventory)
        ing['available'] = ok
        ing['source'] = source
    return render_template('cocktail_detail.html',
                           cocktail=cocktail, can_make=can_make, missing=missing)


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
    return render_template('new_cocktail.html', cocktail=cocktails[idx], prefill={})


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


# ── Routes: finder ────────────────────────────────────────────────────────────

@app.route('/finder')
def finder():
    return render_template('finder.html')


@app.route('/finder/stream', methods=['POST'])
def finder_stream():
    data = request.get_json()
    messages = data.get('messages', [])
    inventory = load_inventory()
    cocktails = load_cocktails()

    inv_text = inventory_summary_text(inventory)
    cocktail_lines = []
    for c in cocktails:
        can_make, missing = get_makeable_status(c, inventory)
        status = 'CAN MAKE' if can_make else f"missing: {', '.join(missing[:3])}"
        ings = ', '.join(i['name'] for i in c.get('ingredients', []))
        cocktail_lines.append(
            f"- {c['name']} [{c.get('category', '')}] [{status}] — {ings}"
        )

    system = f"""You are Lloid, the knowledgeable bartender for this home bar. Help guests find the perfect cocktail from the bar's database.

CURRENT INVENTORY:
{inv_text}

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


# ── Routes: designer ─────────────────────────────────────────────────────────

@app.route('/designer')
def designer():
    return render_template('designer.html')


@app.route('/designer/stream', methods=['POST'])
def designer_stream():
    data = request.get_json()
    messages = data.get('messages', [])
    inventory = load_inventory()
    inv_text = inventory_summary_text(inventory)

    system = f"""You are Lloid, a creative cocktail designer. Help create original cocktail recipes using this home bar's inventory.

CURRENT INVENTORY:
{inv_text}

PANTRY BASICS ALWAYS AVAILABLE: fresh lemon juice, fresh lime juice, simple syrup, rich demerara syrup, honey syrup, agave syrup, Angostura bitters, orange bitters, egg white, salt, soda water, tonic water, ginger beer, mint, cucumber, and standard fresh garnishes.

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

After presenting a complete recipe, ask if they'd like to save it to the bar's database.

When they confirm saving, output a JSON block in EXACTLY this format (it will be parsed by the app):
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

    return stream_claude(system, messages, max_tokens=2048)


@app.route('/designer/save', methods=['POST'])
def designer_save():
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

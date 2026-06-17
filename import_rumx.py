#!/usr/bin/env python3
"""import_rumx.py — one-shot import of RumX tasting CSV into Lloid.

Usage:
  python import_rumx.py              # live run
  python import_rumx.py --dry-run    # preview only
  python import_rumx.py --fix-tags   # re-normalize all flavor_tags in DB
  python import_rumx.py --fix-tags --dry-run
"""

import csv
import json
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'Data'
INVENTORY_FILE = DATA_DIR / 'bar_inventory.csv'
DB_PATH = DATA_DIR / 'lloid.db'
RUMX_FILE = Path('/Users/iangilman/Dropbox/Projects/SpiritedAway/data/RumX-2025-07-09.csv')
INVENTORY_FIELDS = ['Name', 'Category', 'Style', 'Country', 'Region', 'Age', 'ABV', 'Producer', 'Use']
DRY_RUN  = '--dry-run'  in sys.argv
FIX_TAGS = '--fix-tags' in sys.argv

# Maps lowercase RumX tag → predefined flavor_tag value (None = skip)
RUMX_TAG_MAP = {
    # Tropical Fruit
    'banana': 'banana',                     'overripe banana': 'banana',
    'pineapple': 'pineapple',
    'mango': 'mango',
    'coconut': 'coconut',
    'passion fruit': 'passion-fruit',
    'papaya': 'papaya',
    'guava': 'guava',
    'lychee': 'lychee',                     'litchi': 'lychee',
    'tropical fruits': 'tropical-fruit',
    # Citrus
    'lemon': 'lemon',                       'lemon peel': 'lemon',
    'lime': 'lime',                         'lime peel': 'lime',
    'orange': 'orange',                     'orange peel': 'orange',
    'bitter orange': 'orange',              'marmalade': 'orange',
    'grapefruit': 'grapefruit',
    'citrus': 'citrus-zest',                'tangerine': 'tangerine',
    # Stone & Other Fruit
    'peaches': 'peach',                     'peach rings': 'peach',
    'apricot': 'apricot',                   'dried apricot': 'apricot',
    'cherry': 'cherry',                     'sour cherry': 'cherry',
    'plum': 'plum',
    'apple': 'apple',                       'green apple': 'apple',
    'baked apple': 'apple',
    'pear': 'pear',
    'berries': 'berry',                     'red fruits': 'berry',
    'strawberry': 'strawberry',             'raspberry': 'raspberry',
    'dark berries': 'berry',
    'melon': 'melon',                       'watermelon rind': 'melon',
    'grapes': 'grape',                      'green grapes': 'grape',
    'green fruits': 'green-fruit',
    # Dried Fruit
    'raisin': 'raisin',
    'dates': 'date',                        'dried dates': 'date',
    'figs': 'fig',                          'dried figs': 'fig',
    'prune': 'prune',
    'currants': 'currant',                  'dried currants': 'currant',
    'dried fruit': 'raisin',
    # Floral
    'floral': 'floral',                     'flowery': 'floral',
    'rose': 'rose',
    'jasmine': 'jasmine',
    'honeysuckle': 'floral',
    'lavender': 'lavender',
    'orange blossom': 'orange-blossom',
    # Herbal & Vegetal
    'mint': 'mint',                         'minty': 'mint',
    'menthol': 'mint',
    'grass': 'grassy',                      'hay': 'grassy',
    'green': 'grassy',
    'herbal': 'herbal',                     'basil': 'herbal',
    'coriander': 'herbal',                  'tea': 'herbal',
    'anise': 'anise',                       'licorice': 'anise',
    'juniper': 'anise',
    'eucalyptus': 'eucalyptus',
    'tobacco leaf': 'tobacco-leaf',
    'vegetal': 'vegetal',                   'cucumber': 'vegetal',
    'green pepper': 'vegetal',              'green peppers': 'vegetal',
    'sugarcane': 'sugarcane',
    'agricole': 'agricole',
    # Baking Spice
    'vanilla': 'vanilla',
    'cinnamon': 'cinnamon',                 'baking spices': 'cinnamon',
    'clove': 'clove',
    'nutmeg': 'nutmeg',
    'allspice': 'allspice',
    'cardamom': 'cardamom',                 'mace': 'cardamom',
    'ginger': 'ginger',
    # Heat & Pepper
    'black pepper': 'black-pepper',         'peppery': 'black-pepper',
    'white pepper': 'white-pepper',
    'spicy': 'spicy-heat',                  'spice': 'spicy-heat',
    'chili': 'chili',
    # Sweet & Caramel
    'caramel': 'caramel',                   'burnt sugar': 'caramel',
    'caramelized': 'caramel',               'candied': 'caramel',
    'toffee': 'toffee',                     'fudge': 'toffee',
    'butterscotch': 'butterscotch',         'buttered popcorn': 'butterscotch',
    'molasses': 'molasses',
    'honey': 'honey',
    'brown sugar': 'brown-sugar',           'demerara sugar': 'brown-sugar',
    'sugar': 'brown-sugar',                 'cookie dough': 'brown-sugar',
    'maple': 'maple',
    'malty': 'malty',
    # Chocolate & Coffee
    'chocolate': 'chocolate',              'milk chocolate': 'chocolate',
    'dark chocolate': 'dark-chocolate',
    'cocoa': 'cocoa',
    'coffee': 'coffee',                    'roasted': 'coffee',
    'espresso': 'espresso',
    'mocha': 'mocha',
    # Wood & Oak
    'oak': 'oak',                          'woody': 'oak',
    'barrel': 'oak',
    'cedar': 'cedar',
    'leather': 'leather',
    'tobacco': 'tobacco',                  'cigar': 'tobacco',
    'resin': 'resin',
    'char': 'char',                        'charred': 'char',
    'toasted': 'char',
    'sawdust': 'sawdust',                  'pencil shavings': 'sawdust',
    'young wood': 'sawdust',               'green wood': 'sawdust',
    'cherry wood': 'sawdust',
    # Earth & Smoke
    'smoky': 'smoky',                      'camp fire': 'smoky',
    'peat': 'peaty',
    'earthy': 'earthy',                    'dirt': 'earthy',
    'mushrooms': 'earthy',                 'musty': 'earthy',
    'after rain': 'earthy',
    'ash': 'ash',
    'mineral': 'mineral',
    'gunpowder': 'gunpowder',
    # Funk & Ferment
    'funky': 'funky',
    'overripe': 'overripe',               'rotten': 'overripe',
    'barnyard': 'barnyard',
    'nail polish': 'acetone',             'acetone': 'acetone',
    'wax': 'wax',
    'solvents': 'solvent',               'varnish': 'solvent',
    'polish': 'solvent',                 'plastic': 'solvent',
    'glue': 'solvent',
    'ester': 'ester',
    'rubber': 'rubber',                  'bicycle tube': 'rubber',
    'petrol': 'petroleum',               'gasoline': 'petroleum',
    'diesel': 'petroleum',
    'bubblegum': 'bubblegum',
    # Texture & Other
    'creamy': 'creamy',                  'cream': 'creamy',
    'custard': 'creamy',                 'creme brulee': 'creamy',
    'velvety': 'creamy',
    'buttery': 'buttery',
    'almond': 'almond',                  'marzipan': 'almond',
    'nutty': 'almond',                   'praline': 'almond',
    'nougat': 'almond',
    'walnut': 'walnut',                  'pecan': 'walnut',
    'hazelnut': 'walnut',
    'briny': 'briny',                    'brine': 'briny',
    'ocean spray': 'briny',             'salty': 'briny',
    'bitter': 'bitter',                  'tannins': 'bitter',
    'gentian': 'bitter',
    'sour': 'sour',                      'vinegar': 'sour',
    'medicinal': 'medicinal',
    'brioche': 'brioche',                'biscuits': 'brioche',
    'pastries': 'brioche',               'graham cracker': 'brioche',
    'macaroons': 'brioche',
    'umami': 'umami',                    'meaty': 'umami',
    'savory': 'umami',                   'smoked sausage': 'umami',
    'pepperoni': 'umami',               'tomato': 'umami',
    'olive': 'olive',
    # Skip — subjective quality/intensity terms
    'alcoholic': None,  'intense': None,   'fresh': None,    'fruity': None,
    'fruits': None,     'complex': None,   'delicious': None, 'dry': None,
    'dark': None,       'light': None,     'mild': None,     'strong': None,
    'full bodied': None,'warm': None,      'hot': None,      'round': None,
    'sharp': None,      'pungent': None,   'oily': None,     'fermented': None,
    'juicy': None,      'sweet': None,     'astringent': None,'popcorn': None,
    'candied fruits': None, 'confections': None,
    # Skip — spirit-type references, not flavor descriptors
    'clairin': None,    'cognac': None,    'bourbon': None,   'brandy': None,
    'port': None,       'sherry': None,    'red wine': None,  'grappa': None,
    'sake': None,       'rye whiskey': None,
    # Skip — unmappable / too obscure
    'new can of tennis balls': None, 'new tennis balls': None,
    'yoghurt': None,    'marshmallow': None, 'apple pie': None,
    'banana bread': None, 'brownie': None, 'cherry cough syrup': None,
    'cough syrup': None, 'play doh': None, 'cardboard': None,
    'cola': None,       'amburana': None,
    "s'more": None,
}

COUNTRY_MAP = {
    'JM': ('Jamaica', ''),        'BB': ('Barbados', ''),
    'TT': ('Trinidad and Tobago', ''), 'HT': ('Haiti', ''),
    'MQ': ('Martinique', ''),     'GP': ('Guadeloupe', ''),
    'RE': ('Réunion', ''),        'GD': ('Grenada', ''),
    'GY': ('Guyana', ''),         'CU': ('Cuba', ''),
    'NI': ('Nicaragua', ''),      'PA': ('Panama', ''),
    'MX': ('Mexico', ''),         'TH': ('Thailand', ''),
    'EC': ('Ecuador', ''),        'ZA': ('South Africa', ''),
    'FJ': ('Fiji', ''),           'AU': ('Australia', ''),
    'BR': ('Brazil', ''),         'PT': ('Portugal', 'Madeira'),
    'MU': ('Mauritius', ''),      'LC': ('Saint Lucia', ''),
    'US': ('USA', ''),            'BM': ('Bermuda', ''),
    'BZ': ('Belize', ''),         'VE': ('Venezuela', ''),
    '&': ('Multi-Country', ''),   'PR': ('Puerto Rico', ''),
    'TW': ('Taiwan', ''),         '': ('', ''),
}

# Cleaned keyword → exact bottle name in current inventory
# key = substring of clean(existing_name), used for fuzzy matching
KNOWN_MATCH_KEYS = {
    'RX284':   'turquoise bay amber rum',
    'RX1410':  'real mccoy 3',
    'RX43':    'smith cross',
    'RX16288': 'maggies farm 5050 dark',
    'RX41':    'havana club especial',
    'RX2030':  'barbancourt 3 stars',
    'RX130':   'savanna herr habitation velier',
    'RX21813': 'papalin',
    'RX1918':  'south pacific sbs fiji 2009',
    'RX23302': 'worthy park overproof',
    'RX5390':  'rum fire',
    'RX11416': 'hamilton 151',
    'RX15873': 'clairin pignon',
    'RX297':   'saint james rhum vieux',
    'RX156':   'labat 59',
    'RX5701':  'wray nephew white',
    'RX23113': 'tsook oaxacan mountain',
    'RX8474':  'aficionados grand arome',
}


def clean(s):
    """Lowercase, strip accents, strip non-alphanumeric, collapse spaces."""
    nfkd = unicodedata.normalize('NFKD', s)
    ascii_ = ''.join(c for c in nfkd if not unicodedata.combining(c))
    stripped = re.sub(r'[^a-z0-9 ]', '', ascii_.lower())
    return re.sub(r'\s+', ' ', stripped).strip()


def normalize_tags(raw_tags):
    """Map raw RumX tag strings to predefined flavor_tag values."""
    result = []
    seen = set()
    for tag in raw_tags:
        key = tag.lower().strip()
        if key in RUMX_TAG_MAP:
            mapped = RUMX_TAG_MAP[key]
            if mapped is not None and mapped not in seen:
                result.append(mapped)
                seen.add(mapped)
        else:
            normalized = re.sub(r'\s+', '-', key)
            if normalized not in seen:
                result.append(normalized)
                seen.add(normalized)
    return sorted(result)


def fix_tags():
    """Re-normalize all flavor_tags in the DB using RUMX_TAG_MAP."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT bottle_name, flavor_tags FROM bottle_notes"
        " WHERE flavor_tags IS NOT NULL AND flavor_tags != '[]'"
    ).fetchall()
    updated = 0
    for row in rows:
        old_tags = json.loads(row['flavor_tags'] or '[]')
        new_tags = normalize_tags(old_tags)
        if new_tags != old_tags:
            if not DRY_RUN:
                conn.execute("UPDATE bottle_notes SET flavor_tags=? WHERE bottle_name=?",
                             (json.dumps(new_tags), row['bottle_name']))
            pfx = '[DRY RUN] ' if DRY_RUN else ''
            print(f"{pfx}{row['bottle_name']}:")
            print(f"  was: {old_tags}")
            print(f"  now: {new_tags}")
            updated += 1
    if not DRY_RUN:
        conn.commit()
    conn.close()
    pfx = '[DRY RUN] ' if DRY_RUN else ''
    print(f"\n{pfx}{updated} bottle(s) updated")


def parse_rum(rum_str):
    """Split RumX rum string into (name_parts[], abv, vintage)."""
    parts = [p.strip() for p in rum_str.split('  ') if p.strip()]
    abv = vintage = ''
    name_parts = []
    for i, p in enumerate(parts):
        if re.match(r'^\d+\.?\d*%$', p):
            abv = p
            if i + 1 < len(parts) and re.match(r'^(19|20)\d{2}$', parts[i + 1]):
                vintage = parts[i + 1]
            break
        name_parts.append(p)
    return name_parts, abv, vintage


def make_name(name_parts, vintage):
    joined = ' '.join(name_parts)
    # Don't append vintage if it already appears anywhere in the name
    if vintage and vintage not in joined:
        joined += ' ' + vintage
    return joined


def guess_style(name_parts, cc):
    full = ' '.join(name_parts).lower()
    if 'clairin' in full:                              return 'Clairin'
    if 'cachaça' in full or 'cachaca' in full or cc == 'BR': return 'Cachaça'
    if 'grand arôme' in full or 'grand arome' in full: return 'Grand Arôme'
    if cc in ('MQ', 'GP') or 'agricole' in full:      return 'Rhum Agricole'
    if cc == 'RE':                                     return 'Rhum'
    if 'mezcal' in full:                               return 'Mezcal'
    if 'charanda' in full:                             return 'Charanda'
    return 'Aged Rum'


def guess_age(name_parts, vintage):
    full = ' '.join(name_parts).lower()
    m = re.search(r'(\d+)\s*year', full)
    if m:    return m.group(1)
    if vintage: return 'NAS'
    if any(x in full for x in ['blanc 5', 'blanc 6', 'blanco', 'silver blanc',
                                'white overproof', 'silver cachaca']):
        return 'Unaged'
    return ''


def load_inv():
    with open(INVENTORY_FILE, newline='', encoding='utf-8') as f:
        return [dict(r) for r in csv.DictReader(f)]


def save_inv(bottles):
    with open(INVENTORY_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=INVENTORY_FIELDS)
        w.writeheader()
        for b in bottles:
            w.writerow({f: b.get(f, '') for f in INVENTORY_FIELDS})


def upsert_existing(conn, name, nose, palate, finish, tags):
    """Update tasting notes for existing bottle; don't change in_stock."""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    row = conn.execute("SELECT * FROM bottle_notes WHERE bottle_name=?", (name,)).fetchone()
    if row:
        n  = nose   if not row['nose']   else row['nose']
        p  = palate if not row['palate'] else row['palate']
        fi = finish if not row['finish'] else row['finish']
        old_tags = json.loads(row['flavor_tags'] or '[]')
        t = json.dumps(tags if not old_tags else old_tags)
        conn.execute(
            "UPDATE bottle_notes SET nose=?,palate=?,finish=?,flavor_tags=?,updated_at=?"
            " WHERE bottle_name=?",
            (n, p, fi, t, now, name))
    else:
        conn.execute(
            "INSERT INTO bottle_notes"
            " (bottle_name,in_stock,nose,palate,finish,flavor_tags,spirit_details,updated_at)"
            " VALUES (?,1,?,?,?,?,'{}',?)",
            (name, nose, palate, finish, json.dumps(tags), now))


def insert_new(conn, name, nose, palate, finish, tags):
    """Insert out-of-stock notes for a new bottle."""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    conn.execute(
        "INSERT OR IGNORE INTO bottle_notes"
        " (bottle_name,in_stock,nose,palate,finish,flavor_tags,spirit_details,updated_at)"
        " VALUES (?,0,?,?,?,?,'{}',?)",
        (name, nose, palate, finish, json.dumps(tags), now))


def main():
    bottles = load_inv()
    exact_set = {b['Name'] for b in bottles}
    clean_map = {clean(b['Name']): b['Name'] for b in bottles}  # cleaned → exact

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    added, updated = [], []
    seen_cleaned = set(clean_map.keys())

    with open(RUMX_FILE, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rumx_id  = row['RumX ID']
            rum      = row['Rum']
            cc       = row['Country'].strip()
            nose     = row.get('Nosing tags', '').strip()
            palate   = row.get('Taste tags',  '').strip()
            finish   = row.get('Finish tags', '').strip()

            raw_tags = sorted({t.strip() for ts in [nose, palate, finish]
                               for t in ts.split(',') if t.strip()})
            tags = normalize_tags(raw_tags)

            name_parts, abv, vintage = parse_rum(rum)
            country, region = COUNTRY_MAP.get(cc, ('', ''))

            # ── Try known match ───────────────────────────────────────────────
            if rumx_id in KNOWN_MATCH_KEYS:
                key = KNOWN_MATCH_KEYS[rumx_id]
                match = next((exact for cn, exact in clean_map.items() if key in cn), None)
                if match:
                    if not DRY_RUN:
                        upsert_existing(conn, match, nose, palate, finish, tags)
                    updated.append(f"{match}  ← {rumx_id}")
                    continue

            # ── Generate name and check for collision ─────────────────────────
            bottle_name = make_name(name_parts, vintage)
            cn = clean(bottle_name)

            if cn in seen_cleaned:
                exact = clean_map.get(cn)
                if exact:
                    if not DRY_RUN:
                        upsert_existing(conn, exact, nose, palate, finish, tags)
                    updated.append(f"{exact}  ← {rumx_id} (name match)")
                continue

            # ── Add new bottle ────────────────────────────────────────────────
            style = guess_style(name_parts, cc)
            age   = guess_age(name_parts, vintage)
            cat   = 'Agave Spirit' if style == 'Mezcal' else 'Rum'

            new_b = {
                'Name': bottle_name, 'Category': cat, 'Style': style,
                'Country': country,  'Region': region, 'Age': age,
                'ABV': abv, 'Producer': name_parts[0] if name_parts else '',
                'Use': 'Cocktail',
            }
            if not DRY_RUN:
                bottles.append(new_b)
                insert_new(conn, bottle_name, nose, palate, finish, tags)

            seen_cleaned.add(cn)
            clean_map[cn] = bottle_name
            added.append(f"{bottle_name}  [{cc}  {abv}]")

    if not DRY_RUN:
        conn.commit()
        bottles.sort(key=lambda b: b.get('Name', '').lower())
        save_inv(bottles)

    conn.close()

    pfx = '[DRY RUN] ' if DRY_RUN else ''
    print(f"{pfx}{len(added)} bottles added:")
    for n in added:   print(f"  + {n}")
    print(f"\n{pfx}{len(updated)} existing bottles updated:")
    for n in updated: print(f"  ~ {n}")


if __name__ == '__main__':
    if FIX_TAGS:
        fix_tags()
    else:
        main()

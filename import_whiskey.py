#!/usr/bin/env python3
"""import_whiskey.py — import whiskey tasting CSV + JSON catalog into Lloid.

Usage:
  python import_whiskey.py           # live run
  python import_whiskey.py --dry-run # preview only
"""

import csv
import json
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

BASE_DIR       = Path(__file__).parent
DATA_DIR       = BASE_DIR / 'Data'
INVENTORY_FILE = DATA_DIR / 'bar_inventory.csv'
DB_PATH        = DATA_DIR / 'lloid.db'
DIST_FILE      = DATA_DIR / 'distilleries.json'
CSV_FILE       = Path('/Users/iangilman/Downloads/Whiskey-Tasting - Sheet1.csv')
JSON_FILE      = Path('/Users/iangilman/Dropbox/Projects/SpiritedAway/data/catalogs/whiskey.json')
INVENTORY_FIELDS = ['Name', 'Category', 'Style', 'Country', 'Region', 'Age', 'ABV', 'Producer', 'Use']
DRY_RUN = '--dry-run' in sys.argv

# ── New distilleries to add ───────────────────────────────────────────────────
NEW_DISTILLERIES = [
    {'id': 'bardstown-bourbon', 'name': 'Bardstown Bourbon Company',
     'region': 'Bardstown, Kentucky', 'country': 'USA'},
    {'id': 'old-forester',      'name': 'Old Forester Distillery',
     'region': 'Louisville, Kentucky', 'country': 'USA'},
    {'id': 'kentucky-peerless', 'name': 'Kentucky Peerless Distilling',
     'region': 'Louisville, Kentucky', 'country': 'USA'},
    {'id': 'wilderness-trail',  'name': 'Wilderness Trail Distillery',
     'region': 'Danville, Kentucky', 'country': 'USA'},
    {'id': 'willett',           'name': 'Willett Distillery',
     'region': 'Bardstown, Kentucky', 'country': 'USA'},
    {'id': 'preservation',      'name': 'Preservation Distillery',
     'region': 'Bardstown, Kentucky', 'country': 'USA'},
    {'id': 'alberta-distillers','name': 'Alberta Distillers',
     'region': 'Calgary, Alberta',    'country': 'Canada'},
    {'id': 'buzzards-roost',    'name': "Buzzard's Roost Spirits",
     'region': 'Louisville, Kentucky','country': 'USA'},
    {'id': 'michters',          'name': "Michter's Fort Nelson Distillery",
     'region': 'Louisville, Kentucky','country': 'USA'},
]

# Maps cleaned bottle name substring → (distillery_id, sourced_note)
# sourced_note = text to put in spirit_details.notes when bottle is sourced, else ''
DIST_MAP = {
    'buffalo trace': ('buffalo-trace', ''),
    'rittenhouse':   ('heaven-hill', ''),
    'elijah craig':  ('heaven-hill', ''),
    'larceny':       ('heaven-hill', ''),
    'bernheim':      ('heaven-hill', ''),
    'heaven hill':   ('heaven-hill', ''),
    'ezra brooks':   ('heaven-hill', 'Bottled by Lux Row Distillers; distilled at Heaven Hill'),
    'wild turkey':   ('wild-turkey', ''),
    "russell's reserve": ('wild-turkey', ''),
    'rare breed':    ('wild-turkey', ''),
    'old forester':  ('old-forester', ''),
    'e h taylor':    ('buffalo-trace', ''),
    'e.h. taylor':   ('buffalo-trace', ''),
    'bardstown origin': ('bardstown-bourbon', ''),
    'bardstown discovery': ('bardstown-bourbon', ''),
    # Bardstown Collaborative series — whiskey sourced from outside distilleries
    'bardstown collaboration':  ('mgp', 'Collaborative series; whiskey sourced from undisclosed Tennessee and/or Indiana (likely MGP) distilleries, finished at Bardstown Bourbon Company'),
    'bardstown bourbon collaborative': ('mgp', 'Collaborative series; whiskey sourced from undisclosed Tennessee and/or Indiana (likely MGP) distilleries, finished at Bardstown Bourbon Company'),
    'peerless':      ('kentucky-peerless', ''),
    'wilderness trail': ('wilderness-trail', ''),
    'willett':       ('willett', ''),
    "willet":        ('willett', ''),
    'bomberger':     ('michters', ''),
    "michter's":     ('michters', ''),
    'michters':      ('michters', ''),
    'pinhook':       ('mgp', 'Pinhook sources whiskey from MGP and other Kentucky distilleries'),
    'buzzard':       ('buzzards-roost', 'Buzzard\'s Roost sources aged whiskey from undisclosed distilleries'),
    'linkumpinch':   ('mgp', 'Sourced from MGP Ingredients, Lawrenceburg, Indiana'),
    'holladay':      (None, 'Holladay is produced at McCormick Distilling; distillery relationship uncertain'),
    'whistlepig piggy back': ('alberta-distillers', 'Piggy Back is sourced from Alberta Distillers (Canada); Whistlepig Farm in Vermont distills some newer expressions'),
    # Old Man Winter / Very Old St. Nick — Preservation
    'old man winter': ('preservation', 'Blend of Preservation and Very Old St. Nick distillates'),
    'very old st nick': ('preservation', 'Bottled by Very Old St. Nick / Preservation Distillery'),
    'rare perfection': (None, 'Sourced from undisclosed Canadian and Kentucky distilleries'),
}

# CSV column indices (0-based)
COL_NAME    = 0; COL_DIST   = 1; COL_LOC    = 2
COL_PROOF   = 3; COL_ABV    = 4; COL_AGE    = 5
COL_BFINISH = 6  # barrel finish type
COL_COLOR   = 7; COL_NOSE   = 8; COL_PALATE = 9
COL_FINISH  = 10  # flavor finish
COL_CORN    = 11; COL_WHEAT  = 12; COL_MALT   = 13; COL_RYE = 14
COL_YEAR    = 15; COL_BARREL = 16; COL_PRICE  = 17
COL_DATE    = 18; COL_SCORE  = 19; COL_VALUE  = 20; COL_NOTES = 21


def clean(s):
    nfkd = unicodedata.normalize('NFKD', s)
    ascii_ = ''.join(c for c in nfkd if not unicodedata.combining(c))
    stripped = re.sub(r'[^a-z0-9 ]', '', ascii_.lower())
    return re.sub(r'\s+', ' ', stripped).strip()


def state_abbr(location: str) -> str:
    """'Bardstown, KY' → 'Kentucky'"""
    STATE = {
        'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
        'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut',
        'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
        'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana',
        'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
        'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan',
        'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana',
        'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
        'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina',
        'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon',
        'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
        'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington',
        'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    }
    m = re.search(r',\s*([A-Z]{2})\s*$', location.strip())
    if m:
        return STATE.get(m.group(1), m.group(1))
    return ''


_STYLE_OVERRIDES = {
    'ezra brooks':           'Straight Bourbon',
    'holladay soft':         'Wheated Bourbon',
    'rare perfection':       'Wheated Bourbon',
    'willett rye':           'Straight Rye Whiskey',
    'willet rye':            'Straight Rye Whiskey',
    'whistlepig piggy back': 'Straight Rye Whiskey',
    'bardstown discovery':   'Straight Bourbon',
    'bardstown collaboration series: west virginia': 'Straight Bourbon',
    'bardstown collaboration series: bourbon pusuit': 'Straight Bourbon',
    'rittenhouse':           'Straight Rye Whiskey',
}

_BOURBON_NAMES = (
    'elijah craig', 'e. h. taylor', 'e.h. taylor', 'heaven hill select',
    'larceny', 'old forester', 'buffalo trace', 'wild turkey', 'rare breed',
    'peerless', 'wilderness trail', 'preservation', 'pinhook', 'bomberger',
    'linkumpinch', 'buzzard', 'old man winter', 'very old st. nick',
    "michter's us 1 kentucky straight bourbon",
    "michter's 10 year kentucky straight bourbon",
    "michter's us 1 barrel strength bourbon",
)

def guess_style(name: str) -> str:
    n = name.lower()
    for k, v in _STYLE_OVERRIDES.items():
        if k in n:
            return v
    if 'wheat whiskey' in n or 'bernheim' in n: return 'Wheat Whiskey'
    if 'wheated' in n:                          return 'Wheated Bourbon'
    # Only call it rye if "rye" appears before any bourbon event context
    rye_pos     = n.find('rye')
    bourbon_pos = n.find('bourbon')
    if rye_pos >= 0 and (bourbon_pos < 0 or rye_pos < bourbon_pos):
        return 'Straight Rye Whiskey'
    if 'bourbon' in n:                          return 'Straight Bourbon'
    if any(k in n for k in _BOURBON_NAMES):     return 'Straight Bourbon'
    if 'whiskey' in n or 'whisky' in n:         return 'Whiskey'
    return 'Whiskey'


def guess_producer(name: str, distillery_col: str) -> str:
    """Brand name (what's on the bottle), not necessarily who distilled it."""
    # Some CSV distillery values are actually the brand; some are the distillery
    # For the cases where distillery_col = the actual distillery (not brand), use name prefix instead
    sourcing_only = {'mgp ingredients', 'heaven hill distilleries', 'heaven hill distilleries sourced by lux row distillers'}
    d = distillery_col.strip().rstrip(',').strip()
    if clean(d) in sourcing_only:
        # Extract brand from name (first word or two before product descriptor)
        m = re.match(r'^([A-Za-z][A-Za-z\'\.]+(?:\s+[A-Za-z][A-Za-z\'\.]+)?)', name)
        return m.group(1) if m else name.split()[0]
    return d if d else name.split()[0]


def normalize_abv(abv_str: str, proof_str: str) -> str:
    def fmt(v):
        return f"{int(v)}%" if v == int(v) else f"{v:.1f}%"
    for s in (abv_str, ''):
        s = s.strip()
        if s:
            try: return fmt(float(s))
            except ValueError: pass
    if proof_str.strip():
        try: return fmt(float(proof_str.strip()) / 2)
        except ValueError: pass
    return ''


def normalize_age(age_str: str) -> str:
    a = age_str.strip()
    if not a:
        return ''
    # "6,8,12" or "6-9" → keep as-is (it's a blend descriptor)
    if re.match(r'^\d+$', a):
        return a
    return a  # keep freeform


def build_mash_bill(corn, wheat, malt, rye):
    rows = []
    pairs = [('corn', corn), ('wheat', wheat), ('malted barley', malt), ('rye', rye)]
    for grain, pct_str in pairs:
        pct_str = pct_str.strip()
        if pct_str:
            try:
                rows.append({'grain': grain, 'pct': float(pct_str)})
            except ValueError:
                pass
    return rows


def lookup_distillery(name: str):
    """Return (dist_id, sourced_note) for a bottle name, or (None, '') if unknown."""
    cn = clean(name)
    for key, val in DIST_MAP.items():
        if key in cn:
            return val
    return (None, '')


def load_inv():
    with open(INVENTORY_FILE, newline='', encoding='utf-8') as f:
        return [dict(r) for r in csv.DictReader(f)]


def save_inv(bottles):
    with open(INVENTORY_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=INVENTORY_FIELDS)
        w.writeheader()
        for b in bottles:
            w.writerow({f: b.get(f, '') for f in INVENTORY_FIELDS})


def load_distilleries():
    with open(DIST_FILE, encoding='utf-8') as f:
        return json.load(f).get('distilleries', [])


def save_distilleries(dists):
    dists = sorted(dists, key=lambda d: d.get('name', '').lower())
    with open(DIST_FILE, 'w', encoding='utf-8') as f:
        json.dump({'distilleries': dists}, f, ensure_ascii=False, indent=2)


def upsert_note(conn, name, nose, palate, finish, spirit_details):
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    row = conn.execute('SELECT * FROM bottle_notes WHERE bottle_name=?', (name,)).fetchone()
    if row:
        n  = nose   if not row['nose']   else row['nose']
        p  = palate if not row['palate'] else row['palate']
        fi = finish if not row['finish'] else row['finish']
        old_sd = json.loads(row['spirit_details'] or '{}')
        # Merge spirit_details — don't overwrite existing keys
        merged = {**spirit_details, **old_sd}
        conn.execute(
            'UPDATE bottle_notes SET nose=?,palate=?,finish=?,spirit_details=?,updated_at=?'
            ' WHERE bottle_name=?',
            (n, p, fi, json.dumps(merged), now, name))
    else:
        conn.execute(
            'INSERT INTO bottle_notes'
            ' (bottle_name,in_stock,nose,palate,finish,flavor_tags,spirit_details,updated_at)'
            ' VALUES (?,0,?,?,?,?,?,?)',
            (name, nose, palate, finish, '[]', json.dumps(spirit_details), now))


def main():
    # ── Load existing inventory ───────────────────────────────────────────────
    bottles   = load_inv()
    clean_map = {clean(b['Name']): b['Name'] for b in bottles}

    # ── Load whiskey.json for enriched data ───────────────────────────────────
    with open(JSON_FILE, encoding='utf-8') as f:
        json_catalog = json.load(f)  # id → entry
    json_by_clean = {}
    for entry in json_catalog.values():
        json_by_clean[clean(entry['name'])] = entry

    # ── Ensure new distilleries exist ─────────────────────────────────────────
    dists    = load_distilleries()
    dist_ids = {d['id'] for d in dists}
    new_dists_added = []
    for nd in NEW_DISTILLERIES:
        if nd['id'] not in dist_ids:
            dists.append(nd)
            dist_ids.add(nd['id'])
            new_dists_added.append(nd['name'])

    # ── Parse CSV (use raw reader to handle duplicate Finish column) ──────────
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')

    added, updated, skipped = [], [], []

    with open(CSV_FILE, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            # Pad short rows
            while len(row) < 22:
                row.append('')

            name       = row[COL_NAME].strip()
            if not name:
                continue

            distillery_col = row[COL_DIST].strip()
            location       = row[COL_LOC].strip()
            proof_str      = row[COL_PROOF].strip()
            abv_str        = row[COL_ABV].strip()
            age_str        = row[COL_AGE].strip()
            barrel_finish  = row[COL_BFINISH].strip()
            nose_raw       = row[COL_NOSE].strip()
            palate_raw     = row[COL_PALATE].strip()
            finish_raw     = row[COL_FINISH].strip()
            corn           = row[COL_CORN].strip()
            wheat          = row[COL_WHEAT].strip()
            malt           = row[COL_MALT].strip()
            rye_pct        = row[COL_RYE].strip()
            notes_raw      = row[COL_NOTES].strip()

            cn = clean(name)

            # ── Check JSON catalog for richer data ───────────────────────────
            jdata = json_by_clean.get(cn)
            # Fuzzy JSON match: first significant word match
            if not jdata:
                for jk, jv in json_by_clean.items():
                    if cn and jk.startswith(cn[:20]):
                        jdata = jv
                        break

            # If JSON has nose/palate/finish, prefer it (more curated)
            if jdata:
                if not nose_raw and jdata.get('nose'):
                    nose_raw = ', '.join(jdata['nose'])
                if not palate_raw and jdata.get('palate'):
                    palate_raw = ', '.join(jdata['palate'])
                if not finish_raw and jdata.get('finish'):
                    finish_raw = ', '.join(jdata['finish'])
                if not abv_str and jdata.get('proof'):
                    abv_str = str(jdata['proof'] / 2)
                if not age_str and jdata.get('age') and str(jdata['age']).isdigit():
                    age_str = str(jdata['age'])
                if jdata.get('mash_bill') and not corn:
                    # Parse "corn 75.0%" format
                    for mb in jdata['mash_bill']:
                        m = re.match(r'(\w[\w\s]*?)\s+([\d.]+)%', mb)
                        if m:
                            grain, pct = m.group(1).lower(), m.group(2)
                            if 'corn'    in grain: corn  = pct
                            elif 'wheat' in grain: wheat = pct
                            elif 'rye'   in grain: rye_pct = pct
                            elif 'malt'  in grain: malt  = pct

            # ── Skip if already in inventory (exact or clean match) ──────────
            if cn in clean_map:
                existing = clean_map[cn]
                # Still upsert notes if we have them
                nose   = nose_raw
                palate = palate_raw
                finish = finish_raw
                sd     = _build_spirit_details(name, corn, wheat, malt, rye_pct,
                                               barrel_finish, notes_raw, jdata)
                if not DRY_RUN and (nose or palate or finish or sd):
                    upsert_note(conn, existing, nose, palate, finish, sd)
                skipped.append(f'{existing}  (already in inventory)')
                continue

            # ── Determine bottle fields ───────────────────────────────────────
            style    = guess_style(name)
            region   = state_abbr(location) if location else 'Kentucky'  # almost all KY
            country  = 'USA'
            # Whistlepig Piggy Back is VT-branded but Canadian-sourced; keep USA as country of brand
            abv      = normalize_abv(abv_str, proof_str)
            age      = normalize_age(age_str)
            producer = guess_producer(name, distillery_col)

            new_b = {
                'Name':     name,
                'Category': 'Whiskey',
                'Style':    style,
                'Country':  country,
                'Region':   region,
                'Age':      age,
                'ABV':      abv,
                'Producer': producer,
                'Use':      'Cocktail',
            }

            # ── Build spirit_details ──────────────────────────────────────────
            sd = _build_spirit_details(name, corn, wheat, malt, rye_pct,
                                       barrel_finish, notes_raw, jdata)

            if not DRY_RUN:
                bottles.append(new_b)
                upsert_note(conn, name, nose_raw, palate_raw, finish_raw, sd)
                clean_map[cn] = name

            added.append(f'{name}  [{style}  {abv}]')

    # ── Commit ────────────────────────────────────────────────────────────────
    if not DRY_RUN:
        conn.commit()
        bottles.sort(key=lambda b: b.get('Name', '').lower())
        save_inv(bottles)
        save_distilleries(dists)

    conn.close()

    pfx = '[DRY RUN] ' if DRY_RUN else ''
    print(f'{pfx}{len(new_dists_added)} distilleries added: {new_dists_added}')
    print(f'\n{pfx}{len(added)} bottles added:')
    for n in added:   print(f'  + {n}')
    print(f'\n{pfx}{len(skipped)} bottles already in inventory (notes updated where available):')
    for n in skipped: print(f'  ~ {n}')


def _build_spirit_details(name, corn, wheat, malt, rye_pct, barrel_finish, notes_raw, jdata):
    sd = {}
    mash = build_mash_bill(corn, wheat, malt, rye_pct)
    if mash:
        sd['mash_bill'] = mash
    if barrel_finish and barrel_finish.lower() not in ('none', ''):
        sd['barrel_type'] = barrel_finish
    # Distillery attribution
    dist_id, sourced_note = lookup_distillery(name)
    if dist_id:
        sd['distilleries'] = [dist_id]
    note_parts = []
    if sourced_note:
        note_parts.append(sourced_note)
    if notes_raw:
        note_parts.append(notes_raw)
    if note_parts:
        sd['notes'] = ' | '.join(note_parts)
    return sd


if __name__ == '__main__':
    main()

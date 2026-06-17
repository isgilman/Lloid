#!/usr/bin/env python3
"""fix_rum_distilleries.py — link rum/agave bottles to distilleries.

Usage:
  python fix_rum_distilleries.py           # live run
  python fix_rum_distilleries.py --dry-run
"""

import csv
import json
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

BASE_DIR  = Path(__file__).parent
DATA_DIR  = BASE_DIR / 'Data'
INV_FILE  = DATA_DIR / 'bar_inventory.csv'
DB_PATH   = DATA_DIR / 'lloid.db'
DIST_FILE = DATA_DIR / 'distilleries.json'
DRY_RUN   = '--dry-run' in sys.argv

NEW_DISTILLERIES = [
    {'id': 'havana-club',              'name': 'Cuba Ron S.A. (Havana Club)',
     'region': 'San José de las Lajas, Mayabeque', 'country': 'Cuba'},
    {'id': 'savanna',                  'name': 'Savanna Distillery',
     'region': 'Saint-Louis',          'country': 'Réunion'},
    {'id': 'saint-lucia-distillers',   'name': 'Saint Lucia Distillers',
     'region': 'Roseau Valley',        'country': 'Saint Lucia'},
    {'id': 'river-antoine',            'name': 'River Antoine Estate Distillery',
     'region': 'Saint Patrick',        'country': 'Grenada'},
    {'id': 'chalong-bay',              'name': 'Chalong Bay Distillery',
     'region': 'Phuket',               'country': 'Thailand'},
    {'id': 'mhoba',                    'name': 'MHOBA Rum Distillery',
     'region': 'Mpumalanga',           'country': 'South Africa'},
    {'id': 'isautier',                 'name': 'Distillerie Isautier',
     'region': 'Saint-Pierre',         'country': 'Réunion'},
    {'id': 'beenleigh',                'name': 'Beenleigh Artisan Distillers',
     'region': 'Eagleby, Queensland',  'country': 'Australia'},
    {'id': 'goslings',                 'name': "Gosling's Rum",
     'region': 'Hamilton',             'country': 'Bermuda'},
    {'id': 'west-indies-rum-distillery','name': 'West Indies Rum Distillery (WIRD)',
     'region': 'Black Rock, St. Michael', 'country': 'Barbados'},
    {'id': 'santa-teresa',             'name': 'Hacienda Santa Teresa',
     'region': 'El Consejo, Aragua',   'country': 'Venezuela'},
    {'id': 'batavia-arrack',           'name': 'Muliadi Distillery (Batavia Arrack)',
     'region': 'West Java',            'country': 'Indonesia'},
    {'id': 'bacardi',                  'name': 'Bacardí Puerto Rico',
     'region': 'Cataño',               'country': 'Puerto Rico'},
    {'id': 'clairin-pignon',           'name': 'Distillerie Malas Auguste (Clairin Pignon)',
     'region': 'Pignon',               'country': 'Haiti'},
    {'id': 'clairin-vaval',            'name': 'Chelo Vaval (Clairin Vaval)',
     'region': 'Cavaillon',            'country': 'Haiti'},
    {'id': 'clairin-le-rocher',        'name': 'Distillerie Le Rocher (Clairin)',
     'region': 'Léogâne',              'country': 'Haiti'},
    {'id': 'clairin-sonson',           'name': 'Sonson Pierre Gilles (Clairin Sonson)',
     'region': 'Saint-Michel de l\'Attalaye', 'country': 'Haiti'},
    {'id': 'maggies-farm',             'name': "Maggie's Farm Rum",
     'region': 'Pittsburgh, Pennsylvania', 'country': 'USA'},
    {'id': 'alambique-serrano',        'name': 'Alambique Serrano (Cañada)',
     'region': 'San Juan Piñas, Oaxaca', 'country': 'Mexico'},
    {'id': 'privateer',                'name': 'Privateer Rum',
     'region': 'Ipswich, Massachusetts', 'country': 'USA'},
    {'id': 'trois-rivieres',           'name': 'Trois-Rivières',
     'region': 'Sainte-Luce',          'country': 'Martinique'},
    {'id': 'novo-fogo',                'name': 'Novo Fogo Distillery',
     'region': 'Morretes, Paraná',     'country': 'Brazil'},
    {'id': 'travellers',               'name': 'Travellers Liquors',
     'region': 'Belize City',          'country': 'Belize'},
]


def clean(s):
    nfkd = unicodedata.normalize('NFKD', s)
    ascii_ = ''.join(c for c in nfkd if not unicodedata.combining(c))
    stripped = re.sub(r'[^a-z0-9 ]', '', ascii_.lower())
    return re.sub(r'\s+', ' ', stripped).strip()


# Maps clean(producer) substring → distillery id
# (checked in order — put more specific keys first if overlap)
PROD_MAP = [
    ('appleton estate',         'appleton-estate'),
    ('barbancourt',             'barbancourt'),
    ('caroni',                  'caroni'),
    ('clement',                 'clement'),
    ('habitation clement',      'clement'),
    ('rhum jm',                 'jm'),
    ('distillerie jm',          'jm'),
    ('compania licorera',       'flor-de-cana'),
    ('foursquare',              'foursquare'),
    ('hampden estate',          'hampden-estate'),
    ('hampden',                 'hampden-estate'),
    ('las cabras',              'las-cabras'),
    ('long pond',               'long-pond'),
    ('longueteau',              'longueteau'),
    ('monymusk',                'monymusk'),
    ('mount gay',               'mount-gay'),
    ('neisson',                 'neisson'),
    ('renegade',                'renegade-rum-distillery'),
    ('river antoine',           'river-antoine'),
    ('saint james',             'saint-james'),
    ('saint lucia distillers',  'saint-lucia-distillers'),
    ('savanna',                 'savanna'),
    ('smith cross',             'new-yarmouth'),
    ('south pacific',           'south-pacific-distillers'),
    ('worthy park estate',      'worthy-park-estate'),
    ('worthy park',             'worthy-park-estate'),
    ('j wray nephew',           'new-yarmouth'),
    ('wray nephew',             'new-yarmouth'),
    ('havana club',             'havana-club'),
    ('demerara distillers',     'demarara-distillers-limited'),
    ('port mourant',            'demarara-distillers-limited'),
    ('uitvlugt',                'demarara-distillers-limited'),
    ('versailles',              'demarara-distillers-limited'),
    ('tdl',                     'angostura'),
    ('chalong bay distillery',  'chalong-bay'),
    ('mhoba',                   'mhoba'),
    ('isautier',                'isautier'),
    ('beenleigh distillery',    'beenleigh'),
    ('beenleigh',               'beenleigh'),
    ('goslings',                'goslings'),
    ('santa teresa',            'santa-teresa'),
    ('van oosten',              'batavia-arrack'),
    ('bacardi',                 'bacardi'),
    ('clairin sajous',          'clairin-sajous'),
    ('distillerie malas',       'clairin-pignon'),
    ('sonson pierre',           'clairin-sonson'),
    ('le rocher',               'clairin-le-rocher'),
    ('arawaks',                 'clairin-vaval'),
    ('chelo',                   'clairin-sajous'),
    ('distillerie bielle',      'bielle'),
    ('distillerie damoiseau',   'damoiseau'),
    ('distillerie depaz',       'depaz'),
    ('distillerie le galion',   'distillerie-le-galion'),
    ('la favorite',             'la-favorite'),
    ('trois rivieres',          'trois-rivieres'),
    ('rum bar',                 'rum-bar'),
    ('westmoreland',            'rum-bar'),
    ('maggie s farm',           'maggies-farm'),
    ('tequila ocho',            'la-altena'),
    ('alambique serrano',       'alambique-serrano'),
    ('privateer rum',           'privateer'),
    ('novo fogo',               'novo-fogo'),
    ('travellers',              'travellers'),
    ('distillerie bielle',      'bielle'),
    ('distillerie damoiseau',   'damoiseau'),
    ('tres generaciones',       'la-altena'),
    ('rhum jm',                 'jm'),
]

# Maps clean(bottle_name) substring → distillery id (for independent bottlings)
NAME_MAP = [
    ('appleton estate',         'appleton-estate'),
    ('hampden',                 'hampden-estate'),
    ('long pond',               'long-pond'),
    ('monymusk',                'monymusk'),
    ('worthy park',             'worthy-park-estate'),
    ('savanna',                 'savanna'),
    ('foursquare',              'foursquare'),
    ('barbancourt',             'barbancourt'),
    ('south pacific',           'south-pacific-distillers'),
    ('beenleigh',               'beenleigh'),
    ('clairin sajous',          'clairin-sajous'),
    ('clairin pignon',          'clairin-pignon'),
    ('clairin vaval',           'clairin-vaval'),
    ('clairin sonson',          'clairin-sonson'),
    ('clairin',                 'clairin-sajous'),  # fallback for unlabeled clairins
    ('saint lucia distillers',  'saint-lucia-distillers'),
    ('river antoine',           'river-antoine'),
    ('rivers royal grenadian',  'river-antoine'),
    ('caroni',                  'caroni'),
    ('el dorado',               'demarara-distillers-limited'),
    ('hamilton 86 demerara',    'demarara-distillers-limited'),
    ('real mccoy',              'foursquare'),
    ('west indies maison ferrand', 'west-indies-rum-distillery'),
    ('batavia arrack',          'batavia-arrack'),
    ('wray nephew',             'new-yarmouth'),
    ('smith cross',             'new-yarmouth'),
    ('flor de cana',            'flor-de-cana'),
    ('longueteau',              'longueteau'),
    ('neisson',                 'neisson'),
    ('trois rivieres',          'trois-rivieres'),
    ('saint james',             'saint-james'),
    ('rhum jm',                 'jm'),
    ('la favorite',             'la-favorite'),
    ('mount gay',               'mount-gay'),
    ('tsook',                   'alambique-serrano'),
    ('canada alambique serrano','alambique-serrano'),
    ('chalong bay',             'chalong-bay'),
    ('mhoba',                   'mhoba'),
    ('goslings',                'goslings'),
    ('pere labat',              'bielle'),
    ('isautier',                'isautier'),
    ('maggie s farm',           'maggies-farm'),
]

# Bottles to explicitly skip (multi-source blends / unknown)
SKIP_NAMES = {
    clean('Barrell Rum Private Release (Barrell Craft Spirits)'),
    clean('Five & 20 Spirits Hamilton 87 White Stache'),
    clean('Maggie\'s Farm 50/50 Dark'),
}


def find_distillery(name, producer):
    cn  = clean(name)
    cp  = clean(producer)
    if cn in SKIP_NAMES:
        return None
    for key, did in PROD_MAP:
        if key in cp:
            return did
    for key, did in NAME_MAP:
        if key in cn:
            return did
    return None


def main():
    # ── Load inventory ────────────────────────────────────────────────────────
    with open(INV_FILE, newline='', encoding='utf-8') as f:
        inv = {r['Name']: r for r in csv.DictReader(f)}

    # ── Ensure new distilleries exist ─────────────────────────────────────────
    with open(DIST_FILE, encoding='utf-8') as f:
        dists = json.load(f).get('distilleries', [])
    existing_ids = {d['id'] for d in dists}
    added_names = []
    for nd in NEW_DISTILLERIES:
        if nd['id'] not in existing_ids:
            dists.append(nd)
            existing_ids.add(nd['id'])
            added_names.append(nd['name'])

    if not DRY_RUN and added_names:
        dists_sorted = sorted(dists, key=lambda d: d.get('name', '').lower())
        with open(DIST_FILE, 'w', encoding='utf-8') as f:
            json.dump({'distilleries': dists_sorted}, f, ensure_ascii=False, indent=2)

    # ── Update bottle_notes ───────────────────────────────────────────────────
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')

    rows = conn.execute('SELECT bottle_name, spirit_details FROM bottle_notes').fetchall()
    linked, skipped_no_match, skipped_multi = [], [], []

    for r in rows:
        b = inv.get(r['bottle_name'], {})
        cat = b.get('Category', '')
        if cat not in ('Rum', 'Agave Spirit'):
            continue

        sd = json.loads(r['spirit_details'] or '{}')
        if sd.get('distilleries'):
            continue  # already set

        producer = b.get('Producer', '')
        did = find_distillery(r['bottle_name'], producer)

        if did is None:
            # Check if in explicit skip
            if clean(r['bottle_name']) in SKIP_NAMES:
                skipped_multi.append(r['bottle_name'])
            else:
                skipped_no_match.append(r['bottle_name'])
            continue

        if did not in existing_ids:
            skipped_no_match.append(f'{r["bottle_name"]}  (unknown dist id: {did})')
            continue

        sd['distilleries'] = [did]
        if not DRY_RUN:
            conn.execute('UPDATE bottle_notes SET spirit_details=? WHERE bottle_name=?',
                         (json.dumps(sd), r['bottle_name']))
        linked.append(f'{r["bottle_name"]}  → {did}')

    if not DRY_RUN:
        conn.commit()
    conn.close()

    pfx = '[DRY RUN] ' if DRY_RUN else ''
    print(f'{pfx}{len(added_names)} distilleries added: {added_names}')
    print(f'\n{pfx}{len(linked)} bottles linked to distilleries:')
    for n in linked: print(f'  ✓ {n}')
    print(f'\n{pfx}{len(skipped_multi)} skipped (multi-source blends):')
    for n in skipped_multi: print(f'  ~ {n}')
    print(f'\n{pfx}{len(skipped_no_match)} no match found:')
    for n in skipped_no_match: print(f'  ? {n}')


if __name__ == '__main__':
    main()

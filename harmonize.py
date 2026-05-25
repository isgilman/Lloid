#!/usr/bin/env python3
"""harmonize.py – Clean up ingredient names across the cocktail database.

What this does:
  1. Fixes 1929 Death & Co. ingredients where the amount+unit was embedded in
     the name field (OCR parsing artifact): "2 ounce Beefeater Gin" →
     amount="2", unit="oz", name="Beefeater Gin"
  2. Normalises brand-specific spirit names to their generic category, moving
     the brand recommendation to the notes field:
       "El Tesoro Platinum Tequila" → name="Blanco Tequila", notes="El Tesoro Platinum"
       "Marie Brizard White Creme De Cacao" → name="White Crème de Cacao", notes="Marie Brizard"
  3. Fixes OCR encoding corruption (Ë→ç, Ô→ñ, Ï→è, etc.)
  4. Normalises capitalisation (title-case ingredient names consistently)

Run from the project root:
    python3 harmonize.py

The script modifies Data/cocktails.json in-place and then reloads into the
SQLite database via db.import_cocktails().
"""

import json
import re
from pathlib import Path
import db as _db

DATA_DIR = Path(__file__).parent / 'Data'
COCKTAILS_FILE = DATA_DIR / 'cocktails.json'

# ── Encoding fixes ─────────────────────────────────────────────────────────────
# These are Windows-1252 / PDF OCR garbling artifacts. Order matters: longer
# sequences first so they don't get partially matched.

# ASCII apostrophe and double-quote as constants (avoids editor smart-quoting them
# in the ENCODING_FIXES list below).
_APOS = chr(0x27)   # ASCII apostrophe
_QUOT = chr(0x22)   # ASCII double quote

ENCODING_FIXES = [
    # Normalise smart/curly apostrophes and quotes to ASCII equivalents.
    # Must come first so later fixes operate on clean text.
    (chr(0x2019), _APOS),  # RIGHT SINGLE QUOTATION MARK
    (chr(0x2018), _APOS),  # LEFT SINGLE QUOTATION MARK
    (chr(0x201d), _QUOT),  # RIGHT DOUBLE QUOTATION MARK
    (chr(0x201c), _QUOT),  # LEFT DOUBLE QUOTATION MARK
    (chr(0x00bb), chr(0x3e)*2),  # RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
    # Specific garbled words (longest first)
    ('BÌnÌdictine', 'Bénédictine'),
    ('CaffÏ Moka',  'Caffè Moka'),
    ('DuchÌ de Longueville', 'Duché de Longueville'),
    ('EmelÐn',      'Emilín'),
    ('GÌnÌpy',      'Génépi'),
    ('GÌnÌp',       'Génépy'),  # alternate spelling
    ('PremiÏre',    'Première'),
    ('SpÇtlese',    'Spätlese'),
    # Per-character replacements in known contexts
    ('XimÌnez',     'Ximénez'),
    ('NuÔo',        'Nuño'),
    ('CaÔa',        'Caña'),
    ('aÔejo',       'añejo'),
    ('Ôejo',        'ñejo'),
    ('crÏme',       'crème'),
    ('CrÏme',       'Crème'),
    ('curaËao',     'curaçao'),
    ('CuraËao',     'Curaçao'),
    ('cachaËa',     'cachaça'),
    ('PÍche',       'Pêche'),
    ('MÜre',        'Mûre'),
    ('Ðn',          'ín'),
    ('Ðo',          'ío'),
]


def fix_encoding(s: str) -> str:
    for bad, good in ENCODING_FIXES:
        s = s.replace(bad, good)
    return s


# ── Amount parsing (D&C OCR artefact) ─────────────────────────────────────────

# Maps Unicode fraction characters to decimal strings
FRAC_TO_DECIMAL = {'½': '0.5', '¼': '0.25', '¾': '0.75'}

# Pattern: optional integer + optional unicode fraction, then unit, then name
_AMOUNT_PAT = re.compile(
    r'^(\d+[½¼¾]?|[½¼¾])\s+'
    r'(ounce[s]?|oz|teaspoon[s]?|tsp|tablespoon[s]?|tbsp|'
    r'dash(?:es)?|drop[s]?|splash|pinch|barspoon|'
    r'cup[s]?|liter[s]?|litre[s]?|ml|cl)\s+'
    r'(.+)$',
    re.IGNORECASE,
)

# Garnish pattern: "1 GRAPEFRUIT twist", "1 LEMON twist", "1 Egg White" etc.
_GARNISH_PAT = re.compile(
    r'^(\d+)\s+(.+)$',
)

UNIT_NORM = {
    'ounce': 'oz',  'ounces': 'oz',
    'teaspoon': 'tsp', 'teaspoons': 'tsp',
    'tablespoon': 'tbsp', 'tablespoons': 'tbsp',
    'dash': 'dash', 'dashes': 'dash',
    'drop': 'drop', 'drops': 'drop',
}


def _parse_amount_str(s: str):
    """'1¾' → '1.75',  '¾' → '0.75',  '2' → '2',  else None."""
    s = s.strip()
    for frac, dec in FRAC_TO_DECIMAL.items():
        if s == frac:
            return dec
        if s.endswith(frac) and s[:-len(frac)].isdigit():
            return str(int(s[:-len(frac)]) + float(dec))
    if s.isdigit():
        return s
    return None


# ── D&C OCR fraction-prefix normalisation ─────────────────────────────────────
# The 1929 D&C book PDF was OCR'd with garbled fraction characters.  Before we
# try to parse "amount unit name" we fix the prefix so the pattern can match.
#
# Mapping: garbled prefix → canonical unicode fraction (keep trailing space).
# Longest/most-specific entries first.
_DC_FRACTION_MAP = [
    # ¾ variants (most common cocktail measure).
    # After ENCODING_FIXES all smart quotes are ASCII, so patterns use ASCII here.
    ('¥%, ',   '¾ '),  # "¥%, Ounce" (comma-space variant)
    ('3%, ',   '¾ '),  # "3%, Ounce"
    ('¥% ',    '¾ '),  # yen-sign + percent
    ('Y% ',    '¾ '),  # Y + percent
    ('Ys ',    '¾ '),  # Y + s
    ('4% ',    '¾ '),  # 4-percent (OCR of ¾)
    ('%">>', '¾ '),    # %">> (was %"»)
    ('\'">>', '¾ '),   # '">> (was '"»)
    ('\'"',    '¾ '),  # '" (straight-single + straight-double after encoding fix)
    ('%"',     '¾ '),  # %" (percent + double-quote)
    ('%\'%~ ', '¾ '),  # %'%~
    ('¥/,',    '¾'),   # yen + slash-comma
    ('">> ',   '¾ '),  # lone ">>" (was "»") before unit
    ('" ',     '¾ '),  # lone double-quote + space before unit
    # 1¼ variants ("1'" where the ¼ OCR'd as a curly-quote then normalised)
    ("1''4 ",  "1" + chr(0xbc) + " "),  # 1''4 → 1¼
    ("1''a ", "1" + chr(0xbc) + " "),  # 1''a → 1¼
    ("1'a ",   "1" + chr(0xbc) + " "),  # 1'a  → 1¼
    ("1' ",    "1" + chr(0xbc) + " "),  # 1'   → 1¼
    # ½ variants
    ("'2 ",    chr(0xbd) + " "),  # straight-apostrophe + "2" + space → ½
    ('\\) ',   chr(0xbd) + " "),  # \) before Teaspoon → ½
    # ¼ variants
    ("'Teaspoon", '¼ Teaspoon'),  # apostrophe right before unit (no space)
    ("'teaspoon", '¼ teaspoon'),
    # Unknown single-quote prefixes → assume ¾ (most common)
    ("' ",     '¾ '),  # lone straight-apostrophe + space
    ('*h ',    '¾ '),
    ('*% ',    '¾ '),
    ("'*h ",   '¾ '),
]

_STRIP_BARE_UNIT = re.compile(
    r'^(Ounce|ounce|Teaspoon|teaspoon)\s+(.+)$'
)


def _normalize_dc_fraction_prefix(name: str) -> str:
    """Replace garbled fraction prefix in a D&C ingredient name."""
    for bad, good in _DC_FRACTION_MAP:
        if name.startswith(bad):
            return good + name[len(bad):]
    # Bare unit with no preceding amount ("Ounce Lime Juice" → "Lime Juice")
    m = _STRIP_BARE_UNIT.match(name)
    if m:
        return m.group(2)
    return name


def maybe_parse_dc_amount(ing: dict) -> bool:
    """Try to split 'amount unit name' out of ing['name'].  Returns True if changed."""
    if ing.get('amount') or ing.get('unit'):
        return False   # already has fields
    name = _normalize_dc_fraction_prefix(ing.get('name', '').strip())
    if name != ing.get('name', '').strip():
        ing['name'] = name   # write back normalised form even if unit-parse fails
    m = _AMOUNT_PAT.match(name)
    if m:
        amt_str, unit_raw, rest = m.group(1), m.group(2).lower(), m.group(3)
        amt = _parse_amount_str(amt_str)
        unit = UNIT_NORM.get(unit_raw, unit_raw)
        if amt:
            ing['amount'] = amt
            ing['unit']   = unit
            ing['name']   = rest.strip()
            return True
    # Garnish / count items: "1 GRAPEFRUIT twist", "1 Egg White", "1 Cinnamon Stick"
    # Only when there's NO recognised unit (handled above) and first token is a digit
    m2 = _GARNISH_PAT.match(name)
    if m2:
        cnt, rest = m2.group(1), m2.group(2)
        # Avoid false positives like "12 WHITE SUGAR cubes" → those have units above
        if rest.replace(' ', '').isalpha() or any(
            rest.lower().startswith(p) for p in
            ['egg', 'grapefruit', 'lemon', 'orange', 'lime', 'mint', 'cilantro',
             'cucumber', 'cinnamon', 'strawberry', 'whole', 'small', 'large',
             'fresh', 'bar', 'piece', 'slice', 'wedge']
        ):
            ing['amount'] = cnt
            ing['unit']   = ''
            ing['name']   = rest.strip()
            return True
    return False


# ── Brand → generic mapping ────────────────────────────────────────────────────
# Key:   normalised (lower-stripped) ingredient name
# Value: (canonical_name, notes_to_prepend)   — notes='' means no brand note added

BRAND_MAP = {
    # ── GIN ──────────────────────────────────────────────────────────────────
    'beefeater london dry gin':                 ('Gin', 'Beefeater'),
    'beefeater 2.4 gin':                        ('Gin', 'Beefeater 2.4'),
    'beefeater gin':                            ('Gin', 'Beefeater'),
    'beefeater london dry':                     ('Gin', 'Beefeater'),
    'tanqueray london dry gin':                 ('Gin', 'Tanqueray'),
    'tanqueray no. ten gin':                    ('Gin', 'Tanqueray No. Ten'),
    'tanqueray 10 gin':                         ('Gin', 'Tanqueray No. Ten'),
    'tanqueray gin':                            ('Gin', 'Tanqueray'),
    'plymouth gin':                             ('Gin', 'Plymouth'),
    'plymouth sloe gin':                        ('Sloe Gin', 'Plymouth'),
    'fords gin':                                ('Gin', 'Fords'),
    "martin miller's westbourne-strength gin":  ('Gin', "Martin Miller's"),
    "perry's tot navy-strength gin":            ('Navy-Strength Gin', "Perry's Tot"),
    'anchor junipero gin':                      ('Gin', 'Anchor Junipero'),
    'bruichladdich botanist gin':               ('Gin', 'The Botanist'),
    'aviation gin':                             ('Gin', 'Aviation'),
    'ransom old tom gin':                       ('Old Tom Gin', 'Ransom'),
    "hayman's old tom gin":                     ('Old Tom Gin', "Hayman's"),
    "hayman's royal dock gin":                  ('Navy-Strength Gin', "Hayman's Royal Dock"),
    "burrough's reserve gin":                   ('Gin', "Burrough's Reserve"),
    'edinburgh seaside gin':                    ('Gin', 'Edinburgh Seaside'),
    'old raj blue navy strength gin':           ('Navy-Strength Gin', 'Old Raj Blue'),
    'st. george dry rye gin':                   ('Gin', 'St. George Dry Rye'),
    'st. george terroir gin':                   ('Gin', 'St. George Terroir'),
    'horseradish infused gin':                  ('Horseradish-Infused Gin', ''),
    'szechuan peppercorn–infused gin':          ('Szechuan Peppercorn-Infused Gin', ''),
    'szechuan peppercorn-infused gin':          ('Szechuan Peppercorn-Infused Gin', ''),

    # ── TEQUILA ───────────────────────────────────────────────────────────────
    'el tesoro platinum tequila':               ('Blanco Tequila', 'El Tesoro Platinum'),
    'el tesoro reposado tequila':               ('Reposado Tequila', 'El Tesoro'),
    'el tesoro anejo tequila':                  ('Añejo Tequila', 'El Tesoro'),
    'siembra azul blanco tequila':              ('Blanco Tequila', 'Siembra Azul'),
    'siembra azul reposado tequila':            ('Reposado Tequila', 'Siembra Azul'),
    'siembra azul anejo tequila':               ('Añejo Tequila', 'Siembra Azul'),
    'siembra azul añejo tequila':               ('Añejo Tequila', 'Siembra Azul'),
    'siete leguas blanco tequila':              ('Blanco Tequila', 'Siete Leguas'),
    'siete leguas reposado tequila':            ('Reposado Tequila', 'Siete Leguas'),
    'siete leguas anejo tequila':               ('Añejo Tequila', 'Siete Leguas'),
    'siete leguas añejo tequila':               ('Añejo Tequila', 'Siete Leguas'),
    'don julio blanco tequila':                 ('Blanco Tequila', 'Don Julio'),
    'don julio reposado tequila':               ('Reposado Tequila', 'Don Julio'),
    'fortaleza reposado tequila':               ('Reposado Tequila', 'Fortaleza'),
    'fortaleza blanco tequila':                 ('Blanco Tequila', 'Fortaleza'),
    'ocho 2012 plata tequila':                  ('Blanco Tequila', 'Ocho Plata'),
    'chinaco verde blanco tequila':             ('Blanco Tequila', 'Chinaco Verde'),
    'cabeza blanco tequila':                    ('Blanco Tequila', 'Cabeza'),
    'centinela reposado tequila':               ('Reposado Tequila', 'Centinela'),
    'pueblo viejo anejo tequila':               ('Añejo Tequila', 'Pueblo Viejo'),
    'excellia blanco tequila':                  ('Blanco Tequila', 'Excellia'),
    'jalapeño infused tequila':                 ('Jalapeño-Infused Blanco Tequila', ''),
    'jalapeño-infused tequila':                 ('Jalapeño-Infused Blanco Tequila', ''),
    'olive oil–washed tequila':                 ('Olive Oil-Washed Blanco Tequila', ''),

    # ── RUM ───────────────────────────────────────────────────────────────────
    'appleton estate v/x rum':                  ('Aged Rum', 'Appleton V/X'),
    'appleton v x jamaican rum':                ('Aged Rum', 'Appleton V/X'),
    'appleton estate reserve rum':              ('Aged Rum', 'Appleton Reserve'),
    'appleton signature blend rum':             ('Aged Rum', 'Appleton Signature'),
    'appleton signature rum':                   ('Aged Rum', 'Appleton Signature'),
    'appleton white rum':                       ('Rum', 'Appleton'),
    'barbancourt 3-star rum':                   ('Aged Rum', 'Barbancourt 3-Star'),
    'barbancourt white rum':                    ('Rum', 'Barbancourt'),
    'ron del barrilito 3-star rum':             ('Aged Rum', 'Ron del Barrilito 3-Star'),
    'scarlet ibis rum':                         ('Rum', 'Scarlet Ibis'),
    'smith & cross rum':                        ('Rum', 'Smith & Cross'),
    'smith & cross':                            ('Rum', 'Smith & Cross'),
    'smith cross navy strength jamaican rum':   ('Rum', 'Smith & Cross Navy Strength'),
    'el dorado 15-year rum':                    ('Aged Rum', 'El Dorado 15-Year'),
    'el dorado 15 year rum':                    ('Aged Rum', 'El Dorado 15-Year'),
    'el dorado 12 year rum':                    ('Aged Rum', 'El Dorado 12-Year'),
    'el dorado 3 year rum':                     ('Rum', 'El Dorado 3-Year'),
    'el dorado 151 rum':                        ('Overproof Rum', 'El Dorado 151'),
    "gosling's black seal rum":                 ('Dark Rum', "Gosling's Black Seal"),
    'cruzan black strap rum':                   ('Dark Rum', 'Cruzan Black Strap'),
    'cruzan black strap':                       ('Dark Rum', 'Cruzan Black Strap'),
    'cruzan single-barrel rum':                 ('Aged Rum', 'Cruzan Single-Barrel'),
    'plantation barbados 5-year rum':           ('Aged Rum', 'Plantation Barbados 5-Year'),
    'plantation pineapple rum':                 ('Pineapple Rum', 'Plantation'),
    'bacardi ron superior limited edition':     ('Rum', 'Bacardi'),
    'zacapa 23-year rum':                       ('Aged Rum', 'Ron Zacapa 23'),
    'ron zacapa 23 rum':                        ('Aged Rum', 'Ron Zacapa 23'),
    'angostura 5-year rum':                     ('Aged Rum', 'Angostura 5-Year'),
    'la favorite rhum agricole blanc':          ('Rhum Agricole Blanc', 'La Favorite'),
    'rhum jm 100-proof agricole blanc':         ('Rhum Agricole Blanc', 'Rhum JM 100-Proof'),
    'rhum j. m blanc agricole martinique 100 proof rum': ('Rhum Agricole Blanc', 'Rhum J.M 100-Proof'),
    'rhum j. m gold rum':                       ('Aged Rhum Agricole', 'Rhum J.M Gold'),
    'rhum clément première canne rum':          ('Rhum Agricole Blanc', 'Rhum Clément Première Canne'),
    'van oosten batavia arrack':                ('Batavia Arrack', 'Van Oosten'),
    'batavia arrack van oosten':                ('Batavia Arrack', 'Van Oosten'),
    'avuá amburana cachaça':                    ('Cachaça', 'Avuá Amburana'),
    'avuá prata cachaça':                       ('Cachaça', 'Avuá Prata'),
    'novo fogo cachaça':                        ('Cachaça', 'Novo Fogo'),
    'caña brava rum':                           ('Rum', 'Caña Brava'),
    'boukman rhum':                             ('Rum', 'Boukman'),
    'flor de caña 4 year extra dry rum':        ('Rum', 'Flor de Caña 4-Year'),
    'flor de caña rum 4 year white':            ('Rum', 'Flor de Caña 4-Year'),
    'flor de cana 4 year extra dry rum':        ('Rum', 'Flor de Caña 4-Year'),
    'english harbour rum':                      ('Aged Rum', 'English Harbour'),
    'hamilton 151 demerara rum':                ('Overproof Rum', 'Hamilton 151 Demerara'),
    'hamilton jamaican gold rum':               ('Aged Rum', 'Hamilton Jamaican Gold'),
    'lemon hart 151 demerara rum':              ('Overproof Rum', 'Lemon Hart 151'),
    'mount gay black barrel rum':               ('Aged Rum', 'Mount Gay Black Barrel'),
    'pampero aniversario rum':                  ('Aged Rum', 'Pampero Aniversario'),
    'santa teresa 1796 rum':                    ('Aged Rum', 'Santa Teresa 1796'),
    'diplomatico mantuano rum':                 ('Aged Rum', 'Diplomático Mantuano'),
    'diplomático mantuano rum':                 ('Aged Rum', 'Diplomático Mantuano'),
    'diplomatico reserva exclusiva rum':        ('Aged Rum', 'Diplomático Reserva Exclusiva'),
    'diplomático reserva exclusiva rum':        ('Aged Rum', 'Diplomático Reserva Exclusiva'),
    'pineapple-infused aged rum':               ('Pineapple-Infused Aged Rum', ''),
    'pineapple-infused rum':                    ('Pineapple-Infused Rum', ''),

    # ── COGNAC / BRANDY ────────────────────────────────────────────────────────
    'hine h cognac':                            ('Cognac', 'Hine H'),
    'pierre ferrand 1840 cognac':               ('Cognac', 'Pierre Ferrand 1840'),
    'pierre ferrand ambre cognac':              ('Cognac', 'Pierre Ferrand Ambre'),
    'louis royer force 53 cognac':              ('Cognac', 'Louis Royer Force 53'),
    'jean grosperrin vsop cognac':              ('Cognac', 'Jean Grosperrin VSOP'),
    'tariquet vs classique bas-armagnac':       ('Armagnac', 'Tariquet VS Classique'),
    "laird's bonded apple brandy":              ('Apple Brandy', "Laird's Bonded"),
    "laird's 7¾ year apple brandy":             ('Apple Brandy', "Laird's 7¾-Year"),
    "laird's apple brandy":                     ('Apple Brandy', "Laird's"),
    'busnel vsop calvados':                     ('Calvados', 'Busnel VSOP'),
    'roger groult 3 year calvados pays d\'auge': ('Calvados', 'Roger Groult 3-Year'),
    'macchu pisco':                             ('Pisco', 'Macchu'),
    'macchu pisco la diablada':                 ('Pisco', 'Macchu La Diablada'),
    'campo de encanto acholado pisco':          ('Acholado Pisco', 'Campo de Encanto'),
    'st. george unaged apple brandy':           ('Apple Brandy', 'St. George Unaged'),
    'clear creek pear brandy':                  ('Pear Brandy', 'Clear Creek'),
    'clear creek kirschwasser':                 ('Kirsch', 'Clear Creek'),
    'purkhart pear williams brandy':            ('Pear Brandy', 'Purkhart'),
    'monteru brandy':                           ('Brandy', 'Monteru'),

    # ── SCOTCH / WHISKY ────────────────────────────────────────────────────────
    'laphroaig 10-year scotch':                 ('Islay Scotch', 'Laphroaig 10-Year'),
    'laphroaig 12-year scotch':                 ('Islay Scotch', 'Laphroaig 12-Year'),
    'laphroaig 10 year islay scotch':           ('Islay Scotch', 'Laphroaig 10-Year'),
    'laphroaig 10 year scotch':                 ('Islay Scotch', 'Laphroaig 10-Year'),
    'macallan fine oak 10-year scotch':         ('Single Malt Scotch', 'Macallan Fine Oak 10-Year'),
    'compass box asyla scotch':                 ('Blended Scotch', 'Compass Box Asyla'),
    'springbank 10-year scotch':                ('Single Malt Scotch', 'Springbank 10-Year'),
    'famous grouse scotch':                     ('Blended Scotch', 'Famous Grouse'),
    'bowmore 12 year scotch':                   ('Islay Scotch', 'Bowmore 12-Year'),
    'caol ila 12 year islay scotch':            ('Islay Scotch', 'Caol Ila 12-Year'),
    'chivas 12 year scotch':                    ('Blended Scotch', 'Chivas Regal 12-Year'),
    'chivas 12 year scotch':                    ('Blended Scotch', 'Chivas Regal 12-Year'),
    'j b blended scotch whisky':                ('Blended Scotch', 'J&B'),
    'j.b. blended scotch':                      ('Blended Scotch', 'J&B'),
    'yamazaki 12-year whiskey':                 ('Japanese Whisky', 'Yamazaki 12-Year'),
    'yamazakt 12-year whiskey':                 ('Japanese Whisky', 'Yamazaki 12-Year'),
    'hibiki harmony japanese whisky':           ('Japanese Whisky', 'Hibiki Harmony'),
    'toki japanese whisky':                     ('Japanese Whisky', 'Toki'),
    'mustard seed infused kikori whiskey':      ('Mustard Seed-Infused Japanese Whisky', 'Kikori'),
    'pandan infused johnnie walker black label scotch': ('Pandan-Infused Blended Scotch', 'Johnnie Walker Black Label'),

    # ── RYE ───────────────────────────────────────────────────────────────────
    'rittenhouse 100 rye':                      ('Rye Whiskey', 'Rittenhouse Bonded'),
    'rittenhouse bonded rye whiskey':           ('Rye Whiskey', 'Rittenhouse Bonded'),
    'old overholt rye':                         ('Rye Whiskey', 'Old Overholt'),
    'old overholt rye whiskey':                 ('Rye Whiskey', 'Old Overholt'),
    'sazerac 6-year rye':                       ('Rye Whiskey', 'Sazerac 6-Year'),
    "russell's reserve rye":                    ('Rye Whiskey', "Russell's Reserve"),
    "russell's reserve 6 year rye whiskey":     ('Rye Whiskey', "Russell's Reserve 6-Year"),
    'woodford reserve rye whiskey':             ('Rye Whiskey', 'Woodford Reserve'),
    'george dickel rye whiskey':                ('Rye Whiskey', 'George Dickel'),
    'wild turkey 101 rye whiskey':              ('Rye Whiskey', 'Wild Turkey 101'),
    'wild turkey 101 whiskey':                  ('Rye Whiskey', 'Wild Turkey 101'),
    'dried currant-infused wild turkey rye':    ('Dried Currant-Infused Rye Whiskey', 'Wild Turkey'),

    # ── BOURBON ────────────────────────────────────────────────────────────────
    'elijah craig 12-year bourbon':             ('Bourbon', 'Elijah Craig 12-Year'),
    'elijah craig 12 year bourbon':             ('Bourbon', 'Elijah Craig 12-Year'),
    'eagle rare 10-year bourbon':               ('Bourbon', 'Eagle Rare 10-Year'),
    'woodford reserve bourbon':                 ('Bourbon', 'Woodford Reserve'),
    'buffalo trace bourbon':                    ('Bourbon', 'Buffalo Trace'),
    'old grand-dad 114 bourbon':                ('Bourbon', 'Old Grand-Dad 114'),
    'old grand dad 114 bourbon':                ('Bourbon', 'Old Grand-Dad 114'),
    "russell's reserve 10-year bourbon":        ('Bourbon', "Russell's Reserve 10-Year"),
    'jim beam black bourbon':                   ('Bourbon', 'Jim Beam Black'),
    'knob creek single barrel reserve bourbon': ('Bourbon', 'Knob Creek Single Barrel'),
    'old forester 100 bourbon':                 ('Bourbon', 'Old Forester 100'),
    'old forester 86 bourbon':                  ('Bourbon', 'Old Forester 86'),
    'coconut infused michter\'s bourbon':       ('Coconut-Infused Bourbon', "Michter's"),
    'mint infused bourbon':                     ('Mint-Infused Bourbon', ''),
    'pecan-infused buffalo trace bourbon':      ('Pecan-Infused Bourbon', 'Buffalo Trace'),
    'pecan infused buffalo trace bourbon':      ('Pecan-Infused Bourbon', 'Buffalo Trace'),

    # ── IRISH WHISKEY ──────────────────────────────────────────────────────────
    'clontarf 1014 irish whiskey':              ('Irish Whiskey', 'Clontarf 1014'),
    'knappogue castle 12-year irish whiskey':   ('Irish Whiskey', 'Knappogue Castle 12-Year'),
    'redbreast 12-year irish whiskey':          ('Irish Whiskey', 'Redbreast 12-Year'),
    'redbreast 15 year irish whiskey':          ('Irish Whiskey', 'Redbreast 15-Year'),
    'jameson irish whiskey':                    ('Irish Whiskey', 'Jameson'),
    'jameson black barrel irish whiskey':       ('Irish Whiskey', 'Jameson Black Barrel'),
    'connemara irish whiskey':                  ('Irish Whiskey', 'Connemara'),

    # ── AQUAVIT ────────────────────────────────────────────────────────────────
    'krogstad aquavit':                         ('Aquavit', 'Krogstad'),
    'linie aquavit':                            ('Aquavit', 'Linie'),
    'o. p. anderson aquavit':                   ('Aquavit', 'O.P. Anderson'),

    # ── GENEVER / VODKA ────────────────────────────────────────────────────────
    'bols genever':                             ('Genever', 'Bols'),
    'bols barrel-aged genever':                 ('Aged Genever', 'Bols'),
    'old duff single malt genever':             ('Single Malt Genever', 'Old Duff'),
    'absolut elyx vodka':                       ('Vodka', 'Absolut Elyx'),
    'absolut vodka':                            ('Vodka', 'Absolut'),
    'coconut infused absolut elyx':             ('Coconut-Infused Vodka', 'Absolut Elyx'),

    # ── VERMOUTH ──────────────────────────────────────────────────────────────
    'carpano antica formula vermouth':          ('Sweet Vermouth', 'Carpano Antica'),
    'carpano antica formula sweet vermouth':    ('Sweet Vermouth', 'Carpano Antica'),
    'carpano antica sweet vermouth':            ('Sweet Vermouth', 'Carpano Antica'),
    'carpano punt e mes vermouth':              ('Punt e Mes', ''),
    'dolin blanc vermouth':                     ('Blanc Vermouth', 'Dolin'),
    'dolin de chambery blanc vermouth':         ('Blanc Vermouth', 'Dolin'),
    'dolin dry vermouth':                       ('Dry Vermouth', 'Dolin'),
    'dolin de chambery dry vermouth':           ('Dry Vermouth', 'Dolin'),
    'dolin rouge vermouth':                     ('Sweet Vermouth', 'Dolin Rouge'),
    'dolin de chambery rouge vermouth':         ('Sweet Vermouth', 'Dolin Rouge'),
    'martini sweet vermouth':                   ('Sweet Vermouth', 'Martini'),
    'martini rossi riserva speciale ambrato vermouth': ('Blanc Vermouth', 'Martini Riserva Ambrato'),
    'cocchi vermouth di torino':                ('Sweet Vermouth', 'Cocchi di Torino'),
    'noilly prat extra dry vermouth':           ('Dry Vermouth', 'Noilly Prat'),
    'noilly prat original dry vermouth':        ('Dry Vermouth', 'Noilly Prat'),
    'lustau vermut rojo vermouth':              ('Sweet Vermouth', 'Lustau Vermut Rojo'),
    'house sweet vermouth':                     ('Sweet Vermouth', ''),
    'bianco vermouth':                          ('Blanc Vermouth', ''),
    'amontillado sherry':                       ('Amontillado Sherry', ''),  # cap fix

    # ── BITTERS ───────────────────────────────────────────────────────────────
    'bitter truth aromatic bitters':            ('Aromatic Bitters', 'Bitter Truth'),
    'bitter truth celery bitters':              ('Celery Bitters', 'Bitter Truth'),
    "bitter truth jerry thomas' bitters":       ('Aromatic Bitters', 'Bitter Truth Jerry Thomas'),
    'bitter truth chocolate bitters':           ('Chocolate Bitters', 'Bitter Truth'),
    'bitter truth xocolatl mole bitters':       ('Mole Bitters', 'Bitter Truth'),
    'bitter truth grapefruit bitters':          ('Grapefruit Bitters', 'Bitter Truth'),
    'bittermens xocolatl mole bitters':         ('Mole Bitters', 'Bittermens Xocolatl'),
    'bittermens hopped grapefruit bitters':     ('Grapefruit Bitters', 'Bittermens'),
    "bittermens 'elemakule tiki bitters":       ('Tiki Bitters', 'Bittermens Elemakule'),
    'bittermens elemakule tiki bitters':        ('Tiki Bitters', 'Bittermens Elemakule'),
    'fee brothers whiskey barrel-aged bitters': ('Barrel-Aged Bitters', 'Fee Brothers'),
    'fee brothers black walnut bitters':        ('Black Walnut Bitters', 'Fee Brothers'),
    "regans' orange bitters":                   ('Orange Bitters', "Regans'"),
    "scrappy's grapefruit bitters":             ('Grapefruit Bitters', "Scrappy's"),
    'cocktail kingdom wormwood bitters':        ('Wormwood Bitters', 'Cocktail Kingdom'),
    'hella smoked chili bitters':               ('Chili Bitters', 'Hella Smoked'),
    'house orange bitters':                     ('Orange Bitters', ''),
    "house peychaud's bitters":                 ("Peychaud's Bitters", ''),
    'vieux pontarlier absinthe':                ('Absinthe', 'Vieux Pontarlier'),
    'vieux pontarlier absinthe verte':          ('Absinthe', 'Vieux Pontarlier'),
    'pernod absinthe':                          ('Absinthe', 'Pernod'),

    # ── SHERRY ────────────────────────────────────────────────────────────────
    'lustau amontillado sherry':                ('Amontillado Sherry', 'Lustau'),
    'lustau los arcos amontillado sherry':      ('Amontillado Sherry', 'Lustau Los Arcos'),
    'lustau east india solera sherry':          ('Cream Sherry', 'Lustau East India Solera'),
    'lustau east india solera cream sherry':    ('Cream Sherry', 'Lustau East India Solera'),
    'lustau manzanilla sherry':                 ('Manzanilla Sherry', 'Lustau'),
    'lustau jarana fino sherry':                ('Fino Sherry', 'Lustau Jarana'),
    'lustau oloroso sherry':                    ('Oloroso Sherry', 'Lustau'),
    'lustau don nuño oloroso sherry':           ('Oloroso Sherry', 'Lustau Don Nuño'),
    'lustau peninsula palo cortado sherry':     ('Palo Cortado Sherry', 'Lustau Peninsula'),
    'lustau emilín moscatel sherry':            ('Moscatel Sherry', 'Lustau Emilín'),
    'lustau san emilio pedro ximénez sherry':   ('Pedro Ximénez Sherry', 'Lustau'),
    'alvear festival pale cream sherry':        ('Cream Sherry', 'Alvear Festival Pale'),
    'alvear pale cream sherry':                 ('Cream Sherry', 'Alvear Pale'),
    'barbadillo principe amontillado sherry':   ('Amontillado Sherry', 'Barbadillo Príncipe'),
    'la cigarrera manzanilla sherry':           ('Manzanilla Sherry', 'La Cigarrera'),
    'la gitana manzanilla sherry':              ('Manzanilla Sherry', 'La Gitana'),
    'williams & humbert dry sack medium sherry': ('Amontillado Sherry', 'Williams & Humbert Dry Sack'),
    'morenita cream sherry':                    ('Cream Sherry', 'Morenita'),
    'banana oloroso':                           ('Banana-Infused Oloroso Sherry', ''),

    # ── PORT / MARSALA ────────────────────────────────────────────────────────
    'otima 10-year tawny port':                 ('Tawny Port', 'Otima 10-Year'),
    'marco de bartoli marsala superiore 10 year riserva': ('Marsala', 'Marco De Bartoli Superiore 10-Year'),

    # ── LIQUEURS ──────────────────────────────────────────────────────────────
    'marie brizard white creme de cacao':       ('White Crème de Cacao', 'Marie Brizard'),
    'marie brizard creme de cacao white':       ('White Crème de Cacao', 'Marie Brizard'),
    'marie brizard crème de cacao white':       ('White Crème de Cacao', 'Marie Brizard'),
    'marie brizard crème de cacao':             ('Crème de Cacao', 'Marie Brizard'),
    'de kuyper crème de cacao white':           ('White Crème de Cacao', 'De Kuyper'),
    'de kuyper crème de cacao':                 ('Crème de Cacao', 'De Kuyper'),
    'de kuyper crème de menthe':                ('White Crème de Menthe', 'De Kuyper'),
    'lapsang souchong–infused de kuyper crème de cacao': ('Lapsang Souchong-Infused Crème de Cacao', 'De Kuyper'),
    'luxardo maraschino liqueur':               ('Maraschino Liqueur', 'Luxardo'),
    'maraska maraschino liqueur':               ('Maraschino Liqueur', 'Maraska'),
    'massenez creme de peche peach liqueur':    ('Peach Liqueur', 'Massenez'),
    'massenez creme de piche peach liqueur':    ('Peach Liqueur', 'Massenez'),
    'massenez creme de pfiche peach liqueur':   ('Peach Liqueur', 'Massenez'),
    'massenez crème de pêche':                  ('Peach Liqueur', 'Massenez'),
    'massenez creme de mure blackberry liqueur': ('Blackberry Liqueur', 'Massenez'),
    'massenez crème de mûre':                   ('Blackberry Liqueur', 'Massenez'),
    'massenez kirsch vieux cherry brandy':      ('Kirsch', 'Massenez'),
    'massenez kirsch vieux':                    ('Kirsch', 'Massenez'),
    'rothman & winter apricot liqueur':         ('Apricot Liqueur', 'Rothman & Winter'),
    'rothman winter apricot liqueur':           ('Apricot Liqueur', 'Rothman & Winter'),
    'marie brizard apry':                       ('Apricot Liqueur', 'Marie Brizard Apry'),
    'pierre ferrand dry curacao':               ('Dry Curaçao', 'Pierre Ferrand'),
    'pierre ferrand dry curaçao':               ('Dry Curaçao', 'Pierre Ferrand'),
    'pierre ferrand dry curaëao':               ('Dry Curaçao', 'Pierre Ferrand'),
    'kalani ron de coco coconut liqueur':       ('Coconut Liqueur', 'Kalani'),
    'del maguey crema de mezcal':               ('Crema de Mezcal', 'Del Maguey'),
    'del maguey vida mezcal':                   ('Mezcal', 'Del Maguey Vida'),
    'del maguey espadin especial mezcal':       ('Mezcal', 'Del Maguey Espadín'),
    'del maguey san luis del rio mezcal':       ('Mezcal', 'Del Maguey San Luis del Río'),
    'del maguey chichicapa mezcal':             ('Mezcal', 'Del Maguey Chichicapa'),
    'sombra mezcal':                            ('Mezcal', 'Sombra'),
    'amaro nonino quintessentia':               ('Amaro Nonino', ''),
    'luxardo amaro abano':                      ('Amaro Abano', 'Luxardo'),
    'disaronno amaretto':                       ('Amaretto', 'Disaronno'),
    'john d. taylor\'s velvet falernum':        ('Falernum', "John D. Taylor's Velvet"),
    "john d. taylor's velvet falernum":         ('Falernum', "John D. Taylor's Velvet"),
    'hamilton pimento dram':                    ('Allspice Dram', 'Hamilton'),
    'combier triple sec':                       ('Triple Sec', 'Combier'),
    'giffard banana liqueur':                   ('Banana Liqueur', 'Giffard'),
    'st. george spiced pear liqueur':           ('Pear Liqueur', 'St. George Spiced'),
    'dolin génépi':                             ('Génépi', 'Dolin'),
    'dolin genepy':                             ('Génépi', 'Dolin'),
    'alpe genepy':                              ('Génépi', 'Alpe'),
    'chai infused cocchi vermouth di torino':   ('Chai-Infused Sweet Vermouth', 'Cocchi di Torino'),
    'chai-infused cocchi vermouth di torino':   ('Chai-Infused Sweet Vermouth', 'Cocchi di Torino'),

    # ── LIQUEUR cont. ─────────────────────────────────────────────────────────
    'velvet falernum':                          ('Falernum', 'Velvet'),
    'rhum clement creole shrubb':               ('Rhum Agricole Liqueur', 'Rhum Clément Creole Shrubb'),
    'rhum clément créole shrubb':               ('Rhum Agricole Liqueur', 'Rhum Clément Creole Shrubb'),
    'la favorite rhum agricole ambre':          ('Aged Rhum Agricole', 'La Favorite Ambre'),
    "galliano l'autentico":                     ('Galliano', ''),
    "galliano l' autentico":                    ('Galliano', ''),
    'galliano ristretto':                       ('Galliano Ristretto', ''),
    'mathilde poire pear liqueur':              ('Pear Liqueur', 'Mathilde Poire'),
    'rothman & winter creme de violette':       ('Crème de Violette', 'Rothman & Winter'),
    'rothman & winter pear liqueur':            ('Pear Liqueur', 'Rothman & Winter'),
    'rothman & winter cherry liqueur':          ('Cherry Liqueur', 'Rothman & Winter'),
    'marie brizard white creme de menthe':      ('White Crème de Menthe', 'Marie Brizard'),
    'marie brizard white crème de menthe':      ('White Crème de Menthe', 'Marie Brizard'),
    'merlet creme de fraise des bois strawberry liqueur': ('Strawberry Liqueur', 'Merlet'),
    'santa teresa orange liqueur':              ('Orange Liqueur', 'Santa Teresa'),
    'banks 5-island white rum':                 ('Rum', 'Banks 5-Island'),
    'el dorado high-strength 151 rum':          ('Overproof Rum', 'El Dorado 151'),
    'stagg bourbon':                            ('Bourbon', 'Stagg'),

    # ── CAPITALIZATION / NORMALISATION ONLY ──────────────────────────────────
    'angostura bitters':                        ('Angostura Bitters', ''),
    'green chartreuse':                         ('Green Chartreuse', ''),
    'yellow chartreuse':                        ('Yellow Chartreuse', ''),
    'green chartreuse v. e. p.':               ('Green Chartreuse V.E.P.', ''),
    'yellow chartreuse v. e. p.':              ('Yellow Chartreuse V.E.P.', ''),
    'fernet branca':                            ('Fernet-Branca', ''),
    'bénédictine':                              ('Bénédictine', ''),
    'benedictine':                              ('Bénédictine', ''),
    'punt e mes':                               ('Punt e Mes', ''),
    "seagram's club soda":                      ("Seagram's Club Soda", ''),
    'london dry gin':                           ('London Dry Gin', ''),
    'unaged rhum agricole':                     ('Unaged Rhum Agricole', ''),
    # Possessive apostrophe + capital-S OCR artifacts
    "peychaud's bitters":                       ("Peychaud's Bitters", ''),
    "house peychaud's bitters":                 ("Peychaud's Bitters", ''),
    # OCR corruption of brand names
    chr(0x27)+"val pale cream sherry":         ('Cream Sherry', 'Alvear Pale'),
}

# ── Infused base-spirit extraction ────────────────────────────────────────────
# Pattern: "{infusion}-Infused {branded_spirit}"
# We genericise {branded_spirit} but keep {infusion}-Infused prefix.
_INFUSED_PAT = re.compile(
    r'^(.+?)\s*[–-]\s*[Ii]nfused\s+(.+)$'
)
_INFUSED_PAT2 = re.compile(   # "Mint Infused Bourbon" (no hyphen)
    r'^(.+?)\s+[Ii]nfused\s+(.+)$'
)

def _apply_brand_to_base(base: str) -> tuple:
    """Look up brand map for base spirit, return (canonical, brand_note)."""
    key = base.lower().strip()
    if key in BRAND_MAP:
        return BRAND_MAP[key]
    return (None, None)


def normalise_ingredient(name: str, existing_notes: str) -> tuple:
    """
    Given a (possibly brand-specific) ingredient name and existing notes,
    return (new_name, new_notes).
    """
    name = name.strip()

    # --- Instruction suffixes to preserve in notes ---
    SUFFIXES = [
        ' to finish', ' to float', ' as a rinse', ' as rinse', ' for rinsing',
        ' for shaking', ' for garnish', ' for rimming',
        ' for angostura cream garnish',
        ' plus more to top', ' plus more to finish', ' plus as a rinse',
        ' verte',   # not a suffix but keep "absinthe verte" → just Absinthe
    ]
    suffix_note = ''
    name_lower = name.lower()
    for sfx in SUFFIXES:
        if name_lower.endswith(sfx):
            suffix_note = name[len(name) - len(sfx):].strip()
            name = name[:len(name) - len(sfx)].strip()
            break

    # --- Direct brand map lookup ---
    key = name.lower().strip()
    if key in BRAND_MAP:
        canonical, brand_note = BRAND_MAP[key]
        if not canonical:
            canonical = name   # no-op (keep name, just fix cap via map)
        new_notes = _merge_notes(brand_note, suffix_note, existing_notes)
        return canonical, new_notes

    # --- Infused ingredient handling ---
    for pat in (_INFUSED_PAT, _INFUSED_PAT2):
        m = pat.match(name)
        if m:
            infusion, base_spirit = m.group(1).strip(), m.group(2).strip()
            mapped, brand_note = _apply_brand_to_base(base_spirit)
            if mapped:
                new_name = f"{infusion}-Infused {mapped}"
                new_notes = _merge_notes(brand_note, suffix_note, existing_notes)
                return new_name, new_notes
            # No match for base spirit - still normalise hyphen
            new_name = f"{infusion}-Infused {base_spirit}"
            if suffix_note:
                new_notes = _merge_notes('', suffix_note, existing_notes)
                return new_name, new_notes
            return new_name, existing_notes

    # --- No match: restore suffix to existing notes if it was stripped ---
    if suffix_note:
        new_notes = _merge_notes('', suffix_note, existing_notes)
        return name, new_notes

    return name, existing_notes


def _merge_notes(brand: str, suffix: str, existing: str) -> str:
    """Combine brand note, instruction suffix, and any existing notes."""
    parts = []
    if brand:
        parts.append(brand)
    if suffix:
        parts.append(suffix)
    if existing and existing.strip():
        # Don't re-add brand if already present
        ex = existing.strip()
        if ex not in parts:
            parts.append(ex)
    return '; '.join(parts)


# ── Capitalisation helper ──────────────────────────────────────────────────────
# Words that should NOT be title-cased inside a name
_LOWER_WORDS = frozenset({
    'a', 'an', 'the', 'of', 'de', 'du', 'des', 'la', 'le', 'les',
    'and', '&', 'or', 'with', 'in', 'on', 'at', 'by', 'for',
    'to', 'from', 'into',
})

def title_case_ingredient(s: str) -> str:
    """Title-case an ingredient name, keeping standard lower-case connectors."""
    words = s.split()
    result = []
    for i, w in enumerate(words):
        # Always capitalise first word; lower-case connectors elsewhere
        if i == 0 or w.lower() not in _LOWER_WORDS:
            # Don't destroy existing ALL-CAPS abbreviations like 'V.E.P.'
            if w.isupper() and len(w) > 1:
                result.append(w)
            else:
                result.append(w[0].upper() + w[1:] if w else w)
        else:
            result.append(w.lower())
    return ' '.join(result)



# ── Saline auto-injection ──────────────────────────────────────────────────────

# Keys identifying citrus juice ingredients that warrant saline
_CITRUS_JUICE_KEYS = ('lemon juice', 'lime juice', 'grapefruit juice')

_FRAC_VALUES = {
    '½': 0.5,    # ½
    '¼': 0.25,   # ¼
    '¾': 0.75,   # ¾
    '⅓': 1/3,    # ⅓
    '⅔': 2/3,    # ⅔
}


def _parse_oz(amount_str: str, unit_str: str) -> float:
    """Return numeric oz value of an ingredient amount, or 0.0 if not in oz."""
    unit = unit_str.lower().strip()
    if unit not in ('oz', 'ounce', 'ounces', ''):
        return 0.0
    s = amount_str.strip()
    if not s:
        return 0.0
    val = 0.0
    for ch, fv in _FRAC_VALUES.items():
        if ch in s:
            s = s.replace(ch, '').strip()
            val += fv
    if s:
        try:
            val += float(s.split('/')[0]) / float(s.split('/')[1]) if '/' in s else float(s)
        except (ValueError, ZeroDivisionError):
            return 0.0
    return val


def _add_saline_if_needed(cocktail: dict) -> bool:
    """Add 5 drops of Saline Solution if the cocktail has >=0.5 oz citrus juice
    and no saline ingredient is already present.  Returns True if added."""
    ings = cocktail.get('ingredients', [])
    # Already has saline?
    if any('saline' in ing.get('name', '').lower() for ing in ings):
        return False
    # Sum citrus juice
    total_oz = sum(
        _parse_oz(ing.get('amount', ''), ing.get('unit', ''))
        for ing in ings
        if any(k in ing.get('name', '').lower() for k in _CITRUS_JUICE_KEYS)
    )
    if total_oz >= 0.5:
        ings.append({'name': 'Saline Solution', 'amount': '5', 'unit': 'drops', 'notes': ''})
        return True
    return False


# ── Main transformation ────────────────────────────────────────────────────────

def harmonise_ingredient(ing: dict, source: str) -> None:
    """Mutate a single ingredient dict in-place."""
    # Step 1: Fix encoding artifacts
    ing['name'] = fix_encoding(ing.get('name', ''))
    if 'notes' in ing:
        ing['notes'] = fix_encoding(ing.get('notes', ''))

    # Step 2: Parse amount/unit from D&C malformed names
    if source == 'Death & Co.':
        maybe_parse_dc_amount(ing)

    # Step 3: Normalise brand → generic
    old_name   = ing.get('name', '').strip()
    old_notes  = ing.get('notes', '').strip()
    new_name, new_notes = normalise_ingredient(old_name, old_notes)
    ing['name']  = new_name
    ing['notes'] = new_notes

    # Step 4: Consistent capitalisation on the final name.
    # Always apply title-case so "Lime juice" → "Lime Juice" etc.
    # Exception: first lowercase ALL-CAPS purely-alphabetic words so "TWIST" → "Twist"
    # but preserve dot-separated abbreviations like "V.E.P." unchanged.
    current = ing.get('name', '')
    if any(w.isupper() and len(w) > 2 and w.isalpha() for w in current.split()):
        ing['name'] = title_case_ingredient(current.lower())
    else:
        ing['name'] = title_case_ingredient(current)


def harmonise(cocktails: list) -> list:
    total_ings = 0
    changed = 0
    for cocktail in cocktails:
        source = cocktail.get('source', '')
        for ing in cocktail.get('ingredients', []):
            before_name  = ing.get('name', '')
            before_notes = ing.get('notes', '')
            before_amt   = ing.get('amount', '')
            harmonise_ingredient(ing, source)
            if (ing.get('name', '') != before_name
                    or ing.get('notes', '') != before_notes
                    or ing.get('amount', '') != before_amt):
                changed += 1
            total_ings += 1
    print(f'Ingredients changed: {changed} / {total_ings}')

    saline_added = sum(1 for c in cocktails if _add_saline_if_needed(c))
    print(f'Saline added to:    {saline_added} cocktails')
    return cocktails


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print('Reading cocktails.json …')
    with open(COCKTAILS_FILE, encoding='utf-8') as f:
        data = json.load(f)
    cocktails = data.get('cocktails', [])
    print(f'  {len(cocktails)} cocktails loaded.')

    print('Harmonising …')
    cocktails = harmonise(cocktails)

    print('Writing cocktails.json …')
    with open(COCKTAILS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'cocktails': cocktails}, f, indent=2, ensure_ascii=False)

    print('Importing into SQLite DB …')
    stats = _db.import_cocktails(cocktails, overwrite_shared=True)
    print(f"  DB: {stats['added']} added, {stats['updated']} updated, "
          f"{stats['skipped']} skipped (personalised).")

    print('Done.')


if __name__ == '__main__':
    main()

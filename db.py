"""db.py – SQLite persistence layer for Lloid cocktail database.

Key design:
  - cocktails table stores all recipes as JSON blobs with an is_local flag.
  - is_local=0  → from shared catalog (can be updated by sync from cocktails.json)
  - is_local=1  → personal/customised version (protected from sync overwrite)
  - cocktail_history tracks every create/update/delete for version history.
  - On first run the DB is bootstrapped from Data/cocktails.json.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'Data'
DB_PATH  = DATA_DIR / 'lloid.db'
COCKTAILS_JSON = DATA_DIR / 'cocktails.json'

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cocktails (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    data       TEXT NOT NULL,
    is_local   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cocktail_history (
    history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    cocktail_id TEXT NOT NULL,
    name        TEXT NOT NULL,
    data        TEXT NOT NULL,
    action      TEXT NOT NULL,
    saved_at    TEXT NOT NULL,
    note        TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS feedback (
    cocktail_id  TEXT PRIMARY KEY REFERENCES cocktails(id) ON DELETE CASCADE,
    tried        INTEGER NOT NULL DEFAULT 0,
    rating       TEXT,
    favorited    INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recently_viewed (
    cocktail_id TEXT PRIMARY KEY,
    viewed_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bottle_notes (
    bottle_name  TEXT PRIMARY KEY,
    in_stock     INTEGER NOT NULL DEFAULT 1,
    nose         TEXT    NOT NULL DEFAULT '',
    palate       TEXT    NOT NULL DEFAULT '',
    finish       TEXT    NOT NULL DEFAULT '',
    flavor_tags  TEXT    NOT NULL DEFAULT '[]',
    updated_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS lists (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS list_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id     TEXT NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
    cocktail_id TEXT NOT NULL,
    added_at    TEXT NOT NULL,
    UNIQUE(list_id, cocktail_id)
);

CREATE TABLE IF NOT EXISTS leagues (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL COLLATE NOCASE,
    is_default INTEGER NOT NULL DEFAULT 0,
    category   TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS league_members (
    league_id   TEXT NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    bottle_name TEXT NOT NULL,
    elo_score   INTEGER NOT NULL DEFAULT 1400,
    match_count INTEGER NOT NULL DEFAULT 0,
    tier        TEXT,
    PRIMARY KEY (league_id, bottle_name)
);

CREATE TABLE IF NOT EXISTS elo_matches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id  TEXT NOT NULL,
    bottle_a   TEXT NOT NULL,
    bottle_b   TEXT NOT NULL,
    winner     TEXT,
    timestamp  TEXT NOT NULL
);
"""


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _row_to_cocktail(row) -> dict:
    """Convert a DB row into a cocktail dict with all expected fields."""
    c = json.loads(row['data'])
    c['id']         = row['id']
    c['is_local']   = bool(row['is_local'])
    c['created_at'] = row['created_at']
    c['updated_at'] = row['updated_at']
    return c


# ── Schema & bootstrap ────────────────────────────────────────────────────────

def init_db():
    """Create schema and bootstrap from cocktails.json on first run."""
    DATA_DIR.mkdir(exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM cocktails").fetchone()[0]
        if count == 0 and COCKTAILS_JSON.exists():
            _bootstrap(conn)


def _bootstrap(conn):
    """Import all cocktails from cocktails.json as is_local=0 entries."""
    with open(COCKTAILS_JSON, encoding='utf-8') as f:
        raw = json.load(f).get('cocktails', [])
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    for c in raw:
        cid  = c.get('id', '')
        name = c.get('name', '')
        ca   = c.get('created_at', now[:10])
        # Strip meta-fields from the JSON blob; they're stored in columns
        blob = {k: v for k, v in c.items()
                if k not in ('id', 'is_local', 'created_at', 'updated_at')}
        conn.execute(
            "INSERT OR IGNORE INTO cocktails "
            "(id, name, data, is_local, created_at, updated_at) VALUES (?,?,?,0,?,?)",
            (cid, name, json.dumps(blob, ensure_ascii=False), ca, now)
        )
    conn.commit()


# ── Read operations ───────────────────────────────────────────────────────────

def get_cocktails() -> list:
    """Return all cocktails sorted by name."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM cocktails ORDER BY name").fetchall()
    return [_row_to_cocktail(r) for r in rows]


def get_cocktail(cocktail_id: str):
    """Return a single cocktail by ID, or None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM cocktails WHERE id=?", (cocktail_id,)
        ).fetchone()
    return _row_to_cocktail(row) if row else None


def get_history(cocktail_id: str, limit: int = 15) -> list:
    """Return recent history entries for a cocktail, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM cocktail_history WHERE cocktail_id=? "
            "ORDER BY saved_at DESC LIMIT ?",
            (cocktail_id, limit)
        ).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['data'] = json.loads(entry['data'])
        result.append(entry)
    return result


def get_deleted_cocktails() -> list:
    """Return cocktails that were deleted (in history but not in main table)."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT h.history_id, h.cocktail_id, h.name, h.data, h.saved_at
            FROM cocktail_history h
            WHERE h.action = 'delete'
              AND h.cocktail_id NOT IN (SELECT id FROM cocktails)
              AND h.saved_at = (
                  SELECT MAX(h2.saved_at)
                  FROM cocktail_history h2
                  WHERE h2.cocktail_id = h.cocktail_id
              )
            ORDER BY h.saved_at DESC
        """).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['data'] = json.loads(entry['data'])
        result.append(entry)
    return result


# ── Write operations ──────────────────────────────────────────────────────────

def save_cocktail(cocktail: dict, is_local: bool = True, note=None) -> dict:
    """Insert or update a cocktail; always writes a history entry.

    is_local is sticky: once a recipe is marked personal (1), it stays that way
    even if save_cocktail is later called with is_local=False.
    """
    now  = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    cid  = cocktail['id']
    name = cocktail.get('name', '')
    blob = {k: v for k, v in cocktail.items()
            if k not in ('id', 'is_local', 'created_at', 'updated_at')}

    with _connect() as conn:
        existing = conn.execute(
            "SELECT is_local, created_at FROM cocktails WHERE id=?", (cid,)
        ).fetchone()

        if existing:
            # Never downgrade: once personal, always personal
            new_local = 1 if (existing['is_local'] or is_local) else 0
            action    = 'update'
            conn.execute(
                "UPDATE cocktails SET name=?, data=?, is_local=?, updated_at=? WHERE id=?",
                (name, json.dumps(blob, ensure_ascii=False), new_local, now, cid)
            )
        else:
            new_local = 1 if is_local else 0
            action    = 'create'
            ca        = cocktail.get('created_at', now[:10])
            conn.execute(
                "INSERT INTO cocktails (id, name, data, is_local, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (cid, name, json.dumps(blob, ensure_ascii=False), new_local, ca, now)
            )

        conn.execute(
            "INSERT INTO cocktail_history "
            "(cocktail_id, name, data, action, saved_at, note) VALUES (?,?,?,?,?,?)",
            (cid, name, json.dumps(blob, ensure_ascii=False), action, now, note)
        )
        conn.commit()

    return get_cocktail(cid)


def delete_cocktail(cocktail_id: str, note=None):
    """Hard-delete from main table; preserve a history record."""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM cocktails WHERE id=?", (cocktail_id,)
        ).fetchone()
        if row:
            conn.execute(
                "INSERT INTO cocktail_history "
                "(cocktail_id, name, data, action, saved_at, note) VALUES (?,?,?,'delete',?,?)",
                (cocktail_id, row['name'], row['data'], now, note)
            )
            conn.execute("DELETE FROM cocktails WHERE id=?", (cocktail_id,))
            conn.commit()


def restore_version(history_id: int):
    """Restore a cocktail to a prior version; marks it is_local=1."""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM cocktail_history WHERE history_id=?", (history_id,)
        ).fetchone()
        if not row:
            return None

        cid  = row['cocktail_id']
        name = row['name']
        data = row['data']   # raw JSON string — keep as-is to preserve exact state

        existing = conn.execute(
            "SELECT created_at FROM cocktails WHERE id=?", (cid,)
        ).fetchone()
        ca = existing['created_at'] if existing else now[:10]

        if existing:
            conn.execute(
                "UPDATE cocktails SET name=?, data=?, is_local=1, updated_at=? WHERE id=?",
                (name, data, now, cid)
            )
        else:
            # Recipe was deleted; bring it back
            conn.execute(
                "INSERT INTO cocktails (id, name, data, is_local, created_at, updated_at) "
                "VALUES (?,?,?,1,?,?)",
                (cid, name, data, ca, now)
            )

        conn.execute(
            "INSERT INTO cocktail_history "
            "(cocktail_id, name, data, action, saved_at, note) VALUES (?,?,?,'update',?,'restored from history')",
            (cid, name, data, now)
        )
        conn.commit()

    return get_cocktail(cid)


# ── Feedback ──────────────────────────────────────────────────────────────────

_BLANK_FEEDBACK = {'tried': False, 'rating': None, 'favorited': False}


def get_feedback(cocktail_id: str) -> dict:
    """Return feedback dict for a cocktail, or a blank default if none exists."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT tried, rating, favorited FROM feedback WHERE cocktail_id=?",
            (cocktail_id,)
        ).fetchone()
    if row:
        return {'tried': bool(row['tried']), 'rating': row['rating'], 'favorited': bool(row['favorited'])}
    return dict(_BLANK_FEEDBACK)


def set_feedback(cocktail_id: str,
                 tried: bool = None,
                 rating: str = None,
                 favorited: bool = None) -> dict:
    """Upsert feedback for a cocktail.  Only supplied (non-None) fields are changed.
    Pass rating='' to explicitly clear the rating."""
    now  = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    current = get_feedback(cocktail_id)

    new_tried    = tried    if tried    is not None else current['tried']
    new_favorited = favorited if favorited is not None else current['favorited']
    # rating=None means "don't change", rating='' or rating=False means "clear it"
    if rating is None:
        new_rating = current['rating']
    elif rating in ('', False):
        new_rating = None
    else:
        new_rating = rating

    # If untrying, also clear the rating
    if not new_tried:
        new_rating = None

    with _connect() as conn:
        conn.execute("""
            INSERT INTO feedback (cocktail_id, tried, rating, favorited, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(cocktail_id) DO UPDATE SET
                tried=excluded.tried,
                rating=excluded.rating,
                favorited=excluded.favorited,
                updated_at=excluded.updated_at
        """, (cocktail_id, int(new_tried), new_rating, int(new_favorited), now))
        conn.commit()

    return {'tried': new_tried, 'rating': new_rating, 'favorited': new_favorited}


def get_all_feedback() -> dict:
    """Return {cocktail_id: feedback_dict} for every cocktail that has a row."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT cocktail_id, tried, rating, favorited FROM feedback"
        ).fetchall()
    return {
        r['cocktail_id']: {
            'tried':     bool(r['tried']),
            'rating':    r['rating'],
            'favorited': bool(r['favorited']),
        }
        for r in rows
    }


# ── Sync ──────────────────────────────────────────────────────────────────────

def import_cocktails(cocktails: list, overwrite_shared: bool = True) -> dict:
    """Bulk-import from an external list (e.g., cocktails.json).

    - Skips any cocktail with is_local=1 (protected personal version).
    - If overwrite_shared=True (default), updates existing is_local=0 cocktails.
    - Returns stats dict: {added, updated, skipped}.
    """
    now     = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    added   = 0
    updated = 0
    skipped = 0

    with _connect() as conn:
        for c in cocktails:
            cid  = c.get('id', '')
            name = c.get('name', '')
            ca   = c.get('created_at', now[:10])
            blob = {k: v for k, v in c.items()
                    if k not in ('id', 'is_local', 'created_at', 'updated_at')}
            data = json.dumps(blob, ensure_ascii=False)

            existing = conn.execute(
                "SELECT is_local FROM cocktails WHERE id=?", (cid,)
            ).fetchone()

            if existing:
                if existing['is_local']:
                    skipped += 1
                    continue
                if overwrite_shared:
                    conn.execute(
                        "UPDATE cocktails SET name=?, data=?, updated_at=? WHERE id=?",
                        (name, data, now, cid)
                    )
                    conn.execute(
                        "INSERT INTO cocktail_history "
                        "(cocktail_id, name, data, action, saved_at, note) "
                        "VALUES (?,?,?,'update',?,'sync')",
                        (cid, name, data, now)
                    )
                    updated += 1
            else:
                conn.execute(
                    "INSERT INTO cocktails "
                    "(id, name, data, is_local, created_at, updated_at) VALUES (?,?,?,0,?,?)",
                    (cid, name, data, ca, now)
                )
                conn.execute(
                    "INSERT INTO cocktail_history "
                    "(cocktail_id, name, data, action, saved_at, note) "
                    "VALUES (?,?,?,'create',?,'sync')",
                    (cid, name, data, now)
                )
                added += 1

        conn.commit()

    return {'added': added, 'updated': updated, 'skipped': skipped}


# ── Bottle notes ──────────────────────────────────────────────────────────────

_BLANK_BOTTLE_NOTE = {'in_stock': True, 'nose': '', 'palate': '', 'finish': '', 'flavor_tags': []}


def get_bottle_note(bottle_name: str) -> dict:
    """Return tasting notes + stock state for a bottle, or blank defaults."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM bottle_notes WHERE bottle_name=?", (bottle_name,)
        ).fetchone()
    if row:
        return {
            'in_stock':    bool(row['in_stock']),
            'nose':        row['nose']   or '',
            'palate':      row['palate'] or '',
            'finish':      row['finish'] or '',
            'flavor_tags': json.loads(row['flavor_tags'] or '[]'),
        }
    return dict(_BLANK_BOTTLE_NOTE)


def set_bottle_note(bottle_name: str, **kwargs) -> dict:
    """Upsert tasting notes / availability for a bottle."""
    now     = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    current = get_bottle_note(bottle_name)
    in_stock    = kwargs.get('in_stock',    current['in_stock'])
    nose        = kwargs.get('nose',        current['nose'])
    palate      = kwargs.get('palate',      current['palate'])
    finish      = kwargs.get('finish',      current['finish'])
    flavor_tags = kwargs.get('flavor_tags', current['flavor_tags'])
    if isinstance(flavor_tags, list):
        flavor_tags = json.dumps(flavor_tags)
    with _connect() as conn:
        conn.execute("""
            INSERT INTO bottle_notes (bottle_name, in_stock, nose, palate, finish, flavor_tags, updated_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(bottle_name) DO UPDATE SET
                in_stock=excluded.in_stock,
                nose=excluded.nose,
                palate=excluded.palate,
                finish=excluded.finish,
                flavor_tags=excluded.flavor_tags,
                updated_at=excluded.updated_at
        """, (bottle_name, int(in_stock), nose, palate, finish, flavor_tags, now))
        conn.commit()
    return get_bottle_note(bottle_name)


def toggle_bottle_stock(bottle_name: str) -> dict:
    """Flip in_stock for a bottle; return new note."""
    note = get_bottle_note(bottle_name)
    return set_bottle_note(bottle_name, in_stock=not note['in_stock'])


def rename_bottle_note(old_name: str, new_name: str):
    """Move a bottle note to a new name (called on bottle rename)."""
    with _connect() as conn:
        conn.execute(
            "UPDATE bottle_notes SET bottle_name=? WHERE bottle_name=?",
            (new_name, old_name)
        )
        conn.commit()


def delete_bottle_note(bottle_name: str):
    """Remove note row for a deleted bottle."""
    with _connect() as conn:
        conn.execute("DELETE FROM bottle_notes WHERE bottle_name=?", (bottle_name,))
        conn.commit()


def get_all_bottle_notes() -> dict:
    """Return {bottle_name: note_dict} for every row in bottle_notes."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM bottle_notes").fetchall()
    return {
        r['bottle_name']: {
            'in_stock':    bool(r['in_stock']),
            'nose':        r['nose']   or '',
            'palate':      r['palate'] or '',
            'finish':      r['finish'] or '',
            'flavor_tags': json.loads(r['flavor_tags'] or '[]'),
        }
        for r in rows
    }


# ── Settings ─────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = '') -> str:
    """Return a settings value by key, or default if not set."""
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row['value'] if row else default


def set_setting(key: str, value: str):
    """Upsert a key/value pair in the settings table."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        conn.commit()


# ── Recently viewed ───────────────────────────────────────────────────────────

def record_view(cocktail_id: str):
    """Upsert a recently-viewed record (one row per cocktail, updated on each visit)."""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    with _connect() as conn:
        conn.execute("""
            INSERT INTO recently_viewed (cocktail_id, viewed_at) VALUES (?, ?)
            ON CONFLICT(cocktail_id) DO UPDATE SET viewed_at=excluded.viewed_at
        """, (cocktail_id, now))
        conn.commit()


def get_recently_viewed(limit: int = 8) -> list:
    """Return up to `limit` cocktail IDs sorted most-recently-viewed first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT cocktail_id, viewed_at FROM recently_viewed "
            "ORDER BY viewed_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{'cocktail_id': r['cocktail_id'], 'viewed_at': r['viewed_at']} for r in rows]


# ── Lists ─────────────────────────────────────────────────────────────────────

def get_lists() -> list:
    """Return all lists with item counts, newest first."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT l.id, l.name, l.created_at,
                   COUNT(li.id) AS count
            FROM lists l
            LEFT JOIN list_items li ON li.list_id = l.id
            GROUP BY l.id
            ORDER BY l.created_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_list(list_id: str):
    """Return a list with its cocktail IDs and timestamps, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, created_at FROM lists WHERE id=?", (list_id,)
        ).fetchone()
        if not row:
            return None
        items = conn.execute(
            "SELECT cocktail_id, added_at FROM list_items "
            "WHERE list_id=? ORDER BY added_at",
            (list_id,)
        ).fetchall()
    return {
        'id':         row['id'],
        'name':       row['name'],
        'created_at': row['created_at'],
        'items':      [{'cocktail_id': r['cocktail_id'], 'added_at': r['added_at']}
                       for r in items],
    }


def create_list(name: str, list_id: str) -> dict:
    """Insert a new list. Caller must supply a unique list_id slug."""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    with _connect() as conn:
        conn.execute(
            "INSERT INTO lists (id, name, created_at) VALUES (?,?,?)",
            (list_id, name, now[:10])
        )
        conn.commit()
    return {'id': list_id, 'name': name, 'created_at': now[:10], 'count': 0}


def rename_list(list_id: str, name: str) -> bool:
    """Rename a list. Returns True if the list was found and updated."""
    with _connect() as conn:
        cur = conn.execute("UPDATE lists SET name=? WHERE id=?", (name, list_id))
        conn.commit()
    return cur.rowcount > 0


def delete_list(list_id: str):
    """Delete a list and all its items (CASCADE)."""
    with _connect() as conn:
        conn.execute("DELETE FROM lists WHERE id=?", (list_id,))
        conn.commit()


def add_to_list(list_id: str, cocktail_id: str) -> bool:
    """Add a cocktail to a list. Returns True if newly added, False if already present."""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO list_items (list_id, cocktail_id, added_at) VALUES (?,?,?)",
                (list_id, cocktail_id, now)
            )
            conn.commit()
            return True
        except Exception:
            return False


def remove_from_list(list_id: str, cocktail_id: str) -> bool:
    """Remove a cocktail from a list. Returns True if it was found and deleted."""
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM list_items WHERE list_id=? AND cocktail_id=?",
            (list_id, cocktail_id)
        )
        conn.commit()
    return cur.rowcount > 0


def get_cocktail_lists(cocktail_id: str) -> set:
    """Return the set of list_ids that contain this cocktail."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT list_id FROM list_items WHERE cocktail_id=?", (cocktail_id,)
        ).fetchall()
    return {r['list_id'] for r in rows}


# ── Leagues & ELO ─────────────────────────────────────────────────────────────

import re as _re
import random as _random


def _league_slug(name: str) -> str:
    return _re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _elo_k(match_count: int) -> int:
    if match_count < 5:  return 64
    if match_count < 15: return 32
    return 16


def _elo_expected(a: int, b: int) -> float:
    return 1.0 / (1.0 + 10 ** ((b - a) / 400.0))


def _apply_elo(score_a: int, score_b: int, winner,
               name_a: str, name_b: str,
               count_a: int, count_b: int):
    """Return (new_a, new_b). winner=None means draw/skip."""
    k_a = _elo_k(count_a)
    k_b = _elo_k(count_b)
    e_a = _elo_expected(score_a, score_b)
    e_b = _elo_expected(score_b, score_a)
    if winner is None:
        r_a, r_b = 0.5, 0.5
    elif winner == name_a:
        r_a, r_b = 1.0, 0.0
    else:
        r_a, r_b = 0.0, 1.0
    new_a = max(100, round(score_a + k_a * (r_a - e_a)))
    new_b = max(100, round(score_b + k_b * (r_b - e_b)))
    return new_a, new_b


def _elo_tier(score: int) -> str:
    if score >= 1600: return 'elite'
    if score >= 1450: return 'great'
    if score >= 1300: return 'good'
    if score >= 1150: return 'fair'
    return 'pass'


_TIER_SEED = {'love': 1600, 'like': 1500, 'okay': 1300, 'dislike': 1100}


def ensure_default_leagues(categories: list) -> None:
    """Create a default league for each inventory category that doesn't exist yet."""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    with _connect() as conn:
        for cat in categories:
            if not cat:
                continue
            lid = 'cat-' + _league_slug(cat)
            conn.execute("""
                INSERT OR IGNORE INTO leagues (id, name, is_default, category, created_at)
                VALUES (?, ?, 1, ?, ?)
            """, (lid, cat, cat, now[:10]))
        conn.commit()


def get_leagues() -> list:
    """Return all leagues with member counts; defaults first, then alphabetical."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT l.id, l.name, l.is_default, l.category, l.created_at,
                   COUNT(lm.bottle_name) AS member_count
            FROM leagues l
            LEFT JOIN league_members lm ON lm.league_id = l.id
            GROUP BY l.id
            ORDER BY l.is_default DESC, l.name
        """).fetchall()
    return [dict(r) for r in rows]


def get_league(league_id: str):
    """Return league info with ranked member list, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM leagues WHERE id=?", (league_id,)
        ).fetchone()
        if not row:
            return None
        members = conn.execute("""
            SELECT bottle_name, elo_score, match_count, tier
            FROM league_members WHERE league_id=?
            ORDER BY elo_score DESC
        """, (league_id,)).fetchall()
    lg = dict(row)
    lg['members'] = [dict(m) for m in members]
    for i, m in enumerate(lg['members']):
        m['rank'] = i + 1
        m['tier_class'] = _elo_tier(m['elo_score'])
    return lg


def create_league(name: str) -> dict:
    """Create a new custom league and return it."""
    now  = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    base = _league_slug(name)
    lid  = base
    with _connect() as conn:
        suffix = 0
        while conn.execute("SELECT 1 FROM leagues WHERE id=?", (lid,)).fetchone():
            suffix += 1
            lid = f"{base}-{suffix}"
        conn.execute(
            "INSERT INTO leagues (id, name, is_default, category, created_at) "
            "VALUES (?,?,0,NULL,?)",
            (lid, name, now[:10])
        )
        conn.commit()
    return {'id': lid, 'name': name, 'is_default': False,
            'category': None, 'created_at': now[:10], 'member_count': 0}


def delete_league(league_id: str) -> bool:
    """Delete a custom (non-default) league. Returns True if deleted."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT is_default FROM leagues WHERE id=?", (league_id,)
        ).fetchone()
        if not row or row['is_default']:
            return False
        conn.execute("DELETE FROM leagues WHERE id=?", (league_id,))
        conn.commit()
    return True


def rename_league(league_id: str, name: str) -> bool:
    """Rename a custom league. Returns True if renamed."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT is_default FROM leagues WHERE id=?", (league_id,)
        ).fetchone()
        if not row or row['is_default']:
            return False
        conn.execute("UPDATE leagues SET name=? WHERE id=?", (name, league_id))
        conn.commit()
    return True


def get_bottle_leagues(bottle_name: str) -> list:
    """Return [{league_id, league_name, is_default, elo_score, match_count, tier}]."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT l.id AS league_id, l.name AS league_name, l.is_default,
                   lm.elo_score, lm.match_count, lm.tier
            FROM league_members lm
            JOIN leagues l ON l.id = lm.league_id
            WHERE lm.bottle_name=?
            ORDER BY l.is_default ASC, lm.elo_score DESC
        """, (bottle_name,)).fetchall()
    result = [dict(r) for r in rows]
    for r in result:
        r['tier_class'] = _elo_tier(r['elo_score'])
    return result


def add_to_league(league_id: str, bottle_name: str,
                  tier: str = None, elo: int = None) -> dict:
    """Add/update a bottle in a league. Seeds ELO from tier if not provided."""
    if elo is None:
        elo = _TIER_SEED.get(tier, 1400)
    with _connect() as conn:
        existing = conn.execute(
            "SELECT elo_score, match_count FROM league_members "
            "WHERE league_id=? AND bottle_name=?",
            (league_id, bottle_name)
        ).fetchone()
        if existing:
            # Re-rating: keep match_count, update tier + elo only if tier given
            if tier:
                conn.execute("""
                    UPDATE league_members SET tier=?, elo_score=?
                    WHERE league_id=? AND bottle_name=?
                """, (tier, elo, league_id, bottle_name))
        else:
            conn.execute("""
                INSERT INTO league_members
                    (league_id, bottle_name, elo_score, match_count, tier)
                VALUES (?,?,?,0,?)
            """, (league_id, bottle_name, elo, tier))
        conn.commit()
    row = conn.execute(
        "SELECT elo_score, match_count, tier FROM league_members "
        "WHERE league_id=? AND bottle_name=?",
        (league_id, bottle_name)
    ).fetchone() if False else None
    return {'league_id': league_id, 'bottle_name': bottle_name,
            'elo_score': elo, 'tier': tier}


def remove_from_league(league_id: str, bottle_name: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM league_members WHERE league_id=? AND bottle_name=?",
            (league_id, bottle_name)
        )
        conn.commit()
    return cur.rowcount > 0


def remove_bottle_from_all_leagues(bottle_name: str):
    """Remove a bottle from every league (called on bottle deletion)."""
    with _connect() as conn:
        conn.execute(
            "DELETE FROM league_members WHERE bottle_name=?", (bottle_name,)
        )
        conn.commit()


def rename_bottle_in_leagues(old_name: str, new_name: str):
    """Update league_members when a bottle is renamed."""
    with _connect() as conn:
        conn.execute(
            "UPDATE league_members SET bottle_name=? WHERE bottle_name=?",
            (new_name, old_name)
        )
        conn.execute(
            "UPDATE elo_matches SET bottle_a=? WHERE bottle_a=?", (new_name, old_name)
        )
        conn.execute(
            "UPDATE elo_matches SET bottle_b=? WHERE bottle_b=?", (new_name, old_name)
        )
        conn.execute(
            "UPDATE elo_matches SET winner=? WHERE winner=?", (new_name, old_name)
        )
        conn.commit()


def get_matchup_candidates(league_id: str, bottle_name: str, n: int = 5) -> list:
    """Return up to n matchup opponents sorted by ELO proximity, with randomisation."""
    with _connect() as conn:
        target = conn.execute(
            "SELECT elo_score FROM league_members WHERE league_id=? AND bottle_name=?",
            (league_id, bottle_name)
        ).fetchone()
        if not target:
            return []
        target_elo = target['elo_score']
        others = conn.execute("""
            SELECT bottle_name, elo_score, match_count, tier
            FROM league_members
            WHERE league_id=? AND bottle_name != ?
            ORDER BY ABS(elo_score - ?) ASC
            LIMIT ?
        """, (league_id, bottle_name, target_elo, n + 4)).fetchall()
    candidates = [dict(r) for r in others]
    for c in candidates:
        c['tier_class'] = _elo_tier(c['elo_score'])
    # Shuffle the tail slightly for variety
    if len(candidates) > n:
        head = candidates[:max(n - 2, 1)]
        tail = candidates[max(n - 2, 1):]
        _random.shuffle(tail)
        candidates = head + tail
    return candidates[:n]


def record_elo_results(league_id: str, results: list) -> dict:
    """
    Process a batch of matchup results.
    results = [{'bottle_a': str, 'bottle_b': str, 'winner': str|None}]
    winner=None means draw/skip.
    Returns {bottle_name: new_elo_score} for every bottle touched.
    """
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    with _connect() as conn:
        involved = set()
        for r in results:
            involved.add(r['bottle_a'])
            involved.add(r['bottle_b'])

        scores = {}
        counts = {}
        for name in involved:
            row = conn.execute(
                "SELECT elo_score, match_count FROM league_members "
                "WHERE league_id=? AND bottle_name=?",
                (league_id, name)
            ).fetchone()
            if row:
                scores[name] = row['elo_score']
                counts[name] = row['match_count']

        for r in results:
            a, b, winner = r['bottle_a'], r['bottle_b'], r.get('winner')
            if a not in scores or b not in scores:
                continue
            new_a, new_b = _apply_elo(
                scores[a], scores[b], winner, a, b, counts[a], counts[b]
            )
            scores[a] = new_a
            scores[b] = new_b
            counts[a] = counts.get(a, 0) + 1
            counts[b] = counts.get(b, 0) + 1
            conn.execute(
                "INSERT INTO elo_matches "
                "(league_id, bottle_a, bottle_b, winner, timestamp) VALUES (?,?,?,?,?)",
                (league_id, a, b, winner, now)
            )

        for name in involved:
            if name in scores:
                conn.execute(
                    "UPDATE league_members SET elo_score=?, match_count=? "
                    "WHERE league_id=? AND bottle_name=?",
                    (scores[name], counts[name], league_id, name)
                )
        conn.commit()

    return {name: scores[name] for name in involved if name in scores}


def get_all_bottle_elo(bottle_names: list) -> dict:
    """
    Return {bottle_name: [league_entry, ...]} for all given bottle names.
    Custom (non-default) leagues are listed first, then defaults.
    """
    if not bottle_names:
        return {}
    with _connect() as conn:
        placeholders = ','.join('?' * len(bottle_names))
        rows = conn.execute(f"""
            SELECT lm.bottle_name, l.id AS league_id, l.name AS league_name,
                   l.is_default, lm.elo_score, lm.tier, lm.match_count
            FROM league_members lm
            JOIN leagues l ON l.id = lm.league_id
            WHERE lm.bottle_name IN ({placeholders})
            ORDER BY lm.bottle_name, l.is_default ASC, lm.elo_score DESC
        """, bottle_names).fetchall()
    result = {}
    for r in rows:
        name = r['bottle_name']
        if name not in result:
            result[name] = []
        entry = dict(r)
        entry['tier_class'] = _elo_tier(entry['elo_score'])
        result[name].append(entry)
    return result

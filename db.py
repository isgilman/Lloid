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

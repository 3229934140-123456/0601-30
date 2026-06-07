import os
import sqlite3
from pathlib import Path

DB_PATH = os.path.expanduser("~/.film_tracker/film_tracker.db")
SCHEMA_VERSION = 2


def get_db_path():
    return Path(DB_PATH)


def init_db():
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    _create_tables(c)
    _create_indexes(c)

    c.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    conn.commit()
    return conn


def _create_tables(c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            original_title TEXT,
            type TEXT NOT NULL CHECK(type IN ('movie', 'tv')),
            year INTEGER,
            director TEXT,
            cast TEXT,
            genre TEXT,
            total_seasons INTEGER DEFAULT 1,
            total_episodes INTEGER,
            runtime INTEGER,
            summary TEXT,
            status TEXT DEFAULT 'watchlist' CHECK(status IN ('watchlist', 'watching', 'finished', 'dropped')),
            rating REAL,
            review TEXT,
            rewatch_count INTEGER DEFAULT 0,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_watched_at TIMESTAMP,
            next_episode_date DATE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL,
            season_number INTEGER NOT NULL,
            total_episodes INTEGER,
            watched_episodes INTEGER DEFAULT 0,
            FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS watch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL,
            season INTEGER,
            episode INTEGER,
            watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS media_tags (
            media_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (media_id, tag_id),
            FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    """)


def _create_indexes(c):
    c.execute("CREATE INDEX IF NOT EXISTS idx_media_title ON media(title)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_media_status ON media(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_media_type ON media(type)")


def _column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


MEDIA_COLUMNS = [
    ("original_title", "TEXT"),
    ("genre", "TEXT"),
    ("total_seasons", "INTEGER DEFAULT 1"),
    ("total_episodes", "INTEGER"),
    ("runtime", "INTEGER"),
    ("summary", "TEXT"),
    ("rating", "REAL"),
    ("review", "TEXT"),
    ("rewatch_count", "INTEGER DEFAULT 0"),
    ("tags", "TEXT"),
    ("last_watched_at", "TIMESTAMP"),
    ("next_episode_date", "DATE"),
]


def migrate_db():
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("PRAGMA user_version")
    current_version = c.fetchone()[0]

    if current_version >= SCHEMA_VERSION:
        conn.close()
        return

    if current_version < 1:
        _create_tables(c)
        _create_indexes(c)
        current_version = 1

    for col_name, col_def in MEDIA_COLUMNS:
        if not _column_exists(c, "media", col_name):
            c.execute(f"ALTER TABLE media ADD COLUMN {col_name} {col_def}")

    if not _table_exists(c, "seasons"):
        c.execute("""
            CREATE TABLE seasons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id INTEGER NOT NULL,
                season_number INTEGER NOT NULL,
                total_episodes INTEGER,
                watched_episodes INTEGER DEFAULT 0,
                FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE
            )
        """)

    if not _table_exists(c, "watch_history"):
        c.execute("""
            CREATE TABLE watch_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id INTEGER NOT NULL,
                season INTEGER,
                episode INTEGER,
                watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE
            )
        """)

    if not _table_exists(c, "tags"):
        c.execute("""
            CREATE TABLE tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

    if not _table_exists(c, "media_tags"):
        c.execute("""
            CREATE TABLE media_tags (
                media_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (media_id, tag_id),
                FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        """)

    _create_indexes(c)

    c.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    conn.close()


def _table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_db():
    path = get_db_path()
    if not path.exists():
        init_db()
    else:
        migrate_db()

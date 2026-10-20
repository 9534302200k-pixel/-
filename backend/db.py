import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import settings


def now():
    return datetime.now(timezone.utc).isoformat()


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False)


@contextmanager
def db():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.data_dir / "alfa.db", timeout=30)
    con.row_factory = sqlite3.Row
    con.create_function(
        "casefold", 1, lambda s: (s or "").casefold(), deterministic=True
    )
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS companies(id TEXT PRIMARY KEY, name TEXT NOT NULL, sector TEXT, region TEXT,
          revenue REAL, credit INTEGER, fts TEXT, group_id TEXT, raw TEXT, conflicts TEXT DEFAULT '[]', synthetic INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS company_records(id INTEGER PRIMARY KEY, company_id TEXT, raw TEXT, fingerprint TEXT UNIQUE);
        CREATE INDEX IF NOT EXISTS company_record_id ON company_records(company_id);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, payer TEXT, beneficiary TEXT, amount REAL, count INTEGER,
          fingerprint TEXT UNIQUE, raw TEXT);
        CREATE INDEX IF NOT EXISTS pay_payer ON payments(payer);
        CREATE INDEX IF NOT EXISTS pay_beneficiary ON payments(beneficiary);
        CREATE TABLE IF NOT EXISTS person_links(id INTEGER PRIMARY KEY, person_id TEXT, company_id TEXT, fingerprint TEXT UNIQUE, raw TEXT);
        CREATE INDEX IF NOT EXISTS person_company ON person_links(company_id);
        CREATE INDEX IF NOT EXISTS person_person ON person_links(person_id);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, title TEXT, body TEXT, url TEXT, source TEXT,
          published TEXT, fetched TEXT, topics TEXT, synthetic INTEGER DEFAULT 0, duplicate_count INTEGER DEFAULT 0, aliases TEXT DEFAULT '[]');
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, title TEXT, published TEXT, url TEXT, filename TEXT,
          synthetic INTEGER DEFAULT 0, sha256 TEXT);
        CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, document_id TEXT REFERENCES documents(id), page INTEGER, text TEXT, ocr INTEGER DEFAULT 0);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED, text, tokenize='unicode61');
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, company_id TEXT, event_id TEXT, role TEXT, question TEXT,
          created TEXT, cache_key TEXT, result TEXT, trace TEXT, elapsed_ms INTEGER, mode TEXT);
        CREATE INDEX IF NOT EXISTS run_cache ON runs(cache_key);
        CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, run_id TEXT REFERENCES runs(id), rating INTEGER, reason TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS usage(id TEXT PRIMARY KEY, day TEXT, status TEXT, reserved REAL, actual REAL DEFAULT 0,
          input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0, created TEXT);
        CREATE TABLE IF NOT EXISTS source_status(id TEXT PRIMARY KEY, checked TEXT, status TEXT, detail TEXT);
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS bookmarks(company_id TEXT, event_id TEXT, PRIMARY KEY(company_id,event_id));
        CREATE TABLE IF NOT EXISTS failures(id INTEGER PRIMARY KEY,company_id TEXT,event_id TEXT,role TEXT,created TEXT,message TEXT);
        """)


def rows(sql, params=()):
    with db() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def company(company_id):
    r = rows("SELECT * FROM companies WHERE id=?", (company_id,))
    if not r:
        raise KeyError("Компания не найдена")
    r = r[0]
    for k in ["raw", "conflicts"]:
        r[k] = json.loads(r[k])
    return r

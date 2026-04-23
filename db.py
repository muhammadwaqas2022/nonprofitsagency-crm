"""SQLite persistence layer for the Credit Repair Cloud MVP."""

import re
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "credit_repair.db"
UPLOADS_DIR = Path(__file__).parent / "uploads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    client_type            TEXT    NOT NULL CHECK(client_type IN ('Personal', 'Business')),
    name                   TEXT    NOT NULL,
    email                  TEXT,
    phone                  TEXT,
    identifier             TEXT,   -- SSN last-4 (personal) or EIN (business)
    dob_or_founded         TEXT,
    address                TEXT,
    city                   TEXT,
    state                  TEXT,
    zip                    TEXT,
    -- Personal bureaus
    initial_equifax        INTEGER,
    initial_experian       INTEGER,
    initial_transunion     INTEGER,
    current_equifax        INTEGER,
    current_experian       INTEGER,
    current_transunion     INTEGER,
    -- Business bureaus
    initial_dnb            INTEGER,
    initial_experian_biz   INTEGER,
    initial_equifax_biz    INTEGER,
    current_dnb            INTEGER,
    current_experian_biz   INTEGER,
    current_equifax_biz    INTEGER,
    status                 TEXT    DEFAULT 'Active',
    notes                  TEXT,
    created_at             TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS credit_items (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id          INTEGER NOT NULL,
    bureau             TEXT    NOT NULL,
    creditor           TEXT,
    account_number     TEXT,
    item_type          TEXT,  -- Collection, Charge-off, Late Payment, Inquiry, Public Record, Other
    balance            REAL,
    date_opened        TEXT,
    reason_to_dispute  TEXT,
    status             TEXT    DEFAULT 'Not Disputed',
    created_at         TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS disputes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id      INTEGER NOT NULL,
    item_id        INTEGER,
    bureau         TEXT    NOT NULL,
    round_number   INTEGER DEFAULT 1,
    reason         TEXT,
    status         TEXT    DEFAULT 'Draft',
    date_sent      TEXT,
    date_response  TEXT,
    outcome        TEXT,
    letter_body    TEXT,
    notes          TEXT,
    follow_up_on   TEXT,
    created_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id)   REFERENCES credit_items(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id     INTEGER,
    dispute_id    INTEGER,
    title         TEXT    NOT NULL,
    due_date      TEXT,
    priority      TEXT    DEFAULT 'Medium',
    done          INTEGER DEFAULT 0,
    notes         TEXT,
    created_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id)  REFERENCES clients(id)  ON DELETE CASCADE,
    FOREIGN KEY (dispute_id) REFERENCES disputes(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS score_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id    INTEGER NOT NULL,
    recorded_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
    bureau       TEXT    NOT NULL,
    score        INTEGER,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

CREATE TABLE IF NOT EXISTS client_documents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id      INTEGER NOT NULL,
    category       TEXT,
    original_name  TEXT    NOT NULL,
    stored_path    TEXT    NOT NULL,
    mime_type      TEXT,
    size_bytes     INTEGER,
    notes          TEXT,
    uploaded_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL,
    invoice_number  TEXT,
    period_start    TEXT,
    period_end      TEXT,
    status          TEXT    DEFAULT 'Draft',
    subtotal        REAL    DEFAULT 0,
    total           REAL    DEFAULT 0,
    notes           TEXT,
    issued_at       TEXT,
    paid_at         TEXT,
    created_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS invoice_line_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id   INTEGER NOT NULL,
    description  TEXT    NOT NULL,
    quantity     REAL    DEFAULT 1,
    unit_price   REAL    DEFAULT 0,
    amount       REAL    DEFAULT 0,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id    INTEGER,
    event_type   TEXT    NOT NULL,
    description  TEXT,
    created_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
);
"""


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        # Lightweight migration: add columns that may be missing from older DBs.
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(disputes)").fetchall()
        }
        if "follow_up_on" not in existing:
            conn.execute("ALTER TABLE disputes ADD COLUMN follow_up_on TEXT")
        client_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(clients)").fetchall()
        }
        if "monthly_fee" not in client_cols:
            conn.execute("ALTER TABLE clients ADD COLUMN monthly_fee REAL DEFAULT 0")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def fetch_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid


BUREAUS_PERSONAL = ["Equifax", "Experian", "TransUnion"]
BUREAUS_BUSINESS = ["Dun & Bradstreet", "Experian Business", "Equifax Business"]
ITEM_TYPES = [
    "Collection",
    "Charge-off",
    "Late Payment",
    "Hard Inquiry",
    "Public Record",
    "Repossession",
    "Foreclosure",
    "Bankruptcy",
    "Other",
]
DISPUTE_STATUSES = ["Draft", "Mailed", "Awaiting Response", "Resolved", "Rejected"]
DISPUTE_OUTCOMES = ["Removed", "Verified", "Updated", "No Response"]
ITEM_STATUSES = ["Not Disputed", "Disputed", "Removed", "Verified"]


def bureaus_for(client_type: str) -> list[str]:
    return BUREAUS_PERSONAL if client_type == "Personal" else BUREAUS_BUSINESS


# Mailing addresses for the major bureaus. Printed above the salutation on
# outgoing dispute letters. Addresses verified against bureau websites.
BUREAU_ADDRESSES: dict[str, str] = {
    "Equifax": (
        "Equifax Information Services LLC\n"
        "P.O. Box 740256\n"
        "Atlanta, GA 30374"
    ),
    "Experian": (
        "Experian\n"
        "P.O. Box 4500\n"
        "Allen, TX 75013"
    ),
    "TransUnion": (
        "TransUnion Consumer Solutions\n"
        "P.O. Box 2000\n"
        "Chester, PA 19016"
    ),
    "Dun & Bradstreet": (
        "Dun & Bradstreet\n"
        "103 JFK Parkway\n"
        "Short Hills, NJ 07078"
    ),
    "Experian Business": (
        "Experian Business Credit\n"
        "P.O. Box 5007\n"
        "Costa Mesa, CA 92628"
    ),
    "Equifax Business": (
        "Equifax Commercial Services\n"
        "P.O. Box 740241\n"
        "Atlanta, GA 30374"
    ),
}


# ---- Settings helpers ---------------------------------------------------
def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_setting(key: str, default: str = "") -> str:
    row = fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def get_settings_dict() -> dict[str, str]:
    rows = fetch_all("SELECT key, value FROM settings")
    return {r["key"]: r["value"] for r in rows}


# ---- Activity log -------------------------------------------------------
def log_activity(
    event_type: str,
    description: str,
    client_id: int | None = None,
) -> None:
    execute(
        "INSERT INTO activity_log (client_id, event_type, description) "
        "VALUES (?,?,?)",
        (client_id, event_type, description),
    )


# ---- File uploads -------------------------------------------------------
def save_upload(client_id: int, filename: str, data: bytes) -> Path:
    """Persist uploaded bytes under uploads/<client_id>/<uuid>_<safe_name>."""
    UPLOADS_DIR.mkdir(exist_ok=True)
    client_dir = UPLOADS_DIR / str(client_id)
    client_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "file"
    target = client_dir / f"{uuid.uuid4().hex}_{safe}"
    target.write_bytes(data)
    return target


def read_upload(stored_path: str) -> bytes | None:
    p = Path(stored_path)
    if not p.exists():
        return None
    return p.read_bytes()


def delete_upload(stored_path: str) -> None:
    p = Path(stored_path)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


DOCUMENT_CATEGORIES = [
    "Credit Report",
    "ID / Proof of Address",
    "Bureau Response",
    "Signed Authorization",
    "Invoice / Receipt",
    "Other",
]

INVOICE_STATUSES = ["Draft", "Sent", "Paid", "Void"]

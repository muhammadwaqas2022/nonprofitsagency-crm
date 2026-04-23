"""SQLite persistence layer for the Credit Repair Cloud MVP."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "credit_repair.db"

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
    created_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id)   REFERENCES credit_items(id) ON DELETE SET NULL
);
"""


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


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

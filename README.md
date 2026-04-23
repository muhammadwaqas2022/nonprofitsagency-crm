# Credit Repair Cloud (MVP)

A Streamlit + SQLite app for repairing personal and business credit.

## Features

- **Dashboard** – KPIs for clients, disputes, and item removals.
- **Clients** – onboard Personal or Business clients with all three relevant
  credit bureaus (Equifax/Experian/TransUnion or D&B/Experian Biz/Equifax Biz),
  initial and current scores.
- **Credit Items** – track negative tradelines, collections, late payments,
  inquiries, public records.
- **Disputes** – open disputes against items, track status across rounds, and
  record outcomes (Removed / Verified / Updated / No Response). Outcomes
  cascade to the underlying credit item.
- **Letter Generator** – FCRA §611 / §609, FDCPA §809 debt validation,
  goodwill, and business-credit templates with merge fields; download or
  attach to a dispute.
- **Progress** – initial vs current scores per bureau, removal rate, and
  pipeline counts.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Data is persisted in `credit_repair.db` (SQLite, created automatically).

## Files

- `app.py` – dashboard / landing page
- `db.py` – schema, helpers, constants
- `letter_templates.py` – dispute letter templates
- `pages/` – Streamlit multipage pages
- `credit_repair.db` – auto-created SQLite database (gitignored recommended)

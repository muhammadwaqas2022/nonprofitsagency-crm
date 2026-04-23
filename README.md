# Credit Repair Cloud (MVP)

A Streamlit + SQLite app for repairing personal and business credit.

## Features

- **Dashboard** – KPIs, overdue tasks, upcoming follow-ups, stale disputes (>30 days).
- **Clients** – onboard Personal or Business clients with the three relevant
  credit bureaus (Equifax / Experian / TransUnion or D&B / Experian Biz /
  Equifax Biz), starting + current scores.
- **Credit Items** – track negative tradelines, collections, late payments,
  inquiries, public records. **CSV bulk import** with validation and preview.
- **Disputes** – open disputes against items, track status across rounds, and
  record outcomes (Removed / Verified / Updated / No Response). Outcomes
  cascade to the underlying credit item.
- **Letter Generator** – FCRA §611 / §609, FDCPA §809 debt validation,
  goodwill, and business-credit templates with merge fields; download as
  TXT or PDF, attach to a dispute, or **bulk-generate letters for all three
  bureaus** at once (ZIP download + optional draft disputes).
- **Progress** – initial vs current scores, score history line chart,
  removal rate, dispute pipeline, downloadable client summary.
- **Tasks** – follow-ups with due dates and priorities, filterable by
  client / priority / status. Dashboard surfaces overdue and upcoming items.
- **Settings** – agency profile, bureau mailing addresses, one-click demo
  data seed, destructive wipe with confirmation.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Data is persisted in `credit_repair.db` (SQLite, auto-created, gitignored).

## First run

Open **⚙️ Settings → Data utilities → Seed demo data** to populate 2 sample
clients, 5 credit items, 3 disputes, 4 tasks, and three months of score
history so you can click through every feature immediately.

## Files

- `app.py` – dashboard + "attention needed" lane
- `db.py` – schema, helpers, bureau addresses, settings key/value
- `letter_templates.py` – dispute letter templates with merge fields
- `pdf_utils.py` – reportlab-based PDF renderer
- `pages/` – Streamlit multipage pages (Clients, Credit Items, Disputes,
  Letter Generator, Progress, Tasks, Settings)
- `credit_repair.db` – auto-created SQLite database (gitignored)

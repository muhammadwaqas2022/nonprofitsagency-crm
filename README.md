# Credit Repair Cloud (MVP)

A Streamlit + SQLite app for repairing personal and business credit.

## Features

- **Dashboard** – KPIs (clients, disputes, items removed, outstanding $,
  paid $), "Attention needed" lane (overdue tasks, upcoming tasks, stale
  30d+ disputes), and a live activity feed.
- **Clients** – onboard Personal or Business clients with the three relevant
  credit bureaus (Equifax / Experian / TransUnion or D&B / Experian Biz /
  Equifax Biz), starting + current scores, and monthly fee.
- **Credit Items** – track negative tradelines, collections, late payments,
  inquiries, public records. CSV bulk import with validation.
- **Disputes** – open disputes against items, track rounds, record outcomes
  (Removed / Verified / Updated / No Response); outcomes cascade to the
  underlying item.
- **Letter Generator** – FCRA §611 / §609, FDCPA §809, goodwill, and
  business-credit templates with merge fields (incl. bureau mailing
  addresses); download TXT/PDF, attach to a dispute, or bulk-generate
  letters for all three bureaus → ZIP + optional draft disputes.
- **Progress** – initial vs current scores, score history line chart,
  removal rate, dispute pipeline, downloadable client summary.
- **Tasks** – follow-ups with due dates, priorities, client/dispute links;
  filters + overdue/upcoming KPIs.
- **Settings** – agency profile, bureau addresses reference, one-click
  demo data seed, typed-confirm destructive wipe.
- **Documents** – upload/download credit reports, IDs, bureau responses,
  signed authorizations per client, with categories.
- **Invoices** – draft/sent/paid invoices with line items and per-client
  monthly fee defaults; single-page PDF export using the agency profile
  as the header.
- **Activity** – full audit trail of creates/updates/deletes across
  clients, items, disputes, letters, documents, and invoices. CSV export.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Data lives in `credit_repair.db` (SQLite) and `uploads/<client_id>/…` —
both auto-created and gitignored.

## First run

Open **⚙️ Settings → Data utilities → Seed demo data** — one click gives
you 2 clients, 5 credit items, 3 disputes, 4 tasks, 3 months of score
history, 2 invoices (one paid, one outstanding), and activity log entries
so every page is populated immediately.

## Files

- `app.py` – dashboard + KPIs + attention lane + activity feed
- `db.py` – schema, helpers, constants, activity log, file upload helpers
- `letter_templates.py` – dispute letter templates with merge fields
- `pdf_utils.py` – reportlab-based letter + invoice PDF renderer
- `pages/` – Streamlit multipage pages:
  - 1 Clients · 2 Credit Items · 3 Disputes · 4 Letter Generator
  - 5 Progress · 6 Tasks · 7 Settings · 8 Documents · 9 Invoices
  - A Activity
- `credit_repair.db` – auto-created SQLite (gitignored)
- `uploads/` – per-client uploaded files (gitignored)

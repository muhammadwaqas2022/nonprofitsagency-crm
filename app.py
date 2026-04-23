"""Credit Repair Cloud - MVP Dashboard.

Streamlit multipage app. Additional pages live in the `pages/` folder.
"""

from datetime import date, timedelta

import streamlit as st

from db import fetch_all, fetch_one, init_db

st.set_page_config(page_title="Credit Repair Cloud", page_icon="💳", layout="wide")

init_db()

st.title("Credit Repair Cloud 💳")
st.caption("MVP for repairing personal and business credit")

# ---- KPIs ---------------------------------------------------------------
total_clients = fetch_one("SELECT COUNT(*) AS n FROM clients")["n"]
personal_clients = fetch_one(
    "SELECT COUNT(*) AS n FROM clients WHERE client_type = 'Personal'"
)["n"]
business_clients = fetch_one(
    "SELECT COUNT(*) AS n FROM clients WHERE client_type = 'Business'"
)["n"]
open_disputes = fetch_one(
    "SELECT COUNT(*) AS n FROM disputes WHERE status NOT IN ('Resolved','Rejected')"
)["n"]
resolved_disputes = fetch_one(
    "SELECT COUNT(*) AS n FROM disputes WHERE status = 'Resolved'"
)["n"]
items_removed = fetch_one(
    "SELECT COUNT(*) AS n FROM credit_items WHERE status = 'Removed'"
)["n"]

outstanding_row = fetch_one(
    "SELECT COALESCE(SUM(total),0) AS amt FROM invoices "
    "WHERE status IN ('Draft','Sent')"
)
outstanding = outstanding_row["amt"] if outstanding_row else 0
paid_row = fetch_one(
    "SELECT COALESCE(SUM(total),0) AS amt FROM invoices WHERE status='Paid'"
)
paid = paid_row["amt"] if paid_row else 0

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Clients", total_clients)
c2.metric("Personal", personal_clients)
c3.metric("Business", business_clients)
c4.metric("Open disputes", open_disputes)
c5.metric("Items removed", items_removed)
c6.metric("Outstanding", f"${outstanding:,.0f}")
c7.metric("Paid", f"${paid:,.0f}")

if total_clients == 0:
    st.info(
        "**First time here?** Head to **⚙️ Settings → Data utilities** and "
        "click **Seed demo data** to populate the app with a sample "
        "personal and business client so you can see every feature in action."
    )

st.divider()

# ---- Attention needed ---------------------------------------------------
today = date.today().isoformat()
in_30 = (date.today() + timedelta(days=30)).isoformat()

overdue_tasks = fetch_all(
    """
    SELECT t.id, t.title, t.due_date, t.priority, c.name AS client
    FROM tasks t LEFT JOIN clients c ON c.id = t.client_id
    WHERE t.done = 0 AND t.due_date IS NOT NULL AND t.due_date < ?
    ORDER BY t.due_date ASC LIMIT 10
    """,
    (today,),
)
upcoming_tasks = fetch_all(
    """
    SELECT t.id, t.title, t.due_date, t.priority, c.name AS client
    FROM tasks t LEFT JOIN clients c ON c.id = t.client_id
    WHERE t.done = 0 AND (t.due_date IS NULL OR t.due_date >= ?)
    ORDER BY COALESCE(t.due_date, '9999-99-99') ASC LIMIT 10
    """,
    (today,),
)
stale_disputes = fetch_all(
    """
    SELECT d.id, d.bureau, d.round_number, d.status, d.date_sent,
           c.name AS client
    FROM disputes d JOIN clients c ON c.id = d.client_id
    WHERE d.status = 'Awaiting Response' AND d.date_sent IS NOT NULL
      AND d.date_sent <= ?
    ORDER BY d.date_sent ASC LIMIT 10
    """,
    ((date.today() - timedelta(days=30)).isoformat(),),
)

st.subheader("Attention needed")
attn_cols = st.columns(3)

with attn_cols[0]:
    st.markdown(f"**🔴 Overdue tasks** ({len(overdue_tasks)})")
    if overdue_tasks:
        st.dataframe(
            [dict(r) for r in overdue_tasks],
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("Nothing overdue.")

with attn_cols[1]:
    st.markdown(f"**⏳ Upcoming tasks** ({len(upcoming_tasks)})")
    if upcoming_tasks:
        st.dataframe(
            [dict(r) for r in upcoming_tasks],
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("No upcoming tasks.")

with attn_cols[2]:
    st.markdown(f"**📬 Stale disputes (30d+)** ({len(stale_disputes)})")
    if stale_disputes:
        st.dataframe(
            [dict(r) for r in stale_disputes],
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("All disputes are within the 30-day response window.")

st.divider()

# ---- Recent activity -----------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Recent clients")
    rows = fetch_all(
        "SELECT id, client_type, name, status, created_at "
        "FROM clients ORDER BY created_at DESC LIMIT 10"
    )
    if rows:
        st.dataframe(
            [dict(r) for r in rows],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No clients yet. Head to **Clients** in the sidebar to add one.")

with right:
    st.subheader("Recent disputes")
    rows = fetch_all(
        "SELECT d.id, c.name AS client, d.bureau, d.round_number, d.status, "
        "d.date_sent FROM disputes d JOIN clients c ON c.id = d.client_id "
        "ORDER BY d.created_at DESC LIMIT 10"
    )
    if rows:
        st.dataframe(
            [dict(r) for r in rows],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No disputes yet. Create one from the **Disputes** page.")

st.divider()

st.subheader("Activity feed")
activity = fetch_all(
    """
    SELECT a.created_at, a.event_type, a.description, c.name AS client
    FROM activity_log a LEFT JOIN clients c ON c.id = a.client_id
    ORDER BY a.created_at DESC LIMIT 15
    """
)
if activity:
    st.dataframe(
        [dict(r) for r in activity],
        use_container_width=True, hide_index=True,
    )
else:
    st.caption("No activity yet — it will populate as you add clients, "
               "disputes, letters, and invoices.")

st.divider()

st.subheader("How the workflow works")
st.markdown(
    """
    1. **Clients** – onboard a personal or business client, record starting scores.
    2. **Credit Items** – list negative tradelines, inquiries, public records
       (or bulk-import them via CSV).
    3. **Disputes** – open a dispute against one or more items, track rounds
       and outcomes.
    4. **Letter Generator** – produce an FCRA / FDCPA-compliant letter from a
       template; download as TXT or PDF, attach to a dispute, or bulk-generate
       letters for all bureaus in one click.
    5. **Progress** – compare initial vs current bureau scores, view score
       history, and export a client summary.
    6. **Tasks** – keep follow-ups organized with due dates and priorities.
    7. **Settings** – agency profile, bureau mailing addresses, demo-data seed.
    8. **Documents** – upload and store credit reports, IDs, and bureau responses per client.
    9. **Invoices** – generate PDF invoices from monthly fees; track outstanding vs paid.
    10. **Activity** – audit trail of every action taken across clients.
    """
)

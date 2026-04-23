"""Tasks & Reminders page: follow-ups for clients and disputes."""

from datetime import date

import streamlit as st

from db import execute, fetch_all, fetch_one, init_db
from auth import logout_button, require_auth

st.set_page_config(page_title="Tasks", page_icon="✅", layout="wide")
init_db()
require_auth()
logout_button()

st.title("Tasks & Reminders ✅")
st.caption("Follow-ups for clients and open disputes.")

PRIORITIES = ["Low", "Medium", "High"]

clients = fetch_all(
    "SELECT id, name, client_type FROM clients ORDER BY name COLLATE NOCASE"
)
client_options = {"— None —": None}
client_options.update(
    {f"{c['name']} ({c['client_type']})": c["id"] for c in clients}
)

disputes = fetch_all(
    """
    SELECT d.id, d.bureau, d.round_number, d.status, c.name AS client
    FROM disputes d JOIN clients c ON c.id = d.client_id
    ORDER BY d.created_at DESC
    """
)
dispute_options = {"— None —": None}
dispute_options.update(
    {
        f"#{d['id']} · {d['client']} · {d['bureau']} · R{d['round_number']}": d["id"]
        for d in disputes
    }
)

# ---- Add task -----------------------------------------------------------
with st.expander("➕ Add task", expanded=False):
    with st.form("add_task", clear_on_submit=True):
        title = st.text_input("Title")
        col1, col2, col3 = st.columns(3)
        due = col1.date_input("Due", value=None, format="YYYY-MM-DD")
        priority = col2.selectbox("Priority", PRIORITIES, index=1)
        client_label = col3.selectbox("Client", list(client_options.keys()))
        dispute_label = st.selectbox("Linked dispute", list(dispute_options.keys()))
        notes = st.text_area("Notes", height=80)

        if st.form_submit_button("Create", type="primary"):
            if not title.strip():
                st.error("Title is required.")
            else:
                new_id = execute(
                    """
                    INSERT INTO tasks (
                        client_id, dispute_id, title, due_date, priority, notes
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    (
                        client_options[client_label],
                        dispute_options[dispute_label],
                        title.strip(),
                        due.isoformat() if due else None,
                        priority,
                        notes.strip(),
                    ),
                )
                st.success(f"Created task #{new_id}.")

# ---- Filters ------------------------------------------------------------
f1, f2, f3 = st.columns(3)
show = f1.radio(
    "Show", ["Open", "Done", "All"], horizontal=True, label_visibility="collapsed"
)
prio_filter = f2.selectbox("Priority", ["All", *PRIORITIES])
client_filter = f3.selectbox("Client", list(client_options.keys()))

sql = """
SELECT t.*, c.name AS client_name
FROM tasks t LEFT JOIN clients c ON c.id = t.client_id WHERE 1=1
"""
params: list = []
if show == "Open":
    sql += " AND t.done = 0"
elif show == "Done":
    sql += " AND t.done = 1"
if prio_filter != "All":
    sql += " AND t.priority = ?"
    params.append(prio_filter)
if client_options[client_filter] is not None:
    sql += " AND t.client_id = ?"
    params.append(client_options[client_filter])
sql += " ORDER BY t.done ASC, COALESCE(t.due_date, '9999-99-99') ASC"

rows = fetch_all(sql, tuple(params))

# ---- KPIs ---------------------------------------------------------------
today = date.today().isoformat()
overdue = sum(
    1 for r in rows
    if not r["done"] and r["due_date"] and r["due_date"] < today
)
due_today = sum(1 for r in rows if not r["done"] and r["due_date"] == today)
open_count = sum(1 for r in rows if not r["done"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total shown", len(rows))
c2.metric("Open", open_count)
c3.metric("Due today", due_today)
c4.metric("Overdue", overdue)

st.divider()

if not rows:
    st.info("No tasks match. Use **➕ Add task** above to create one.")
else:
    for t in rows:
        is_overdue = (
            not t["done"] and t["due_date"] and t["due_date"] < today
        )
        badge = "✅" if t["done"] else ("🔴" if is_overdue else "⏳")
        prio_icon = {"High": "🔺", "Medium": "•", "Low": "▫"}.get(t["priority"], "•")

        header = f"{badge} {prio_icon} {t['title']}"
        if t["due_date"]:
            header += f" · due {t['due_date']}"
        if t["client_name"]:
            header += f" · {t['client_name']}"

        cols = st.columns([6, 1, 1])
        cols[0].markdown(header)
        if not t["done"]:
            if cols[1].button("Done", key=f"done_{t['id']}"):
                execute("UPDATE tasks SET done=1 WHERE id=?", (t["id"],))
                st.rerun()
        else:
            if cols[1].button("Reopen", key=f"reopen_{t['id']}"):
                execute("UPDATE tasks SET done=0 WHERE id=?", (t["id"],))
                st.rerun()
        if cols[2].button("🗑", key=f"delt_{t['id']}"):
            execute("DELETE FROM tasks WHERE id=?", (t["id"],))
            st.rerun()

        if t["notes"]:
            st.caption(f"Notes: {t['notes']}")
        if t["dispute_id"]:
            st.caption(f"Linked to dispute #{t['dispute_id']}")
        st.markdown("---")

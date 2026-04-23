"""Activity log page: audit trail of actions across clients."""

import streamlit as st

from db import execute, fetch_all, init_db

st.set_page_config(page_title="Activity", page_icon="🕒", layout="wide")
init_db()

st.title("Activity 🕒")
st.caption("Audit trail of actions taken on clients, items, disputes, "
           "documents, and invoices.")

clients = fetch_all(
    "SELECT id, name FROM clients ORDER BY name COLLATE NOCASE"
)
client_options = {"All clients": None}
client_options.update({c["name"]: c["id"] for c in clients})

c1, c2, c3 = st.columns([2, 2, 1])
sel_label = c1.selectbox("Client", list(client_options.keys()))
event_filter = c2.text_input(
    "Event contains (e.g. 'dispute', 'invoice', 'letter')"
)
limit = c3.number_input("Rows", min_value=25, max_value=2000, value=200, step=25)

sql = """
SELECT a.id, a.created_at, a.event_type, a.description,
       c.name AS client_name
FROM activity_log a
LEFT JOIN clients c ON c.id = a.client_id
WHERE 1=1
"""
params: list = []
if client_options[sel_label] is not None:
    sql += " AND a.client_id = ?"
    params.append(client_options[sel_label])
if event_filter.strip():
    sql += " AND (a.event_type LIKE ? OR a.description LIKE ?)"
    like = f"%{event_filter.strip()}%"
    params.extend([like, like])
sql += " ORDER BY a.created_at DESC LIMIT ?"
params.append(int(limit))

rows = fetch_all(sql, tuple(params))
st.caption(f"{len(rows)} event(s)")

if not rows:
    st.info("No activity matches the filter.")
else:
    st.dataframe(
        [dict(r) for r in rows], use_container_width=True, hide_index=True
    )

    csv_rows = "timestamp,client,event,description\n" + "\n".join(
        (
            f'"{r["created_at"]}","{(r["client_name"] or "").replace(chr(34), "")}",'
            f'"{r["event_type"]}","{(r["description"] or "").replace(chr(34), "")}"'
        )
        for r in rows
    )
    st.download_button(
        "⬇️ Export CSV",
        data=csv_rows,
        file_name="activity_log.csv",
        mime="text/csv",
    )

st.divider()
with st.expander("Clear activity log (destructive)"):
    confirm = st.text_input("Type CLEAR to confirm", key="act_clear")
    if st.button("Delete all activity log rows"):
        if confirm.strip() == "CLEAR":
            execute("DELETE FROM activity_log")
            st.warning("Activity log cleared.")
            st.rerun()
        else:
            st.error("Type CLEAR to confirm.")

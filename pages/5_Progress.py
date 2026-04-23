"""Progress page: initial vs current scores and per-client dispute stats."""

import pandas as pd
import streamlit as st

from db import fetch_all, fetch_one, init_db

st.set_page_config(page_title="Progress", page_icon="📈", layout="wide")
init_db()

st.title("Progress 📈")
st.caption("Track score changes and dispute resolution per client.")

clients = fetch_all(
    "SELECT id, name, client_type FROM clients ORDER BY name COLLATE NOCASE"
)
if not clients:
    st.info("Add a client first on the **Clients** page.")
    st.stop()

client_options = {f"{c['name']} ({c['client_type']})": c["id"] for c in clients}
sel_label = st.selectbox("Client", list(client_options.keys()))
client_id = client_options[sel_label]
client = fetch_one("SELECT * FROM clients WHERE id = ?", (client_id,))

# ---- Score deltas --------------------------------------------------------
st.subheader("Score progress")

if client["client_type"] == "Personal":
    bureau_fields = [
        ("Equifax", client["initial_equifax"], client["current_equifax"]),
        ("Experian", client["initial_experian"], client["current_experian"]),
        ("TransUnion", client["initial_transunion"], client["current_transunion"]),
    ]
else:
    bureau_fields = [
        ("Dun & Bradstreet", client["initial_dnb"], client["current_dnb"]),
        ("Experian Business", client["initial_experian_biz"],
         client["current_experian_biz"]),
        ("Equifax Business", client["initial_equifax_biz"],
         client["current_equifax_biz"]),
    ]

cols = st.columns(len(bureau_fields))
for col, (name, initial, current) in zip(cols, bureau_fields):
    if initial is None and current is None:
        col.metric(name, "—", "no data")
        continue
    initial_display = initial if initial is not None else 0
    current_display = current if current is not None else initial_display
    delta = current_display - initial_display
    col.metric(name, current_display, delta)

chart_df = pd.DataFrame(
    [
        {"Bureau": name, "Stage": "Initial", "Score": initial or 0}
        for name, initial, _ in bureau_fields
    ]
    + [
        {"Bureau": name, "Stage": "Current", "Score": current or (initial or 0)}
        for name, initial, current in bureau_fields
    ]
)
st.bar_chart(chart_df, x="Bureau", y="Score", color="Stage", stack=False)

# ---- Item stats ----------------------------------------------------------
st.subheader("Credit item outcomes")
items = fetch_all(
    "SELECT status, COUNT(*) AS n FROM credit_items WHERE client_id=? GROUP BY status",
    (client_id,),
)
total_items = fetch_one(
    "SELECT COUNT(*) AS n FROM credit_items WHERE client_id=?", (client_id,)
)["n"]
removed = fetch_one(
    "SELECT COUNT(*) AS n FROM credit_items WHERE client_id=? AND status='Removed'",
    (client_id,),
)["n"]

c1, c2, c3 = st.columns(3)
c1.metric("Total items", total_items)
c2.metric("Items removed", removed)
c3.metric(
    "Removal rate",
    f"{(removed / total_items * 100):.0f}%" if total_items else "—",
)

if items:
    st.dataframe(
        [dict(r) for r in items], use_container_width=True, hide_index=True
    )

# ---- Dispute stats -------------------------------------------------------
st.subheader("Dispute pipeline")
disputes = fetch_all(
    "SELECT status, COUNT(*) AS n FROM disputes WHERE client_id=? GROUP BY status",
    (client_id,),
)
if disputes:
    st.dataframe(
        [dict(r) for r in disputes], use_container_width=True, hide_index=True
    )
else:
    st.caption("No disputes yet.")

outcomes = fetch_all(
    """
    SELECT outcome, COUNT(*) AS n FROM disputes
    WHERE client_id=? AND outcome IS NOT NULL AND outcome != ''
    GROUP BY outcome
    """,
    (client_id,),
)
if outcomes:
    st.markdown("**Outcomes**")
    st.dataframe(
        [dict(r) for r in outcomes], use_container_width=True, hide_index=True
    )

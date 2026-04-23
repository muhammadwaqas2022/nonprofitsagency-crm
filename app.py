"""Credit Repair Cloud - MVP Dashboard.

Streamlit multipage app. Additional pages live in the `pages/` folder.
"""

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

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total clients", total_clients)
c2.metric("Personal", personal_clients)
c3.metric("Business", business_clients)
c4.metric("Open disputes", open_disputes)
c5.metric("Resolved disputes", resolved_disputes)
c6.metric("Items removed", items_removed)

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
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No clients yet. Head to **Clients** in the sidebar to add one.")

with right:
    st.subheader("Recent disputes")
    rows = fetch_all(
        "SELECT d.id, c.name AS client, d.bureau, d.round_number, d.status, d.date_sent "
        "FROM disputes d JOIN clients c ON c.id = d.client_id "
        "ORDER BY d.created_at DESC LIMIT 10"
    )
    if rows:
        st.dataframe(
            [dict(r) for r in rows],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No disputes yet. Create one from the **Disputes** page.")

st.divider()

st.subheader("How the workflow works")
st.markdown(
    """
    1. **Clients** – onboard a personal or business client, record starting credit scores.
    2. **Credit Items** – list the negative tradelines, inquiries, or public records.
    3. **Disputes** – open a dispute against one or more items, track rounds and outcomes.
    4. **Letter Generator** – produce an FCRA / FDCPA-compliant letter from a template,
       copy or download it, and attach it to the dispute record.
    5. **Progress** – compare initial vs current bureau scores and removed items per client.
    """
)

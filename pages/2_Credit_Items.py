"""Credit Items page: negative tradelines, inquiries and public records per client."""

import streamlit as st

from db import (
    ITEM_STATUSES,
    ITEM_TYPES,
    bureaus_for,
    execute,
    fetch_all,
    fetch_one,
    init_db,
)

st.set_page_config(page_title="Credit Items", page_icon="📝", layout="wide")
init_db()

st.title("Credit Items 📝")
st.caption("Track the negative items that will drive dispute activity.")

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

bureaus = bureaus_for(client["client_type"])

tab_list, tab_add = st.tabs(["Items", "➕ Add item"])

with tab_add:
    with st.form("add_item", clear_on_submit=True):
        col1, col2 = st.columns(2)
        bureau = col1.selectbox("Bureau", bureaus)
        item_type = col2.selectbox("Item type", ITEM_TYPES)
        creditor = col1.text_input("Creditor / Furnisher")
        account_number = col2.text_input("Account number (mask as needed)")
        balance = col1.number_input(
            "Balance ($)", min_value=0.0, step=50.0, format="%.2f"
        )
        date_opened = col2.text_input("Date opened (YYYY-MM-DD)")
        reason = st.text_area(
            "Reason to dispute",
            placeholder="e.g. Not mine. I have no record of this account. "
                        "Please verify or delete.",
            height=90,
        )

        if st.form_submit_button("Save item", type="primary"):
            if not creditor.strip():
                st.error("Creditor is required.")
            else:
                new_id = execute(
                    """
                    INSERT INTO credit_items (
                        client_id, bureau, creditor, account_number,
                        item_type, balance, date_opened, reason_to_dispute
                    ) VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        client_id, bureau, creditor.strip(), account_number.strip(),
                        item_type, balance or None, date_opened.strip(),
                        reason.strip(),
                    ),
                )
                st.success(f"Saved item #{new_id}.")

with tab_list:
    items = fetch_all(
        "SELECT * FROM credit_items WHERE client_id=? ORDER BY created_at DESC",
        (client_id,),
    )
    if not items:
        st.info("No credit items yet for this client.")
    else:
        for it in items:
            badge = {
                "Not Disputed": "⚪",
                "Disputed": "🟡",
                "Removed": "🟢",
                "Verified": "🔴",
            }.get(it["status"], "⚪")
            with st.expander(
                f"{badge} #{it['id']} · {it['bureau']} · {it['creditor']} · "
                f"{it['item_type']} · ${it['balance'] or 0:.2f}"
            ):
                st.write(f"**Account #:** {it['account_number'] or '—'}")
                st.write(f"**Date opened:** {it['date_opened'] or '—'}")
                st.write(f"**Status:** {it['status']}")
                if it["reason_to_dispute"]:
                    st.caption(f"Reason: {it['reason_to_dispute']}")

                c1, c2 = st.columns([2, 1])
                new_status = c1.selectbox(
                    "Update status",
                    ITEM_STATUSES,
                    index=ITEM_STATUSES.index(it["status"])
                    if it["status"] in ITEM_STATUSES else 0,
                    key=f"stat_{it['id']}",
                )
                if c1.button("Save status", key=f"savestat_{it['id']}"):
                    execute(
                        "UPDATE credit_items SET status=? WHERE id=?",
                        (new_status, it["id"]),
                    )
                    st.success("Status updated.")
                    st.rerun()
                if c2.button("🗑 Delete", key=f"delit_{it['id']}"):
                    execute("DELETE FROM credit_items WHERE id=?", (it["id"],))
                    st.warning(f"Deleted item #{it['id']}.")
                    st.rerun()

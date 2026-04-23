"""Disputes page: open, track, and resolve disputes across rounds."""

from datetime import date

import streamlit as st

from db import (
    DISPUTE_OUTCOMES,
    DISPUTE_STATUSES,
    bureaus_for,
    execute,
    fetch_all,
    fetch_one,
    init_db,
    log_activity,
)
from auth import logout_button, require_auth

st.set_page_config(page_title="Disputes", page_icon="⚖️", layout="wide")
init_db()
require_auth()
logout_button()

st.title("Disputes ⚖️")
st.caption("Open disputes against credit items and track each round to resolution.")

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

tab_list, tab_add = st.tabs(["Disputes", "➕ Open new dispute"])

# ---- Open new ------------------------------------------------------------
with tab_add:
    items = fetch_all(
        "SELECT id, bureau, creditor, item_type FROM credit_items WHERE client_id=?",
        (client_id,),
    )
    item_map = {
        f"#{i['id']} · {i['bureau']} · {i['creditor']} · {i['item_type']}": i["id"]
        for i in items
    }
    item_map = {"— No specific item —": None, **item_map}

    with st.form("add_dispute", clear_on_submit=True):
        col1, col2 = st.columns(2)
        bureau = col1.selectbox("Bureau", bureaus)
        round_number = col2.number_input("Round #", 1, 10, 1)
        item_label = st.selectbox("Linked credit item", list(item_map.keys()))
        reason = st.text_area(
            "Reason / basis for dispute",
            placeholder="e.g. Inaccurate balance; account was paid in full; "
                        "not my account.",
            height=100,
        )
        status = col1.selectbox("Status", DISPUTE_STATUSES, index=0)
        date_sent = col2.date_input(
            "Date sent (optional)", value=None, format="YYYY-MM-DD"
        )
        notes = st.text_area("Internal notes", height=70)

        if st.form_submit_button("Create dispute", type="primary"):
            new_id = execute(
                """
                INSERT INTO disputes (
                    client_id, item_id, bureau, round_number, reason,
                    status, date_sent, notes
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    client_id, item_map[item_label], bureau, int(round_number),
                    reason.strip(), status,
                    date_sent.isoformat() if date_sent else None,
                    notes.strip(),
                ),
            )
            if item_map[item_label] and status in ("Mailed", "Awaiting Response"):
                execute(
                    "UPDATE credit_items SET status='Disputed' WHERE id=?",
                    (item_map[item_label],),
                )
            log_activity(
                "dispute.opened",
                f"{bureau} · Round {round_number} · {status}",
                client_id,
            )
            st.success(f"Opened dispute #{new_id}.")

# ---- List / update ------------------------------------------------------
with tab_list:
    disputes = fetch_all(
        """
        SELECT d.*, ci.creditor AS item_creditor, ci.item_type AS item_type_name
        FROM disputes d
        LEFT JOIN credit_items ci ON ci.id = d.item_id
        WHERE d.client_id = ?
        ORDER BY d.created_at DESC
        """,
        (client_id,),
    )
    if not disputes:
        st.info("No disputes yet for this client.")
    else:
        for d in disputes:
            badge = {
                "Draft": "📝", "Mailed": "📬", "Awaiting Response": "⏳",
                "Resolved": "✅", "Rejected": "❌",
            }.get(d["status"], "•")
            header = (
                f"{badge} #{d['id']} · {d['bureau']} · Round {d['round_number']} · "
                f"{d['status']}"
            )
            if d["item_creditor"]:
                header += f" · {d['item_creditor']} ({d['item_type_name']})"
            with st.expander(header):
                st.write(f"**Sent:** {d['date_sent'] or '—'}")
                st.write(f"**Response received:** {d['date_response'] or '—'}")
                st.write(f"**Outcome:** {d['outcome'] or '—'}")
                if d["reason"]:
                    st.caption(f"Reason: {d['reason']}")
                if d["notes"]:
                    st.caption(f"Notes: {d['notes']}")

                with st.form(f"upd_{d['id']}"):
                    c1, c2, c3 = st.columns(3)
                    new_status = c1.selectbox(
                        "Status", DISPUTE_STATUSES,
                        index=DISPUTE_STATUSES.index(d["status"])
                        if d["status"] in DISPUTE_STATUSES else 0,
                        key=f"st_{d['id']}",
                    )
                    outcome_options = ["", *DISPUTE_OUTCOMES]
                    cur_outcome = d["outcome"] or ""
                    new_outcome = c2.selectbox(
                        "Outcome", outcome_options,
                        index=outcome_options.index(cur_outcome)
                        if cur_outcome in outcome_options else 0,
                        key=f"oc_{d['id']}",
                    )
                    response_date = c3.date_input(
                        "Response date",
                        value=date.fromisoformat(d["date_response"])
                        if d["date_response"] else None,
                        format="YYYY-MM-DD",
                        key=f"rd_{d['id']}",
                    )
                    if st.form_submit_button("Update"):
                        execute(
                            """
                            UPDATE disputes
                            SET status=?, outcome=?, date_response=?
                            WHERE id=?
                            """,
                            (
                                new_status,
                                new_outcome or None,
                                response_date.isoformat() if response_date else None,
                                d["id"],
                            ),
                        )
                        # Cascade outcome to the linked credit item.
                        if d["item_id"] and new_outcome == "Removed":
                            execute(
                                "UPDATE credit_items SET status='Removed' WHERE id=?",
                                (d["item_id"],),
                            )
                        elif d["item_id"] and new_outcome == "Verified":
                            execute(
                                "UPDATE credit_items SET status='Verified' WHERE id=?",
                                (d["item_id"],),
                            )
                        log_activity(
                            "dispute.updated",
                            f"#{d['id']} {d['bureau']} R{d['round_number']}: "
                            f"{new_status}"
                            + (f" · {new_outcome}" if new_outcome else ""),
                            client_id,
                        )
                        st.success("Dispute updated.")
                        st.rerun()

                if d["letter_body"]:
                    with st.popover("📄 View attached letter"):
                        st.code(d["letter_body"], language="text")

                if st.button("🗑 Delete dispute", key=f"deld_{d['id']}"):
                    execute("DELETE FROM disputes WHERE id=?", (d["id"],))
                    st.warning(f"Deleted dispute #{d['id']}.")
                    st.rerun()

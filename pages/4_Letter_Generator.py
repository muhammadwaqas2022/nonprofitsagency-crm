"""Letter Generator page: render FCRA/FDCPA dispute letters from templates."""

import streamlit as st

from db import bureaus_for, execute, fetch_all, fetch_one, init_db
from letter_templates import all_templates, render

st.set_page_config(page_title="Letter Generator", page_icon="✉️", layout="wide")
init_db()

st.title("Letter Generator ✉️")
st.caption(
    "Pick a client, choose a template, merge their data, and download or attach "
    "the letter to a dispute."
)

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

templates = all_templates(client["client_type"])
template_name = st.selectbox("Template", list(templates.keys()))

bureau = st.selectbox("Bureau", bureaus_for(client["client_type"]))

items = fetch_all(
    "SELECT id, bureau, creditor, account_number, item_type, reason_to_dispute "
    "FROM credit_items WHERE client_id=? ORDER BY created_at DESC",
    (client_id,),
)
item_map = {"— Manual entry —": None}
for i in items:
    item_map[
        f"#{i['id']} · {i['bureau']} · {i['creditor']} · {i['item_type']}"
    ] = i["id"]
item_label = st.selectbox("Credit item (optional)", list(item_map.keys()))
item = None
if item_map[item_label]:
    item = fetch_one(
        "SELECT * FROM credit_items WHERE id=?", (item_map[item_label],)
    )

with st.expander("Template fields", expanded=True):
    col1, col2 = st.columns(2)
    creditor = col1.text_input(
        "Creditor", value=(item["creditor"] if item else "")
    )
    account_number = col2.text_input(
        "Account number", value=(item["account_number"] if item else "")
    )
    item_type = col1.text_input(
        "Item type", value=(item["item_type"] if item else "")
    )
    reason = st.text_area(
        "Reason", height=100,
        value=(item["reason_to_dispute"] if item else ""),
    )
    signer_name = col2.text_input(
        "Signer name",
        value=client["name"] if client["client_type"] == "Business" else "",
    )

context = {
    "client_name": client["name"],
    "client_address": client["address"],
    "client_city": client["city"],
    "client_state": client["state"],
    "client_zip": client["zip"],
    "bureau": bureau,
    "creditor": creditor,
    "account_number": account_number,
    "item_type": item_type,
    "reason": reason,
    "ssn_last4": client["identifier"] if client["client_type"] == "Personal" else "",
    "dob": client["dob_or_founded"] if client["client_type"] == "Personal" else "",
    "ein": client["identifier"] if client["client_type"] == "Business" else "",
    "signer_name": signer_name or client["name"],
}

letter = render(templates[template_name], context)

st.subheader("Preview")
letter = st.text_area("Edit before saving", value=letter, height=480)

c1, c2, c3 = st.columns(3)
safe_name = "".join(ch for ch in client["name"] if ch.isalnum() or ch in ("-", "_"))
c1.download_button(
    "⬇️ Download .txt",
    data=letter,
    file_name=f"{safe_name}_{bureau.replace(' ', '_')}_{template_name.split(' ')[0]}.txt",
    mime="text/plain",
    use_container_width=True,
)

with c2:
    disputes = fetch_all(
        "SELECT id, bureau, round_number, status FROM disputes "
        "WHERE client_id=? ORDER BY created_at DESC",
        (client_id,),
    )
    dispute_map = {
        f"#{d['id']} · {d['bureau']} · R{d['round_number']} · {d['status']}": d["id"]
        for d in disputes
    }
    if dispute_map:
        target = st.selectbox(
            "Attach to dispute", list(dispute_map.keys()), label_visibility="collapsed"
        )
        if st.button("📎 Attach letter to dispute", use_container_width=True):
            execute(
                "UPDATE disputes SET letter_body=? WHERE id=?",
                (letter, dispute_map[target]),
            )
            st.success(f"Attached to dispute #{dispute_map[target]}.")
    else:
        st.caption("No disputes to attach to yet.")

with c3:
    if st.button("📬 Create dispute from this letter", use_container_width=True):
        new_id = execute(
            """
            INSERT INTO disputes (
                client_id, item_id, bureau, round_number, reason,
                status, letter_body
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                client_id,
                item_map[item_label],
                bureau,
                1,
                reason,
                "Draft",
                letter,
            ),
        )
        st.success(f"Created draft dispute #{new_id} with this letter attached.")

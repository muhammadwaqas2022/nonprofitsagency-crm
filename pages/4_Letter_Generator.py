"""Letter Generator page: render FCRA/FDCPA dispute letters, export as PDF,
or bulk-generate letters for all bureaus at once."""

import io
import re
import zipfile

import streamlit as st

from db import (
    BUREAU_ADDRESSES,
    bureaus_for,
    execute,
    fetch_all,
    fetch_one,
    init_db,
    log_activity,
)
from auth import logout_button, require_auth
from letter_templates import all_templates, render
from pdf_utils import letter_to_pdf_bytes

st.set_page_config(page_title="Letter Generator", page_icon="✉️", layout="wide")
init_db()
require_auth()
logout_button()

st.title("Letter Generator ✉️")
st.caption(
    "Pick a client, choose a template, merge their data, export as TXT/PDF, "
    "or bulk-generate letters for all three bureaus."
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

all_bureaus = bureaus_for(client["client_type"])
bureau = st.selectbox("Bureau (for single letter)", all_bureaus)

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
    item = fetch_one("SELECT * FROM credit_items WHERE id=?", (item_map[item_label],))

with st.expander("Template fields", expanded=True):
    col1, col2 = st.columns(2)
    creditor = col1.text_input("Creditor", value=(item["creditor"] if item else ""))
    account_number = col2.text_input(
        "Account number", value=(item["account_number"] if item else "")
    )
    item_type = col1.text_input(
        "Item type", value=(item["item_type"] if item else "")
    )
    reason = st.text_area(
        "Reason",
        height=100,
        value=(item["reason_to_dispute"] if item else ""),
    )
    signer_name = col2.text_input(
        "Signer name",
        value=client["name"] if client["client_type"] == "Business" else "",
    )


def _context(bureau_name: str) -> dict:
    return {
        "client_name": client["name"],
        "client_address": client["address"],
        "client_city": client["city"],
        "client_state": client["state"],
        "client_zip": client["zip"],
        "bureau": bureau_name,
        "bureau_address": BUREAU_ADDRESSES.get(bureau_name, bureau_name),
        "creditor": creditor,
        "account_number": account_number,
        "item_type": item_type,
        "reason": reason,
        "ssn_last4": client["identifier"] if client["client_type"] == "Personal" else "",
        "dob": client["dob_or_founded"] if client["client_type"] == "Personal" else "",
        "ein": client["identifier"] if client["client_type"] == "Business" else "",
        "signer_name": signer_name or client["name"],
    }


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "letter"


tab_single, tab_bulk = st.tabs(["📝 Single letter", "📦 Bulk — all bureaus"])

# ---- Single letter ------------------------------------------------------
with tab_single:
    letter = render(templates[template_name], _context(bureau))
    letter = st.text_area("Preview / edit", value=letter, height=480, key="single_body")

    safe_name = _slug(client["name"])
    file_stub = f"{safe_name}_{_slug(bureau)}_{_slug(template_name.split(' - ')[0])}"

    c1, c2, c3, c4 = st.columns(4)
    c1.download_button(
        "⬇️ TXT",
        data=letter,
        file_name=f"{file_stub}.txt",
        mime="text/plain",
        use_container_width=True,
    )
    c2.download_button(
        "📄 PDF",
        data=letter_to_pdf_bytes(letter),
        file_name=f"{file_stub}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    disputes = fetch_all(
        "SELECT id, bureau, round_number, status FROM disputes "
        "WHERE client_id=? ORDER BY created_at DESC",
        (client_id,),
    )
    dispute_map = {
        f"#{d['id']} · {d['bureau']} · R{d['round_number']} · {d['status']}": d["id"]
        for d in disputes
    }

    with c3:
        if dispute_map:
            target = st.selectbox(
                "Attach to",
                list(dispute_map.keys()),
                label_visibility="collapsed",
                key="attach_target",
            )
            if st.button("📎 Attach", use_container_width=True):
                execute(
                    "UPDATE disputes SET letter_body=? WHERE id=?",
                    (letter, dispute_map[target]),
                )
                log_activity(
                    "letter.attached",
                    f"{template_name} → dispute #{dispute_map[target]}",
                    client_id,
                )
                st.success(f"Attached to dispute #{dispute_map[target]}.")
        else:
            st.caption("No disputes yet.")

    with c4:
        if st.button("📬 Create dispute", use_container_width=True):
            log_activity(
                "letter.created_dispute",
                f"{template_name} · {bureau}",
                client_id,
            )
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
            st.success(f"Created draft dispute #{new_id}.")

# ---- Bulk: one letter per bureau ----------------------------------------
with tab_bulk:
    st.markdown(
        f"Generate **{template_name}** for every bureau "
        f"({', '.join(all_bureaus)}) in one shot. You get a ZIP with a TXT "
        "and a PDF per bureau, and can optionally open a draft dispute per bureau."
    )

    include_pdf = st.checkbox("Include PDF versions", value=True)
    include_txt = st.checkbox("Include TXT versions", value=True)
    open_drafts = st.checkbox(
        "Also open a draft dispute per bureau (attaches letter)", value=False
    )

    preview_bureau = st.selectbox(
        "Preview one rendered letter", all_bureaus, key="bulk_preview_bureau"
    )
    st.code(
        render(templates[template_name], _context(preview_bureau)),
        language="text",
    )

    safe_name = _slug(client["name"])
    tpl_slug = _slug(template_name.split(" - ")[0])

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for b in all_bureaus:
            body = render(templates[template_name], _context(b))
            stub = f"{safe_name}_{_slug(b)}_{tpl_slug}"
            if include_txt:
                zf.writestr(f"{stub}.txt", body)
            if include_pdf:
                zf.writestr(f"{stub}.pdf", letter_to_pdf_bytes(body))
    buf.seek(0)

    c1, c2 = st.columns(2)
    c1.download_button(
        "⬇️ Download ZIP (all bureaus)",
        data=buf.getvalue(),
        file_name=f"{safe_name}_{tpl_slug}_all_bureaus.zip",
        mime="application/zip",
        use_container_width=True,
        disabled=not (include_pdf or include_txt),
    )

    with c2:
        if st.button(
            "📬 Create draft disputes for all bureaus",
            use_container_width=True,
            disabled=not open_drafts,
        ):
            created = []
            for b in all_bureaus:
                body = render(templates[template_name], _context(b))
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
                        b,
                        1,
                        reason,
                        "Draft",
                        body,
                    ),
                )
                created.append(new_id)
            log_activity(
                "letter.bulk_disputes",
                f"{template_name} · {len(all_bureaus)} bureaus · "
                f"disputes: {', '.join(f'#{i}' for i in created)}",
                client_id,
            )
            st.success(f"Created draft disputes: {', '.join(f'#{i}' for i in created)}")

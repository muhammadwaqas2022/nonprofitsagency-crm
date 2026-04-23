"""Documents page: upload credit reports, IDs, bureau responses, etc."""

import streamlit as st

from db import (
    DOCUMENT_CATEGORIES,
    delete_upload,
    execute,
    fetch_all,
    init_db,
    log_activity,
    read_upload,
    save_upload,
)
from auth import logout_button, require_auth

st.set_page_config(page_title="Documents", page_icon="📎", layout="wide")
init_db()
require_auth()
logout_button()

st.title("Documents 📎")
st.caption("Upload and manage files for each client (credit reports, IDs, "
           "bureau responses, signed authorizations).")

clients = fetch_all(
    "SELECT id, name, client_type FROM clients ORDER BY name COLLATE NOCASE"
)
if not clients:
    st.info("Add a client first on the **Clients** page.")
    st.stop()

client_options = {f"{c['name']} ({c['client_type']})": c["id"] for c in clients}
sel_label = st.selectbox("Client", list(client_options.keys()))
client_id = client_options[sel_label]

tab_list, tab_upload = st.tabs(["Files", "⬆️ Upload"])

with tab_upload:
    with st.form("upload_doc", clear_on_submit=True):
        uploaded = st.file_uploader(
            "Choose a file",
            type=["pdf", "png", "jpg", "jpeg", "txt", "csv", "docx", "xlsx"],
        )
        category = st.selectbox("Category", DOCUMENT_CATEGORIES)
        notes = st.text_input("Notes (optional)")
        if st.form_submit_button("Upload", type="primary"):
            if uploaded is None:
                st.error("Pick a file first.")
            else:
                data = uploaded.getvalue()
                stored = save_upload(client_id, uploaded.name, data)
                execute(
                    """
                    INSERT INTO client_documents (
                        client_id, category, original_name, stored_path,
                        mime_type, size_bytes, notes
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        client_id, category, uploaded.name, str(stored),
                        uploaded.type, len(data), notes.strip(),
                    ),
                )
                log_activity(
                    "document.uploaded",
                    f"{category}: {uploaded.name} ({len(data):,} bytes)",
                    client_id,
                )
                st.success(f"Uploaded {uploaded.name}.")

with tab_list:
    cat_filter = st.selectbox("Filter by category", ["All", *DOCUMENT_CATEGORIES])
    sql = "SELECT * FROM client_documents WHERE client_id=?"
    params: list = [client_id]
    if cat_filter != "All":
        sql += " AND category=?"
        params.append(cat_filter)
    sql += " ORDER BY uploaded_at DESC"
    docs = fetch_all(sql, tuple(params))

    st.caption(f"{len(docs)} file(s)")
    if not docs:
        st.info("No files yet for this client.")
    else:
        for d in docs:
            with st.expander(
                f"📄 {d['original_name']} · {d['category']} · "
                f"{(d['size_bytes'] or 0):,} bytes · {d['uploaded_at']}"
            ):
                if d["notes"]:
                    st.caption(f"Notes: {d['notes']}")
                c1, c2 = st.columns([1, 4])
                file_bytes = read_upload(d["stored_path"])
                if file_bytes is not None:
                    c1.download_button(
                        "⬇️ Download",
                        data=file_bytes,
                        file_name=d["original_name"],
                        mime=d["mime_type"] or "application/octet-stream",
                        key=f"dl_{d['id']}",
                    )
                else:
                    c1.warning("File missing from disk.")
                if c2.button("🗑 Delete", key=f"deld_{d['id']}"):
                    delete_upload(d["stored_path"])
                    execute(
                        "DELETE FROM client_documents WHERE id=?", (d["id"],)
                    )
                    log_activity(
                        "document.deleted",
                        f"{d['original_name']}",
                        client_id,
                    )
                    st.warning(f"Deleted {d['original_name']}.")
                    st.rerun()

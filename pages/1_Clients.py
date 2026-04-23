"""Clients page: create and manage Personal and Business clients."""

import streamlit as st

from db import (
    BUREAUS_BUSINESS,
    BUREAUS_PERSONAL,
    execute,
    fetch_all,
    init_db,
    log_activity,
)

st.set_page_config(page_title="Clients", page_icon="👤", layout="wide")
init_db()

st.title("Clients 👤")
st.caption("Onboard personal or business clients and track their starting scores.")

tab_list, tab_add = st.tabs(["All clients", "➕ Add client"])

# ---- Add client ---------------------------------------------------------
with tab_add:
    with st.form("add_client", clear_on_submit=True):
        client_type = st.radio("Client type", ["Personal", "Business"], horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input(
                "Full name" if client_type == "Personal" else "Business name"
            )
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            identifier = st.text_input(
                "SSN (last 4)" if client_type == "Personal" else "EIN"
            )
            dob_or_founded = st.text_input(
                "Date of birth" if client_type == "Personal" else "Date founded"
            )
        with col2:
            address = st.text_input("Street address")
            city = st.text_input("City")
            state = st.text_input("State", max_chars=2)
            zip_code = st.text_input("ZIP")
            monthly_fee = st.number_input(
                "Monthly fee ($)", min_value=0.0, step=25.0, format="%.2f"
            )
            notes = st.text_area("Notes", height=70)

        st.markdown("**Starting credit scores** (optional)")
        bureaus = BUREAUS_PERSONAL if client_type == "Personal" else BUREAUS_BUSINESS
        score_inputs: dict[str, int | None] = {}
        cols = st.columns(len(bureaus))
        for col, bureau in zip(cols, bureaus):
            with col:
                score_inputs[bureau] = st.number_input(
                    bureau, min_value=0, max_value=999, value=0, step=1
                )

        submitted = st.form_submit_button("Save client", type="primary")
        if submitted:
            if not name.strip():
                st.error("Name is required.")
            else:
                if client_type == "Personal":
                    eq = score_inputs.get("Equifax") or None
                    ex = score_inputs.get("Experian") or None
                    tu = score_inputs.get("TransUnion") or None
                    biz_vals = (None, None, None)
                else:
                    eq = ex = tu = None
                    biz_vals = (
                        score_inputs.get("Dun & Bradstreet") or None,
                        score_inputs.get("Experian Business") or None,
                        score_inputs.get("Equifax Business") or None,
                    )
                new_id = execute(
                    """
                    INSERT INTO clients (
                        client_type, name, email, phone, identifier,
                        dob_or_founded, address, city, state, zip,
                        initial_equifax, initial_experian, initial_transunion,
                        current_equifax, current_experian, current_transunion,
                        initial_dnb, initial_experian_biz, initial_equifax_biz,
                        current_dnb, current_experian_biz, current_equifax_biz,
                        monthly_fee, notes
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        client_type, name.strip(), email.strip(), phone.strip(),
                        identifier.strip(), dob_or_founded.strip(),
                        address.strip(), city.strip(), state.strip().upper(),
                        zip_code.strip(),
                        eq, ex, tu, eq, ex, tu,
                        biz_vals[0], biz_vals[1], biz_vals[2],
                        biz_vals[0], biz_vals[1], biz_vals[2],
                        monthly_fee or 0, notes.strip(),
                    ),
                )
                log_activity(
                    "client.created",
                    f"{client_type}: {name}",
                    new_id,
                )
                st.success(f"Saved client #{new_id}: {name}")

# ---- List / edit --------------------------------------------------------
with tab_list:
    filter_type = st.selectbox("Filter by type", ["All", "Personal", "Business"])
    search = st.text_input("🔍 Search name / email / identifier")

    sql = "SELECT * FROM clients WHERE 1=1"
    params: list = []
    if filter_type != "All":
        sql += " AND client_type = ?"
        params.append(filter_type)
    if search:
        sql += " AND (name LIKE ? OR email LIKE ? OR identifier LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    sql += " ORDER BY created_at DESC"

    rows = fetch_all(sql, tuple(params))
    st.caption(f"{len(rows)} client(s)")

    if not rows:
        st.info("No clients match. Add one from the **➕ Add client** tab.")
    else:
        for r in rows:
            with st.expander(
                f"#{r['id']} · {r['name']} · {r['client_type']} · {r['status']}"
            ):
                col1, col2, col3 = st.columns(3)
                col1.write(f"**Email:** {r['email'] or '—'}")
                col1.write(f"**Phone:** {r['phone'] or '—'}")
                col1.write(
                    f"**{'SSN (last 4)' if r['client_type'] == 'Personal' else 'EIN'}:** "
                    f"{r['identifier'] or '—'}"
                )
                col2.write(
                    f"**Address:** {r['address'] or '—'}, {r['city'] or ''} "
                    f"{r['state'] or ''} {r['zip'] or ''}"
                )
                col2.write(
                    f"**{'DOB' if r['client_type'] == 'Personal' else 'Founded'}:** "
                    f"{r['dob_or_founded'] or '—'}"
                )

                if r["client_type"] == "Personal":
                    col3.write(
                        f"**Equifax:** {r['initial_equifax']} → {r['current_equifax']}"
                    )
                    col3.write(
                        f"**Experian:** {r['initial_experian']} → {r['current_experian']}"
                    )
                    col3.write(
                        f"**TransUnion:** {r['initial_transunion']} → "
                        f"{r['current_transunion']}"
                    )
                else:
                    col3.write(
                        f"**D&B:** {r['initial_dnb']} → {r['current_dnb']}"
                    )
                    col3.write(
                        f"**Experian Biz:** {r['initial_experian_biz']} → "
                        f"{r['current_experian_biz']}"
                    )
                    col3.write(
                        f"**Equifax Biz:** {r['initial_equifax_biz']} → "
                        f"{r['current_equifax_biz']}"
                    )

                if r["notes"]:
                    st.caption(f"Notes: {r['notes']}")

                st.markdown("**Update current scores**")
                with st.form(f"score_form_{r['id']}"):
                    if r["client_type"] == "Personal":
                        c1, c2, c3 = st.columns(3)
                        new_eq = c1.number_input(
                            "Equifax", 0, 999, int(r["current_equifax"] or 0),
                            key=f"eq_{r['id']}"
                        )
                        new_ex = c2.number_input(
                            "Experian", 0, 999, int(r["current_experian"] or 0),
                            key=f"ex_{r['id']}"
                        )
                        new_tu = c3.number_input(
                            "TransUnion", 0, 999,
                            int(r["current_transunion"] or 0),
                            key=f"tu_{r['id']}"
                        )
                        if st.form_submit_button("Save scores"):
                            execute(
                                "UPDATE clients SET current_equifax=?, "
                                "current_experian=?, current_transunion=? WHERE id=?",
                                (new_eq or None, new_ex or None, new_tu or None, r["id"]),
                            )
                            st.success("Scores updated.")
                            st.rerun()
                    else:
                        c1, c2, c3 = st.columns(3)
                        new_dnb = c1.number_input(
                            "D&B", 0, 999, int(r["current_dnb"] or 0),
                            key=f"dnb_{r['id']}"
                        )
                        new_ex = c2.number_input(
                            "Experian Biz", 0, 999,
                            int(r["current_experian_biz"] or 0),
                            key=f"exb_{r['id']}"
                        )
                        new_eq = c3.number_input(
                            "Equifax Biz", 0, 999,
                            int(r["current_equifax_biz"] or 0),
                            key=f"eqb_{r['id']}"
                        )
                        if st.form_submit_button("Save scores"):
                            execute(
                                "UPDATE clients SET current_dnb=?, "
                                "current_experian_biz=?, current_equifax_biz=? "
                                "WHERE id=?",
                                (new_dnb or None, new_ex or None, new_eq or None,
                                 r["id"]),
                            )
                            st.success("Scores updated.")
                            st.rerun()

                st.markdown("---")
                danger = st.columns([1, 5])
                if danger[0].button("🗑 Delete client", key=f"del_{r['id']}"):
                    log_activity(
                        "client.deleted",
                        f"{r['client_type']}: {r['name']}",
                        None,
                    )
                    execute("DELETE FROM clients WHERE id=?", (r["id"],))
                    st.warning(f"Deleted client #{r['id']}.")
                    st.rerun()

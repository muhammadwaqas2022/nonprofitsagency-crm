"""Settings page: agency info, demo data seeding, database utilities."""

from datetime import date, timedelta

import streamlit as st

from db import (
    BUREAU_ADDRESSES,
    DB_PATH,
    execute,
    fetch_all,
    fetch_one,
    get_setting,
    init_db,
    set_setting,
)

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
init_db()

st.title("Settings ⚙️")

tab_agency, tab_bureau, tab_data = st.tabs(
    ["Agency profile", "Bureau addresses", "Data utilities"]
)

# ---- Agency profile -----------------------------------------------------
with tab_agency:
    st.caption("Appears on generated reports and summary PDFs.")
    with st.form("agency_form"):
        agency_name = st.text_input("Agency name", value=get_setting("agency_name"))
        col1, col2 = st.columns(2)
        contact_name = col1.text_input(
            "Primary contact name", value=get_setting("contact_name")
        )
        contact_email = col2.text_input(
            "Contact email", value=get_setting("contact_email")
        )
        phone = col1.text_input("Phone", value=get_setting("phone"))
        website = col2.text_input("Website", value=get_setting("website"))
        address = st.text_input("Street address", value=get_setting("address"))
        col3, col4, col5 = st.columns(3)
        city = col3.text_input("City", value=get_setting("city"))
        state = col4.text_input("State", value=get_setting("state"), max_chars=2)
        zip_code = col5.text_input("ZIP", value=get_setting("zip"))

        if st.form_submit_button("Save agency profile", type="primary"):
            for key, value in {
                "agency_name": agency_name,
                "contact_name": contact_name,
                "contact_email": contact_email,
                "phone": phone,
                "website": website,
                "address": address,
                "city": city,
                "state": state.upper(),
                "zip": zip_code,
            }.items():
                set_setting(key, value.strip())
            st.success("Agency profile saved.")

# ---- Bureau addresses ---------------------------------------------------
with tab_bureau:
    st.caption(
        "Mailing addresses printed on outgoing dispute letters. These are "
        "built into the app; changing them here is not yet persisted."
    )
    for bureau, addr in BUREAU_ADDRESSES.items():
        st.markdown(f"**{bureau}**")
        st.code(addr, language="text")

# ---- Data utilities -----------------------------------------------------
with tab_data:
    st.caption(f"Database path: `{DB_PATH}`")

    existing = fetch_one("SELECT COUNT(*) AS n FROM clients")["n"]
    st.write(f"Current clients in DB: **{existing}**")

    st.markdown("### 🌱 Seed demo data")
    st.caption(
        "Creates 2 sample clients (1 personal, 1 business), 5 credit items, "
        "3 disputes, 4 tasks, and baseline score history. Safe to run more "
        "than once — it only seeds if the DB has no clients."
    )

    if st.button("Seed demo data", type="primary"):
        if existing > 0:
            st.warning(
                f"DB already has {existing} client(s). Clear the DB first "
                "if you want a clean seed."
            )
        else:
            # --- Personal client ---
            pid = execute(
                """
                INSERT INTO clients (
                    client_type, name, email, phone, identifier,
                    dob_or_founded, address, city, state, zip,
                    initial_equifax, initial_experian, initial_transunion,
                    current_equifax, current_experian, current_transunion
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "Personal", "Jane Sample", "jane@example.com", "555-0100",
                    "1234", "1985-04-12", "42 Oak Lane", "Austin", "TX", "78701",
                    562, 571, 558, 604, 612, 598,
                ),
            )
            # --- Business client ---
            bid = execute(
                """
                INSERT INTO clients (
                    client_type, name, email, phone, identifier,
                    dob_or_founded, address, city, state, zip,
                    initial_dnb, initial_experian_biz, initial_equifax_biz,
                    current_dnb, current_experian_biz, current_equifax_biz
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "Business", "Acme Widgets LLC", "ops@acmewidgets.com",
                    "555-0200", "12-3456789", "2018-06-01",
                    "500 Industrial Pkwy", "Dallas", "TX", "75201",
                    35, 40, 42, 58, 61, 65,
                ),
            )

            # --- Credit items for Jane ---
            items = [
                ("Equifax", "ABC Collections", "XXXX1234", "Collection",
                 845.50, "2022-03-15", "Not mine - no record of this account",
                 "Disputed"),
                ("Experian", "ABC Collections", "XXXX1234", "Collection",
                 845.50, "2022-03-15", "Not mine - no record of this account",
                 "Removed"),
                ("TransUnion", "Capital Bank", "XXXX9876", "Late Payment",
                 0, "2021-11-15", "Payment was made on time", "Disputed"),
                ("Equifax", "MegaCard", "XXXX5555", "Charge-off",
                 2310.00, "2020-07-22", "Balance is incorrect",
                 "Not Disputed"),
                ("Experian", "QuickCash", "XXXX1111", "Hard Inquiry",
                 0, "2023-01-05", "Inquiry not authorized", "Disputed"),
            ]
            item_ids = []
            for bureau, creditor, acct, itype, bal, opened, reason, status in items:
                item_ids.append(
                    execute(
                        """
                        INSERT INTO credit_items (
                            client_id, bureau, creditor, account_number,
                            item_type, balance, date_opened,
                            reason_to_dispute, status
                        ) VALUES (?,?,?,?,?,?,?,?,?)
                        """,
                        (pid, bureau, creditor, acct, itype,
                         bal, opened, reason, status),
                    )
                )

            # --- Disputes ---
            today = date.today()
            execute(
                """
                INSERT INTO disputes (
                    client_id, item_id, bureau, round_number, reason,
                    status, date_sent, date_response, outcome
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (pid, item_ids[1], "Experian", 1, "Not mine",
                 "Resolved",
                 (today - timedelta(days=45)).isoformat(),
                 (today - timedelta(days=10)).isoformat(),
                 "Removed"),
            )
            execute(
                """
                INSERT INTO disputes (
                    client_id, item_id, bureau, round_number, reason,
                    status, date_sent
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (pid, item_ids[0], "Equifax", 1, "Not mine",
                 "Awaiting Response",
                 (today - timedelta(days=14)).isoformat()),
            )
            execute(
                """
                INSERT INTO disputes (
                    client_id, item_id, bureau, round_number, reason, status
                ) VALUES (?,?,?,?,?,?)
                """,
                (pid, item_ids[2], "TransUnion", 1,
                 "Payment was on time", "Draft"),
            )

            # --- Tasks ---
            tasks = [
                ("Call Jane to review plan", (today + timedelta(days=1)).isoformat(),
                 "High", pid),
                ("Mail Equifax round 2 letter",
                 (today + timedelta(days=5)).isoformat(), "Medium", pid),
                ("Follow up on Acme EIN verification",
                 (today - timedelta(days=2)).isoformat(), "High", bid),
                ("Pull updated 3-bureau report",
                 (today + timedelta(days=14)).isoformat(), "Low", pid),
            ]
            for title, due, prio, cid in tasks:
                execute(
                    "INSERT INTO tasks (client_id, title, due_date, priority) "
                    "VALUES (?,?,?,?)",
                    (cid, title, due, prio),
                )

            # --- Score history (3 snapshots, monthly) ---
            for months_ago, offsets in [
                (2, (-42, -41, -40)),
                (1, (-15, -10, -20)),
                (0, (0, 0, 0)),
            ]:
                snap_date = (
                    today - timedelta(days=months_ago * 30)
                ).isoformat()
                execute(
                    "INSERT INTO score_history (client_id, recorded_at, "
                    "bureau, score) VALUES (?,?,?,?)",
                    (pid, snap_date, "Equifax", 604 + offsets[0]),
                )
                execute(
                    "INSERT INTO score_history (client_id, recorded_at, "
                    "bureau, score) VALUES (?,?,?,?)",
                    (pid, snap_date, "Experian", 612 + offsets[1]),
                )
                execute(
                    "INSERT INTO score_history (client_id, recorded_at, "
                    "bureau, score) VALUES (?,?,?,?)",
                    (pid, snap_date, "TransUnion", 598 + offsets[2]),
                )

            st.success(
                f"Seeded 2 clients, 5 items, 3 disputes, 4 tasks, and score "
                f"history. Navigate to **Clients** to start exploring."
            )
            st.rerun()

    st.markdown("---")
    st.markdown("### 🧹 Wipe all data")
    st.caption("Deletes every client, credit item, dispute, task, and score history row.")
    confirm = st.text_input(
        "Type **WIPE** to confirm", key="wipe_confirm", value=""
    )
    if st.button("Delete everything", type="secondary"):
        if confirm.strip() == "WIPE":
            for table in ["tasks", "score_history", "disputes",
                          "credit_items", "clients"]:
                execute(f"DELETE FROM {table}")
            st.warning("All data deleted.")
            st.rerun()
        else:
            st.error("Type WIPE (all caps) to confirm.")

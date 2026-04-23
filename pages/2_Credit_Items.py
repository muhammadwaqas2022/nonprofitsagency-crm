"""Credit Items page: negative tradelines, inquiries and public records per client."""

import io

import pandas as pd
import streamlit as st

from db import (
    ITEM_STATUSES,
    ITEM_TYPES,
    bureaus_for,
    execute,
    fetch_all,
    fetch_one,
    init_db,
    log_activity,
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

tab_list, tab_add, tab_import = st.tabs(["Items", "➕ Add item", "📥 Import CSV"])

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
                log_activity(
                    "item.created",
                    f"{bureau} · {creditor} · {item_type}",
                    client_id,
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
                    log_activity(
                        "item.status",
                        f"{it['bureau']} · {it['creditor']} → {new_status}",
                        client_id,
                    )
                    st.success("Status updated.")
                    st.rerun()
                if c2.button("🗑 Delete", key=f"delit_{it['id']}"):
                    execute("DELETE FROM credit_items WHERE id=?", (it["id"],))
                    st.warning(f"Deleted item #{it['id']}.")
                    st.rerun()

# ---- CSV import ---------------------------------------------------------
with tab_import:
    st.markdown(
        "Bulk-load credit items from a CSV. Required columns: "
        "**bureau, creditor, item_type**. Optional columns: "
        "**account_number, balance, date_opened, reason_to_dispute**."
    )

    REQUIRED = ["bureau", "creditor", "item_type"]
    OPTIONAL = ["account_number", "balance", "date_opened", "reason_to_dispute"]
    ALL_COLS = REQUIRED + OPTIONAL

    sample = pd.DataFrame(
        [
            {
                "bureau": bureaus[0],
                "creditor": "ABC Collections",
                "item_type": "Collection",
                "account_number": "XXXX1234",
                "balance": 450.00,
                "date_opened": "2022-05-01",
                "reason_to_dispute": "Not mine",
            },
            {
                "bureau": bureaus[-1],
                "creditor": "Capital Bank",
                "item_type": "Late Payment",
                "account_number": "XXXX9876",
                "balance": 0,
                "date_opened": "2021-11-15",
                "reason_to_dispute": "Payment was on time",
            },
        ]
    )
    st.download_button(
        "⬇️ Download sample CSV",
        data=sample.to_csv(index=False),
        file_name="credit_items_sample.csv",
        mime="text/csv",
    )

    uploaded = st.file_uploader("Upload CSV", type=["csv"], key="items_csv")
    if uploaded is not None:
        try:
            df = pd.read_csv(io.BytesIO(uploaded.getvalue()))
        except Exception as exc:
            st.error(f"Could not read CSV: {exc}")
            st.stop()

        df.columns = [c.strip().lower() for c in df.columns]
        missing = [c for c in REQUIRED if c not in df.columns]
        if missing:
            st.error(f"Missing required column(s): {', '.join(missing)}")
        else:
            # Keep only recognized columns
            df = df[[c for c in ALL_COLS if c in df.columns]].copy()
            df = df.fillna("")

            # Validate bureau + item_type against allowed values for this client
            valid_bureaus = set(bureaus)
            valid_items = set(ITEM_TYPES)
            df["_bureau_ok"] = df["bureau"].astype(str).isin(valid_bureaus)
            df["_item_ok"] = df["item_type"].astype(str).isin(valid_items)

            good = df[df["_bureau_ok"] & df["_item_ok"]].drop(
                columns=["_bureau_ok", "_item_ok"]
            )
            bad = df[~(df["_bureau_ok"] & df["_item_ok"])]

            st.markdown(f"**Preview — {len(good)} valid row(s):**")
            st.dataframe(good, use_container_width=True, hide_index=True)

            if len(bad):
                st.warning(
                    f"{len(bad)} row(s) skipped — bureau must be one of "
                    f"{sorted(valid_bureaus)} and item_type one of "
                    f"{sorted(valid_items)}."
                )
                st.dataframe(bad, use_container_width=True, hide_index=True)

            if len(good) and st.button("📥 Import rows", type="primary"):
                inserted = 0
                log_activity(
                    "item.import.start",
                    f"Importing {len(good)} row(s) from CSV",
                    client_id,
                )
                for _, row in good.iterrows():
                    try:
                        balance = (
                            float(row["balance"])
                            if "balance" in row and str(row["balance"]).strip() != ""
                            else None
                        )
                    except (TypeError, ValueError):
                        balance = None
                    execute(
                        """
                        INSERT INTO credit_items (
                            client_id, bureau, creditor, account_number,
                            item_type, balance, date_opened, reason_to_dispute
                        ) VALUES (?,?,?,?,?,?,?,?)
                        """,
                        (
                            client_id,
                            str(row["bureau"]).strip(),
                            str(row["creditor"]).strip(),
                            str(row.get("account_number", "")).strip(),
                            str(row["item_type"]).strip(),
                            balance,
                            str(row.get("date_opened", "")).strip(),
                            str(row.get("reason_to_dispute", "")).strip(),
                        ),
                    )
                    inserted += 1
                log_activity(
                    "item.import.done",
                    f"Imported {inserted} row(s) from CSV",
                    client_id,
                )
                st.success(f"Imported {inserted} item(s).")
                st.rerun()

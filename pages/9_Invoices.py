"""Invoices page: draft invoices per client with PDF export."""

from datetime import date

import streamlit as st

from db import (
    INVOICE_STATUSES,
    execute,
    fetch_all,
    fetch_one,
    get_settings_dict,
    init_db,
    log_activity,
)
from pdf_utils import invoice_to_pdf_bytes

st.set_page_config(page_title="Invoices", page_icon="💵", layout="wide")
init_db()

st.title("Invoices 💵")
st.caption("Track monthly fees and one-off charges per client.")

clients = fetch_all(
    "SELECT id, name, client_type, monthly_fee FROM clients "
    "ORDER BY name COLLATE NOCASE"
)
if not clients:
    st.info("Add a client first on the **Clients** page.")
    st.stop()

client_options = {f"{c['name']} ({c['client_type']})": c["id"] for c in clients}
sel_label = st.selectbox("Client", list(client_options.keys()))
client_id = client_options[sel_label]
client = fetch_one("SELECT * FROM clients WHERE id=?", (client_id,))
agency = get_settings_dict()

tab_list, tab_new = st.tabs(["Invoices", "➕ New invoice"])

# ---- New invoice --------------------------------------------------------
with tab_new:
    st.markdown("**Auto-populates a line item using the client's monthly fee.**")
    with st.form("new_invoice", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        period_start = c1.date_input(
            "Period start",
            value=date.today().replace(day=1),
            format="YYYY-MM-DD",
        )
        period_end = c2.date_input(
            "Period end", value=date.today(), format="YYYY-MM-DD"
        )
        status = c3.selectbox("Status", INVOICE_STATUSES, index=0)
        notes = st.text_area("Notes (optional)", height=80)

        st.markdown("**Line items**")
        default_desc = f"Credit repair service · {period_start} → {period_end}"
        default_fee = float(client["monthly_fee"] or 0)

        items: list[dict] = []
        for i in range(3):
            cc1, cc2, cc3 = st.columns([6, 1, 2])
            desc = cc1.text_input(
                f"Description {i + 1}",
                value=default_desc if i == 0 else "",
                label_visibility="collapsed",
                key=f"inv_desc_{i}",
            )
            qty = cc2.number_input(
                f"Qty {i + 1}",
                min_value=0.0, value=1.0 if i == 0 else 0.0, step=1.0,
                label_visibility="collapsed", key=f"inv_qty_{i}",
            )
            unit = cc3.number_input(
                f"Unit price {i + 1}",
                min_value=0.0,
                value=default_fee if i == 0 else 0.0,
                step=10.0, format="%.2f",
                label_visibility="collapsed", key=f"inv_unit_{i}",
            )
            if desc.strip() and qty > 0:
                items.append({
                    "description": desc.strip(),
                    "quantity": qty,
                    "unit_price": unit,
                    "amount": qty * unit,
                })

        if st.form_submit_button("Create invoice", type="primary"):
            if not items:
                st.error("Add at least one line item.")
            else:
                subtotal = sum(x["amount"] for x in items)
                next_num = fetch_one(
                    "SELECT COUNT(*) AS n FROM invoices"
                )["n"] + 1
                invoice_number = f"INV-{next_num:04d}"
                inv_id = execute(
                    """
                    INSERT INTO invoices (
                        client_id, invoice_number, period_start, period_end,
                        status, subtotal, total, notes, issued_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        client_id, invoice_number,
                        period_start.isoformat(), period_end.isoformat(),
                        status, subtotal, subtotal, notes.strip(),
                        date.today().isoformat() if status != "Draft" else None,
                    ),
                )
                for li in items:
                    execute(
                        """
                        INSERT INTO invoice_line_items (
                            invoice_id, description, quantity, unit_price, amount
                        ) VALUES (?,?,?,?,?)
                        """,
                        (
                            inv_id, li["description"], li["quantity"],
                            li["unit_price"], li["amount"],
                        ),
                    )
                log_activity(
                    "invoice.created",
                    f"{invoice_number} · ${subtotal:,.2f} · {status}",
                    client_id,
                )
                st.success(f"Created {invoice_number}.")

# ---- List invoices ------------------------------------------------------
with tab_list:
    invoices = fetch_all(
        "SELECT * FROM invoices WHERE client_id=? ORDER BY created_at DESC",
        (client_id,),
    )
    total_outstanding = sum(
        i["total"] for i in invoices if i["status"] in ("Draft", "Sent")
    )
    total_paid = sum(i["total"] for i in invoices if i["status"] == "Paid")
    c1, c2, c3 = st.columns(3)
    c1.metric("Invoices", len(invoices))
    c2.metric("Outstanding", f"${total_outstanding:,.2f}")
    c3.metric("Paid", f"${total_paid:,.2f}")

    if not invoices:
        st.info("No invoices yet for this client.")
    else:
        for inv in invoices:
            header = (
                f"{inv['invoice_number']} · ${inv['total']:,.2f} · "
                f"{inv['status']} · {inv['period_start']} → {inv['period_end']}"
            )
            with st.expander(header):
                line_items = fetch_all(
                    "SELECT * FROM invoice_line_items WHERE invoice_id=?",
                    (inv["id"],),
                )
                st.dataframe(
                    [dict(r) for r in line_items],
                    use_container_width=True, hide_index=True,
                )
                if inv["notes"]:
                    st.caption(f"Notes: {inv['notes']}")

                cols = st.columns(4)
                pdf = invoice_to_pdf_bytes(
                    dict(inv), dict(client),
                    [dict(li) for li in line_items], agency,
                )
                cols[0].download_button(
                    "📄 PDF",
                    data=pdf,
                    file_name=f"{inv['invoice_number']}.pdf",
                    mime="application/pdf",
                    key=f"pdf_{inv['id']}",
                )
                new_status = cols[1].selectbox(
                    "Status", INVOICE_STATUSES,
                    index=INVOICE_STATUSES.index(inv["status"])
                    if inv["status"] in INVOICE_STATUSES else 0,
                    key=f"stat_{inv['id']}",
                )
                if cols[2].button("Save status", key=f"save_{inv['id']}"):
                    paid_at = date.today().isoformat() if new_status == "Paid" else None
                    execute(
                        "UPDATE invoices SET status=?, paid_at=? WHERE id=?",
                        (new_status, paid_at, inv["id"]),
                    )
                    log_activity(
                        "invoice.status",
                        f"{inv['invoice_number']} → {new_status}",
                        client_id,
                    )
                    st.success("Updated.")
                    st.rerun()
                if cols[3].button("🗑 Delete", key=f"del_{inv['id']}"):
                    execute("DELETE FROM invoices WHERE id=?", (inv["id"],))
                    log_activity(
                        "invoice.deleted", inv["invoice_number"], client_id
                    )
                    st.rerun()

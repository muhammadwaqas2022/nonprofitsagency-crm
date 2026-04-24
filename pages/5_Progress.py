"""Progress page: initial vs current scores, score history chart, and
per-client dispute / item stats."""

from datetime import date

import pandas as pd
import streamlit as st

from db import bureaus_for, execute, fetch_all, fetch_one, init_db
from auth import logout_button, require_auth

st.set_page_config(page_title="Progress", page_icon="📈", layout="wide")
init_db()
require_auth()
logout_button()

st.title("Progress 📈")
st.caption("Track score changes and dispute outcomes per client.")

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

# ---- Score deltas --------------------------------------------------------
st.subheader("Score progress")

if client["client_type"] == "Personal":
    bureau_fields = [
        ("Equifax", client["initial_equifax"], client["current_equifax"]),
        ("Experian", client["initial_experian"], client["current_experian"]),
        ("TransUnion", client["initial_transunion"], client["current_transunion"]),
    ]
    current_columns = (
        "current_equifax", "current_experian", "current_transunion"
    )
else:
    bureau_fields = [
        ("Dun & Bradstreet", client["initial_dnb"], client["current_dnb"]),
        ("Experian Business", client["initial_experian_biz"],
         client["current_experian_biz"]),
        ("Equifax Business", client["initial_equifax_biz"],
         client["current_equifax_biz"]),
    ]
    current_columns = (
        "current_dnb", "current_experian_biz", "current_equifax_biz"
    )

cols = st.columns(len(bureau_fields))
for col, (name, initial, current) in zip(cols, bureau_fields):
    if initial is None and current is None:
        col.metric(name, "—", "no data")
        continue
    initial_display = initial if initial is not None else 0
    current_display = current if current is not None else initial_display
    delta = current_display - initial_display
    col.metric(name, current_display, delta)

# ---- Record new scores + log history ------------------------------------
with st.expander("📌 Record new score snapshot"):
    st.caption(
        "Updates current scores on the client record and appends a row to "
        "score history for charting."
    )
    with st.form("record_scores"):
        c1, c2, c3 = st.columns(3)
        new_vals = []
        for col, (name, _, current) in zip((c1, c2, c3), bureau_fields):
            new_vals.append(
                col.number_input(
                    name, 0, 999, int(current or 0), key=f"rec_{name}"
                )
            )
        snapshot_date = st.date_input(
            "Snapshot date", value=date.today(), format="YYYY-MM-DD"
        )
        if st.form_submit_button("Save snapshot", type="primary"):
            # Update clients table
            execute(
                f"UPDATE clients SET {current_columns[0]}=?, "
                f"{current_columns[1]}=?, {current_columns[2]}=? WHERE id=?",
                (
                    new_vals[0] or None, new_vals[1] or None,
                    new_vals[2] or None, client_id,
                ),
            )
            # Log to history
            for (name, _, _), val in zip(bureau_fields, new_vals):
                if val:
                    execute(
                        "INSERT INTO score_history (client_id, recorded_at, "
                        "bureau, score) VALUES (?,?,?,?)",
                        (client_id, snapshot_date.isoformat(), name, val),
                    )
            st.success("Snapshot saved.")
            st.rerun()

# ---- Score history chart -------------------------------------------------
history_rows = fetch_all(
    "SELECT recorded_at, bureau, score FROM score_history WHERE client_id=? "
    "ORDER BY recorded_at ASC",
    (client_id,),
)
if history_rows:
    hist = pd.DataFrame(
        [
            {
                "Date": r["recorded_at"][:10],
                "Bureau": r["bureau"],
                "Score": r["score"],
            }
            for r in history_rows
        ]
    )
    pivot = hist.pivot_table(
        index="Date", columns="Bureau", values="Score", aggfunc="last"
    ).sort_index()
    st.markdown("**Score history**")
    st.line_chart(pivot)
else:
    st.caption("No score history yet — record a snapshot above to begin tracking.")

st.divider()

# ---- Item stats ----------------------------------------------------------
st.subheader("Credit item outcomes")
items = fetch_all(
    "SELECT status, COUNT(*) AS n FROM credit_items WHERE client_id=? GROUP BY status",
    (client_id,),
)
total_items = fetch_one(
    "SELECT COUNT(*) AS n FROM credit_items WHERE client_id=?", (client_id,)
)["n"]
removed = fetch_one(
    "SELECT COUNT(*) AS n FROM credit_items WHERE client_id=? AND status='Removed'",
    (client_id,),
)["n"]

c1, c2, c3 = st.columns(3)
c1.metric("Total items", total_items)
c2.metric("Items removed", removed)
c3.metric(
    "Removal rate",
    f"{(removed / total_items * 100):.0f}%" if total_items else "—",
)

if items:
    st.dataframe(
        [dict(r) for r in items], use_container_width=True, hide_index=True
    )

# ---- Dispute stats -------------------------------------------------------
st.subheader("Dispute pipeline")
disputes = fetch_all(
    "SELECT status, COUNT(*) AS n FROM disputes WHERE client_id=? GROUP BY status",
    (client_id,),
)
if disputes:
    st.dataframe(
        [dict(r) for r in disputes], use_container_width=True, hide_index=True
    )
else:
    st.caption("No disputes yet.")

outcomes = fetch_all(
    """
    SELECT outcome, COUNT(*) AS n FROM disputes
    WHERE client_id=? AND outcome IS NOT NULL AND outcome != ''
    GROUP BY outcome
    """,
    (client_id,),
)
if outcomes:
    st.markdown("**Outcomes**")
    st.dataframe(
        [dict(r) for r in outcomes], use_container_width=True, hide_index=True
    )

# ---- Client summary export ----------------------------------------------
st.divider()
st.subheader("Client summary report")

summary_lines = [
    "Client Progress Summary",
    "=" * 50,
    f"Name:            {client['name']}",
    f"Type:            {client['client_type']}",
    f"Status:          {client['status']}",
    f"Generated:       {date.today().strftime('%B %d, %Y')}",
    "",
    "Credit Scores",
    "-" * 50,
]
for name, initial, current in bureau_fields:
    initial = initial or 0
    current = current if current is not None else initial
    summary_lines.append(
        f"  {name:<22} Initial: {initial:>4}   "
        f"Current: {current:>4}   Δ: {current - initial:+d}"
    )

summary_lines.extend(
    [
        "",
        "Credit Items",
        "-" * 50,
        f"  Total:          {total_items}",
        f"  Removed:        {removed}",
        f"  Removal rate:   "
        f"{(removed / total_items * 100):.0f}%" if total_items else "  Removal rate:   —",
        "",
        "Dispute Pipeline",
        "-" * 50,
    ]
)
for row in disputes:
    summary_lines.append(f"  {row['status']:<22} {row['n']}")
if outcomes:
    summary_lines.append("")
    summary_lines.append("Outcomes")
    for row in outcomes:
        summary_lines.append(f"  {row['outcome']:<22} {row['n']}")

summary_text = "\n".join(summary_lines)

st.code(summary_text, language="text")
st.download_button(
    "⬇️ Download summary (.txt)",
    data=summary_text,
    file_name=f"{client['name'].replace(' ', '_')}_summary.txt",
    mime="text/plain",
)

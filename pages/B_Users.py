"""Users page: manage staff accounts (admin only, or bootstrap first admin)."""

import streamlit as st

from auth import (
    ROLES,
    active_admin_count,
    current_user,
    list_users,
    logout_button,
    render_add_user_form,
    render_bootstrap_form,
    require_auth,
    set_password,
    users_exist,
)
from db import execute, init_db, log_activity

st.set_page_config(page_title="Users", page_icon="🧑‍💼", layout="wide")
init_db()

st.title("Users 🧑‍💼")

# If no users exist, anyone can bootstrap the first admin. After that,
# auth is required.
if not users_exist():
    st.caption("Set up your first admin account to enable sign-in.")
    render_bootstrap_form()
    st.stop()

require_auth()
logout_button()

me = current_user()
if me["role"] != "admin":
    st.error("🔒 Admin access required to manage users.")
    st.caption(
        f"You're signed in as **{me['username']}** ({me['role']}). Ask an "
        "admin to promote you, or use **Settings → Security** to change your "
        "own password."
    )
    st.stop()

st.caption("Add, deactivate, promote, or reset passwords for staff accounts.")

render_add_user_form()
st.divider()

st.subheader("All users")
users = list_users()
for u in users:
    is_me = u["id"] == me["id"]
    active_badge = "🟢" if u["active"] else "⚪"
    role_badge = {"admin": "👑", "agent": "🧑‍💻"}.get(u["role"], "•")
    header = (
        f"{active_badge} {role_badge} {u['username']}"
        + (f" · {u['full_name']}" if u["full_name"] else "")
        + (" · you" if is_me else "")
        + (f" · last login {u['last_login']}" if u["last_login"] else "")
    )
    with st.expander(header):
        st.write(f"**Email:** {u['email'] or '—'}")
        st.write(f"**Created:** {u['created_at']}")
        st.write(f"**Status:** {'Active' if u['active'] else 'Deactivated'}")

        # --- Change role ---
        with st.form(f"role_{u['id']}"):
            new_role = st.selectbox(
                "Role", ROLES,
                index=ROLES.index(u["role"]) if u["role"] in ROLES else 1,
                key=f"rolesel_{u['id']}",
            )
            if st.form_submit_button("Save role"):
                if (
                    u["role"] == "admin"
                    and new_role != "admin"
                    and active_admin_count() <= 1
                ):
                    st.error(
                        "Can't demote the last active admin. Promote another "
                        "user first."
                    )
                else:
                    execute(
                        "UPDATE users SET role=? WHERE id=?",
                        (new_role, u["id"]),
                    )
                    log_activity(
                        "user.role_changed",
                        f"{u['username']} → {new_role}",
                    )
                    st.success("Role updated.")
                    st.rerun()

        # --- Activate / deactivate ---
        st.markdown("---")
        if u["active"]:
            if st.button("⏸ Deactivate", key=f"deact_{u['id']}"):
                if is_me:
                    st.error("You can't deactivate yourself.")
                elif (
                    u["role"] == "admin" and active_admin_count() <= 1
                ):
                    st.error("Can't deactivate the last active admin.")
                else:
                    execute(
                        "UPDATE users SET active=0 WHERE id=?", (u["id"],)
                    )
                    log_activity(
                        "user.deactivated", f"{u['username']}"
                    )
                    st.warning(f"Deactivated {u['username']}.")
                    st.rerun()
        else:
            if st.button("▶️ Reactivate", key=f"react_{u['id']}"):
                execute("UPDATE users SET active=1 WHERE id=?", (u["id"],))
                log_activity("user.reactivated", f"{u['username']}")
                st.success(f"Reactivated {u['username']}.")
                st.rerun()

        # --- Reset password ---
        st.markdown("---")
        with st.form(f"pw_{u['id']}"):
            st.caption(f"Reset {u['username']}'s password.")
            col1, col2 = st.columns(2)
            new_pw = col1.text_input(
                "New password", type="password", key=f"newpw_{u['id']}"
            )
            confirm = col2.text_input(
                "Confirm", type="password", key=f"confpw_{u['id']}"
            )
            if st.form_submit_button("Reset password"):
                if len(new_pw) < 8:
                    st.error("Password must be at least 8 characters.")
                elif new_pw != confirm:
                    st.error("Passwords do not match.")
                else:
                    set_password(u["id"], new_pw)
                    log_activity(
                        "user.password_reset",
                        f"admin reset password for {u['username']}",
                    )
                    st.success(f"Password reset for {u['username']}.")

        # --- Delete (hard delete, not just deactivate) ---
        st.markdown("---")
        if not is_me and st.button("🗑 Delete user", key=f"del_{u['id']}"):
            if u["role"] == "admin" and active_admin_count() <= 1 and u["active"]:
                st.error("Can't delete the last active admin.")
            else:
                execute("DELETE FROM users WHERE id=?", (u["id"],))
                log_activity("user.deleted", f"{u['username']}")
                st.warning(f"Deleted user {u['username']}.")
                st.rerun()

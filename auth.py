"""Authentication for the Credit Repair Cloud.

Soft-gated: if the `users` table is empty, the app runs open (preserving
the demo flow). The moment you create the first user, every page
requires sign-in. Use the Settings page or Users page to bootstrap.

Passwords are hashed with PBKDF2-HMAC-SHA256 (200,000 iterations, per-user
salt) — no external dependencies.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any

import streamlit as st

from db import execute, fetch_all, fetch_one, log_activity

ITERATIONS = 200_000
ROLES = ["admin", "agent"]


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        ITERATIONS,
    ).hex()
    return digest, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    calc, _ = hash_password(password, salt)
    return secrets.compare_digest(calc, stored_hash)


def create_user(
    username: str,
    password: str,
    role: str = "agent",
    full_name: str = "",
    email: str = "",
) -> int:
    ph, salt = hash_password(password)
    return execute(
        """
        INSERT INTO users (
            username, password_hash, password_salt, role, full_name, email
        ) VALUES (?,?,?,?,?,?)
        """,
        (
            username.strip().lower(), ph, salt, role,
            full_name.strip(), email.strip(),
        ),
    )


def set_password(user_id: int, new_password: str) -> None:
    ph, salt = hash_password(new_password)
    execute(
        "UPDATE users SET password_hash=?, password_salt=? WHERE id=?",
        (ph, salt, user_id),
    )


def users_exist() -> bool:
    return fetch_one("SELECT COUNT(*) AS n FROM users")["n"] > 0


def active_admin_count() -> int:
    return fetch_one(
        "SELECT COUNT(*) AS n FROM users WHERE role='admin' AND active=1"
    )["n"]


def current_user() -> dict[str, Any] | None:
    return st.session_state.get("auth_user")


# --------------------------------------------------------------------------
# Page-level guards
# --------------------------------------------------------------------------

def require_auth() -> None:
    """Render login/bootstrap if needed and stop the page; no-op if open."""
    if not users_exist():
        _render_sidebar_notice()
        return

    user = current_user()
    if user:
        # Re-validate against DB — handles deactivation mid-session.
        fresh = fetch_one(
            "SELECT * FROM users WHERE id=? AND active=1", (user["id"],)
        )
        if fresh:
            st.session_state["auth_user"] = dict(fresh)
            return
        st.session_state.pop("auth_user", None)

    _render_login()
    st.stop()


def require_admin() -> None:
    require_auth()
    user = current_user()
    if not user or user["role"] != "admin":
        st.error("🔒 Admin access required.")
        st.stop()


# --------------------------------------------------------------------------
# Sidebar UI
# --------------------------------------------------------------------------

def logout_button() -> None:
    user = current_user()
    if not user:
        return
    with st.sidebar:
        st.divider()
        st.caption(
            f"👤 **{user['full_name'] or user['username']}** · "
            f"`{user['role']}`"
        )
        if st.button("Sign out", use_container_width=True, key="_auth_logout"):
            log_activity("user.logout", f"{user['username']} signed out")
            st.session_state.pop("auth_user", None)
            st.rerun()


def _render_sidebar_notice() -> None:
    with st.sidebar:
        st.caption(
            "🔓 Auth is off. Create the first admin on the **Users** or "
            "**Settings → Security** page to enable sign-in."
        )


# --------------------------------------------------------------------------
# Login form
# --------------------------------------------------------------------------

def _render_login() -> None:
    st.title("🔐 Sign in")
    st.caption("Enter your credentials to access Credit Repair Cloud.")
    with st.form("_auth_login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            user = fetch_one(
                "SELECT * FROM users WHERE username=? AND active=1",
                (username.strip().lower(),),
            )
            if user and verify_password(
                password, user["password_hash"], user["password_salt"]
            ):
                st.session_state["auth_user"] = dict(user)
                execute(
                    "UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?",
                    (user["id"],),
                )
                log_activity("user.login", f"{user['username']} signed in")
                st.rerun()
            else:
                st.error("Invalid credentials or account deactivated.")


# --------------------------------------------------------------------------
# Bootstrap + management UI used by Users and Settings pages
# --------------------------------------------------------------------------

def render_bootstrap_form() -> None:
    """Shown when no users exist — create the first admin."""
    st.markdown("### 🌱 Create the first admin account")
    st.caption(
        "Once you create this account, sign-in becomes required on every "
        "page. You can add more staff users afterwards."
    )
    with st.form("_auth_bootstrap"):
        username = st.text_input("Username")
        full_name = st.text_input("Full name")
        email = st.text_input("Email")
        col1, col2 = st.columns(2)
        password = col1.text_input("Password (min 8 chars)", type="password")
        confirm = col2.text_input("Confirm password", type="password")
        if st.form_submit_button("Create admin", type="primary"):
            _validate_and_create(
                username, password, confirm, "admin", full_name, email
            )


def render_add_user_form() -> None:
    """Admin-only: add additional users."""
    st.markdown("### ➕ Add user")
    with st.form("_auth_add_user", clear_on_submit=True):
        username = st.text_input("Username")
        full_name = st.text_input("Full name")
        email = st.text_input("Email")
        role = st.selectbox("Role", ROLES, index=1)
        col1, col2 = st.columns(2)
        password = col1.text_input("Password", type="password")
        confirm = col2.text_input("Confirm password", type="password")
        if st.form_submit_button("Create user", type="primary"):
            _validate_and_create(
                username, password, confirm, role, full_name, email
            )


def render_change_own_password() -> None:
    user = current_user()
    if not user:
        return
    st.markdown("### 🔑 Change your password")
    with st.form("_auth_change_pw", clear_on_submit=True):
        current = st.text_input("Current password", type="password")
        col1, col2 = st.columns(2)
        new = col1.text_input("New password", type="password")
        confirm = col2.text_input("Confirm new password", type="password")
        if st.form_submit_button("Change password", type="primary"):
            fresh = fetch_one("SELECT * FROM users WHERE id=?", (user["id"],))
            if not fresh or not verify_password(
                current, fresh["password_hash"], fresh["password_salt"]
            ):
                st.error("Current password is incorrect.")
            elif len(new) < 8:
                st.error("New password must be at least 8 characters.")
            elif new != confirm:
                st.error("Passwords do not match.")
            else:
                set_password(user["id"], new)
                log_activity(
                    "user.password_changed",
                    f"{user['username']} changed own password",
                )
                st.success("Password changed.")


def _validate_and_create(
    username: str,
    password: str,
    confirm: str,
    role: str,
    full_name: str,
    email: str,
) -> None:
    if not username.strip():
        st.error("Username is required.")
        return
    if len(password) < 8:
        st.error("Password must be at least 8 characters.")
        return
    if password != confirm:
        st.error("Passwords do not match.")
        return
    existing = fetch_one(
        "SELECT id FROM users WHERE username=?", (username.strip().lower(),)
    )
    if existing:
        st.error("That username already exists.")
        return
    uid = create_user(username, password, role, full_name, email)
    log_activity("user.created", f"{role}: {username.strip().lower()}")
    st.success(f"Created {role} '{username.strip().lower()}'. Please sign in.")
    st.rerun()


def list_users() -> list:
    return fetch_all(
        "SELECT id, username, role, full_name, email, active, last_login, "
        "created_at FROM users ORDER BY created_at ASC"
    )

"""Lightweight CSRF + duplicate-submit helpers (no Flask-WTF required)."""
import secrets
from functools import wraps
from flask import session, request, abort, flash, redirect, url_for


def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def validate_csrf():
    token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not token or token != session.get("_csrf_token"):
        return False
    return True


def csrf_protect(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "POST":
            if not validate_csrf():
                flash("Invalid security token. Please try again.", "danger")
                return redirect(request.referrer or url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated


def inject_csrf():
    return {"csrf_token": generate_csrf_token}

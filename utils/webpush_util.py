"""Web Push (browser / phone notification tray)."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

_keys_cache = None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _instance_path() -> Path:
    try:
        from flask import current_app
        return Path(current_app.instance_path)
    except Exception:
        return Path("instance")


def ensure_vapid_keys():
    """Return (public_key_urlsafe, private_key_urlsafe_or_pem)."""
    global _keys_cache
    if _keys_cache:
        return _keys_cache

    pub = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    priv = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    if pub and priv:
        _keys_cache = (pub, priv)
        return _keys_cache

    path = _instance_path() / "vapid.json"
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("publicKey") and data.get("privateKey"):
                _keys_cache = (data["publicKey"], data["privateKey"])
                return _keys_cache
    except Exception as e:
        print("vapid read:", e)

    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.backends import default_backend

        key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        priv_num = key.private_numbers().private_value
        priv = _b64url(priv_num.to_bytes(32, "big"))
        pub_nums = key.public_key().public_numbers()
        pub_bytes = b"\x04" + pub_nums.x.to_bytes(32, "big") + pub_nums.y.to_bytes(32, "big")
        pub = _b64url(pub_bytes)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"publicKey": pub, "privateKey": priv}), encoding="utf-8")
        _keys_cache = (pub, priv)
        return _keys_cache
    except Exception as e:
        print("ensure_vapid_keys:", e)
        return None, None


def get_vapid_public_key() -> str:
    pub, _ = ensure_vapid_keys()
    return pub or ""


def send_web_push_to_user(user_id: int, title: str, body: str, url: str = "/profile/notifications") -> int:
    try:
        from pywebpush import webpush
    except ImportError:
        print("pywebpush not installed — pip install pywebpush")
        return 0

    pub, priv = ensure_vapid_keys()
    if not pub or not priv:
        return 0

    try:
        from models.push_subscription import PushSubscription
        from extensions import db
    except Exception as e:
        print("push import:", e)
        return 0

    subs = PushSubscription.query.filter_by(user_id=user_id).all()
    if not subs:
        return 0

    payload = json.dumps({
        "title": title or "Taskmill",
        "body": (body or "")[:180],
        "url": url or "/profile/notifications",
        "icon": "/static/img/taskmill-logo.png",
        "badge": "/static/img/taskmill-logo.png",
    })
    claims = {"sub": os.environ.get("VAPID_CLAIM_EMAIL", "mailto:support@taskmill.local")}
    sent = 0
    dead = []
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=priv,
                vapid_claims=claims,
                vapid_public_key=pub,
            )
            sent += 1
        except Exception as e:
            err = str(e)
            print("webpush:", err)
            if any(x in err for x in ("410", "404", "Gone", "not found", "unsubscribed")):
                dead.append(sub)
    for sub in dead:
        try:
            db.session.delete(sub)
        except Exception:
            pass
    if dead:
        try:
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
    return sent

"""Notify admin(s) on Telegram for deposits, withdrawals, and chat messages."""
from __future__ import annotations


def _bot_token():
    try:
        from models.settings import Settings
        s = Settings.query.first()
        return (getattr(s, "telegram_bot_token", None) or "").strip() or None
    except Exception:
        return None


def _admin_chat_ids():
    """Comma-separated admin_telegram_chat_ids in Settings, or env ADMIN_TELEGRAM_CHAT_IDS."""
    ids = []
    try:
        from models.settings import Settings
        s = Settings.query.first()
        raw = getattr(s, "admin_telegram_chat_ids", None) if s else None
        if raw:
            for part in str(raw).replace(";", ",").split(","):
                p = part.strip()
                if p:
                    ids.append(p)
    except Exception:
        pass
    if not ids:
        import os
        raw = (os.environ.get("ADMIN_TELEGRAM_CHAT_IDS") or "").strip()
        for part in raw.replace(";", ",").split(","):
            p = part.strip()
            if p:
                ids.append(p)
    return ids


def notify_admin(title: str, body: str):
    token = _bot_token()
    chats = _admin_chat_ids()
    if not token or not chats:
        return False
    text = f"🛡 Taskmill Admin\n\n{title}\n\n{body}".strip()[:4000]
    import urllib.request
    import urllib.parse
    ok = False
    for chat in chats:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": str(chat).strip(),
                "text": text,
                "disable_web_page_preview": "true",
            }).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=8):
                ok = True
        except Exception as e:
            print("admin telegram:", chat, e)
    return ok


def alert_deposit(user, deposit):
    try:
        uname = getattr(user, "username", None) or f"user#{getattr(user, 'id', '?')}"
        amt = float(getattr(deposit, "amount", 0) or 0)
        method = getattr(deposit, "payment_method", None) or getattr(deposit, "provider", "") or "—"
        notify_admin(
            "New deposit request",
            f"User: {uname}\nAmount: {amt:,.0f}\nMethod: {method}\nStatus: Pending\nOpen admin → Deposits",
        )
    except Exception as e:
        print("alert_deposit:", e)


def alert_withdraw(user, withdrawal):
    try:
        uname = getattr(user, "username", None) or f"user#{getattr(user, 'id', '?')}"
        amt = float(getattr(withdrawal, "amount", 0) or 0)
        notify_admin(
            "New withdrawal request",
            f"User: {uname}\nAmount: {amt:,.0f}\nStatus: Pending\nOpen admin → Withdrawals",
        )
    except Exception as e:
        print("alert_withdraw:", e)


def alert_chat(user, message_preview: str):
    try:
        uname = getattr(user, "username", None) or f"user#{getattr(user, 'id', '?')}"
        preview = (message_preview or "")[:200]
        notify_admin(
            "New support message",
            f"User: {uname}\nMessage: {preview}\nOpen admin → Chat",
        )
    except Exception as e:
        print("alert_chat:", e)

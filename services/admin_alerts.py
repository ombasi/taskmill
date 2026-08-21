"""Notify admin(s) on Telegram for Live Ops: deposit, withdraw, chat."""
from __future__ import annotations


def _bot_token():
    try:
        from models.settings import Settings
        s = Settings.query.first()
        tok = (getattr(s, "telegram_bot_token", None) or "").strip()
        if tok:
            return tok
    except Exception as e:
        print("admin_alerts token settings:", e)
    import os
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip() or None


def _admin_chat_ids():
    ids = []
    seen = set()

    def add(raw):
        if not raw:
            return
        for part in str(raw).replace(";", ",").split(","):
            p = part.strip()
            if p and p not in seen:
                seen.add(p)
                ids.append(p)

    try:
        from models.settings import Settings
        s = Settings.query.first()
        if s:
            add(getattr(s, "admin_telegram_chat_ids", None))
    except Exception as e:
        print("admin_alerts settings ids:", e)

    try:
        import os
        add(os.environ.get("ADMIN_TELEGRAM_CHAT_IDS"))
    except Exception:
        pass

    try:
        from models.user import User
        q = User.query.filter(
            (User.is_admin.is_(True)) | (User.is_agent.is_(True))
        )
        for u in q.limit(50).all():
            add(getattr(u, "telegram_chat_id", None))
    except Exception as e:
        print("admin_alerts user ids:", e)

    return ids


def notify_admin(title: str, body: str):
    token = _bot_token()
    chats = _admin_chat_ids()
    if not token:
        print("admin telegram: NO BOT TOKEN")
        return False
    if not chats:
        print("admin telegram: NO CHAT IDS")
        return False

    text = f"Taskmill Live Ops\n\n{title}\n\n{body}".strip()[:4000]
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
            with urllib.request.urlopen(req, timeout=12) as resp:
                resp.read()
            ok = True
            print(f"admin telegram: sent to {chat}")
        except Exception as e:
            print(f"admin telegram FAIL chat={chat}:", e)
    return ok


def alert_deposit(user, deposit):
    try:
        uname = getattr(user, "username", None) or f"user#{getattr(user, 'id', '?')}"
        amt = float(getattr(deposit, "amount", 0) or 0)
        method = (
            getattr(deposit, "payment_method", None)
            or getattr(deposit, "provider", None)
            or "—"
        )
        tid = getattr(deposit, "transaction_id", None) or "—"
        cur = getattr(deposit, "currency", None) or getattr(user, "currency", None) or "UGX"
        dep_id = getattr(deposit, "id", None) or "?"
        notify_admin(
            "New DEPOSIT request",
            f"User: {uname}\nAmount: {amt:,.2f} {cur}\nMethod: {method}\nTx: {tid}\nDeposit ID: {dep_id}\nStatus: Pending\n→ Admin · Deposits",
        )
    except Exception as e:
        print("alert_deposit:", e)


def alert_withdraw(user, withdrawal):
    try:
        uname = getattr(user, "username", None) or f"user#{getattr(user, 'id', '?')}"
        amt = float(getattr(withdrawal, "amount", 0) or 0)
        wid = getattr(withdrawal, "id", None) or "?"
        cur = getattr(user, "currency", None) or "UGX"
        notify_admin(
            "New WITHDRAWAL request",
            f"User: {uname}\nAmount: {amt:,.2f} {cur}\nWithdraw ID: {wid}\nStatus: Pending\n→ Admin · Withdrawals",
        )
    except Exception as e:
        print("alert_withdraw:", e)


def alert_chat(user, message_preview: str):
    try:
        uname = getattr(user, "username", None) or f"user#{getattr(user, 'id', '?')}"
        preview = (message_preview or "")[:280]
        notify_admin(
            "New support CHAT",
            f"User: {uname}\nMessage: {preview}\n→ Admin · Chat",
        )
    except Exception as e:
        print("alert_chat:", e)

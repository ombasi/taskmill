
"""XP, levels, check-in, quality score, outbound alerts."""
from __future__ import annotations
from datetime import date, datetime, timedelta
from extensions import db


def xp_for_level(level: int) -> int:
    """XP required to reach next level from this level."""
    level = max(1, int(level or 1))
    return int(100 * level * 1.35)


def level_from_xp(xp: int) -> int:
    xp = int(xp or 0)
    level = 1
    while xp >= xp_for_level(level):
        xp -= xp_for_level(level)
        level += 1
        if level > 99:
            break
    return level


def progress_in_level(user) -> dict:
    xp = int(getattr(user, "xp_points", 0) or 0)
    level = int(getattr(user, "user_level", 1) or 1)
    # recompute level from total xp for consistency
    remaining = xp
    lvl = 1
    while remaining >= xp_for_level(lvl) and lvl < 99:
        remaining -= xp_for_level(lvl)
        lvl += 1
    need = xp_for_level(lvl)
    pct = min(100, int(100 * remaining / max(1, need)))
    return {
        "level": lvl,
        "xp_total": xp,
        "xp_in_level": remaining,
        "xp_need": need,
        "percent": pct,
    }


def add_xp(user, amount: int, reason: str = "") -> int:
    amount = int(amount or 0)
    if amount <= 0 or not user:
        return 0
    user.xp_points = int(getattr(user, "xp_points", 0) or 0) + amount
    prog = progress_in_level(user)
    user.user_level = prog["level"]
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return amount


def quality_multiplier(user) -> float:
    """0.95 .. 1.08 based on quality_score (50 = 1.0)."""
    q = float(getattr(user, "quality_score", 50) or 50)
    q = max(0.0, min(100.0, q))
    # 0 → 0.95, 50 → 1.0, 100 → 1.08
    return 0.95 + (q / 100.0) * 0.13


def bump_quality(user, delta: float):
    q = float(getattr(user, "quality_score", 50) or 50) + float(delta)
    user.quality_score = max(0.0, min(100.0, q))


def do_checkin(user) -> tuple[bool, str, dict]:
    from models.engagement import CheckIn
    today = date.today()
    exists = CheckIn.query.filter_by(user_id=user.id, day=today).first()
    if exists:
        return False, "Already checked in today.", {}

    last = getattr(user, "last_checkin", None)
    if last == today - timedelta(days=1):
        user.checkin_streak = int(getattr(user, "checkin_streak", 0) or 0) + 1
    else:
        user.checkin_streak = 1
    user.last_checkin = today

    streak = int(user.checkin_streak or 1)
    reward_xp = 15 + min(50, streak * 2)
    # small cash every 7 days (UGX base)
    reward_cash = 500.0 if streak % 7 == 0 else 0.0

    row = CheckIn(user_id=user.id, day=today, reward_xp=reward_xp, reward_cash=reward_cash)
    db.session.add(row)
    add_xp(user, reward_xp, "checkin")

    if reward_cash > 0:
        before = float(user.available_balance or 0)
        user.available_balance = before + reward_cash
        try:
            from models.wallet_transaction import WalletTransaction
            db.session.add(WalletTransaction(
                user_id=user.id,
                amount=reward_cash,
                transaction_type="checkin_bonus",
                description=f"Check-in streak day {streak} bonus",
                balance_before=before,
                balance_after=float(user.available_balance),
            ))
        except Exception:
            pass

    db.session.commit()
    return True, "Check-in recorded!", {"xp": reward_xp, "cash": reward_cash, "streak": streak}


def month_calendar(user, year: int = None, month: int = None) -> list:
    from models.engagement import CheckIn
    import calendar
    today = date.today()
    year = year or today.year
    month = month or today.month
    days_in = calendar.monthrange(year, month)[1]
    rows = CheckIn.query.filter(
        CheckIn.user_id == user.id,
        CheckIn.day >= date(year, month, 1),
        CheckIn.day <= date(year, month, days_in),
    ).all()
    done = {r.day.day for r in rows}
    return [{"day": d, "checked": d in done, "is_today": (year, month, d) == (today.year, today.month, today.day)} for d in range(1, days_in + 1)]


def send_outbound_alert(user, title: str, body: str):
    """Push money/ops alerts via Telegram and optional SMTP email."""
    title = (title or "Taskmill").strip()
    body = (body or "").strip()
    text = f"{title}\n\n{body}".strip()

    # In-app already handled by callers via NotificationService; this is outbound only.
    # --- Telegram ---
    try:
        from models.settings import Settings
        s = Settings.query.first()
        token = getattr(s, "telegram_bot_token", None) if s else None
        chat = getattr(user, "telegram_chat_id", None)
        if token and chat:
            import urllib.request, urllib.parse, json
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": str(chat).strip(),
                "text": text[:4000],
                "disable_web_page_preview": "true",
            }).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=8):
                pass
    except Exception as e:
        print("telegram alert:", e)

    # --- Email (optional: set MAIL_SERVER / MAIL_USERNAME / MAIL_PASSWORD / MAIL_FROM) ---
    try:
        import os, smtplib
        from email.mime.text import MIMEText
        host = os.environ.get("MAIL_SERVER") or os.environ.get("SMTP_HOST")
        to_addr = (getattr(user, "email", None) or "").strip()
        if host and to_addr and "@" in to_addr:
            port = int(os.environ.get("MAIL_PORT") or os.environ.get("SMTP_PORT") or 587)
            user_n = os.environ.get("MAIL_USERNAME") or os.environ.get("SMTP_USER") or ""
            pwd = os.environ.get("MAIL_PASSWORD") or os.environ.get("SMTP_PASSWORD") or ""
            from_addr = os.environ.get("MAIL_FROM") or user_n or "noreply@taskmill.app"
            msg = MIMEText(body or title, "plain", "utf-8")
            msg["Subject"] = f"Taskmill · {title}"
            msg["From"] = from_addr
            msg["To"] = to_addr
            use_tls = (os.environ.get("MAIL_USE_TLS", "1") not in ("0", "false", "False"))
            with smtplib.SMTP(host, port, timeout=12) as smtp:
                if use_tls:
                    smtp.starttls()
                if user_n and pwd:
                    smtp.login(user_n, pwd)
                smtp.sendmail(from_addr, [to_addr], msg.as_string())
    except Exception as e:
        print("email alert:", e)



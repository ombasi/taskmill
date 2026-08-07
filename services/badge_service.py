
"""Award collectible badges."""
from extensions import db

DEFAULTS = [
    ("first_deposit", "First deposit", "Completed your first deposit", "fa-piggy-bank"),
    ("first_task", "First task", "Submitted your first product review", "fa-check"),
    ("streak_3", "3-day streak", "Active 3 days in a row", "fa-fire"),
    ("first_referral", "Recruiter", "Referred your first member", "fa-user-plus"),
    ("combo_cleared", "Combo closer", "Cleared a combo negative", "fa-bolt"),
    ("full_day", "Full day", "Completed all daily tasks", "fa-trophy"),
]

def ensure_badges():
    from models.badge import Badge
    for code, name, desc, icon in DEFAULTS:
        if not Badge.query.filter_by(code=code).first():
            db.session.add(Badge(code=code, name=name, description=desc, icon=icon))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

def award(user_id, code):
    from models.badge import Badge, UserBadge
    ensure_badges()
    badge = Badge.query.filter_by(code=code).first()
    if not badge:
        return False
    exists = UserBadge.query.filter_by(user_id=user_id, badge_id=badge.id).first()
    if exists:
        return False
    db.session.add(UserBadge(user_id=user_id, badge_id=badge.id))
    try:
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False

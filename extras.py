"""User extras: goal jar, salary mode, skip token, theme, contract, lounge, lucky hour."""
from datetime import datetime, date, time, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from extensions import db
from utils.security import csrf_protect

extras_bp = Blueprint("extras", __name__)


def _ensure_user_extra_cols():
    try:
        from sqlalchemy import text, inspect
        dialect = db.engine.dialect.name
        insp = inspect(db.engine)
        if "users" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("users")}
        specs = [
            ("goal_title", "VARCHAR(120)"),
            ("goal_target", "FLOAT DEFAULT 0"),
            ("salary_day", "INTEGER"),  # 0=Mon .. 6=Sun preferred
            ("salary_mode", "BOOLEAN DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN DEFAULT 0"),
            ("skip_tokens", "INTEGER DEFAULT 0"),
            ("theme_pref", "VARCHAR(20)"),
            ("contract_accepted_at", "TIMESTAMP" if dialect == "postgresql" else "DATETIME"),
            ("streak_insurance_month", "VARCHAR(7)"),
            ("streak_insurance_used", "BOOLEAN DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN DEFAULT 0"),
            ("last_balance_interest_at", "TIMESTAMP" if dialect == "postgresql" else "DATETIME"),
        ]
        for name, typ in specs:
            if name in cols:
                continue
            try:
                if dialect == "postgresql":
                    db.session.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {name} {typ}"))
                else:
                    db.session.execute(text(f"ALTER TABLE users ADD COLUMN {name} {typ}"))
                db.session.commit()
            except Exception:
                db.session.rollback()
        # tables
        try:
            from models.extra_features import GoalJar, TeamShoutout, BrandMission
            GoalJar.__table__.create(db.engine, checkfirst=True)
            TeamShoutout.__table__.create(db.engine, checkfirst=True)
            BrandMission.__table__.create(db.engine, checkfirst=True)
        except Exception as e:
            print("extra tables:", e)
        # settings lucky hour
        try:
            if "settings" in insp.get_table_names():
                scols = {c["name"] for c in insp.get_columns("settings")}
                for name, typ in [
                    ("lucky_hour_start", "INTEGER"),
                    ("lucky_hour_boost", "FLOAT DEFAULT 0"),
                    ("ops_ticker_enabled", "BOOLEAN DEFAULT TRUE" if dialect == "postgresql" else "BOOLEAN DEFAULT 1"),
                ]:
                    if name not in scols:
                        try:
                            if dialect == "postgresql":
                                db.session.execute(text(f"ALTER TABLE settings ADD COLUMN IF NOT EXISTS {name} {typ}"))
                            else:
                                db.session.execute(text(f"ALTER TABLE settings ADD COLUMN {name} {typ}"))
                            db.session.commit()
                        except Exception:
                            db.session.rollback()
        except Exception:
            pass
    except Exception as e:
        print("ensure user extras:", e)


@extras_bp.record_once
def _on_load(state):
    pass


@extras_bp.route("/goal", methods=["POST"])
@login_required
@csrf_protect
def set_goal():
    title = (request.form.get("goal_title") or "My goal").strip()[:120]
    try:
        target = float(request.form.get("goal_target") or 0)
    except ValueError:
        target = 0
    current_user.goal_title = title
    current_user.goal_target = max(0, target)
    db.session.commit()
    flash("Goal jar updated.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))


@extras_bp.route("/salary-mode", methods=["POST"])
@login_required
@csrf_protect
def salary_mode():
    current_user.salary_mode = request.form.get("salary_mode") == "1"
    try:
        current_user.salary_day = int(request.form.get("salary_day") or 4)  # default Friday
    except ValueError:
        current_user.salary_day = 4
    db.session.commit()
    flash("Salary mode saved.", "success")
    return redirect(url_for("profile.index"))


@extras_bp.route("/theme", methods=["POST"])
@login_required
@csrf_protect
def set_theme():
    theme = (request.form.get("theme") or "diamond").strip()[:20]
    if theme not in ("diamond", "dark", "midnight"):
        theme = "diamond"
    current_user.theme_pref = theme
    session["theme"] = theme
    db.session.commit()
    flash("Theme updated.", "success")
    return redirect(request.referrer or url_for("profile.index"))


@extras_bp.route("/contract", methods=["POST"])
@login_required
@csrf_protect
def accept_contract():
    current_user.contract_accepted_at = datetime.utcnow()
    db.session.commit()
    flash("Membership agreement accepted.", "success")
    return redirect(url_for("dashboard.membership"))


@extras_bp.route("/skip-task/<int:task_id>", methods=["POST"])
@login_required
@csrf_protect
def skip_task(task_id):
    from models.task import Task
    mname = (current_user.membership.name if current_user.membership else "").lower()
    if "vip" not in mname:
        flash("Skip tokens are for VIP members.", "warning")
        return redirect(url_for("task.index"))
    tokens = int(getattr(current_user, "skip_tokens", 0) or 0)
    if tokens < 1:
        flash("No skip tokens left.", "warning")
        return redirect(url_for("task.index"))
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    if (task.status or "").lower() not in ("assigned", "pending", "frozen"):
        flash("Task cannot be skipped.", "warning")
        return redirect(url_for("task.index"))
    task.status = "skipped"
    current_user.skip_tokens = tokens - 1
    db.session.commit()
    flash("Product skipped.", "success")
    return redirect(url_for("task.index"))


@extras_bp.route("/streak-insurance", methods=["POST"])
@login_required
@csrf_protect
def streak_insurance():
    month = date.today().strftime("%Y-%m")
    if getattr(current_user, "streak_insurance_month", None) == month and getattr(current_user, "streak_insurance_used", False):
        flash("Streak insurance already used this month.", "warning")
        return redirect(url_for("engagement.check_in"))
    current_user.streak_insurance_month = month
    current_user.streak_insurance_used = True
    # restore streak display soft bump
    try:
        current_user.streak_days = int(getattr(current_user, "streak_days", 0) or 0) + 1
    except Exception:
        pass
    db.session.commit()
    flash("Streak insurance applied for this month.", "success")
    return redirect(url_for("engagement.check_in"))


@extras_bp.route("/lounge")
@login_required
def country_lounge():
    from models.user import User
    from sqlalchemy import func
    rows = (
        db.session.query(User.country, func.count(User.id))
        .filter(User.is_admin.is_(False), User.country.isnot(None))
        .group_by(User.country)
        .order_by(func.count(User.id).desc())
        .limit(30)
        .all()
    )
    mine = getattr(current_user, "country", None) or "—"
    return render_template("extras/lounge.html", rows=rows, mine=mine)


@extras_bp.route("/api/ops-ticker")
def ops_ticker():
    from datetime import datetime, timedelta
    from models.deposit import Deposit
    from models.withdraw import Withdrawal
    since = datetime.utcnow() - timedelta(hours=1)
    try:
        deps = Deposit.query.filter(Deposit.status == "Approved", Deposit.approved_at >= since).count()
    except Exception:
        deps = Deposit.query.filter(Deposit.status == "Approved").count()
        deps = min(deps, 12)
    try:
        wds = Withdrawal.query.filter(Withdrawal.status.in_(["Approved", "Paid"])).count()
    except Exception:
        wds = 0
    return jsonify({
        "deposits_approved_1h": int(deps),
        "withdrawals_done": int(wds),
        "message": f"{deps} deposits approved in the last hour" if deps else "All systems normal",
    })


@extras_bp.route("/shoutout", methods=["POST"])
@login_required
@csrf_protect
def shoutout():
    if not (getattr(current_user, "is_agent", False) or getattr(current_user, "is_admin", False)):
        flash("Agents only.", "danger")
        return redirect(url_for("dashboard.index"))
    msg = (request.form.get("message") or "").strip()[:280]
    if not msg:
        flash("Write a short shoutout.", "warning")
        return redirect(request.referrer or url_for("dashboard.index"))
    from models.extra_features import TeamShoutout
    db.session.add(TeamShoutout(agent_id=current_user.id, message=msg))
    db.session.commit()
    flash("Shoutout posted to your team.", "success")
    return redirect(request.referrer or url_for("admin.agents_hub") if hasattr(current_user, "is_admin") else url_for("dashboard.index"))


@extras_bp.route("/agent-site/<code>")
def agent_mini_site(code):
    from models.user import User
    agent = User.query.filter_by(referral_code=code).first_or_404()
    return render_template("extras/agent_site.html", agent=agent, code=code)


@extras_bp.route("/balance-interest/claim", methods=["POST"])
@login_required
@csrf_protect
def claim_balance_interest():
    from services.balance_interest import apply_interest
    ok, msg, amount = apply_interest(current_user)
    flash(msg if not ok else f"Interest credited.", "success" if ok else "warning")
    return redirect(request.referrer or url_for("dashboard.index"))

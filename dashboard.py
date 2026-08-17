from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models.task import Task
from models.wallet_transaction import WalletTransaction
from models.combo_task import ComboTask
from datetime import datetime, timedelta
from sqlalchemy import func

from services.task_service import TaskService
from utils.security import csrf_protect

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _ensure_membership(user):
    """Assign Starter if user has no membership (broken signup / empty seed)."""
    if user.membership_id and user.membership:
        return
    from models.membership import Membership
    starter = (
        Membership.query.filter_by(name="Starter").first()
        or Membership.query.order_by(Membership.price.asc()).first()
    )
    if starter:
        user.membership_id = starter.id
        db.session.commit()


@dashboard_bp.route("/")
@login_required
def index():
    _ensure_membership(current_user)
    TaskService.ensure_daily_reset(current_user)
    progress = TaskService.progress(current_user)
    streak = TaskService.activity_streak(current_user)

    completed = Task.query.filter_by(user_id=current_user.id, status="completed").count()
    pending = Task.query.filter_by(user_id=current_user.id, status="assigned").count()

    current_task = None
    allowed, _ = TaskService.can_perform_tasks(current_user)
    if allowed:
        current_task = TaskService.assign_task(current_user)

    membership = current_user.membership
    mandatory = progress["mandatory"]
    today_completed = progress["completed_today"]

    combo = None
    try:
        combo = ComboTask.query.filter_by(user_id=current_user.id, completed=False).first()
    except Exception:
        combo = None

    total_earned = float(current_user.total_earned or 0)
    total_withdrawn = float(current_user.total_withdrawn or 0)
    avg_per_task = round(total_earned / completed, 0) if completed > 0 else 0

    today = datetime.utcnow().date()
    current_month = today.replace(day=1)
    month_total = db.session.query(func.sum(WalletTransaction.amount)).filter(
        WalletTransaction.user_id == current_user.id,
        func.date(WalletTransaction.created_at) >= current_month,
        WalletTransaction.amount > 0
    ).scalar() or 0.0

    pending_amount = db.session.query(func.sum(Task.commission)).filter(
        Task.user_id == current_user.id,
        Task.status == "assigned"
    ).scalar() or 0.0

    referral_earnings = float(getattr(current_user, "referral_income", 0) or 0)
    referral_bonus = referral_earnings
    frozen_balance = float(getattr(current_user, "combo_balance", 0) or 0)
    referral_count = int(getattr(current_user, "referral_count", 0) or 0)

    weekly_labels = []
    weekly_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        daily_earning = db.session.query(func.sum(WalletTransaction.amount)).filter(
            WalletTransaction.user_id == current_user.id,
            func.date(WalletTransaction.created_at) == day,
            WalletTransaction.amount > 0
        ).scalar() or 0.0
        weekly_labels.append(day.strftime("%a"))
        weekly_data.append(round(float(daily_earning), 0))

    announcements = []
    try:
        from models.announcement import Announcement
        announcements = Announcement.query.filter_by(active=True).order_by(
            Announcement.created_at.desc()
        ).limit(5).all()
    except Exception:
        pass

    recent_transactions = (
        WalletTransaction.query
        .filter_by(user_id=current_user.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(8)
        .all()
    )

    membership_commission = float(getattr(membership, "commission_percent", 15) or 15) if membership else 15
    upgrade_progress = min(100, int((today_completed / max(mandatory, 1)) * 100))

    # Progress object for dashboard template (TaskService.progress returns a dict)
    try:
        mem_ds = int(getattr(membership, "daily_sets", None) or 2)
        mem_tps = int(getattr(membership, "tasks_per_set", None) or mandatory or 16)
    except Exception:
        mem_ds = 2
        mem_tps = int(mandatory or 16)
    sets_done = int(getattr(current_user, "daily_sets_completed", 0) or 0)
    p = {
        "sets_completed": sets_done,
        "daily_sets": mem_ds,
        "tasks_completed": int(today_completed or 0),
        "tasks_per_set": mem_tps,
        "tasks_today": int(today_completed or 0),
        "daily_goal": int(mandatory or mem_tps or 16),
        "percent": int(upgrade_progress or 0),
        "current_set": min(sets_done + 1, mem_ds),
        "max_sets": mem_ds,
        "progress": int(upgrade_progress or 0),
        "mandatory": int(mandatory or 0),
        "completed_today": int(today_completed or 0),
    }

    # Guidance + extras for dashboard upgrades
    try:
        from utils.user_guidance import next_step, combo_timeline
        ns = next_step(current_user, progress=progress, combo=combo)
        combo_steps = combo_timeline(current_user, combo)
    except Exception:
        ns = None
        combo_steps = []
    recent_deposits = []
    try:
        from models.deposit import Deposit
        recent_deposits = (
            Deposit.query.filter_by(user_id=current_user.id)
            .order_by(Deposit.created_at.desc()).limit(5).all()
        )
    except Exception:
        pass
    product_of_day = None
    try:
        from models.product import Product
        product_of_day = Product.query.filter_by(active=True).order_by(Product.id.desc()).first()
    except Exception:
        pass
    checkin_done = False
    try:
        from datetime import date
        checkin_done = (getattr(current_user, "last_checkin", None) == date.today())
    except Exception:
        pass

    # Daily balance interest (lazy claim on visit)
    interest_info = None
    try:
        from services.balance_interest import preview, apply_interest
        interest_info = preview(current_user)
        if interest_info.get("can_claim"):
            ok, msg, amt = apply_interest(current_user)
            interest_info = preview(current_user)
            interest_info["just_credited"] = ok
            interest_info["credited_amount"] = amt
    except Exception as _bi:
        print("balance interest:", _bi)

    return render_template(
        "dashboard.html",
        p=p,
        interest_info=interest_info,
        next_step=ns,
        combo_steps=combo_steps,
        recent_deposits=recent_deposits,
        product_of_day=product_of_day,
        checkin_done=checkin_done,
        completed=completed,
        pending=pending,
        maximum=mandatory,
        current_task=current_task,
        today_completed=today_completed,
        tasks_per_set=mandatory,
        max_sets=1,
        current_set=1,
        progress=progress,
        streak=streak,
        combo=combo,
        total_earned=total_earned,
        total_withdrawn=abs(total_withdrawn),
        avg_per_task=avg_per_task,
        month_total=float(month_total),
        pending_amount=float(pending_amount),
        referral_earnings=referral_earnings,
        referral_bonus=referral_bonus,
        frozen_balance=frozen_balance,
        referral_count=referral_count,
        active_referrals=referral_count,
        referral_commission=5,
        weekly_labels=weekly_labels,
        weekly_data=weekly_data,
        weekly_breakdown=[{"day": l, "amount": a} for l, a in zip(weekly_labels, weekly_data)],
        weekly_percentage=0,
        success_rate=95,
        announcements=announcements,
        leaderboard=[],
        recent_transactions=recent_transactions,
        membership_commission=membership_commission,
        upgrade_progress=upgrade_progress,
        show_onboarding=not bool(getattr(current_user, "checklist_done", False)),
    )


@dashboard_bp.route("/onboarding/complete", methods=["POST"])
@login_required
def complete_onboarding():
    try:
        current_user.checklist_done = True
        db.session.commit()
    except Exception:
        db.session.rollback()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return {"ok": True}
    return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/earn")
@login_required
def earn():
    return render_template(
        "earn.html",
        total_referrals=getattr(current_user, "referral_count", 0) or 0,
        referral_income=getattr(current_user, "referral_income", 0) or 0,
    )


@dashboard_bp.route("/faq")
def faq():
    return render_template("faq.html")


@dashboard_bp.route("/contact", methods=["GET", "POST"])
def contact():
    support = None
    try:
        from models.support import Support
        support = Support.query.first()
        if support is None:
            support = Support()
            db.session.add(support)
            db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("contact support load:", e)
        # minimal stand-in so template never crashes
        class _S:
            whatsapp1 = whatsapp2 = telegram1 = telegram2 = livechat = None
            whatsapp1_enabled = whatsapp2_enabled = False
            telegram1_enabled = telegram2_enabled = False
            livechat_enabled = False
        support = _S()

    if request.method == "POST":
        flash("Thank you! Your message has been received.", "success")
        return redirect(url_for("dashboard.contact"))

    return render_template("contact.html", support=support)


@dashboard_bp.route("/about")
def about():
    return render_template("about.html")


@dashboard_bp.route("/certificate")
@login_required
def certificate():
    return render_template("certificate.html")


@dashboard_bp.route("/terms")
def terms():
    return render_template("terms.html")


@dashboard_bp.route("/membership")
@login_required
def membership():
    from services.membership_service import MembershipService
    plans = MembershipService.all()
    return render_template(
        "membership.html",
        memberships=plans,
        current=current_user.membership,
    )


@dashboard_bp.route("/membership/upgrade/<int:plan_id>", methods=["POST"])
@login_required
@csrf_protect
def upgrade_membership(plan_id):
    from services.membership_service import MembershipService
    plan = MembershipService.get(plan_id)
    if not plan or not plan.active:
        flash("Membership plan not found.", "danger")
        return redirect(url_for("dashboard.membership"))

    if current_user.membership and current_user.membership.id == plan.id:
        flash("You are already on this plan.", "info")
        return redirect(url_for("dashboard.membership"))

    if current_user.membership and float(plan.price or 0) < float(current_user.membership.price or 0):
        flash("You cannot downgrade your membership. Please contact admin.", "danger")
        return redirect(url_for("dashboard.membership"))

    ok, msg = MembershipService.upgrade(current_user, plan)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("dashboard.membership"))


@dashboard_bp.route("/join/<code>")
def join_invite(code):
    """Branded invite landing; stores referral code in session."""
    from flask import session
    from models.user import User
    code = (code or "").strip()
    referrer = User.query.filter_by(referral_code=code).first()
    session["referral_code"] = code
    return render_template("join.html", code=code, referrer=referrer)


@dashboard_bp.route("/status")
def public_status():
    from models.settings import Settings
    settings = Settings.query.first()
    return render_template("status.html", settings=settings)


@dashboard_bp.route("/stories")
def stories():
    from models.success_story import SuccessStory
    items = SuccessStory.query.filter_by(approved=True).order_by(SuccessStory.created_at.desc()).limit(50).all()
    return render_template("stories.html", stories=items)


@dashboard_bp.route("/a/<code>")
def agent_site(code):
    from models.user import User
    agent = User.query.filter(
        (User.referral_code == code) | (User.username == code)
    ).filter((User.is_agent == True) | (User.is_admin == True)).first()
    return render_template("agent_site.html", agent=agent, code=code)


@dashboard_bp.route("/digest")
@login_required
def daily_digest():
    """In-app daily summary of what needs attention."""
    from models.deposit import Deposit
    from models.withdraw import Withdrawal
    from models.notification import Notification
    from services.task_service import TaskService
    TaskService.ensure_daily_reset(current_user)
    tps, ds, total = TaskService._limits(current_user)
    done = int(current_user.tasks_completed_today or 0)
    pending_deps = Deposit.query.filter_by(user_id=current_user.id, status="Pending").count()
    pending_wds = Withdrawal.query.filter(
        Withdrawal.user_id == current_user.id,
        Withdrawal.status.in_(["Pending", "Processing"]),
    ).count()
    unread = 0
    try:
        unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    except Exception:
        try:
            unread = Notification.query.filter_by(user_id=current_user.id, read=False).count()
        except Exception:
            pass
    items = []
    if float(current_user.available_balance or 0) < 0 or getattr(current_user, "combo_active", False):
        items.append({"level": "danger", "title": "Combo / negative balance", "body": "Deposit to clear the hold, then submit the frozen product.", "url": url_for("wallet.deposit")})
    if done < total:
        items.append({"level": "info", "title": "Tasks remaining", "body": f"{done}/{total} completed today.", "url": url_for("task.index")})
    else:
        items.append({"level": "ok", "title": "Daily tasks complete", "body": "Great work — check mystery box if available.", "url": url_for("task.mystery_box")})
    if pending_deps:
        items.append({"level": "warn", "title": "Deposit pending", "body": f"{pending_deps} deposit(s) waiting for admin.", "url": url_for("wallet.index")})
    if pending_wds:
        items.append({"level": "warn", "title": "Withdrawal in progress", "body": f"{pending_wds} withdrawal(s) Pending/Processing.", "url": url_for("wallet.my_withdrawals")})
    if unread:
        items.append({"level": "info", "title": "Unread notifications", "body": f"{unread} new message(s).", "url": url_for("profile.notifications")})
    if not getattr(current_user, "payout_confirmed", False):
        items.append({"level": "info", "title": "Payout method", "body": "Set or wait for admin confirmation before withdrawing.", "url": url_for("wallet.withdraw")})
    return render_template(
        "digest.html",
        items=items,
        done=done,
        total=total,
        pending_deps=pending_deps,
        pending_wds=pending_wds,
    )


@dashboard_bp.route("/language/<code>")
def set_language(code):
    """Manual language override (session)."""
    from flask import session, redirect, request, url_for
    code = (code or "en").lower()[:8]
    allowed = {"en", "lg", "sw", "fr", "de", "ar", "pt", "es", "zh", "hi", "rw", "am"}
    if code not in allowed:
        code = "en"
    session["lang"] = code
    ref = request.referrer or url_for("dashboard.index")
    return redirect(ref)

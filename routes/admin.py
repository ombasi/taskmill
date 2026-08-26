from functools import wraps
import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request
)
from flask_login import (
    login_required,
    current_user
)
from sqlalchemy import func, or_
from extensions import db

# Models
from models import notification
from models import notification
from models.user import User
from models.task import Task
from models.product import Product
from models.deposit import Deposit
from models.withdraw import Withdrawal
from models.wallet_transaction import WalletTransaction
from models.membership import Membership
from models.settings import Settings
from models.support import Support
from models.partner import Partner
from models.notification import Notification
from models.announcement import Announcement
from models.banner import Banner
from models.combo import Combo
from models.payment_setting import PaymentSetting

# Services
from services.wallet_service import WalletService
from services.task_service import TaskService
from services.combo_service import ComboService

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


# ==========================================================
# ADMIN REQUIRED
# ==========================================================
def admin_required(f):
    """Full admin OR team agent (agents limited to whitelist + own downline)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        is_full = bool(getattr(current_user, "is_admin", False))
        is_agent = bool(getattr(current_user, "is_agent", False))
        if not is_full and not is_agent:
            flash("Administrator access required.", "danger")
            return redirect(url_for("dashboard.index"))
        # Agents: only certain endpoints
        if is_agent and not is_full:
            ep = (request.endpoint or "")
            # Support-only role: read + chat + notes + flag. No money / security / combo / membership.
            allowed = {
                "admin.users",
                "admin.view_user",
                "admin.add_user_note",
                "admin.team_report",
                "admin.deposits",          # view pending only (approve routes are full_admin)
                "admin.withdrawals",      # view pending only
                "admin.flag_deposit",
                "admin.export_team_users_csv",
                "admin.referral_leaderboard",
                "admin.stuck_users",
                "admin.team_challenges",
                "chat.admin_inbox",
                "chat.admin_thread",
                "auth.setup_2fa",
                "auth.verify_2fa",
                "auth.logout",
            }
            if ep not in allowed:
                flash("Support agents can only view their team, chat, add notes, and flag items. Money and security actions are main admin only.", "warning")
                return redirect(url_for("admin.users"))
        return f(*args, **kwargs)
    return decorated_function



def _deny_agent_write():
    """Block agents from any money/security write (support role only)."""
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        flash("Support agents cannot perform this action. Main admin only.", "danger")
        return True
    return False

def full_admin_required(f):
    """Strict full administrator only (not agents)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not getattr(current_user, "is_admin", False):
            flash("Full administrator access required.", "danger")
            return redirect(url_for("admin.users") if getattr(current_user, "is_agent", False) else url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated_function


def get_downline_ids(root_user_id, max_depth=25):
    """All user ids in referral pyramid under root (not including root)."""
    ids = set()
    frontier = [int(root_user_id)]
    depth = 0
    while frontier and depth < max_depth:
        children = (
            User.query.filter(User.referred_by_id.in_(frontier))
            .with_entities(User.id)
            .all()
        )
        child_ids = [c[0] for c in children]
        # avoid cycles
        child_ids = [i for i in child_ids if i not in ids and i != root_user_id]
        if not child_ids:
            break
        ids.update(child_ids)
        frontier = child_ids
        depth += 1
    return ids


def can_manage_user(actor, target_user):
    """Full admin: anyone. Agent: only users in their referral downline."""
    if not actor or not target_user:
        return False
    if getattr(actor, "is_admin", False):
        return True
    if not getattr(actor, "is_agent", False):
        return False
    # Agents cannot manage full admins or other agents outside tree
    if getattr(target_user, "is_admin", False):
        return False
    downline = get_downline_ids(actor.id)
    return int(target_user.id) in downline


def _reset_agent_limits_if_needed(actor):
    from datetime import datetime as dt
    today = dt.utcnow().strftime("%Y-%m-%d")
    if getattr(actor, "agent_limits_day", None) != today:
        actor.agent_credit_used_today = 0.0
        actor.agent_debit_used_today = 0.0
        actor.agent_limits_day = today


def _agent_can_credit(actor, amount):
    if getattr(actor, "is_admin", False):
        return True, None
    if not getattr(actor, "is_agent", False):
        return False, "Not allowed"
    _reset_agent_limits_if_needed(actor)
    lim = float(getattr(actor, "agent_credit_limit_daily", 0) or 0)
    used = float(getattr(actor, "agent_credit_used_today", 0) or 0)
    if lim > 0 and used + amount > lim:
        return False, f"Daily credit limit exceeded (limit {lim:,.0f}, used {used:,.0f})."
    return True, None


def _agent_can_debit(actor, amount):
    if getattr(actor, "is_admin", False):
        return True, None
    if not getattr(actor, "is_agent", False):
        return False, "Not allowed"
    _reset_agent_limits_if_needed(actor)
    lim = float(getattr(actor, "agent_debit_limit_daily", 0) or 0)
    used = float(getattr(actor, "agent_debit_used_today", 0) or 0)
    if lim > 0 and used + amount > lim:
        return False, f"Daily debit limit exceeded (limit {lim:,.0f}, used {used:,.0f})."
    return True, None


def log_staff_action(module, action, target="", description=""):

    """Log admin/agent action for main admin audit trail."""
    try:
        from utils.audit import log_admin_action
        log_admin_action(
            current_user,
            module=module,
            action=action,
            target=str(target)[:255],
            description=(description or "")[:2000],
        )
        db.session.commit()
    except Exception as e:
        print("log_staff_action:", e)
        try:
            db.session.rollback()
        except Exception:
            pass


def assert_can_manage(user_id):

    """Abort/redirect if current user cannot manage this user."""
    target = User.query.get_or_404(user_id)
    if can_manage_user(current_user, target):
        return target
    flash("You can only manage users who joined under your referral tree.", "danger")
    return None


# ==========================================================
# DASHBOARD
# ==========================================================

def _combo_max_for_user(user):
    """No membership cap on combo — high-value products allowed for all tiers."""
    return None  # unlimited


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        return redirect(url_for("admin.users"))

    total_users = User.query.count()
    active_users = User.query.filter_by(
        is_active=True  # countries set below if supported
    ).count()
    blocked_users = User.query.filter_by(
        is_blocked=True
    ).count()
    total_products = Product.query.count()
    active_tasks = Task.query.filter_by(
        status="pending"
    ).count()
    completed_tasks = Task.query.filter_by(
        status="completed"
    ).count()
    pending_deposits = Deposit.query.filter_by(
        status="Pending"
    ).count()
    pending_withdrawals = Withdrawal.query.filter_by(
        status="Pending"
    ).count()
    today = datetime.utcnow().date()
    deposits_today = db.session.query(
        func.coalesce(
            func.sum(Deposit.amount),
            0
        )
    ).filter(
        func.date(Deposit.created_at) == today,
        Deposit.status == "Approved"
    ).scalar()
    withdrawals_today = db.session.query(
        func.coalesce(
            func.sum(Withdrawal.amount),
            0
        )
    ).filter(
        func.date(Withdrawal.created_at) == today,
        Withdrawal.status == "Approved"
    ).scalar()
    revenue_labels = []
    revenue_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        revenue_labels.append(
            day.strftime("%a")
        )
        amount = db.session.query(
            func.coalesce(
                func.sum(WalletTransaction.amount),
                0
            )
        ).filter(
            func.date(
                WalletTransaction.created_at
            ) == day
        ).scalar()
        revenue_data.append(float(amount))
    user_labels = []
    user_values = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        user_labels.append(
            day.strftime("%a")
        )
        count = User.query.filter(
            func.date(User.created_at) == day
        ).count()
        user_values.append(count)
    recent_users = User.query.order_by(
        User.created_at.desc()
    ).limit(10).all()
    activities = []
    for user in recent_users:
        activities.append({
            "message": f"{user.username} registered",
            "time": user.created_at.strftime(
                "%d %b %Y %H:%M"
            ),
            "type": "User"
        })

    # Command center queues
    pending_deposit_list = (
        Deposit.query.filter_by(status="Pending")
        .order_by(Deposit.created_at.desc())
        .limit(8)
        .all()
    )
    pending_withdrawal_list = (
        Withdrawal.query.filter_by(status="Pending")
        .order_by(Withdrawal.created_at.desc())
        .limit(8)
        .all()
    )
    negative_users = (
        User.query.filter(User.available_balance < 0)
        .order_by(User.available_balance.asc())
        .limit(8)
        .all()
    )
    open_combos = (
        Combo.query.filter(Combo.status.in_(["Pending", "Triggered"]))
        .order_by(Combo.created_at.desc())
        .limit(8)
        .all()
    )

    unread_chats = 0
    try:
        from models.chat import ChatMessage
        unread_chats = ChatMessage.query.filter_by(is_from_admin=False, is_read=False).count()
    except Exception:
        pass
    negative_count = User.query.filter(User.available_balance < 0).count()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        active_users=active_users,
        blocked_users=blocked_users,
        pending_deposit_list=pending_deposit_list,
        pending_withdrawal_list=pending_withdrawal_list,
        negative_users=negative_users,
        negative_count=negative_count,
        open_combos=open_combos,
        total_products=total_products,
        active_tasks=active_tasks,
        completed_tasks=completed_tasks,
        pending_deposits=pending_deposits,
        unread_chats=unread_chats,
        pending_withdrawals=pending_withdrawals,
        deposits_today=float(deposits_today or 0),
        withdrawals_today=float(withdrawals_today or 0),
        revenue_labels=revenue_labels,
        revenue_data=revenue_data,
        user_labels=user_labels,
        user_values=user_values,
        activities=activities
    )


# ==========================================================
# USERS
# ==========================================================
@admin_bp.route("/users")
@login_required
@admin_required
def users():
    page = request.args.get("page", 1, type=int)
    q = (request.args.get("q") or "").strip()
    filter_neg = request.args.get("negative") == "1"
    filter_membership = request.args.get("membership_id", type=int)

    query = User.query
    # Agents only see their referral pyramid
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        downline = get_downline_ids(current_user.id)
        if downline:
            query = query.filter(User.id.in_(list(downline)))
        else:
            query = query.filter(User.id == -1)  # empty
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                User.username.ilike(like),
                User.email.ilike(like),
                User.phone.ilike(like),
                User.referral_code.ilike(like),
                User.ip_address.ilike(like),
                User.full_name.ilike(like),
            )
        )
    if filter_neg:
        query = query.filter(User.available_balance < 0)
    if filter_membership:
        query = query.filter(User.membership_id == filter_membership)

    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=30, error_out=False
    )
    memberships = Membership.query.order_by(Membership.price.asc()).all()
    from datetime import datetime
    return render_template(
        "admin/users.html",
        users=users,
        q=q,
        filter_neg=filter_neg,
        filter_membership=filter_membership,
        memberships=memberships,
        now_utc=datetime.utcnow(),
    )



@admin_bp.route("/payments/seed-locals", methods=["POST", "GET"])
@login_required
@admin_required
def seed_local_payments():
    """Create inactive catalog rows for all country local methods + crypto."""
    from utils.payment_methods import ensure_catalog_payment_methods
    n = ensure_catalog_payment_methods(include_local=True, include_crypto=True, activate=False)
    flash(f"Payment catalog updated ({n} new methods). Toggle Active and set account details.", "success")
    return redirect(url_for("admin.payment_settings"))

@admin_bp.route("/payment-settings")
@login_required
@admin_required
def payment_settings():
    settings = PaymentSetting.query.order_by(
        PaymentSetting.method.asc()
    ).all()
    return render_template(
        "admin/payment_settings.html",
        settings=settings
    )


@admin_bp.route("/payment-settings/seed-crypto", methods=["POST"])
@login_required
@admin_required
def seed_crypto_methods():
    """Create TRC20/ERC20/BTC/ETH rows inactive if missing."""
    try:
        from utils.payment_methods import ensure_crypto_payment_methods
        ensure_crypto_payment_methods()
        flash("Crypto methods ready (inactive). Toggle Active to show on deposit.", "success")
    except Exception as e:
        flash(f"Could not seed crypto: {e}", "danger")
    return redirect(url_for("admin.payment_settings"))

@admin_bp.route("/payment-settings/add", methods=["POST"])
@login_required
@admin_required
def add_payment_setting():

    method = (request.form.get("method") or "").strip()
    if not method:
        flash("Method name is required.", "danger")
        return redirect(url_for("admin.payment_settings"))
    setting = PaymentSetting(
        method=method,
        provider=(request.form.get("provider") or method).strip(),
        account_name=(request.form.get("account_name") or "").strip(),
        account_number=(request.form.get("account_number") or "").strip(),
        instructions=(request.form.get("instructions") or "").strip(),
        active=True,
    )
    if hasattr(setting, "countries"):
        setting.countries = (request.form.get("countries") or "ALL").strip() or "ALL"
    db.session.add(setting)
    db.session.commit()

    flash(
        "Payment method added.",
        "success"
    )

    return redirect(
        url_for("admin.payment_settings")
    )

@admin_bp.route("/payment-settings/<int:id>/edit", methods=["POST"])
@login_required
@admin_required
def edit_payment_setting(id):

    setting = PaymentSetting.query.get_or_404(id)

    setting.method = (request.form.get("method") or setting.method).strip()
    setting.provider = (request.form.get("provider") or setting.provider or "").strip()
    setting.account_name = (request.form.get("account_name") or "").strip()
    setting.account_number = (request.form.get("account_number") or "").strip()
    setting.instructions = (request.form.get("instructions") or "").strip()
    if hasattr(setting, "countries"):
        setting.countries = (request.form.get("countries") or "ALL").strip() or "ALL"

    db.session.commit()

    flash(
        "Payment updated.",
        "success"
    )

    return redirect(
        url_for("admin.payment_settings")
    )

@admin_bp.route("/payment-settings/<int:id>/toggle")
@login_required
@admin_required
def toggle_payment_setting(id):
    setting = PaymentSetting.query.get_or_404(id)
    setting.active = not bool(setting.active)
    db.session.commit()
    flash(
        f"{setting.method} is now {'active' if setting.active else 'disabled'}.",
        "success",
    )
    return redirect(url_for("admin.payment_settings"))

@admin_bp.route("/payment-settings/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_payment_setting(id):

    setting = PaymentSetting.query.get_or_404(id)

    db.session.delete(setting)

    db.session.commit()

    flash(
        "Payment method deleted.",
        "success"
    )

    return redirect(
        url_for("admin.payment_settings")
    )


# ==========================================================
# VIEW USER
# ==========================================================

@admin_bp.route("/payment-settings/ensure-crypto", methods=["POST"])
@login_required
@admin_required
def ensure_crypto_payments():
    """Add TRC20 / ERC20 / BTC / ETH rows if missing (admin can then set addresses)."""
    from utils.payment_methods import ensure_crypto_payment_methods
    n = ensure_crypto_payment_methods()
    if n:
        flash(f"Added {n} crypto payment method(s). Update the wallet addresses below.", "success")
    else:
        flash("Crypto methods already exist. Edit addresses below.", "info")
    return redirect(url_for("admin.payment_settings"))


@admin_bp.route("/users/<int:user_id>")
@login_required
@admin_required
def view_user(user_id):
    """Admin user detail — hardened for Render (missing tables/nulls)."""
    user = User.query.get_or_404(user_id)

    def _safe_list(query_fn, default=None):
        try:
            return query_fn()
        except Exception as e:
            print("view_user query error:", e)
            try:
                db.session.rollback()
            except Exception:
                pass
            return default if default is not None else []

    tasks = _safe_list(lambda: (
        Task.query.filter_by(user_id=user.id)
        .order_by(Task.created_at.desc())
        .limit(50).all()
    ))
    deposits = _safe_list(lambda: (
        Deposit.query.filter_by(user_id=user.id)
        .order_by(Deposit.created_at.desc())
        .limit(30).all()
    ))
    withdrawals = _safe_list(lambda: (
        Withdrawal.query.filter_by(user_id=user.id)
        .order_by(Withdrawal.created_at.desc())
        .limit(30).all()
    ))
    wallet_transactions = _safe_list(lambda: (
        WalletTransaction.query.filter_by(user_id=user.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(40).all()
    ))
    referrals = _safe_list(lambda: (
        User.query.filter_by(referred_by_id=user.id).all()
    ))

    login_history = []
    try:
        from models.login_history import LoginHistory
        login_history = (
            LoginHistory.query
            .filter_by(user_id=user.id)
            .order_by(LoginHistory.login_time.desc(), LoginHistory.id.desc())
            .limit(50)
            .all()
        )
    except Exception as e:
        print("login_history error:", e)
        try:
            db.session.rollback()
        except Exception:
            pass

    from models.membership import Membership
    from models.product import Product

    memberships = _safe_list(lambda: (
        Membership.query.order_by(Membership.price.asc()).all()
    ))

    combo_products = []
    try:
        # No membership price cap — show highest-value products first
        bal = float(user.available_balance or 0)
        min_price = max(0.0, bal * 0.3) if bal > 0 else 0.0
        combo_products = (
            Product.query
            .filter(
                Product.active.is_(True),
                Product.price > 0,
                Product.price >= min_price,
            )
            .order_by(Product.price.desc())
            .limit(300)
            .all()
        )
        if len(combo_products) < 15:
            combo_products = (
                Product.query
                .filter(
                    Product.active.is_(True),
                    Product.price > 0,
                )
                .order_by(Product.price.desc())
                .limit(300)
                .all()
            )
    except Exception as e:
        print("combo_products error:", e)
        try:
            db.session.rollback()
        except Exception:
            pass
        combo_products = _safe_list(lambda: (
            Product.query.filter(Product.price > 0)
            .order_by(Product.price.desc()).limit(100).all()
        ))

    last_ip = getattr(user, "ip_address", None) or "—"
    if last_ip == "—" and login_history:
        for row in login_history:
            if getattr(row, "ip_address", None):
                last_ip = row.ip_address
                break

    return render_template(
        "admin/user_details.html",
        now_utc=__import__("datetime").datetime.utcnow(),
        user=user,
        tasks=tasks or [],
        deposits=deposits or [],
        withdrawals=withdrawals or [],
        wallet_transactions=wallet_transactions or [],
        referrals=referrals or [],
        memberships=memberships or [],
        combo_products=combo_products or [],
        login_history=login_history or [],
        last_ip=last_ip or "—",
        spin_prizes=_safe_list(lambda: __import__("models.spin", fromlist=["SpinPrize"]).SpinPrize.query.filter_by(active=True).all()),
        user_notes=_safe_list(lambda: __import__("models.user_note", fromlist=["UserNote"]).UserNote.query.filter_by(user_id=user.id).order_by(__import__("models.user_note", fromlist=["UserNote"]).UserNote.created_at.desc()).limit(30).all()),
    )

# ==========================================================
# BLOCK / UNBLOCK USER
# ==========================================================
@admin_bp.route("/users/<int:user_id>/toggle-block")
@login_required
@admin_required
def toggle_block(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash(
            "You cannot block your own account.",
            "warning"
        )
        return redirect(url_for("admin.users"))
    user.is_blocked = not user.is_blocked
    db.session.commit()
    log_staff_action(
        "users",
        "block" if user.is_blocked else "unblock",
        target=user.username,
        description=f"User #{user.id} {'blocked' if user.is_blocked else 'unblocked'} by {current_user.username}",
    )
    flash(
        f"{user.username} has been {'blocked' if user.is_blocked else 'unblocked'}.",
        "success"
    )
    return redirect(url_for("admin.view_user", user_id=user.id))


# ==========================================================
# ACTIVATE / DEACTIVATE USER
# ==========================================================
@admin_bp.route("/users/<int:user_id>/toggle-active")
@login_required
@admin_required
def toggle_active(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash(
            "You cannot deactivate yourself.",
            "warning"
        )
        return redirect(
            url_for("admin.users")
        )
    user.is_active = not user.is_active
    db.session.commit()
    flash(
        f"{user.username} updated successfully.",
        "success"
    )
    return redirect(url_for("admin.view_user", user_id=user.id))
from werkzeug.security import generate_password_hash

@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_password(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))

    user = User.query.get_or_404(user_id)
    new_password = "12345678"
    user.set_password(new_password)
    user.must_change_password = True
    db.session.commit()
    flash(
        f"Password reset for {user.username}. Temporary password: {new_password}. "
        "User will be forced to change it on next login.",
        "success"
    )
    return redirect(url_for("admin.view_user", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/payout", methods=["POST"])
@login_required
@admin_required
def update_user_payout(user_id):
    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))
    user = User.query.get_or_404(user_id)
    action = (request.form.get("action") or "save").strip()
    if action == "confirm":
        if not user.payout_method or not user.payout_account_number:
            flash("User has no payout method to confirm.", "warning")
        else:
            user.payout_confirmed = True
            db.session.commit()
            flash("Payout method confirmed.", "success")
            try:
                from utils.audit import log_action
                log_action(current_user.id, "confirm_payout", "users", str(user.id), f"Confirmed {user.payout_method}")
            except Exception:
                pass
        return redirect(url_for("admin.view_user", user_id=user.id))

    user.payout_method = (request.form.get("payout_method") or user.payout_method or "").strip()
    user.payout_account_name = (request.form.get("payout_account_name") or "").strip()
    user.payout_account_number = (request.form.get("payout_account_number") or "").strip()
    user.payout_provider = (request.form.get("payout_provider") or user.payout_method or "").strip()
    user.payout_confirmed = request.form.get("payout_confirmed") == "1"
    from datetime import datetime
    if user.payout_method and user.payout_account_number and not user.payout_set_at:
        user.payout_set_at = datetime.utcnow()
    db.session.commit()
    flash("Payout method updated.", "success")
    try:
        from utils.audit import log_action
        log_action(current_user.id, "update_payout", "users", str(user.id), f"{user.payout_method} {user.payout_account_number}")
    except Exception:
        pass
    return redirect(url_for("admin.view_user", user_id=user.id))


# ==========================================================
# MAKE ADMIN
# ==========================================================

@admin_bp.route("/users/<int:user_id>/make-agent", methods=["POST"])
@login_required
@admin_required
def make_agent(user_id):
    """Promote user to team leader (agent): manages only their referral tree."""
    if not getattr(current_user, "is_admin", False):
        flash("Full admin only.", "danger")
        return redirect(url_for("admin.users"))
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Cannot change your own agent role here.", "warning")
        return redirect(url_for("admin.view_user", user_id=user.id))
    user.is_agent = True
    # Agents are not full admins
    # keep is_admin as-is only if already admin — prefer agent-only
    if user.is_admin:
        flash("User is a full admin. Demote admin first if you want agent-only access.", "warning")
    db.session.commit()
    flash(f"{user.username} is now a team leader (agent). They only see their referral tree.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/remove-agent", methods=["POST"])
@login_required
@admin_required
def remove_agent(user_id):
    if not getattr(current_user, "is_admin", False):
        flash("Full admin only.", "danger")
        return redirect(url_for("admin.users"))
    user = User.query.get_or_404(user_id)
    user.is_agent = False
    db.session.commit()
    flash(f"Agent role removed from {user.username}.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/make-admin")
@login_required
@admin_required
def make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    flash(
        f"{user.username} is now an administrator.",
        "success"
    )
    return redirect(
        url_for("admin.users")
    )


# ==========================================================
# REMOVE ADMIN
# ==========================================================
@admin_bp.route("/users/<int:user_id>/remove-admin")
@login_required
@admin_required
def remove_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash(
            "You cannot remove yourself as admin.",
            "warning"
        )
        return redirect(
            url_for("admin.users")
        )
    user.is_admin = False
    db.session.commit()
    flash(
        "Administrator removed.",
        "success"
    )
    return redirect(
        url_for("admin.users")
    )


# ==========================================================
# DELETE USER
# ==========================================================
@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash(
            "You cannot delete your own account.",
            "danger"
        )
        return redirect(
            url_for("admin.users")
        )
    db.session.delete(user)
    db.session.commit()
    flash(
        "User deleted successfully.",
        "success"
    )
    return redirect(
        url_for("admin.users")
    )

# ==========================================================
# CREDIT USER WALLET
# ==========================================================
@admin_bp.route("/users/<int:user_id>/credit", methods=["POST"])
@login_required
@admin_required
def credit_wallet(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))


    user = User.query.get_or_404(user_id)

    amount = float(request.form["amount"])

    reason = request.form.get("reason", "Admin Credit")

    before = user.available_balance

    user.available_balance += amount
    try:
        from services.task_service import TaskService
        TaskService.sync_negative_and_combo_tasks(user)
    except Exception:
        pass

    transaction = WalletTransaction(
        user_id=user.id,
        amount=amount,
        transaction_type="Admin Credit",
        description=reason,
        balance_before=before,
        balance_after=user.available_balance
    )

    db.session.add(transaction)

    db.session.commit()

    log_staff_action("wallet", "credit", target=str(user_id), description=f"Credit by {current_user.username}")
    flash(f"New balance ~ {float(user.available_balance or 0):,.0f} UGX. " + "Wallet credited successfully.", "success")

    return redirect(
        url_for("admin.view_user", user_id=user.id)
    )

# ==========================================================
# DEDUCT USER WALLET
# ==========================================================
@admin_bp.route("/users/<int:user_id>/deduct", methods=["POST"])
@login_required
@admin_required
def deduct_wallet(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))


    user = User.query.get_or_404(user_id)

    amount = float(request.form["amount"])

    reason = request.form.get("reason", "Admin Deduction")

    if amount <= 0:
        flash("Invalid amount.", "danger")
        return redirect(url_for("admin.view_user", user_id=user.id))

    if user.available_balance < amount:
        flash("User has insufficient balance.", "danger")
        return redirect(url_for("admin.view_user", user_id=user.id))

    before = user.available_balance

    user.available_balance -= amount

    transaction = WalletTransaction(
        user_id=user.id,
        amount=-amount,
        transaction_type="Admin Deduction",
        description=reason,
        balance_before=before,
        balance_after=user.available_balance
    )

    db.session.add(transaction)

    db.session.commit()

    log_staff_action("wallet", "deduct", target=str(user_id), description=f"Deduct by {current_user.username}")
    flash("Wallet deducted successfully.", "success")

    return redirect(
        url_for("admin.view_user", user_id=user.id)
    )
# ==========================================================
# COMBO MANAGER
# ==========================================================
from models.combo import Combo


@admin_bp.route("/combos")
@login_required
@admin_required
def combos():

    page = request.args.get("page", 1, type=int)

    query = Combo.query
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        downline = get_downline_ids(current_user.id)
        if downline:
            query = query.filter(Combo.user_id.in_(list(downline)))
        else:
            query = query.filter(Combo.user_id == -1)

    combos = query.order_by(
        Combo.created_at.desc()
    ).paginate(
        page=page,
        per_page=20,
        error_out=False
    )

    return render_template(
        "admin/combos.html",
        combos=combos
    )
# ==========================================================
# CREATE COMBO
# ==========================================================
@admin_bp.route("/combos/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_combo():

    users = User.query.order_by(User.username).all()

    if request.method == "POST":

        combo = Combo(

            user_id=request.form.get(
                "user_id",
                type=int
            ),

            trigger_task=request.form.get(
                "trigger_task",
                type=int
            ),

            amount=request.form.get(
                "amount",
                type=float
            ),

            combo_type=request.form.get(
                "combo_type"
            ),

            tasks_required=request.form.get(
                "tasks_required",
                type=int
            ),

            notes=request.form.get(
                "notes"
            ),

            created_by=current_user.id,

            status="Pending"

        )

        db.session.add(combo)
        db.session.commit()

        flash(
            "Combo created successfully.",
            "success"
        )

        return redirect(
            url_for("admin.combos")
        )

    return render_template(
        "admin/combo_form.html",
        combo=None,
        users=users
    )

@admin_bp.route("/combos/assign", methods=["POST"])
@login_required
@admin_required
def assign_combo_from_manager():
    ref = (request.form.get("user_ref") or "").strip()
    user = None
    if ref.isdigit():
        user = User.query.get(int(ref))
    if user is None:
        user = User.query.filter_by(username=ref).first()
    if user is None:
        user = User.query.filter_by(email=ref).first()
    if user is None:
        flash("User not found. Use ID or username.", "danger")
        return redirect(url_for("admin.combos"))
    # Forward to assign_combo by replacing form user - call function with user_id
    return assign_combo(user.id)

@admin_bp.route("/users/<int:user_id>/assign-combo", methods=["POST"])
@login_required
@admin_required
def assign_combo(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))

    """
    Admin enters target combo amount (how much the product should cost).
    System picks a product within ±3000 UGX of that target.
    On trigger: product price is deducted (can go negative).
    """
    from models.product import Product
    import random

    user = User.query.get_or_404(user_id)
    trigger_task = request.form.get("trigger_task", type=int) or 1
    notes = (request.form.get("notes") or "").strip()
    product_id = request.form.get("product1_id", type=int) or request.form.get("product_id", type=int)

    try:
        target = float(request.form.get("target_amount") or 0)
    except (TypeError, ValueError):
        target = 0

    bal = float(user.available_balance or 0)
    RANGE = max(3000.0, target * 0.05)  # ±5% of target or 3000, whichever larger

    # Suggested default shown to admin: slightly above balance
    if target <= 0:
        flash("Enter a target amount (UGX) for the combo product.", "danger")
        return redirect(url_for("admin.view_user", user_id=user.id))

    p1 = None
    if product_id:
        p1 = Product.query.get(product_id)

    if not p1:
        low = max(0.0, target - RANGE)
        high = target + RANGE
        candidates = (
            Product.query
            .filter(
                Product.active.is_(True),
                Product.price > 0,
                Product.price >= low,
                Product.price <= high,
            )
            .order_by(Product.price.asc())
            .limit(80)
            .all()
        )
        if not candidates:
            # nearest products to target
            all_p = (
                Product.query
                .filter(Product.active.is_(True), Product.price > 0)
                .order_by(Product.price.asc())
                .limit(400)
                .all()
            )
            all_p.sort(key=lambda x: abs(float(x.price or 0) - target))
            candidates = all_p[:15]
        if not candidates:
            flash("No products available near that amount.", "danger")
            return redirect(url_for("admin.view_user", user_id=user.id))
        # Display product only — prefer closest to target (charge uses target, not catalog)
        candidates.sort(key=lambda x: abs(float(x.price or 0) - target))
        p1 = candidates[0]

    # Use ADMIN TARGET as the charged combo amount (catalog price is display only).
    # This fixes cases where no product exists near 900k and nearest was ~16k.
    catalog_price = float(p1.price or 0)
    price = float(target)  # amount deducted from user = what admin entered
    if price <= 0:
        price = catalog_price

    # Cancel previous pending combos
    Combo.query.filter_by(user_id=user.id, status="Pending", active=True).update(
        {"active": False, "status": "Cancelled"}
    )

    combo = Combo(
        user_id=user.id,
        product1_id=p1.id,
        product1_name=p1.name,
        product1_price=price,
        product1_image=getattr(p1, "image_url", None) or getattr(p1, "image", None),
        amount=price,
        trigger_task=max(1, trigger_task),
        status="Pending",
        active=True,
        notes=notes or f"Target {target:,.0f} · display product catalog {catalog_price:,.0f} · bal {bal:,.0f}",
    )
    # optional fields if model has them
    for attr, val in (
        ("product2_id", None),
        ("product2_name", None),
        ("product2_price", None),
    ):
        if hasattr(combo, attr):
            setattr(combo, attr, val)

    # ALWAYS charge admin target (never catalog price)
    charge = float(target)
    if charge <= 0:
        charge = float(p1.price or 0)
    combo.amount = charge
    combo.product1_price = charge
    if hasattr(combo, "notes") and not notes:
        combo.notes = f"CHARGE={charge:,.0f} (target) · catalog display was {float(p1.price or 0):,.0f}"

    db.session.add(combo)
    db.session.commit()

    flash(
        f"Combo assigned: {p1.name} will CHARGE {charge:,.0f} "
        f"(your target {target:,.0f}). Catalog price {float(p1.price or 0):,.0f} is display only. "
        f"Balance {bal:,.0f} → after trigger ~{bal - charge:,.0f}. "
        f"Auto at task #{combo.trigger_task}.",
        "success",
    )
    if "combos" in (request.referrer or "") or request.form.get("from_manager"):
        return redirect(url_for("admin.combos"))
    return redirect(url_for("admin.view_user", user_id=user.id))


@admin_bp.route("/combos/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_combo(id):

    combo = Combo.query.get_or_404(id)

    users = User.query.order_by(
        User.username
    ).all()

    if request.method == "POST":

        combo.user_id = request.form.get(
            "user_id",
            type=int
        )

        combo.trigger_task = request.form.get(
            "trigger_task",
            type=int
        )

        combo.amount = request.form.get(
            "amount",
            type=float
        )

        combo.combo_type = request.form.get(
            "combo_type"
        )

        combo.tasks_required = request.form.get(
            "tasks_required",
            type=int
        )

        combo.notes = request.form.get(
            "notes"
        )

        db.session.commit()

        flash(
            "Combo updated.",
            "success"
        )

        return redirect(
            url_for("admin.combos")
        )

    return render_template(
        "admin/combo_form.html",
        combo=combo,
        users=users
    )
# ==========================================================
# TRIGGER COMBO
# ==========================================================
@admin_bp.route("/combos/<int:combo_id>/trigger", methods=["POST", "GET"])
@login_required
@admin_required
def trigger_combo(combo_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    _c = Combo.query.get_or_404(combo_id)
    if assert_can_manage(_c.user_id) is None:
        return redirect(url_for("admin.users"))

    """Manual trigger — same logic as auto-trigger at configured task number."""
    combo = Combo.query.get_or_404(combo_id)
    user = combo.user
    from services.combo_service import ComboService
    ok, msg = ComboService.apply_trigger(combo)
    if not ok:
        flash(msg, "warning")
    else:
        flash(msg, "success")
    return redirect(url_for("admin.view_user", user_id=user.id))


@admin_bp.route("/combos/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_combo(id):

    combo = Combo.query.get_or_404(id)

    db.session.delete(combo)

    db.session.commit()

    flash(
        "Combo deleted.",
        "success"
    )

    return redirect(
        url_for("admin.combos")
    )
# ==========================================================
# REMOVE COMBO
# ==========================================================
@admin_bp.route("/users/<int:user_id>/remove-combo", methods=["POST"])
@login_required
@admin_required
def remove_combo(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    user = User.query.get_or_404(user_id)

    user.combo_active = False
    user.combo_completed = False
    user.combo_started_at = None

    db.session.commit()

    flash("Combo removed.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))


# ==========================================================
# RESET DAILY TASKS
# ==========================================================
@admin_bp.route("/users/<int:user_id>/reset-tasks", methods=["POST"])
@login_required
@admin_required
def reset_tasks(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))

    user = User.query.get_or_404(user_id)
    Task.query.filter_by(user_id=user.id, status="assigned").update({"status": "cancelled"})
    user.tasks_completed_today = 0
    user.daily_sets_completed = 0
    user.mandatory_completed = False
    user.daily_limit_reached = False
    user.must_withdraw_today = False
    user.withdrawal_completed_today = False
    user.negative_today = False
    user.set2_unlocked = False
    user.last_daily_reset = None
    db.session.commit()
    flash("Daily tasks reset for this user.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))
# ==========================================================
# RESET COMBO
# ==========================================================
@admin_bp.route("/users/<int:user_id>/reset-combo", methods=["POST"])
@login_required
@admin_required
def reset_combo(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))

    user = User.query.get_or_404(user_id)

    user.combo_active = False
    user.combo_completed = False
    user.combo_started_at = None

    db.session.commit()

    flash("Combo reset.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))


# ==========================================================
# RESET SPIN WHEEL
# ==========================================================
@admin_bp.route("/users/<int:user_id>/reset-spin", methods=["POST"])
@login_required
@admin_required
def reset_spin(user_id):
    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))

    user = User.query.get_or_404(user_id)

    user.daily_spins_used = 0

    db.session.commit()

    flash("Spin wheel reset.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))
@admin_bp.route("/users/<int:user_id>/unlock-set2", methods=["POST", "GET"])
@login_required
@admin_required
def unlock_set2(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))

    from services.task_service import TaskService
    user = User.query.get_or_404(user_id)
    ok, msg = TaskService.admin_unlock_set2(user)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("admin.view_user", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/send-notification", methods=["POST"])
@login_required
@admin_required
def send_notification(user_id):
    user = User.query.get_or_404(user_id)
    title = (request.form.get("title") or "").strip() or "Message from Admin"
    message = (request.form.get("message") or "").strip()
    if not message:
        flash("Notification message is required.", "danger")
        return redirect(url_for("admin.view_user", user_id=user.id))
    try:
        from services.notification_service import NotificationService
        NotificationService.send(user, title, message)
    except Exception:
        n = Notification(user_id=user.id, title=title, message=message)
        db.session.add(n)
        db.session.commit()
    flash("Notification sent.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))

# ==========================================================
# PRODUCTS
# ==========================================================

@admin_bp.route("/users/<int:user_id>/reset-withdraw-pin", methods=["POST"])
@login_required
@admin_required
def reset_withdraw_pin(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))

    """Admin resets withdraw PIN to default 1234."""
    user = User.query.get_or_404(user_id)
    user.set_withdraw_pin("1234")
    db.session.add(user)
    db.session.commit()
    flash("Withdraw PIN reset to 1234. User must enter 1234 on withdraw.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))

@admin_bp.route("/products")
@login_required
@admin_required
def products():
    page = request.args.get("page", 1, type=int)
    search = (request.args.get("search") or "").strip()
    q = Product.query
    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                Product.name.ilike(like),
                Product.category.ilike(like),
                Product.description.ilike(like),
            )
        )
    products = q.order_by(Product.price.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    total_all = Product.query.count()
    return render_template(
        "admin/products.html",
        products=products,
        total_all=total_all,
        search=search,
    )


@admin_bp.route("/products/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_product():
    if request.method == "POST":
        product = Product(
            name=request.form.get("name"),
            description=request.form.get("description"),
            image=request.form.get("image"),
            category=request.form.get("category"),
            partner_id=request.form.get(
                "partner_id",
                type=int
            ),
            price=request.form.get(
                "price",
                type=float
            ),
            commission=request.form.get(
                "commission",
                type=float
            ),
            stock=request.form.get(
                "stock",
                type=int
            ),
            active=True
        )
        db.session.add(product)
        db.session.commit()
        flash(
            "Product created successfully.",
            "success"
        )
        return redirect(
            url_for("admin.products")
        )
    return render_template(
        "admin/product_form.html",
        partners=Partner.query.order_by(Partner.name).all(),
        product=None
    )


@admin_bp.route("/products/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    if request.method == "POST":
        product.name = request.form.get("name")
        product.description = request.form.get("description")
        product.image = request.form.get("image")
        product.category = request.form.get("category")
        product.partner_id = request.form.get(
            "partner_id",
            type=int
        )
        product.price = request.form.get(
            "price",
            type=float
        )
        product.commission = request.form.get(
            "commission",
            type=float
        )
        product.stock = request.form.get(
            "stock",
            type=int
        )
        db.session.commit()
        flash(
            "Product updated successfully.",
            "success"
        )
        return redirect(
            url_for("admin.products")
        )
    return render_template(
        "admin/product_form.html",
        product=product,
        partners=Partner.query.order_by(Partner.name).all()
    )


@admin_bp.route("/products/<int:id>/toggle")
@login_required
@admin_required
def toggle_product(id):
    product = Product.query.get_or_404(id)
    product.active = not product.active
    db.session.commit()
    flash(
        "Product updated.",
        "success"
    )
    return redirect(
        url_for("admin.products")
    )


@admin_bp.route("/products/<int:id>/delete")
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash(
        "Product deleted.",
        "success"
    )
    return redirect(
        url_for("admin.products")
    )


# ==========================================================
# DEPOSITS
# ==========================================================
@admin_bp.route("/deposits")
@login_required
@admin_required
def deposits():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    query = Deposit.query
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        downline = get_downline_ids(current_user.id)
        query = query.filter(Deposit.user_id.in_(list(downline) or [-1]))
        # Agents only see Pending for support
        if not status:
            status = "Pending"
    if status:
        query = query.filter(
            Deposit.status == status
        )
    deposits = query.order_by(
        Deposit.created_at.desc()
    ).paginate(
        page=page,
        per_page=20,
        error_out=False
    )
    return render_template(
        "admin/deposits.html",
        deposits=deposits,
        status=status
    )


@admin_bp.route("/deposit/<int:deposit_id>/approve")
@login_required
@admin_required
def approve_deposit(deposit_id):
    deposit = Deposit.query.get_or_404(deposit_id)
    if deposit.status == "Approved":
        flash("Deposit already approved.", "warning")
        return redirect(url_for("admin.deposits"))

    user = User.query.get(deposit.user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.deposits"))

    amount = float(deposit.amount or 0)
    before = float(user.available_balance or 0)
    user.available_balance = before + amount

    # Permanent history stays in wallet_transactions
    tx = WalletTransaction(
        user_id=user.id,
        amount=amount,
        transaction_type="deposit",
        description=(
            f"Deposit approved · {deposit.payment_method or 'Pay'} · "
            f"Ref {deposit.transaction_id or deposit.id}"
        ),
        balance_before=before,
        balance_after=float(user.available_balance),
    )
    db.session.add(tx)

    # Referral 10%
    if user.referred_by_id:
        ref = User.query.get(user.referred_by_id)
        if ref and amount > 0:
            bonus = round(amount * 0.10, 0)
            rb = float(ref.available_balance or 0)
            ref.available_balance = rb + bonus
            ref.referral_income = (ref.referral_income or 0) + bonus
            db.session.add(WalletTransaction(
                user_id=ref.id,
                amount=bonus,
                transaction_type="referral_bonus",
                description=f"10% of deposit by {user.username}",
                balance_before=rb,
                balance_after=float(ref.available_balance),
            ))

    # Keep deposit row for admin history / accountability
    deposit.status = "Approved"
    try:
        deposit.approved_by = current_user.id
    except Exception:
        pass
    try:
        from datetime import datetime
        deposit.approved_at = datetime.utcnow()
    except Exception:
        pass

    # Commit money + status first so notifications cannot poison this transaction
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Approve failed: {e}", "danger")
        return redirect(url_for("admin.deposits"))

    try:
        from helpers.currency import money as _money
        amt_txt = _money(user, amount)
    except Exception:
        amt_txt = f"{amount:,.0f}"

    # Notifications after commit — never rollback the money transaction
    try:
        from services.notification_service import NotificationService
        NotificationService.send(
            user,
            "Deposit Approved",
            f"{amt_txt} credited. Receipt in Wallet history.",
        )
        db.session.commit()
    except Exception as e:
        print("deposit notify:", e)
        try:
            db.session.rollback()
        except Exception:
            pass

    try:
        from services.engagement_service import send_outbound_alert
        send_outbound_alert(
            user,
            "Deposit approved",
            f"Your deposit of {amt_txt} has been approved and credited to your wallet.",
        )
    except Exception as e:
        print("deposit approve telegram:", e)

    try:
        from services.admin_alerts import alert_deposit
        alert_deposit(user, deposit)
    except Exception:
        pass

    flash("Deposit approved and credited.", "success")
    return redirect(url_for("admin.deposits"))


@admin_bp.route("/deposit/<int:deposit_id>/reject")
@login_required
@admin_required
def reject_deposit(deposit_id):

    deposit = Deposit.query.get_or_404(deposit_id)

    deposit.status = "Rejected"

    db.session.commit()

    flash("Deposit rejected.", "danger")

    return redirect(url_for("admin.deposits"))


# ==========================================================
# WITHDRAWALS
# ==========================================================
@admin_bp.route("/withdrawals")
@login_required
@admin_required
def withdrawals():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    query = Withdrawal.query
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        downline = get_downline_ids(current_user.id)
        query = query.filter(Withdrawal.user_id.in_(list(downline) or [-1]))
        if not status:
            status = "Pending"
    if status:
        query = query.filter(Withdrawal.status == status)
    withdrawals = query.order_by(
        Withdrawal.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    today = datetime.utcnow().date()
    pending = Withdrawal.query.filter_by(status="Pending").count()
    approved_today = Withdrawal.query.filter(
        Withdrawal.status == "Approved",
        func.date(Withdrawal.created_at) == today,
    ).count()
    rejected = Withdrawal.query.filter_by(status="Rejected").count()
    today_amount = (
        db.session.query(func.coalesce(func.sum(Withdrawal.amount), 0))
        .filter(
            Withdrawal.status == "Approved",
            func.date(Withdrawal.created_at) == today,
        )
        .scalar()
        or 0
    )

    return render_template(
        "admin/withdrawals.html",
        withdrawals=withdrawals,
        status=status,
        pending=pending,
        approved_today=approved_today,
        rejected=rejected,
        today_amount=float(today_amount),
    )


@admin_bp.route("/withdrawals/<int:withdrawal_id>/processing")
@login_required
@admin_required
def mark_withdrawal_processing(withdrawal_id):
    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)
    if withdrawal.status != "Pending":
        flash("Only pending withdrawals can move to processing.", "warning")
        return redirect(url_for("admin.withdrawals"))
    withdrawal.status = "Processing"
    if hasattr(withdrawal, "reviewed_by"):
        withdrawal.reviewed_by = current_user.id
    if hasattr(withdrawal, "reviewed_at"):
        from datetime import datetime
        withdrawal.reviewed_at = datetime.utcnow()
    db.session.commit()
    try:
        from services.notification_service import NotificationService
        NotificationService.send(
            withdrawal.user_id if hasattr(withdrawal, "user_id") else withdrawal.user,
            "Withdrawal processing",
            f"Your withdrawal of {float(withdrawal.amount):,.0f} is being processed.",
        )
    except Exception:
        pass
    flash("Marked as processing.", "success")
    return redirect(url_for("admin.withdrawals"))


@admin_bp.route("/withdrawals/<int:withdrawal_id>/approve")
@login_required
@admin_required
def approve_withdrawal(withdrawal_id):
    from services.wallet_service import WalletService
    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)
    if withdrawal.status not in ("Pending", "Processing"):
        flash("Already reviewed.", "warning")
        return redirect(url_for("admin.withdrawals"))
    try:
        ok = WalletService.approve_withdrawal(withdrawal, current_user)
        if ok:
            try:
                if getattr(withdrawal, "status", None) in ("Pending", "Processing"):
                    withdrawal.status = "Approved"
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f"Approve failed: {e}", "danger")
                return redirect(url_for("admin.withdrawals"))
            try:
                from services.engagement_service import send_outbound_alert
                from helpers.currency import money as _money
                u = getattr(withdrawal, "user", None) or User.query.get(withdrawal.user_id)
                if u:
                    send_outbound_alert(u, "Withdrawal approved", f"Your withdrawal of {_money(u, float(withdrawal.amount or 0))} was approved.")
            except Exception as e:
                print("withdraw approve telegram:", e)
            flash("Withdrawal approved.", "success")
        else:
            flash("Could not approve withdrawal.", "danger")
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash(f"Approve error: {e}", "danger")
    return redirect(url_for("admin.withdrawals"))


@admin_bp.route("/withdrawals/<int:withdrawal_id>/reject")
@login_required
@admin_required
def reject_withdrawal(withdrawal_id):
    from services.wallet_service import WalletService
    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)
    if withdrawal.status not in ("Pending", "Processing"):
        flash("Already reviewed.", "warning")
        return redirect(url_for("admin.withdrawals"))
    ok = WalletService.reject_withdrawal(withdrawal, current_user)
    if ok:
        flash("Withdrawal rejected and balance refunded.", "success")
    else:
        flash("Could not reject withdrawal.", "danger")
    return redirect(url_for("admin.withdrawals"))


@admin_bp.route("/withdrawals/<int:withdrawal_id>/paid")
@login_required
@admin_required
def mark_withdrawal_paid(withdrawal_id):
    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)
    if withdrawal.status not in ("Approved", "Pending"):
        flash("Cannot mark this withdrawal as paid.", "warning")
        return redirect(url_for("admin.withdrawals"))
    withdrawal.status = "Paid"
    withdrawal.reviewed_by = current_user.id
    withdrawal.reviewed_at = datetime.utcnow()
    db.session.commit()
    try:
        from services.notification_service import NotificationService
        NotificationService.send(
            withdrawal.user,
            "Withdrawal Paid",
            f"Your withdrawal of UGX {float(withdrawal.amount):,.0f} has been paid."
        )
    except Exception:
        pass
    flash("Marked as paid.", "success")
    return redirect(url_for("admin.withdrawals"))


# ==========================================================
# MEMBERSHIPS
# ==========================================================
from models.membership import Membership


@admin_bp.route("/memberships")
@login_required
@admin_required
def memberships():
    memberships = Membership.query.order_by(
        Membership.price.asc()
    ).all()
    return render_template(
        "admin/memberships.html",
        memberships=memberships
    )


@admin_bp.route("/memberships/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_membership():
    if request.method == "POST":
        membership = Membership(
            name=request.form.get("name"),
            price=request.form.get(
                "price",
                type=float
            ),
            daily_tasks=request.form.get(
                "daily_tasks",
                type=int
            ),
            tasks_per_set=request.form.get(
                "tasks_per_set",
                type=int
            ),
            daily_sets=request.form.get(
                "daily_sets",
                type=int
            ),
            commission_percent=request.form.get(
                "commission_percent",
                type=float
            ) or 15.0,
            combo_probability=request.form.get(
                "combo_probability",
                type=int
            ),
            max_product_price=request.form.get(
                "max_product_price",
                type=float
            ),
            withdrawal_limit=request.form.get(
                "withdrawal_limit",
                type=float
            ),
            minimum_deposit=request.form.get(
                "minimum_deposit",
                type=float
            ),
            referral_bonus=request.form.get(
                "referral_bonus",
                type=float
            ),
            active=True
        )
        db.session.add(membership)
        db.session.commit()
        flash(
            "Membership created successfully.",
            "success"
        )
        return redirect(
            url_for("admin.memberships")
        )
    return render_template(
        "admin/membership_form.html",
        membership=None
    )


@admin_bp.route("/memberships/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_membership(id):
    membership = Membership.query.get_or_404(id)
    if request.method == "POST":
        membership.name = request.form.get("name")
        membership.price = request.form.get(
            "price",
            type=float
        )
        membership.daily_tasks = request.form.get(
            "daily_tasks",
            type=int
        )
        membership.tasks_per_set = request.form.get(
            "tasks_per_set",
            type=int
        )
        membership.daily_sets = request.form.get(
            "daily_sets",
            type=int
        )
        membership.commission_percent = request.form.get(
            "commission_percent",
            type=float
        ) or membership.commission_percent or 15.0
        membership.combo_probability = request.form.get(
            "combo_probability",
            type=int
        )
        membership.max_product_price = request.form.get(
            "max_product_price",
            type=float
        )
        membership.withdrawal_limit = request.form.get(
            "withdrawal_limit",
            type=float
        )
        membership.minimum_deposit = request.form.get(
            "minimum_deposit",
            type=float
        )
        membership.referral_bonus = request.form.get(
            "referral_bonus",
            type=float
        )
        db.session.commit()
        flash(
            "Membership updated successfully.",
            "success"
        )
        return redirect(
            url_for("admin.memberships")
        )
    return render_template(
        "admin/membership_form.html",
        membership=membership
    )
@admin_bp.route("/users/<int:user_id>/membership", methods=["POST"])
@login_required
@admin_required
def change_membership(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))


    user = User.query.get_or_404(user_id)

    membership_id = request.form.get(
        "membership_id",
        type=int
    )

    membership = Membership.query.get_or_404(
        membership_id
    )

    user.membership_id = membership.id

    db.session.commit()

    flash(
        f"{user.username} is now on {membership.name}.",
        "success"
    )

    return redirect(
        url_for(
            "admin.view_user",
            user_id=user.id
        )
    )

@admin_bp.route("/memberships/<int:id>/toggle")
@login_required
@admin_required
def toggle_membership(id):
    membership = Membership.query.get_or_404(id)
    membership.active = not membership.active
    db.session.commit()
    flash(
        "Membership updated.",
        "success"
    )
    return redirect(
        url_for("admin.memberships")
    )


@admin_bp.route("/memberships/<int:id>/delete")
@login_required
@admin_required
def delete_membership(id):
    membership = Membership.query.get_or_404(id)
    db.session.delete(membership)
    db.session.commit()
    flash(
        "Membership deleted.",
        "success"
    )
    return redirect(
        url_for("admin.memberships")
    )


# =====================================================
# SETTINGS
# =====================================================
from models.settings import Settings


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@full_admin_required
def settings():
    """Main admin system settings (site name, telegram, toggles)."""
    from models.settings import Settings
    from sqlalchemy import text, inspect

    # Ensure optional columns exist (Postgres + SQLite)
    try:
        insp = inspect(db.engine)
        if "settings" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("settings")}
            dialect = db.engine.dialect.name
            for col, typ in (
                ("admin_telegram_chat_ids", "TEXT"),
                ("telegram_bot_token", "VARCHAR(120)"),
                ("interest_enabled", "BOOLEAN DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN DEFAULT 0"),
                ("interest_min_ugx", "DOUBLE PRECISION DEFAULT 30000" if dialect == "postgresql" else "FLOAT DEFAULT 30000"),
                ("interest_rate", "DOUBLE PRECISION DEFAULT 5" if dialect == "postgresql" else "FLOAT DEFAULT 5"),
            ):
                if col not in cols:
                    if dialect == "postgresql":
                        db.session.execute(text(f"ALTER TABLE settings ADD COLUMN IF NOT EXISTS {col} {typ}"))
                    else:
                        db.session.execute(text(f"ALTER TABLE settings ADD COLUMN {col} {typ}"))
                    db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("settings cols:", e)

    settings = Settings.query.first()
    if not settings:
        settings = Settings(site_name="Taskmill")
        db.session.add(settings)
        db.session.commit()

    if request.method == "POST":
        try:
            settings.site_name = (request.form.get("site_name") or settings.site_name or "Taskmill").strip()[:100]
            settings.site_url = (request.form.get("site_url") or "").strip() or None
            if hasattr(settings, "registration_enabled"):
                settings.registration_enabled = request.form.get("registration_enabled") in ("on", "1", "true", "yes")
            if hasattr(settings, "deposits_enabled"):
                settings.deposits_enabled = request.form.get("deposits_enabled") in ("on", "1", "true", "yes")
            if hasattr(settings, "withdrawals_enabled"):
                settings.withdrawals_enabled = request.form.get("withdrawals_enabled") in ("on", "1", "true", "yes")
            settings.maintenance = request.form.get("maintenance") in ("on", "1", "true", "yes")
            token = (request.form.get("telegram_bot_token") or "").strip() or None
            try:
                settings.telegram_bot_token = token
            except Exception:
                pass
            admin_ids = (request.form.get("admin_telegram_chat_ids") or "").strip() or None
            try:
                settings.admin_telegram_chat_ids = admin_ids
            except Exception:
                # column missing on mapped class — raw SQL
                try:
                    db.session.execute(
                        text("UPDATE settings SET admin_telegram_chat_ids = :v WHERE id = :id"),
                        {"v": admin_ids, "id": settings.id},
                    )
                except Exception as e2:
                    print("admin_telegram_chat_ids save:", e2)
            db.session.commit()
            flash("Settings saved.", "success")
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            flash(f"Could not save settings: {e}", "danger")
            print("settings save:", e)
        return redirect(url_for("admin.settings"))

    return render_template("admin/settings.html", settings=settings)





# ==========================================================
# SUPPORT
# ==========================================================
from models.support import Support


@admin_bp.route("/support", methods=["GET", "POST"])
@login_required
@admin_required
def support():
    support = Support.query.first()
    if not support:
        support = Support()
        db.session.add(support)
        db.session.commit()
    if request.method == "POST":
        support.whatsapp1 = request.form.get("whatsapp1")
        support.whatsapp2 = request.form.get("whatsapp2")
        support.telegram1 = request.form.get("telegram1")
        support.telegram2 = request.form.get("telegram2")
        support.livechat = request.form.get("livechat")
        support.whatsapp1_enabled = (
            request.form.get("whatsapp1_enabled") == "on"
        )
        support.whatsapp2_enabled = (
            request.form.get("whatsapp2_enabled") == "on"
        )
        support.telegram1_enabled = (
            request.form.get("telegram1_enabled") == "on"
        )
        support.telegram2_enabled = (
            request.form.get("telegram2_enabled") == "on"
        )
        support.livechat_enabled = (
            request.form.get("livechat_enabled") == "on"
        )
        support.updated_at = datetime.utcnow()
        db.session.commit()
        flash(
            "Support settings updated successfully.",
            "success"
        )
        return redirect(url_for("admin.support"))
    return render_template(
        "admin/support.html",
        support=support
    )


# ==========================================================
# NOTIFICATIONS
# ==========================================================
@admin_bp.route("/notifications")
@login_required
@admin_required
def notifications():
    page = request.args.get("page", 1, type=int)
    notifications = (
        Notification.query
        .order_by(Notification.created_at.desc())
        .paginate(page=page, per_page=30, error_out=False)
    )
    users = User.query.order_by(User.username.asc()).limit(500).all()
    total = Notification.query.count()
    unread = Notification.query.filter_by(is_read=False).count()
    return render_template(
        "admin/notifications.html",
        notifications=notifications,
        users=users,
        total=total,
        unread=unread,
    )


@admin_bp.route("/notifications/send", methods=["POST"])
@login_required
@admin_required
def send_broadcast_notification():
    title = (request.form.get("title") or "").strip()
    message = (request.form.get("message") or "").strip()
    target = request.form.get("target") or "all"
    user_id = request.form.get("user_id", type=int)

    if not title or not message:
        flash("Title and message are required.", "danger")
        return redirect(url_for("admin.notifications"))

    if target == "one" and user_id:
        user = User.query.get(user_id)
        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("admin.notifications"))
        recipients = [user]
    else:
        recipients = User.query.filter_by(is_admin=False).all()
        if not recipients:
            recipients = User.query.all()

    count = 0
    for user in recipients:
        n = Notification(
            user_id=user.id,
            title=title,
            message=message,
            is_read=False,
            is_broadcast=True,
        )
        db.session.add(n)
        count += 1
    db.session.commit()

    flash(f"Notification sent to {count} user(s).", "success")
    return redirect(url_for("admin.notifications"))


@admin_bp.route("/notifications/<int:id>/delete", methods=["POST", "GET"])
@login_required
@admin_required
def delete_notification(id):
    notification = Notification.query.get_or_404(id)
    db.session.delete(notification)
    db.session.commit()
    flash("Notification deleted.", "success")
    return redirect(url_for("admin.notifications"))


@admin_bp.route("/notifications/clear-read", methods=["POST"])
@login_required
@admin_required
def clear_read_notifications():
    Notification.query.filter_by(is_read=True).delete()
    db.session.commit()
    flash("Read notifications cleared.", "success")
    return redirect(url_for("admin.notifications"))


# ==========================================================
# REPORTS
# ==========================================================
@admin_bp.route("/reports")
@login_required
@admin_required
def reports():
    total_users = User.query.count()
    active_users = User.query.filter_by(
        is_active=True
    ).count()
    blocked_users = User.query.filter_by(
        is_blocked=True
    ).count()
    total_deposits = (
        db.session.query(
            func.sum(Deposit.amount)
        ).scalar()
        or 0
    )
    total_withdrawals = (
        db.session.query(
            func.sum(Withdrawal.amount)
        ).scalar()
        or 0
    )
    total_revenue = (
        db.session.query(
            func.sum(
                WalletTransaction.amount
            )
        ).filter(
            WalletTransaction.transaction_type == "commission"
        ).scalar()
        or 0
    )
    memberships = Membership.query.all()
    membership_labels = []
    membership_values = []
    for m in memberships:
        membership_labels.append(m.name)
        membership_values.append(len(m.users))
    return render_template(
        "admin/reports.html",
        total_users=total_users,
        active_users=active_users,
        blocked_users=blocked_users,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        total_revenue=total_revenue,
        membership_labels=membership_labels,
        membership_values=membership_values
    )


# ==========================================================
# ANNOUNCEMENTS
# ==========================================================
@admin_bp.route("/announcements")
@login_required
@admin_required
def announcements():
    announcements = Announcement.query.order_by(
        Announcement.created_at.desc()
    ).all()
    return render_template(
        "admin/announcements.html",
        announcements=announcements
    )


@admin_bp.route("/announcements/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_announcement():
    if request.method == "POST":
        announcement = Announcement(
            title=request.form.get("title"),
            message=request.form.get("message"),
            active=True
        )
        db.session.add(announcement)
        db.session.commit()
        flash(
            "Announcement created successfully.",
            "success"
        )
        return redirect(url_for("admin.announcements"))
    return render_template(
        "admin/announcement_form.html",
        announcement=None
    )


@admin_bp.route("/announcements/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_announcement(id):
    announcement = Announcement.query.get_or_404(id)
    if request.method == "POST":
        announcement.title = request.form.get("title")
        announcement.message = request.form.get("message")
        db.session.commit()
        flash(
            "Announcement updated successfully.",
            "success"
        )
        return redirect(url_for("admin.announcements"))
    return render_template(
        "admin/announcement_form.html",
        announcement=announcement
    )


@admin_bp.route("/announcements/<int:id>/toggle")
@login_required
@admin_required
def toggle_announcement(id):
    announcement = Announcement.query.get_or_404(id)
    announcement.active = not announcement.active
    db.session.commit()
    flash(
        "Announcement updated.",
        "success"
    )
    return redirect(url_for("admin.announcements"))


@admin_bp.route("/announcements/<int:id>/delete")
@login_required
@admin_required
def delete_announcement(id):
    announcement = Announcement.query.get_or_404(id)
    db.session.delete(announcement)
    db.session.commit()
    flash(
        "Announcement deleted.",
        "success"
    )
    return redirect(url_for("admin.announcements"))


# ==========================================================
# BANNERS
# ==========================================================
@admin_bp.route("/banners")
@login_required
@admin_required
def banners():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "")
    query = Banner.query
    if search:
        query = query.filter(
            Banner.title.ilike(f"%{search}%")
        )
    banners = query.order_by(
        Banner.id.desc()
    ).paginate(
        page=page,
        per_page=15
    )
    return render_template(
        "admin/banners.html",
        banners=banners,
        search=search
    )


@admin_bp.route("/banners/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_banner():
    if request.method == "POST":
        banner = Banner(
            title=request.form.get("title"),
            image=request.form.get("image"),
            link=request.form.get("link"),
            active=True,
            created_at=datetime.utcnow()
        )
        db.session.add(banner)
        db.session.commit()
        flash(
            "Banner created successfully.",
            "success"
        )
        return redirect(url_for("admin.banners"))
    return render_template(
        "admin/banner_form.html",
        banner=None
    )


@admin_bp.route("/banners/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_banner(id):
    banner = Banner.query.get_or_404(id)
    if request.method == "POST":
        banner.title = request.form.get("title")
        banner.image = request.form.get("image")
        banner.link = request.form.get("link")
        db.session.commit()
        flash(
            "Banner updated.",
            "success"
        )
        return redirect(url_for("admin.banners"))
    return render_template(
        "admin/banner_form.html",
        banner=banner
    )


@admin_bp.route("/banners/<int:id>/toggle")
@login_required
@admin_required
def toggle_banner(id):
    banner = Banner.query.get_or_404(id)
    banner.active = not banner.active
    db.session.commit()
    flash(
        "Banner updated.",
        "success"
    )
    return redirect(url_for("admin.banners"))


@admin_bp.route("/banners/<int:id>/delete")
@login_required
@admin_required
def delete_banner(id):
    banner = Banner.query.get_or_404(id)
    db.session.delete(banner)
    db.session.commit()
    flash(
        "Banner deleted.",
        "success"
    )
    return redirect(url_for("admin.banners"))


# ==========================================================
# PARTNERS
# ==========================================================
@admin_bp.route("/partners")
@login_required
@admin_required
def partners():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "")
    query = Partner.query
    if search:
        query = query.filter(
            Partner.name.ilike(f"%{search}%")
        )
    partners = query.order_by(
        Partner.id.desc()
    ).paginate(
        page=page,
        per_page=15
    )
    return render_template(
        "admin/partners.html",
        partners=partners,
        search=search
    )


@admin_bp.route("/partners/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_partner():
    if request.method == "POST":
        partner = Partner(
            name=request.form.get("name"),
            logo=request.form.get("logo"),
            website=request.form.get("website"),
            description=request.form.get("description"),
            active=True
        )
        db.session.add(partner)
        db.session.commit()
        flash(
            "Partner created successfully.",
            "success"
        )
        return redirect(url_for("admin.partners"))
    return render_template(
        "admin/partner_form.html",
        partner=None
    )


@admin_bp.route("/partners/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_partner(id):
    partner = Partner.query.get_or_404(id)
    if request.method == "POST":
        partner.name = request.form.get("name")
        partner.logo = request.form.get("logo")
        partner.website = request.form.get("website")
        partner.description = request.form.get("description")
        db.session.commit()
        flash(
            "Partner updated successfully.",
            "success"
        )
        return redirect(url_for("admin.partners"))
    return render_template(
        "admin/partner_form.html",
        partner=partner
    )


@admin_bp.route("/partners/<int:id>/toggle")
@login_required
@admin_required
def toggle_partner(id):
    partner = Partner.query.get_or_404(id)
    partner.active = not partner.active
    db.session.commit()
    flash(
        "Partner updated.",
        "success"
    )
    return redirect(url_for("admin.partners"))


@admin_bp.route("/partners/<int:id>/delete")
@login_required
@admin_required
def delete_partner(id):
    partner = Partner.query.get_or_404(id)
    db.session.delete(partner)
    db.session.commit()
    flash(
        "Partner deleted.",
        "success"
    )
    return redirect(url_for("admin.partners"))


# =====================================================
# WALLET MANAGEMENT
# =====================================================

@admin_bp.route("/wallets")
@login_required
@admin_required
def wallets():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "")
    query = User.query
    if search:
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    users = query.order_by(
        User.id.desc()
    ).paginate(
        page=page,
        per_page=20
    )
    return render_template(
        "admin/wallets.html",
        users=users,
        search=search
    )



# ==========================================================
# BULK DEPOSIT APPROVE
# ==========================================================
@admin_bp.route("/deposits/bulk-approve", methods=["POST"])
@login_required
@admin_required
def bulk_approve_deposits():
    """Approve many pending deposits; each gets in-app + Telegram alert."""
    ids = request.form.getlist("deposit_ids")
    ok = 0
    failed = 0
    for did in ids:
        try:
            deposit = Deposit.query.get(int(did))
        except Exception:
            failed += 1
            continue
        if not deposit or (deposit.status or "").lower() != "pending":
            continue
        try:
            user = User.query.get(deposit.user_id) or deposit.user
            if not user:
                failed += 1
                continue

            before = float(user.available_balance or 0)
            amount = float(deposit.amount or 0)
            user.available_balance = before + amount
            db.session.add(WalletTransaction(
                user_id=user.id,
                amount=amount,
                transaction_type="deposit",
                description=(
                    f"{deposit.payment_method or 'Deposit'} approved · "
                    f"Ref {deposit.transaction_id or deposit.id}"
                ),
                balance_before=before,
                balance_after=float(user.available_balance),
            ))
            deposit.status = "Approved"
            try:
                from datetime import datetime
                deposit.approved_at = datetime.utcnow()
                deposit.approved_by = current_user.id
            except Exception:
                pass

            try:
                from helpers.currency import money as _money
                amt_txt = _money(user, amount)
            except Exception:
                amt_txt = f"{amount:,.0f}"

            # In-app notification for depositor
            try:
                from services.notification_service import NotificationService
                NotificationService.send(
                    user,
                    "Deposit Approved",
                    f"{amt_txt} credited. Receipt in Wallet history.",
                )
            except Exception as e:
                print("bulk deposit notify:", e)

            # Telegram / email for depositor
            try:
                from services.engagement_service import send_outbound_alert
                send_outbound_alert(
                    user,
                    "Deposit approved",
                    f"Your deposit of {amt_txt} has been approved and credited to your wallet.",
                )
            except Exception as e:
                print("bulk deposit telegram:", e)

            # Referral 10% + notify referrer
            if user.referred_by_id and amount > 0:
                ref = User.query.get(user.referred_by_id)
                if ref:
                    bonus = round(amount * 0.10, 0)
                    rb = float(ref.available_balance or 0)
                    ref.available_balance = rb + bonus
                    ref.referral_income = (ref.referral_income or 0) + bonus
                    db.session.add(WalletTransaction(
                        user_id=ref.id,
                        amount=bonus,
                        transaction_type="referral_bonus",
                        description=f"10% of deposit by {user.username}",
                        balance_before=rb,
                        balance_after=float(ref.available_balance),
                    ))
                    try:
                        from helpers.currency import money as _money
                        bonus_txt = _money(ref, bonus)
                    except Exception:
                        bonus_txt = f"{bonus:,.0f}"
                    try:
                        from services.notification_service import NotificationService
                        NotificationService.send(
                            ref,
                            "Referral bonus",
                            f"You earned {bonus_txt} from {user.username}'s deposit.",
                        )
                    except Exception:
                        pass
                    try:
                        from services.engagement_service import send_outbound_alert
                        send_outbound_alert(
                            ref,
                            "Referral bonus",
                            f"You earned {bonus_txt} from {user.username}'s approved deposit.",
                        )
                    except Exception as e:
                        print("bulk referral telegram:", e)

            # Commit each deposit so one failure does not undo others
            db.session.commit()
            ok += 1
        except Exception as e:
            print("bulk approve", did, e)
            try:
                db.session.rollback()
            except Exception:
                pass
            failed += 1

    if ok and not failed:
        flash(f"Approved {ok} deposit(s). Users notified (app + Telegram).", "success")
    elif ok and failed:
        flash(f"Approved {ok} deposit(s); {failed} failed. Notified successful ones.", "warning")
    else:
        flash("No deposits were approved.", "warning")
    return redirect(url_for("admin.deposits", status="Pending"))


@admin_bp.route("/reports/daily")
@login_required
@admin_required
def daily_ops_report():
    from datetime import datetime as dt, timedelta
    today = dt.utcnow().date()
    try:
        date_from = dt.strptime(request.args.get("from") or today.isoformat(), "%Y-%m-%d").date()
    except ValueError:
        date_from = today
    try:
        date_to = dt.strptime(request.args.get("to") or today.isoformat(), "%Y-%m-%d").date()
    except ValueError:
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    new_users = User.query.filter(
        func.date(User.created_at) >= date_from,
        func.date(User.created_at) <= date_to,
    ).count()
    dep_pending = Deposit.query.filter_by(status="Pending").count()
    dep_approved = Deposit.query.filter(
        Deposit.status == "Approved",
        func.date(Deposit.approved_at) >= date_from,
        func.date(Deposit.approved_at) <= date_to,
    ).count()
    dep_sum = db.session.query(func.coalesce(func.sum(Deposit.amount), 0)).filter(
        Deposit.status == "Approved",
        func.date(Deposit.approved_at) >= date_from,
        func.date(Deposit.approved_at) <= date_to,
    ).scalar()
    wd_pending = Withdrawal.query.filter_by(status="Pending").count()
    wd_paid = Withdrawal.query.filter(
        Withdrawal.status.in_(["Approved", "Paid"]),
        func.date(Withdrawal.created_at) >= date_from,
        func.date(Withdrawal.created_at) <= date_to,
    ).count()
    wd_sum = db.session.query(func.coalesce(func.sum(Withdrawal.amount), 0)).filter(
        Withdrawal.status.in_(["Approved", "Paid"]),
        func.date(Withdrawal.created_at) >= date_from,
        func.date(Withdrawal.created_at) <= date_to,
    ).scalar()
    combos = Combo.query.filter(
        func.date(Combo.created_at) >= date_from,
        func.date(Combo.created_at) <= date_to,
    ).count()
    negative = User.query.filter(User.available_balance < 0).count()
    tasks_done = 0
    try:
        from models.task import Task
        tasks_done = Task.query.filter(
            Task.status == "completed",
            func.date(Task.completed_at) >= date_from,
            func.date(Task.completed_at) <= date_to,
        ).count()
    except Exception:
        pass

    return render_template(
        "admin/daily_report.html",
        today=today,
        date_from=date_from,
        date_to=date_to,
        new_users=new_users,
        dep_pending=dep_pending,
        dep_approved=dep_approved,
        dep_sum=float(dep_sum or 0),
        wd_pending=wd_pending,
        wd_paid=wd_paid,
        wd_sum=float(wd_sum or 0),
        combos=combos,
        negative=negative,
        tasks_done=tasks_done,
    )


# ==========================================================
# LUCKY SPIN — prizes & grants
# ==========================================================
@admin_bp.route("/spin-prizes", methods=["GET", "POST"])
@login_required
@admin_required
def spin_prizes():
    from models.spin import SpinPrize
    from models.membership import Membership
    if request.method == "POST":
        label = (request.form.get("label") or "").strip()
        prize_type = (request.form.get("prize_type") or "cash").strip()
        if not label:
            flash("Label required.", "danger")
            return redirect(url_for("admin.spin_prizes"))
        try:
            amount = float(request.form.get("amount") or 0)
        except ValueError:
            amount = 0
        membership_id = request.form.get("membership_id", type=int)
        weight = request.form.get("weight", type=int) or 10
        color = (request.form.get("color") or "#6366f1").strip()
        voucher_code = (request.form.get("voucher_code") or "").strip()
        voucher_note = (request.form.get("voucher_note") or "").strip()
        p = SpinPrize(
            label=label,
            prize_type=prize_type,
            amount=amount,
            membership_id=membership_id if prize_type == "membership" else None,
            voucher_code=voucher_code or None,
            voucher_note=voucher_note or None,
            weight=weight,
            color=color,
            active=True,
        )
        db.session.add(p)
        db.session.commit()
        flash("Prize added to wheel.", "success")
        return redirect(url_for("admin.spin_prizes"))

    prizes = SpinPrize.query.order_by(SpinPrize.sort_order, SpinPrize.id).all()
    memberships = Membership.query.order_by(Membership.price.asc()).all()
    return render_template(
        "admin/spin_prizes.html",
        prizes=prizes,
        memberships=memberships,
    )


@admin_bp.route("/spin-prizes/<int:prize_id>/toggle", methods=["POST"])
@login_required
@admin_required
def spin_prize_toggle(prize_id):
    from models.spin import SpinPrize
    p = SpinPrize.query.get_or_404(prize_id)
    p.active = not p.active
    db.session.commit()
    flash("Prize updated.", "success")
    return redirect(url_for("admin.spin_prizes"))


@admin_bp.route("/spin-prizes/<int:prize_id>/delete", methods=["POST"])
@login_required
@admin_required
def spin_prize_delete(prize_id):
    from models.spin import SpinPrize
    p = SpinPrize.query.get_or_404(prize_id)
    db.session.delete(p)
    db.session.commit()
    flash("Prize deleted.", "success")
    return redirect(url_for("admin.spin_prizes"))


@admin_bp.route("/users/<int:user_id>/grant-spin", methods=["POST"])
@login_required
@admin_required
def grant_spin(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))

    from models.spin import SpinGrant, SpinPrize
    user = User.query.get_or_404(user_id)
    spins = request.form.get("spins", type=int) or 1
    note = (request.form.get("note") or "").strip()
    selected = request.form.getlist("prize_ids")
    allowed = ",".join([s for s in selected if s.isdigit()]) or None
    grant = SpinGrant(
        user_id=user.id,
        spins_total=max(1, spins),
        spins_used=0,
        allowed_prize_ids=allowed,
        granted_by=current_user.id,
        note=note,
        active=True,
    )
    db.session.add(grant)
    try:
        from services.notification_service import NotificationService
        NotificationService.send(
            user,
            "Lucky Spin awarded",
            f"You received {spins} lucky spin(s). Open Lucky Spin to play!",
        )
    except Exception:
        pass
    db.session.commit()
    flash(f"Granted {spins} spin(s) to {user.username}.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))




@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_user():
    """Create a normal user or an admin (role-based)."""
    from models.membership import Membership
    memberships = Membership.query.order_by(Membership.price.asc()).all()
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        full_name = (request.form.get("full_name") or "").strip()
        password = request.form.get("password") or "12345678"
        role = (request.form.get("role") or "user").strip()
        membership_id = request.form.get("membership_id", type=int)
        if not username:
            flash("Username required.", "danger")
            return redirect(url_for("admin.create_user"))
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("admin.create_user"))
        if email and User.query.filter_by(email=email).first():
            flash("Email already exists.", "danger")
            return redirect(url_for("admin.create_user"))
        u = User(
            username=username,
            email=email or f"{username}@taskmill.local",
            phone=phone or None,
            full_name=full_name or username,
            is_admin=(role == "admin"),
            is_agent=(role == "agent"),
            is_active=True,
            is_blocked=False,
            membership_id=membership_id,
            country=request.form.get("country") or "Uganda",
            currency="UGX",
            currency_symbol="UGX",
        )
        u.set_password(password)
        if hasattr(u, "must_change_password"):
            u.must_change_password = True
        db.session.add(u)
        db.session.commit()
        flash(
            f"{'Admin' if role == 'admin' else 'User'} {username} created. Temp password: {password}",
            "success",
        )
        return redirect(url_for("admin.view_user", user_id=u.id))
    return render_template(
        "admin/create_user.html",
        memberships=memberships,
    )


# ==========================================================
# USER NOTES (agent + admin)
# ==========================================================
@admin_bp.route("/users/<int:user_id>/notes", methods=["POST"])
@login_required
@admin_required
def add_user_note(user_id):
    if assert_can_manage(user_id) is None:
        return redirect(url_for("admin.users"))
    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Note cannot be empty.", "warning")
        return redirect(url_for("admin.view_user", user_id=user_id))
    try:
        from models.user_note import UserNote
        note = UserNote(user_id=user_id, author_id=current_user.id, body=body[:4000])
        db.session.add(note)
        db.session.commit()
        log_staff_action("users", "note", target=str(user_id), description=body[:200])
        flash("Note saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Could not save note: {e}", "danger")
    return redirect(url_for("admin.view_user", user_id=user_id))


# ==========================================================
# TEAM REPORT (agent)
# ==========================================================
@admin_bp.route("/team-report")
@login_required
@admin_required
def team_report():
    from datetime import datetime as dt, timedelta
    from sqlalchemy import func
    from models.membership import Membership
    from models.deposit import Deposit
    from models.withdraw import Withdrawal
    from models.task import Task
    today = dt.utcnow().date()
    try:
        date_from = dt.strptime(request.args.get("from") or today.isoformat(), "%Y-%m-%d").date()
    except ValueError:
        date_from = today
    try:
        date_to = dt.strptime(request.args.get("to") or today.isoformat(), "%Y-%m-%d").date()
    except ValueError:
        date_to = today

    if getattr(current_user, "is_admin", False) and not request.args.get("agent_id"):
        # full admin without filter — redirect to agents hub
        return redirect(url_for("admin.agents_hub"))

    root_id = current_user.id
    if getattr(current_user, "is_admin", False):
        root_id = request.args.get("agent_id", type=int) or current_user.id

    downline = get_downline_ids(root_id)
    ids = list(downline) or [-1]

    team_count = len(downline)
    bal = db.session.query(func.coalesce(func.sum(User.available_balance), 0)).filter(User.id.in_(ids)).scalar() or 0
    dep_pending = Deposit.query.filter(Deposit.user_id.in_(ids), Deposit.status == "Pending").count()
    dep_sum = db.session.query(func.coalesce(func.sum(Deposit.amount), 0)).filter(
        Deposit.user_id.in_(ids), Deposit.status == "Approved",
        func.date(Deposit.created_at) >= date_from, func.date(Deposit.created_at) <= date_to,
    ).scalar() or 0
    wd_sum = db.session.query(func.coalesce(func.sum(Withdrawal.amount), 0)).filter(
        Withdrawal.user_id.in_(ids), Withdrawal.status.in_(["Approved", "Paid"]),
        func.date(Withdrawal.created_at) >= date_from, func.date(Withdrawal.created_at) <= date_to,
    ).scalar() or 0
    tasks_done = Task.query.filter(
        Task.user_id.in_(ids), Task.status == "completed",
        func.date(Task.completed_at) >= date_from, func.date(Task.completed_at) <= date_to,
    ).count()

    # membership breakdown for pie
    mem_rows = (
        db.session.query(Membership.name, func.count(User.id))
        .join(User, User.membership_id == Membership.id)
        .filter(User.id.in_(ids))
        .group_by(Membership.name)
        .all()
    )
    pie_labels = [r[0] for r in mem_rows] or ["None"]
    pie_values = [int(r[1]) for r in mem_rows] or [0]

    return render_template(
        "admin/team_report.html",
        team_count=team_count,
        total_balance=float(bal),
        dep_pending=dep_pending,
        dep_sum=float(dep_sum),
        wd_sum=float(wd_sum),
        tasks_done=tasks_done,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        pie_labels=pie_labels,
        pie_values=pie_values,
    )


# ==========================================================
# AGENTS HUB (full admin) — list, logs, charts
# ==========================================================
@admin_bp.route("/agents")
@login_required
@admin_required
def agents_hub():
    if not getattr(current_user, "is_admin", False):
        return redirect(url_for("admin.team_report"))

    from sqlalchemy import func
    from models.audit_log import AuditLog

    agents = User.query.filter_by(is_agent=True).order_by(User.username.asc()).all()
    rows = []
    bar_labels, bar_teams, bar_deps = [], [], []
    for a in agents:
        dl = get_downline_ids(a.id)
        ids = list(dl) or [-1]
        team_n = len(dl)
        bal = db.session.query(func.coalesce(func.sum(User.available_balance), 0)).filter(User.id.in_(ids)).scalar() or 0
        deps = Deposit.query.filter(Deposit.user_id.in_(ids), Deposit.status == "Pending").count()
        tasks = Task.query.filter(Task.user_id.in_(ids), Task.status == "completed").count()
        rows.append({
            "agent": a,
            "team": team_n,
            "balance": float(bal),
            "pending_deposits": deps,
            "tasks": tasks,
        })
        bar_labels.append(a.username)
        bar_teams.append(team_n)
        bar_deps.append(deps)

    # Recent agent actions only (table may not exist on older DBs)
    agent_ids = [a.id for a in agents]
    logs = []
    if agent_ids:
        try:
            logs = (
                AuditLog.query.filter(AuditLog.admin_id.in_(agent_ids))
                .order_by(AuditLog.created_at.desc())
                .limit(80)
                .all()
            )
        except Exception as e:
            print("agents_hub audit_logs:", e)
            try:
                db.session.rollback()
            except Exception:
                pass
            logs = []

    # Pie: share of team sizes
    pie_labels = bar_labels[:] or ["No agents"]
    pie_values = bar_teams[:] or [1]

    return render_template(
        "admin/agents.html",
        rows=rows,
        logs=logs,
        bar_labels=bar_labels,
        bar_teams=bar_teams,
        bar_deps=bar_deps,
        pie_labels=pie_labels,
        pie_values=pie_values,
    )


@admin_bp.route("/deposits/<int:deposit_id>/flag", methods=["POST"])
@login_required
@admin_required
def flag_deposit(deposit_id):
    d = Deposit.query.get_or_404(deposit_id)
    if assert_can_manage(d.user_id) is None:
        return redirect(url_for("admin.deposits"))
    note = (request.form.get("note") or "Verified by team leader").strip()[:255]
    d.flagged_by_id = current_user.id
    if hasattr(d, "flag_note"):
        d.flag_note = note
    db.session.commit()
    log_staff_action("deposits", "flag", target=str(deposit_id), description=note)
    flash("Deposit flagged for main admin review.", "success")
    return redirect(url_for("admin.deposits", status="Pending"))


@admin_bp.route("/users/<int:user_id>/freeze-wallet", methods=["POST"])
@login_required
@admin_required
def freeze_wallet(user_id):
    if _deny_agent_write():
        return redirect(url_for("admin.users"))

    if assert_can_manage(user_id) is None and not current_user.is_admin:
        return redirect(url_for("admin.users"))
    user = User.query.get_or_404(user_id)
    user.wallet_frozen = not bool(getattr(user, "wallet_frozen", False))
    db.session.commit()
    log_staff_action("wallet", "freeze" if user.wallet_frozen else "unfreeze", target=user.username)
    flash(f"Wallet {'frozen' if user.wallet_frozen else 'unfrozen'}.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))


@admin_bp.route("/export/team-users.csv")
@login_required
@admin_required
def export_team_users_csv():
    import csv
    from io import StringIO
    from flask import Response
    if getattr(current_user, "is_admin", False):
        q = User.query.filter_by(is_admin=False)
    else:
        ids = list(get_downline_ids(current_user.id)) or [-1]
        q = User.query.filter(User.id.in_(ids))
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "username", "email", "phone", "balance", "membership", "blocked", "created_at"])
    for u in q.order_by(User.id.asc()).limit(5000):
        w.writerow([
            u.id, u.username, u.email, u.phone or "",
            u.available_balance or 0,
            u.membership.name if u.membership else "",
            u.is_blocked, u.created_at,
        ])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=team_users.csv"})


@admin_bp.route("/leaderboard")
@login_required
@admin_required
def referral_leaderboard():
    leaders = []
    try:
        from sqlalchemy import func
        leaders = (
            User.query
            .filter(User.is_admin.is_(False))
            .filter((User.referral_count.isnot(None)) & (User.referral_count > 0))
            .order_by(User.referral_count.desc())
            .limit(50)
            .all()
        )
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("leaderboard query:", e)
        try:
            leaders = (
                User.query
                .order_by(User.id.desc())
                .limit(50)
                .all()
            )
            leaders = [u for u in leaders if int(getattr(u, "referral_count", 0) or 0) > 0]
            leaders.sort(key=lambda u: int(getattr(u, "referral_count", 0) or 0), reverse=True)
        except Exception as e2:
            try:
                db.session.rollback()
            except Exception:
                pass
            print("leaderboard fallback:", e2)
            leaders = []
    return render_template("admin/leaderboard.html", leaders=leaders)


@admin_bp.route("/stuck-users")
@login_required
@admin_required

@admin_bp.route("/users/<int:user_id>/unlock-pin", methods=["POST"])
@login_required
@admin_required
def unlock_withdraw_pin(user_id):
    user = User.query.get_or_404(user_id)
    if not can_manage_user(current_user, user):
        flash("Not allowed.", "danger")
        return redirect(url_for("admin.users"))
    try:
        user.unlock_withdraw_pin()
        flash(f"Withdraw PIN unlocked for {user.username}.", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.view_user", user_id=user.id))



@admin_bp.route("/proofs", methods=["GET", "POST"])
@login_required
@admin_required
def manage_proofs():
    from models.proof import WithdrawProof
    if request.method == "POST":
        row = WithdrawProof(
            amount_label=(request.form.get("amount_label") or "").strip()[:80],
            country=(request.form.get("country") or "").strip()[:60] or None,
            membership_name=(request.form.get("membership_name") or "").strip()[:60] or None,
            note=(request.form.get("note") or "").strip()[:200] or None,
            approved=True,
            created_by=current_user.id,
        )
        if not row.amount_label:
            flash("Amount label required (e.g. UGX ***2,500).", "warning")
        else:
            db.session.add(row)
            db.session.commit()
            flash("Proof published.", "success")
        return redirect(url_for("admin.manage_proofs"))
    rows = WithdrawProof.query.order_by(WithdrawProof.created_at.desc()).limit(50).all()
    return render_template("admin/proofs.html", proofs=rows)


@admin_bp.route("/proofs/<int:proof_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_proof(proof_id):
    from models.proof import WithdrawProof
    row = WithdrawProof.query.get_or_404(proof_id)
    db.session.delete(row)
    db.session.commit()
    flash("Proof removed.", "success")
    return redirect(url_for("admin.manage_proofs"))


def stuck_users():
    """Users who need attention: negative, idle, pending deposit, set2 locked."""
    from datetime import datetime, timedelta
    from models.deposit import Deposit
    from sqlalchemy import or_
    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)
    h12 = now - timedelta(hours=12)

    q = User.query.filter(User.is_admin.is_(False))
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        # agents: only downline — best effort flat referral
        q = q.filter(User.referred_by_id == current_user.id)

    users = q.order_by(User.id.desc()).limit(500).all()
    stuck = []
    for u in users:
        reasons = []
        if float(u.available_balance or 0) < 0:
            reasons.append("negative_balance")
        if getattr(u, "negative_today", False):
            reasons.append("combo_hold")
        if not getattr(u, "set2_unlocked", True) and int(u.daily_sets_completed or 0) >= 1:
            reasons.append("set2_locked")
        last = getattr(u, "last_login", None) or getattr(u, "updated_at", None)
        if last and last < day_ago and int(u.tasks_completed_today or 0) == 0:
            reasons.append("idle_24h")
        if int(u.tasks_completed_today or 0) == 0 and getattr(u, "membership_id", None) and float(u.available_balance or 0) >= 0:
            # funded-ish members with zero tasks today
            if float(u.available_balance or 0) >= 1000:
                reasons.append("no_tasks_today")
        pending = Deposit.query.filter_by(user_id=u.id, status="Pending").filter(Deposit.created_at <= h12).count()
        if pending:
            reasons.append("deposit_pending_12h")
        if reasons:
            stuck.append({"user": u, "reasons": reasons})

    return render_template("admin/stuck_users.html", stuck=stuck)


@admin_bp.route("/campaigns", methods=["GET", "POST"])
@login_required
@admin_required
def campaign_settings():
    from models.settings import Settings
    from datetime import datetime
    s = Settings.query.first()
    if not s:
        s = Settings(site_name="Taskmill")
        db.session.add(s)
        db.session.commit()
    if request.method == "POST":
        s.deposit_match_active = request.form.get("deposit_match_active") == "1"
        try:
            s.deposit_match_percent = float(request.form.get("deposit_match_percent") or 0)
        except ValueError:
            s.deposit_match_percent = 0
        ends = (request.form.get("deposit_match_ends_at") or "").strip()
        if ends:
            try:
                s.deposit_match_ends_at = datetime.fromisoformat(ends)
            except ValueError:
                try:
                    s.deposit_match_ends_at = datetime.strptime(ends, "%Y-%m-%dT%H:%M")
                except ValueError:
                    pass
        else:
            s.deposit_match_ends_at = None
        s.deposit_match_message = (request.form.get("deposit_match_message") or "").strip() or None
        s.whatsapp_number = (request.form.get("whatsapp_number") or "").strip() or None
        s.status_message = (request.form.get("status_message") or "All systems normal").strip()
        s.status_deposits = (request.form.get("status_deposits") or "normal").strip()
        s.status_withdrawals = (request.form.get("status_withdrawals") or "normal").strip()
        s.status_tasks = (request.form.get("status_tasks") or "normal").strip()
        try:
            s.weekend_bonus_percent = float(request.form.get("weekend_bonus_percent") or 0)
        except ValueError:
            pass
        try:
            s.potd_product_id = int(request.form.get("potd_product_id") or 0) or None
        except ValueError:
            s.potd_product_id = None
        try:
            s.potd_boost_percent = float(request.form.get("potd_boost_percent") or 25)
        except ValueError:
            pass
        try:
            s.potd_slots_left = int(request.form.get("potd_slots_left") or 0)
        except ValueError:
            pass
        try:
            s.withdraw_cooling_minutes = int(request.form.get("withdraw_cooling_minutes") or 30)
        except ValueError:
            pass
        try:
            s.withdraw_cooling_threshold = float(request.form.get("withdraw_cooling_threshold") or 500000)
        except ValueError:
            pass
        db.session.commit()
        flash("Campaign & status settings saved.", "success")
        return redirect(url_for("admin.campaign_settings"))
    return render_template("admin/campaigns.html", settings=s)


@admin_bp.route("/success-stories", methods=["GET", "POST"])
@login_required
@admin_required
def success_stories_admin():
    from models.success_story import SuccessStory
    if request.method == "POST":
        story = SuccessStory(
            display_name=(request.form.get("display_name") or "Member").strip()[:80],
            country=(request.form.get("country") or "").strip()[:80] or None,
            membership_name=(request.form.get("membership_name") or "").strip()[:40] or None,
            body=(request.form.get("body") or "").strip(),
            approved=request.form.get("approved") == "1",
        )
        if story.body:
            db.session.add(story)
            db.session.commit()
            flash("Story saved.", "success")
        return redirect(url_for("admin.success_stories_admin"))
    stories = SuccessStory.query.order_by(SuccessStory.created_at.desc()).limit(100).all()
    return render_template("admin/success_stories.html", stories=stories)


@admin_bp.route("/success-stories/<int:id>/toggle")
@login_required
@admin_required
def success_story_toggle(id):
    from models.success_story import SuccessStory
    s = SuccessStory.query.get_or_404(id)
    s.approved = not s.approved
    db.session.commit()
    return redirect(url_for("admin.success_stories_admin"))


@admin_bp.route("/success-stories/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def success_story_delete(id):
    from models.success_story import SuccessStory
    s = SuccessStory.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    flash("Deleted.", "success")
    return redirect(url_for("admin.success_stories_admin"))


@admin_bp.route("/team-challenges", methods=["GET", "POST"])
@login_required
@admin_required
def team_challenges():
    from models.team_challenge import TeamChallenge
    from datetime import datetime, timedelta
    if request.method == "POST":
        agent_id = request.form.get("agent_id", type=int) or current_user.id
        ch = TeamChallenge(
            agent_id=agent_id,
            title=(request.form.get("title") or "Team race").strip()[:120],
            target_sets=int(request.form.get("target_sets") or 10),
            prize_spins=int(request.form.get("prize_spins") or 1),
            prize_cash=float(request.form.get("prize_cash") or 0),
            ends_at=datetime.utcnow() + timedelta(days=int(request.form.get("days") or 7)),
            active=True,
        )
        db.session.add(ch)
        db.session.commit()
        flash("Challenge created.", "success")
        return redirect(url_for("admin.team_challenges"))
    q = TeamChallenge.query.order_by(TeamChallenge.created_at.desc())
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        q = q.filter_by(agent_id=current_user.id)
    items = q.limit(50).all()
    agents = User.query.filter((User.is_agent == True) | (User.is_admin == True)).limit(100).all()
    # Progress: sum of daily_sets_completed among direct referrals of agent
    progress = {}
    for c in items:
        members = User.query.filter_by(referred_by_id=c.agent_id).all()
        sets_sum = sum(int(m.daily_sets_completed or 0) for m in members)
        progress[c.id] = {"sets": sets_sum, "members": len(members), "pct": min(100, int(100 * sets_sum / max(1, c.target_sets or 1)))}
    return render_template("admin/team_challenges.html", items=items, agents=agents, progress=progress)


@admin_bp.route("/users/<int:user_id>/combo-suggest")
@login_required
@admin_required
def combo_suggest(user_id):
    """JSON: 3 products near target amount for smart combo."""
    from models.product import Product
    from flask import jsonify
    if assert_can_manage(user_id) is None:
        return jsonify({"error": "forbidden"}), 403
    user = User.query.get_or_404(user_id)
    try:
        target = float(request.args.get("target") or 0)
    except ValueError:
        target = 0
    bal = float(user.available_balance or 0)
    if target <= 0:
        target = bal + 50000
    products = (
        Product.query.filter(Product.active.is_(True), Product.price > 0)
        .order_by(Product.price.asc()).limit(500).all()
    )
    products.sort(key=lambda p: abs(float(p.price or 0) - target))
    out = []
    for p in products[:3]:
        price = float(p.price or 0)
        out.append({
            "id": p.id,
            "name": p.name,
            "price": price,
            "projected_balance": round(bal - price, 2),
        })
    return jsonify({"target": target, "balance": bal, "suggestions": out})


@admin_bp.route("/team-challenges/<int:id>/claim", methods=["POST"])
@login_required
@admin_required
def claim_challenge_prize(id):
    """Award prize to agent when team hit target sets (direct referrals)."""
    from models.team_challenge import TeamChallenge
    from models.wallet_transaction import WalletTransaction
    from datetime import datetime
    ch = TeamChallenge.query.get_or_404(id)
    if not ch.active:
        flash("Challenge is not active.", "warning")
        return redirect(url_for("admin.team_challenges"))
    members = User.query.filter_by(referred_by_id=ch.agent_id).all()
    sets_sum = sum(int(m.daily_sets_completed or 0) for m in members)
    if sets_sum < int(ch.target_sets or 0):
        flash(f"Target not met ({sets_sum}/{ch.target_sets}).", "warning")
        return redirect(url_for("admin.team_challenges"))
    agent = User.query.get(ch.agent_id)
    if not agent:
        flash("Agent not found.", "danger")
        return redirect(url_for("admin.team_challenges"))
    cash = float(ch.prize_cash or 0)
    spins = int(ch.prize_spins or 0)
    if cash > 0:
        before = float(agent.available_balance or 0)
        agent.available_balance = before + cash
        agent.total_earned = (agent.total_earned or 0) + cash
        db.session.add(WalletTransaction(
            user_id=agent.id,
            amount=cash,
            transaction_type="challenge_prize",
            description=f"Team challenge prize: {ch.title}",
            balance_before=before,
            balance_after=float(agent.available_balance),
        ))
    if spins > 0 and hasattr(agent, "daily_spins_used"):
        agent.daily_spins_used = max(0, int(agent.daily_spins_used or 0) - spins)
    ch.active = False
    db.session.commit()
    flash(f"Prize awarded to {agent.username}: cash {cash:,.0f}, spins {spins}.", "success")
    return redirect(url_for("admin.team_challenges"))


@admin_bp.route("/deposits/bulk-reject", methods=["POST"])
@login_required
@admin_required
def bulk_reject_deposits():
    ids = request.form.getlist("deposit_ids")
    ok = 0
    for did in ids:
        try:
            deposit = Deposit.query.get(int(did))
        except Exception:
            continue
        if not deposit or deposit.status != "Pending":
            continue
        try:
            WalletService.reject_deposit(deposit, current_user)
            ok += 1
        except Exception as e:
            print("bulk reject", e)
    db.session.commit()
    flash(f"Rejected {ok} deposit(s).", "success" if ok else "warning")
    return redirect(url_for("admin.deposits", status="Pending"))


@admin_bp.route("/withdrawals/bulk-processing", methods=["POST"])
@login_required
@admin_required
def bulk_withdrawals_processing():
    ids = request.form.getlist("withdrawal_ids")
    ok = 0
    from datetime import datetime
    for wid in ids:
        try:
            w = Withdrawal.query.get(int(wid))
        except Exception:
            continue
        if not w or w.status != "Pending":
            continue
        w.status = "Processing"
        if hasattr(w, "reviewed_by"):
            w.reviewed_by = current_user.id
        if hasattr(w, "reviewed_at"):
            w.reviewed_at = datetime.utcnow()
        ok += 1
    db.session.commit()
    flash(f"Marked {ok} withdrawal(s) as processing.", "success" if ok else "warning")
    return redirect(url_for("admin.withdrawals", status="Pending"))


@admin_bp.route("/kyc")
@login_required
@admin_required
def kyc_list():
    from models.engagement import KycDocument
    rows = KycDocument.query.order_by(KycDocument.created_at.desc()).limit(100).all()
    return render_template("admin/kyc.html", rows=rows)


@admin_bp.route("/kyc/<int:id>/<action>", methods=["POST"])
@login_required
@admin_required
def kyc_review(id, action):
    from models.engagement import KycDocument
    from datetime import datetime
    row = KycDocument.query.get_or_404(id)
    user = User.query.get(row.user_id)
    if action == "approve":
        row.status = "Approved"
        if user:
            user.kyc_status = "Approved"
    else:
        row.status = "Rejected"
        if user:
            user.kyc_status = "Rejected"
    row.reviewed_by = current_user.id
    row.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash(f"KYC {row.status}.", "success")
    return redirect(url_for("admin.kyc_list"))


@admin_bp.route("/seasons", methods=["GET", "POST"])
@login_required
@admin_required
def seasons():
    from models.engagement import LeaderboardSeason
    from datetime import datetime, timedelta
    if request.method == "POST":
        s = LeaderboardSeason(
            title=(request.form.get("title") or "Season").strip()[:120],
            prize_note=(request.form.get("prize_note") or "").strip()[:255],
            starts_at=datetime.utcnow(),
            ends_at=datetime.utcnow() + timedelta(days=int(request.form.get("days") or 30)),
            active=True,
        )
        db.session.add(s)
        db.session.commit()
        flash("Season created.", "success")
        return redirect(url_for("admin.seasons"))
    items = LeaderboardSeason.query.order_by(LeaderboardSeason.id.desc()).limit(20).all()
    return render_template("admin/seasons.html", items=items)


@admin_bp.route("/interest-logs")
@login_required
@admin_required
def interest_logs():
    from models.interest_log import InterestLog
    from extensions import db
    try:
        InterestLog.__table__.create(db.engine, checkfirst=True)
    except Exception:
        pass
    rows = InterestLog.query.order_by(InterestLog.created_at.desc()).limit(200).all()
    users = {u.id: u for u in User.query.filter(User.id.in_([r.user_id for r in rows] or [0])).all()}
    return render_template("admin/interest_logs.html", rows=rows, users=users)


@admin_bp.route("/interest-settings", methods=["POST"])
@login_required
@admin_required
def interest_settings():
    from models.settings import Settings
    s = Settings.query.first()
    if not s:
        flash("Settings missing.", "danger")
        return redirect(url_for("admin.settings"))
    s.interest_enabled = request.form.get("interest_enabled") == "1"
    try:
        s.interest_min_ugx = float(request.form.get("interest_min_ugx") or 30000)
    except Exception:
        s.interest_min_ugx = 30000
    try:
        s.interest_rate = float(request.form.get("interest_rate") or 5)
    except Exception:
        s.interest_rate = 5
    db.session.commit()
    flash("Interest settings saved.", "success")
    return redirect(url_for("admin.settings"))


@admin_bp.route("/users/<int:user_id>/telegram", methods=["POST"])
@login_required
def set_user_telegram(user_id):
    """Admin/agent sets Telegram chat ID for a user."""
    if not (getattr(current_user, "is_admin", False) or getattr(current_user, "is_agent", False)):
        flash("Not allowed.", "danger")
        return redirect(url_for("admin.users"))
    user = User.query.get_or_404(user_id)
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        # tree-only if helper exists
        try:
            from routes.admin import _agent_can_manage
            if not _agent_can_manage(current_user, user):
                flash("User not in your team.", "danger")
                return redirect(url_for("admin.users"))
        except Exception:
            pass
    chat = (request.form.get("telegram_chat_id") or "").strip() or None
    if chat and not str(chat).lstrip("-").isdigit():
        flash("Chat ID should be numbers only.", "warning")
        return redirect(url_for("admin.view_user", user_id=user.id))
    try:
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        cols = {c["name"] for c in insp.get_columns("users")}
        if "telegram_chat_id" not in cols:
            dialect = db.engine.dialect.name
            if dialect == "postgresql":
                db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(64)"))
            else:
                db.session.execute(text("ALTER TABLE users ADD COLUMN telegram_chat_id VARCHAR(64)"))
            db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("tg col:", e)
    user.telegram_chat_id = chat
    db.session.commit()
    try:
        from utils.audit import log_action
        log_action(current_user.id, "set_telegram", "user", str(user.id), f"chat_id={chat}")
    except Exception:
        pass
    if chat:
        flash(f"Telegram linked for {user.username}.", "success")
        try:
            from services.engagement_service import send_outbound_alert
            send_outbound_alert(user, "Telegram linked", "Your Taskmill Telegram alerts are now active.")
        except Exception:
            pass
    else:
        flash(f"Telegram unlinked for {user.username}.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))


@admin_bp.route("/test-admin-telegram", methods=["POST"])
@login_required
@admin_required
def test_admin_telegram():
    from services.admin_alerts import notify_admin, _admin_chat_ids, _bot_token
    if not _bot_token():
        flash("Bot token missing in Settings.", "danger")
        return redirect(url_for("admin.settings"))
    if not _admin_chat_ids():
        flash("Set Admin chat ID(s) in Settings and Save.", "warning")
        return redirect(url_for("admin.settings"))
    ok = notify_admin("Admin test", "If you see this, admin Telegram alerts work.")
    flash("Test sent." if ok else "Send failed — check Chat ID and that you pressed Start on the bot.", "success" if ok else "danger")
    return redirect(url_for("admin.settings"))

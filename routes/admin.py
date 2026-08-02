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
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_admin:
            flash(
                "Administrator access required.",
                "danger"
            )
            return redirect(
                url_for("dashboard.index")
            )
        return f(*args, **kwargs)
    return decorated_function


# ==========================================================
# DASHBOARD
# ==========================================================

def _combo_max_for_user(user):
    """Max combo product price by membership (UGX). High enough for real combo hits."""
    name = (user.membership.name if user.membership else "Starter").lower()
    caps = {
        "starter": 150000,
        "silver": 350000,
        "gold": 600000,
        "vip": 1000000,
    }
    return caps.get(name, 150000)


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(
        is_active=True
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

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        active_users=active_users,
        blocked_users=blocked_users,
        pending_deposit_list=pending_deposit_list,
        pending_withdrawal_list=pending_withdrawal_list,
        negative_users=negative_users,
        open_combos=open_combos,
        total_products=total_products,
        active_tasks=active_tasks,
        completed_tasks=completed_tasks,
        pending_deposits=pending_deposits,
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
    return render_template(
        "admin/users.html",
        users=users,
        q=q,
        filter_neg=filter_neg,
        filter_membership=filter_membership,
        memberships=memberships,
    )


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

@admin_bp.route("/payment-settings/add", methods=["POST"])
@login_required
@admin_required
def add_payment_setting():

    setting = PaymentSetting(

        method=request.form["method"],

        provider=request.form["provider"],

        account_name=request.form["account_name"],

        account_number=request.form["account_number"],

        instructions=request.form["instructions"]

    )

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

    setting.method = request.form["method"]

    setting.provider = request.form["provider"]

    setting.account_name = request.form["account_name"]

    setting.account_number = request.form["account_number"]

    setting.instructions = request.form["instructions"]

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

    setting.active = not setting.active

    db.session.commit()

    return redirect(
        url_for("admin.payment_settings")
    )

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
            .order_by(LoginHistory.id.desc())
            .limit(20)
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
        max_combo = float(_combo_max_for_user(user) or 150000)
        bal = float(user.available_balance or 0)
        min_price = 0.0
        if bal > 0:
            min_price = min(bal * 0.5, max_combo * 0.1)
        combo_products = (
            Product.query
            .filter(
                Product.active.is_(True),
                Product.price > 0,
                Product.price <= max_combo,
                Product.price >= min_price,
            )
            .order_by(Product.price.desc())
            .limit(200)
            .all()
        )
        if len(combo_products) < 10:
            combo_products = (
                Product.query
                .filter(
                    Product.active.is_(True),
                    Product.price > 0,
                    Product.price <= max_combo,
                )
                .order_by(Product.price.desc())
                .limit(200)
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
    )

# ==========================================================
# BLOCK / UNBLOCK USER
# ==========================================================
@admin_bp.route("/users/<int:user_id>/toggle-block")
@login_required
@admin_required
def toggle_block(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash(
            "You cannot block your own account.",
            "warning"
        )
        return redirect(url_for("admin.users"))
    user.is_blocked = not user.is_blocked
    db.session.commit()
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


# ==========================================================
# MAKE ADMIN
# ==========================================================
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

    flash("Wallet credited successfully.", "success")

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

    combos = Combo.query.order_by(
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
    RANGE = 3000.0  # ±3000 UGX

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
        # Prefer price slightly above balance when possible
        above = [p for p in candidates if float(p.price or 0) > bal]
        pool = above if above else candidates
        p1 = random.choice(pool)

    price = float(p1.price or 0)
    if abs(price - target) > RANGE * 2:
        # soft warning only
        pass

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
        notes=notes or f"Target UGX {target:,.0f} · picked {price:,.0f} (bal {bal:,.0f})",
    )
    # optional fields if model has them
    for attr, val in (
        ("product2_id", None),
        ("product2_name", None),
        ("product2_price", None),
    ):
        if hasattr(combo, attr):
            setattr(combo, attr, val)

    db.session.add(combo)
    db.session.commit()

    # Prefer combo manager when assigned from there
    next_page = request.form.get("next") or request.referrer or ""
    flash(
        f"Combo assigned: {p1.name} @ UGX {price:,.0f} "
        f"(target {target:,.0f} ±{int(RANGE)}). "
        f"User balance UGX {bal:,.0f} → projected {bal - price:,.0f} after trigger. "
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
    user = User.query.get_or_404(user_id)

    user.daily_spins_used = 0

    db.session.commit()

    flash("Spin wheel reset.", "success")
    return redirect(url_for("admin.view_user", user_id=user.id))
@admin_bp.route("/users/<int:user_id>/unlock-set2", methods=["POST", "GET"])
@login_required
@admin_required
def unlock_set2(user_id):
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
    """Admin resets withdraw PIN to default 1234. User should change it."""
    user = User.query.get_or_404(user_id)
    user.set_withdraw_pin("1234")
    db.session.commit()
    flash("Withdraw PIN reset to 1234. Ask the user to change it after login.", "success")
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

    # Referral 25%
    if user.referred_by_id:
        ref = User.query.get(user.referred_by_id)
        if ref and amount > 0:
            bonus = round(amount * 0.25, 0)
            rb = float(ref.available_balance or 0)
            ref.available_balance = rb + bonus
            ref.referral_income = (ref.referral_income or 0) + bonus
            db.session.add(WalletTransaction(
                user_id=ref.id,
                amount=bonus,
                transaction_type="referral_bonus",
                description=f"25% of deposit by {user.username}",
                balance_before=rb,
                balance_after=float(ref.available_balance),
            ))

    try:
        from services.notification_service import NotificationService
        NotificationService.send(
            user,
            "Deposit Approved",
            f"UGX {amount:,.0f} credited. Receipt in Wallet history.",
        )
    except Exception:
        pass

    # Delete proof file to save storage
    try:
        if deposit.proof_image:
            import os
            from flask import current_app
            path = os.path.join(
                current_app.static_folder, "uploads", "deposits", str(deposit.proof_image)
            )
            if os.path.isfile(path):
                os.remove(path)
    except Exception as e:
        print("proof delete:", e)

    # Remove deposit row after processing (history is in wallet_transactions)
    db.session.delete(deposit)
    db.session.commit()

    flash("Deposit approved, credited, and archived (removed from deposits list).", "success")
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


@admin_bp.route("/withdrawals/<int:withdrawal_id>/approve")
@login_required
@admin_required
def approve_withdrawal(withdrawal_id):
    from services.wallet_service import WalletService
    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)
    if withdrawal.status != "Pending":
        flash("Already reviewed.", "warning")
        return redirect(url_for("admin.withdrawals"))
    ok = WalletService.approve_withdrawal(withdrawal, current_user)
    if ok:
        # Archive: remove withdrawal row (ledger remains in wallet_transactions)
        try:
            db.session.delete(withdrawal)
            db.session.commit()
            flash("Withdrawal approved and archived (removed from list).", "success")
        except Exception as e:
            print("wd delete", e)
            flash("Withdrawal approved.", "success")
    else:
        flash("Could not approve withdrawal.", "danger")
    return redirect(url_for("admin.withdrawals"))


@admin_bp.route("/withdrawals/<int:withdrawal_id>/reject")
@login_required
@admin_required
def reject_withdrawal(withdrawal_id):
    from services.wallet_service import WalletService
    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)
    if withdrawal.status != "Pending":
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
@admin_required
def settings():
    settings = Settings.query.first()
    if not settings:
        settings = Settings()
        db.session.add(settings)
        db.session.commit()
    if request.method == "POST":
        settings.site_name = request.form.get("site_name")
        settings.site_url = request.form.get("site_url")
        settings.registration_enabled = (
            request.form.get("registration_enabled") == "on"
        )
        settings.deposits_enabled = (
            request.form.get("deposits_enabled") == "on"
        )
        settings.withdrawals_enabled = (
            request.form.get("withdrawals_enabled") == "on"
        )
        settings.maintenance = (
            request.form.get("maintenance") == "on"
        )
        settings.referral_bonus = float(
            request.form.get("referral_bonus") or 0
        )
        settings.referral_activation = float(
            request.form.get("referral_activation") or 0
        )
        settings.daily_task_reset_hour = int(
            request.form.get("daily_task_reset_hour") or 0
        )
        settings.task_delay = int(
            request.form.get("task_delay") or 3
        )
        settings.combo_probability = float(
            request.form.get("combo_probability") or 0
        )
        settings.combo_penalty = float(
            request.form.get("combo_penalty") or 0
        )
        settings.max_daily_combo = int(
            request.form.get("max_daily_combo") or 1
        )
        settings.combo_minimum_amount = float(
            request.form.get("combo_minimum_amount") or 0
        )
        settings.daily_spins = int(
            request.form.get("daily_spins") or 1
        )
        settings.max_spin_reward = float(
            request.form.get("max_spin_reward") or 100
        )
        settings.smtp_host = request.form.get("smtp_host")
        settings.smtp_port = int(
            request.form.get("smtp_port") or 587
        )
        settings.smtp_username = request.form.get("smtp_username")
        settings.smtp_password = request.form.get("smtp_password")
        settings.sender_email = request.form.get("sender_email")
        settings.minimum_withdrawal = float(
            request.form.get("minimum_withdrawal") or 10
        )
        settings.maximum_withdrawal = float(
            request.form.get("maximum_withdrawal") or 100000
        )
        db.session.commit()
        flash("Settings updated successfully.", "success")
        return redirect(url_for("admin.settings"))
    return render_template(
        "admin/settings.html",
        settings=settings
    )


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
            # Inline approve core
            user = deposit.user
            before = float(user.available_balance or 0)
            amount = float(deposit.amount or 0)
            user.available_balance = before + amount
            db.session.add(WalletTransaction(
                user_id=user.id,
                amount=amount,
                transaction_type="deposit",
                description=f"{deposit.payment_method or 'Deposit'} approved · Ref {deposit.transaction_id or deposit.id}",
                balance_before=before,
                balance_after=float(user.available_balance),
            ))
            # delete proof
            try:
                if deposit.proof_image:
                    import os
                    path = os.path.join(
                        current_app.static_folder, "uploads", "deposits", str(deposit.proof_image)
                    )
                    if os.path.isfile(path):
                        os.remove(path)
            except Exception:
                pass
            db.session.delete(deposit)
            try:
                from services.notification_service import NotificationService
                NotificationService.send(user, "Deposit Approved", f"UGX {amount:,.0f} credited.")
            except Exception:
                pass
            # Referral 25% on deposit
            if user.referred_by_id:
                ref = User.query.get(user.referred_by_id)
                if ref:
                    bonus = round(amount * 0.25, 0)
                    rb = float(ref.available_balance or 0)
                    ref.available_balance = rb + bonus
                    ref.referral_income = (ref.referral_income or 0) + bonus
                    db.session.add(WalletTransaction(
                        user_id=ref.id,
                        amount=bonus,
                        transaction_type="referral_bonus",
                        description=f"25% of deposit by {user.username}",
                        balance_before=rb,
                        balance_after=float(ref.available_balance),
                    ))
            ok += 1
        except Exception as e:
            print("bulk approve", did, e)
            db.session.rollback()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    flash(f"Approved {ok} deposit(s).", "success")
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

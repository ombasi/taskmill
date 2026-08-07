from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from flask_login import (
    login_required,
    current_user,
)

from services.wallet_service import WalletService
from utils.security import csrf_protect
from services.combo_service import ComboService
from models.payment_setting import PaymentSetting

wallet_bp = Blueprint(
    "wallet",
    __name__,
    url_prefix="/wallet"
)


# =====================================================
# WALLET HOME
# =====================================================

@wallet_bp.route("/")
@login_required
def index():

    transactions = WalletService.history(current_user)

    return render_template(

        "wallet.html",

        transactions=transactions,

        available_balance=current_user.available_balance,

        combo_balance=current_user.combo_balance,

        pending_balance=current_user.pending_balance

    )


# =====================================================
# DEPOSIT
# =====================================================
# =====================================================
# DEPOSIT
# =====================================================
from werkzeug.utils import secure_filename
import os
from models.deposit import Deposit
from extensions import db

# =====================================================
# DEPOSIT
# =====================================================
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

from models.deposit import Deposit


@wallet_bp.route("/deposit", methods=["GET", "POST"])
@login_required
@csrf_protect
def deposit():

    payment_settings = PaymentSetting.query.filter(
        PaymentSetting.active.is_(True)
    ).order_by(PaymentSetting.method.asc()).all()

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount") or 0)
        except (TypeError, ValueError):
            flash("Enter a valid deposit amount.", "danger")
            return redirect(url_for("wallet.deposit"))
        # User enters amount in their local currency → store UGX
        try:
            from utils.fx import to_ugx
            amount = to_ugx(amount, getattr(current_user, "currency", None) or "UGX")
        except Exception as _fx:
            print("deposit fx:", _fx)
        if amount <= 0:
            flash("Deposit amount must be greater than zero.", "danger")
            return redirect(url_for("wallet.deposit"))

        payment_method = (request.form.get("payment_method") or "").strip()
        if not payment_method:
            flash("Select a payment method.", "danger")
            return redirect(url_for("wallet.deposit"))

        provider = (request.form.get("provider") or payment_method or "Other").strip()
        transaction_id = (request.form.get("transaction_id") or "").strip()
        if not transaction_id:
            flash("Enter the transaction ID / reference.", "danger")
            return redirect(url_for("wallet.deposit"))

        notes = request.form.get("notes")

        proof = request.files.get("proof")

        filename = None

        if proof and proof.filename:
            original = proof.filename.strip()
            parts = original.rsplit(".", 1)
            if len(parts) == 2 and parts[1].isalnum() and len(parts[1]) <= 8:
                ext = parts[1].lower()
            else:
                # No extension or odd name (e.g. "receipt") — default to png
                ext = "png"

            allowed = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "bmp"}
            if ext not in allowed:
                flash("Proof must be an image (png/jpg/webp) or PDF.", "danger")
                return redirect(url_for("wallet.deposit"))

            filename = f"{uuid.uuid4().hex}.{ext}"
            upload_folder = os.path.join(
                current_app.static_folder, "uploads", "deposits"
            )
            os.makedirs(upload_folder, exist_ok=True)
            proof.save(os.path.join(upload_folder, filename))

        deposit = Deposit(
            user_id=current_user.id,
            amount=amount,
            currency=getattr(current_user, "currency", None) or "UGX",
            payment_method=payment_method,
            provider=provider or payment_method or "Other",
            wallet_address=request.form.get("wallet_address") or request.form.get("account") or "",
            transaction_id=transaction_id,
            proof_image=filename,
            notes=notes,
            status="Pending",
        )

        db.session.add(deposit)

        db.session.commit()

        flash(
            "Deposit submitted. Next: wait for admin approval — your balance updates automatically when approved.",
            "success",
        )
        return redirect(url_for("wallet.index"))

    # Active PaymentSetting rows only (admin toggle). Crypto only if enabled there.
    payment_settings = PaymentSetting.query.filter(
        PaymentSetting.active.is_(True)
    ).order_by(PaymentSetting.method.asc()).all()
    # Fallback if column is integer 1 on some DBs
    if not payment_settings:
        payment_settings = [
            s for s in PaymentSetting.query.order_by(PaymentSetting.method.asc()).all()
            if bool(s.active)
        ]
    pay_methods = [
        {
            "id": s.id,
            "method": s.method,
            "name": s.method,
            "provider": s.provider or s.method,
            "account_name": s.account_name or "",
            "account_number": s.account_number or "",
            "instructions": s.instructions or "",
        }
        for s in payment_settings
    ]
    return render_template(
        "wallet/deposit.html",
        payment_methods=pay_methods,
        payment_settings=payment_settings,
    )

# =====================================================
# WITHDRAW
# =====================================================

@wallet_bp.route("/payout-method", methods=["POST"])
@login_required
@csrf_protect
def set_payout_method():
    """User may set payout destination once. Further changes require admin."""
    from extensions import db
    from datetime import datetime

    if getattr(current_user, "payout_method", None) and getattr(current_user, "payout_account_number", None):
        flash("Your payout method is already set. Contact admin to change it.", "warning")
        return redirect(url_for("wallet.withdraw"))

    method = (request.form.get("payment_method") or request.form.get("payout_method") or "").strip()
    account_name = (request.form.get("account_name") or "").strip()
    account_number = (request.form.get("account_number") or "").strip()
    provider = (request.form.get("provider") or method or "").strip()

    if not method or not account_number:
        flash("Payment method and account / phone number are required.", "danger")
        return redirect(url_for("wallet.withdraw"))

    current_user.payout_method = method
    current_user.payout_account_name = account_name or current_user.full_name
    current_user.payout_account_number = account_number
    current_user.payout_provider = provider
    current_user.payout_confirmed = False
    current_user.payout_set_at = datetime.utcnow()
    db.session.commit()

    try:
        from services.notification_service import NotificationService
        NotificationService.send(
            current_user.id,
            "Payout method submitted",
            f"{method} · {account_number} — waiting for admin confirmation.",
        )
    except Exception:
        pass

    flash("Payout method submitted. Admin will confirm it before you can withdraw.", "success")
    return redirect(url_for("wallet.withdraw"))


@wallet_bp.route("/withdraw", methods=["GET", "POST"])
@login_required
@csrf_protect
def withdraw():
    from services.task_service import TaskService

    # Always show the page (so user can add payout method).
    # Eligibility is enforced only when submitting a withdrawal.
    if request.method == "POST":
        allowed, reason = TaskService.can_withdraw(current_user)
        if not allowed:
            flash(reason, "warning")
            return redirect(url_for("wallet.withdraw"))
        try:
            amount_local = float(request.form.get("amount") or 0)
        except ValueError:
            amount_local = 0

        # User enters amount in their display currency → store/process as UGX
        try:
            from utils.fx import to_ugx
            amount = to_ugx(amount_local, getattr(current_user, "currency", None) or "UGX")
        except Exception:
            amount = amount_local

        pin = (request.form.get("withdraw_pin") or request.form.get("pin") or "").strip()
        if not current_user.has_withdraw_pin():
            flash("Set a withdraw PIN in Profile before withdrawing.", "warning")
            return redirect(url_for("profile.set_withdraw_pin"))
        if not current_user.check_withdraw_pin(pin):
            flash("Incorrect withdraw PIN.", "danger")
            return redirect(url_for("wallet.withdraw"))

        if not (getattr(current_user, "payout_method", None) and getattr(current_user, "payout_account_number", None)):
            flash("Add a payout method first.", "warning")
            return redirect(url_for("wallet.withdraw"))
        if not getattr(current_user, "payout_confirmed", False):
            flash("Your payout method is waiting for admin confirmation.", "warning")
            return redirect(url_for("wallet.withdraw"))

        # Cooling-off for large withdrawals
        try:
            from models.settings import Settings
            from datetime import datetime, timedelta
            settings = Settings.query.first()
            thr = float(getattr(settings, "withdraw_cooling_threshold", 500000) or 500000)
            mins = int(getattr(settings, "withdraw_cooling_minutes", 30) or 30)
            if amount >= thr and mins > 0:
                last = getattr(current_user, "last_big_withdraw_at", None)
                if last and datetime.utcnow() < last + timedelta(minutes=mins):
                    left = int((last + timedelta(minutes=mins) - datetime.utcnow()).total_seconds() // 60) + 1
                    flash(f"Large withdrawals have a {mins}-minute cooling period. Try again in ~{left} min.", "warning")
                    return redirect(url_for("wallet.withdraw"))
        except Exception:
            pass

        withdrawal = WalletService.create_withdrawal(
            current_user,
            amount,
            current_user.payout_method,
            current_user.payout_account_name or current_user.full_name or "",
            current_user.payout_account_number,
            current_user.payout_provider or current_user.payout_method,
        )

        if withdrawal:
            try:
                from models.settings import Settings
                from datetime import datetime
                settings = Settings.query.first()
                thr = float(getattr(settings, "withdraw_cooling_threshold", 500000) or 500000)
                if amount >= thr:
                    current_user.last_big_withdraw_at = datetime.utcnow()
                    from extensions import db
                    db.session.commit()
            except Exception:
                pass
            flash("Withdrawal request submitted. Funds held pending admin approval.", "success")
        else:
            flash("Cannot withdraw: insufficient balance after the required reserve, or invalid amount.", "danger")

        return redirect(url_for("wallet.index"))

    checklist = TaskService.withdraw_checklist(current_user)
    reserve = 15000.0
    bal = float(current_user.available_balance or 0)
    max_wd_ugx = max(0.0, bal - reserve)
    min_wd_ugx = 1000.0  # base minimum in UGX
    try:
        from utils.fx import ugx_to
        cur = getattr(current_user, "currency", None) or "UGX"
        max_wd_local = ugx_to(max_wd_ugx, cur)
        min_wd_local = ugx_to(min_wd_ugx, cur)
        # sensible steps: whole units for UGX-like, cents for EUR/USD
        if cur in ("EUR", "USD", "GBP", "CAD", "AUD", "CHF"):
            step = 0.01
            min_wd_local = max(0.01, round(min_wd_local, 2))
            max_wd_local = max(0.0, round(max_wd_local, 2))
        else:
            step = 1
            min_wd_local = max(1, int(round(min_wd_local)))
            max_wd_local = max(0, int(round(max_wd_local)))
    except Exception:
        max_wd_local = max_wd_ugx
        min_wd_local = min_wd_ugx
        step = 100
    return render_template(
        "wallet/withdraw.html",
        checklist=checklist,
        min_wd_local=min_wd_local,
        max_wd_local=max_wd_local,
        amount_step=step,
        reserve=reserve,
        max_wd=max_wd_ugx,
    )

@wallet_bp.route("/referrals")
@login_required
def referrals():

    from models.user import User

    referrals = User.query.filter_by(
        referred_by_id=current_user.id
    ).all()

    total_referrals = len(referrals)

    referral_income = 0

    return render_template(
        "referral/index.html",
        referrals=referrals,
        total_referrals=total_referrals,
        referral_income=referral_income
    )
# =====================================================
# REFRESH COMBO
# =====================================================

@wallet_bp.route("/combo/refresh")
@login_required
def refresh_combo():

    combo = ComboService.get_active_combo(current_user)

    if combo:

        ComboService.refresh_combo(combo)

    return redirect(

        url_for("task.combo")

    )

@wallet_bp.route("/receipt/<string:kind>/<int:item_id>")
@login_required
def receipt(kind, item_id):
    """
    Show a receipt.
    kind: deposit | withdrawal | tx
    After admin approval records may be deleted — use kind=tx with WalletTransaction id.
    """
    from models.deposit import Deposit
    from models.wallet_transaction import WalletTransaction
    try:
        from models.withdraw import Withdrawal
    except Exception:
        from models.withdrawal import Withdrawal

    item = None
    title = "Receipt"
    meta = {}

    if kind == "tx":
        item = WalletTransaction.query.get_or_404(item_id)
        if item.user_id != current_user.id and not current_user.is_admin:
            flash("Not allowed.", "danger")
            return redirect(url_for("wallet.index"))
        title = "Transaction Receipt"
        meta = {
            "amount": item.amount,
            "status": "Completed",
            "method": item.transaction_type,
            "date": item.created_at,
            "description": item.description,
            "reference": f"TX-{item.id}",
        }
    elif kind == "deposit":
        item = Deposit.query.get(item_id)
        if not item:
            # Fall back: find wallet tx for this deposit amount recently
            flash("This deposit was processed and archived. Open it from Wallet history.", "info")
            return redirect(url_for("wallet.index"))
        if item.user_id != current_user.id and not current_user.is_admin:
            flash("Not allowed.", "danger")
            return redirect(url_for("wallet.index"))
        title = "Deposit Receipt"
        meta = {
            "amount": item.amount,
            "status": item.status,
            "method": item.payment_method,
            "date": item.created_at,
            "description": getattr(item, "transaction_id", None) or "",
            "reference": f"DEP-{item.id}",
        }
    elif kind == "withdrawal":
        item = Withdrawal.query.get(item_id)
        if not item:
            flash("This withdrawal was processed and archived. Open it from Wallet history.", "info")
            return redirect(url_for("wallet.index"))
        if item.user_id != current_user.id and not current_user.is_admin:
            flash("Not allowed.", "danger")
            return redirect(url_for("wallet.index"))
        title = "Withdrawal Receipt"
        meta = {
            "amount": item.amount,
            "status": item.status,
            "method": item.payment_method,
            "date": item.created_at,
            "description": getattr(item, "account_number", None) or "",
            "reference": f"WD-{item.id}",
        }
    else:
        flash("Unknown receipt type.", "danger")
        return redirect(url_for("wallet.index"))

    return render_template(
        "wallet/receipt.html",
        item=item,
        kind=kind,
        title=title,
        meta=meta,
    )


@wallet_bp.route("/withdrawals")
@login_required
def my_withdrawals():
    from models.withdraw import Withdrawal
    rows = (
        Withdrawal.query.filter_by(user_id=current_user.id)
        .order_by(Withdrawal.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template("wallet/my_withdrawals.html", withdrawals=rows)

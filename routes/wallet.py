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

    payment_settings = PaymentSetting.query.filter_by(
        active=True
    ).all()

    if request.method == "POST":

        amount = float(request.form["amount"])

        payment_method = request.form["payment_method"]

        provider = request.form["provider"]

        transaction_id = request.form["transaction_id"]

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
            "Deposit submitted successfully. Awaiting approval.",
            "success"
        )

        return redirect(
            url_for("wallet.deposit")
        )

    from utils.payment_methods import methods_for_country
    pay_methods = methods_for_country(getattr(current_user, "country", None))
    return render_template(
        "wallet/deposit.html",
        payment_methods=pay_methods,
        payment_settings=payment_settings
    )

# =====================================================
# WITHDRAW
# =====================================================
@wallet_bp.route("/withdraw", methods=["GET", "POST"])
@login_required
@csrf_protect
def withdraw():
    from services.task_service import TaskService

    allowed, reason = TaskService.can_withdraw(current_user)
    if not allowed:
        flash(reason, "warning")
        return redirect(url_for("wallet.index"))

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount") or 0)
        except ValueError:
            amount = 0

        pin = (request.form.get("withdraw_pin") or "").strip()
        if not current_user.has_withdraw_pin():
            flash("Set a withdraw PIN in Profile before withdrawing.", "warning")
            return redirect(url_for("profile.set_withdraw_pin"))
        if not current_user.check_withdraw_pin(pin):
            flash("Incorrect withdraw PIN.", "danger")
            return redirect(url_for("wallet.withdraw"))

        withdrawal = WalletService.create_withdrawal(
            current_user,
            amount,
            request.form.get("payment_method") or "MTN Mobile Money",
            request.form.get("account_name") or "",
            request.form.get("account_number") or "",
            request.form.get("provider") or "MTN",
        )

        if withdrawal:
            flash("Withdrawal request submitted. Funds held pending admin approval.", "success")
        else:
            flash("Invalid amount, or you must leave UGX 15,000 in the wallet for next day tasks.", "danger")

        return redirect(url_for("wallet.index"))

    return render_template("wallet/withdraw.html")

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

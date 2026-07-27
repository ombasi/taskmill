from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from services.combo_service import ComboService
from services.wallet_service import WalletService

combo_bp = Blueprint("combo", __name__, url_prefix="/combo")


# =====================================
# ACTIVE COMBO
# =====================================

@combo_bp.route("/")
@login_required
def index():

    combo = ComboService.get_active_combo(current_user)

    if not combo:

        flash("No active combo.", "info")
        return redirect(url_for("dashboard.index"))

    return render_template(
        "tasks/combo.html",
        combo=combo
    )


# =====================================
# COMPLETE COMBO
# =====================================

@combo_bp.route("/<int:combo_id>/complete")
@login_required
def complete(combo_id):

    combo = ComboService.get_active_combo(current_user)

    if not combo:

        flash("Combo not found.", "danger")
        return redirect(url_for("dashboard.index"))

    if combo.id != combo_id:

        flash("Invalid combo.", "danger")
        return redirect(url_for("dashboard.index"))

    if combo.deposit_required:

        flash("Required balance has not been met.", "warning")
        return redirect(url_for("combo.index"))

    WalletService.credit(

        current_user,

        combo.commission,

        "Combo Commission"

    )

    ComboService.complete(combo)

    flash("Combo completed successfully.", "success")

    return redirect(url_for("dashboard.index"))

import json
import random
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.spin import SpinPrize, SpinGrant, SpinHistory
from models.wallet_transaction import WalletTransaction
from utils.security import csrf_protect

spin_bp = Blueprint("spin", __name__, url_prefix="/spin")


def _user_remaining(user):
    grants = (
        SpinGrant.query.filter_by(user_id=user.id, active=True)
        .order_by(SpinGrant.id.desc())
        .all()
    )
    return sum(g.remaining for g in grants), grants


def _prizes_for_grant(grant):
    q = SpinPrize.query.filter_by(active=True)
    if grant and grant.allowed_prize_ids:
        ids = []
        for part in str(grant.allowed_prize_ids).split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        if ids:
            q = q.filter(SpinPrize.id.in_(ids))
    prizes = q.order_by(SpinPrize.sort_order.asc(), SpinPrize.id.asc()).all()
    return prizes


def _pick_prize(prizes):
    if not prizes:
        return None
    weights = [max(1, int(p.weight or 1)) for p in prizes]
    return random.choices(prizes, weights=weights, k=1)[0]


def _apply_prize(user, prize):
    detail = ""
    amount = float(prize.amount or 0)
    if prize.prize_type == "cash" and amount > 0:
        before = float(user.available_balance or 0)
        user.available_balance = before + amount
        user.total_earned = float(user.total_earned or 0) + amount
        db.session.add(WalletTransaction(
            user_id=user.id,
            amount=amount,
            transaction_type="spin_reward",
            description=f"Lucky Spin: {prize.label}",
            balance_before=before,
            balance_after=float(user.available_balance),
        ))
        detail = f"Credited UGX {amount:,.0f}"
    elif prize.prize_type == "membership" and prize.membership_id:
        user.membership_id = prize.membership_id
        mname = prize.membership.name if prize.membership else "plan"
        detail = f"Upgraded to {mname}"
    elif prize.prize_type == "voucher":
        detail = f"Voucher: {prize.voucher_code or prize.label}"
        if prize.voucher_note:
            detail += f" — {prize.voucher_note}"
    else:
        detail = "Better luck next time"
        amount = 0
    return detail, amount


@spin_bp.route("/")
@login_required
def index():
    remaining, grants = _user_remaining(current_user)
    # Use first grant with remaining for allowed prizes, else all active
    active_grant = next((g for g in grants if g.remaining > 0), None)
    prizes = _prizes_for_grant(active_grant) if active_grant else (
        SpinPrize.query.filter_by(active=True).order_by(SpinPrize.sort_order).all()
    )
    history = (
        SpinHistory.query.filter_by(user_id=current_user.id)
        .order_by(SpinHistory.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "luckyspin.html",
        prizes=prizes,
        remaining=remaining,
        history=history,
    )


@spin_bp.route("/play", methods=["POST"])
@login_required
@csrf_protect
def play():
    remaining, grants = _user_remaining(current_user)
    if remaining <= 0:
        flash("No spins available. Ask admin to award a spin.", "warning")
        return redirect(url_for("spin.index"))

    grant = next((g for g in grants if g.remaining > 0), None)
    prizes = _prizes_for_grant(grant)
    if not prizes:
        flash("No prizes configured on the wheel.", "danger")
        return redirect(url_for("spin.index"))

    prize = _pick_prize(prizes)
    detail, amount = _apply_prize(current_user, prize)
    grant.spins_used = int(grant.spins_used or 0) + 1
    if grant.remaining <= 0:
        grant.active = False

    hist = SpinHistory(
        user_id=current_user.id,
        prize_id=prize.id,
        prize_type=prize.prize_type,
        label=prize.label,
        amount=amount,
        detail=detail,
    )
    db.session.add(hist)
    try:
        from services.notification_service import NotificationService
        NotificationService.send(
            current_user,
            "Lucky Spin result",
            f"You won: {prize.label}. {detail}",
        )
    except Exception:
        pass
    db.session.commit()

    # index of prize in list for wheel animation
    idx = next((i for i, p in enumerate(prizes) if p.id == prize.id), 0)
    flash(f"You won: {prize.label}! {detail}", "success")
    return redirect(url_for("spin.index", won=prize.id, idx=idx))

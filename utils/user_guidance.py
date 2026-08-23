"""User-facing guidance: next step, combo timeline, deposit tracker helpers."""
from __future__ import annotations


def next_step(user, progress=None, combo=None, checklist=None):
    """Return dict: title, body, cta_label, cta_endpoint, tone, steps(optional)."""
    bal = float(getattr(user, "available_balance", 0) or 0)
    membership = getattr(user, "membership", None)

    # Combo hold
    if combo or bal < 0:
        return {
            "title": "Clear combo hold",
            "body": "Deposit until your balance is at least 0, then open Tasks and submit the held product to earn combo commission.",
            "cta_label": "Deposit to clear",
            "cta_endpoint": "wallet.deposit",
            "tone": "rose",
            "code": "combo_hold",
        }

    # Need capital to start
    min_start = 15000
    try:
        from helpers.currency import money
        # keep logic in UGX internal; display elsewhere
    except Exception:
        pass
    if bal < min_start and int(getattr(user, "tasks_completed_today", 0) or 0) == 0:
        # if they have membership and never funded
        return {
            "title": "Fund your wallet",
            "body": "Make a deposit so you can start product reviews. Keep a small reserve after withdrawals for the next day.",
            "cta_label": "Deposit now",
            "cta_endpoint": "wallet.deposit",
            "tone": "sky",
            "code": "deposit",
        }

    # Tasks in progress
    done = 0
    goal = 16
    if isinstance(progress, dict):
        done = int(progress.get("completed_today") or 0)
        goal = int(progress.get("mandatory") or goal)
    else:
        done = int(getattr(user, "tasks_completed_today", 0) or 0)
        if membership:
            goal = int(getattr(membership, "daily_tasks", None) or getattr(membership, "tasks_per_set", 16) or 16)

    sets_done = int(getattr(user, "daily_sets_completed", 0) or 0)
    sets_max = int(getattr(membership, "daily_sets", 2) or 2) if membership else 2

    # Set 1 done, Set 2 locked
    if sets_done >= 1 and not bool(getattr(user, "set2_unlocked", False)) and sets_max > 1:
        return {
            "title": "Set 1 complete — unlock Set 2",
            "body": "Message Support to unlock your second set, then finish remaining tasks and withdraw when ready.",
            "cta_label": "Contact support",
            "cta_endpoint": "chat.inbox",
            "tone": "amber",
            "code": "set2_unlock",
        }

    if done < goal or sets_done < sets_max:
        return {
            "title": "Continue your tasks",
            "body": f"Progress today: {done}/{goal} reviews · sets {sets_done}/{sets_max}. Finish sets to unlock withdrawals.",
            "cta_label": "Open tasks",
            "cta_endpoint": "task.index",
            "tone": "emerald",
            "code": "tasks",
            "done": done,
            "goal": goal,
        }

    # Withdrawal available?
    can_wd = False
    reason = ""
    try:
        from services.task_service import TaskService
        can_wd, reason = TaskService.can_withdraw(user)
    except Exception:
        can_wd = False
        reason = ""

    if can_wd:
        return {
            "title": "Withdrawal available",
            "body": "You completed today’s requirements. Submit a withdrawal when ready (reserve balance is kept for tomorrow).",
            "cta_label": "Withdraw",
            "cta_endpoint": "wallet.withdraw",
            "tone": "amber",
            "code": "withdraw",
        }

    # Blocked withdraw — show reason / checklist
    if reason:
        return {
            "title": "Almost ready to withdraw",
            "body": reason,
            "cta_label": "View checklist",
            "cta_endpoint": "wallet.withdraw",
            "tone": "zinc",
            "code": "checklist",
        }

    return {
        "title": "You’re all set for today",
        "body": "Check history, invite friends, or open your wallet.",
        "cta_label": "Wallet",
        "cta_endpoint": "wallet.index",
        "tone": "sky",
        "code": "idle",
    }


def combo_timeline(user, combo=None):
    bal = float(getattr(user, "available_balance", 0) or 0)
    steps = [
        {"key": "hold", "label": "Hold placed", "done": True},
        {"key": "deposit", "label": "Deposit to clear", "done": bal >= 0},
        {"key": "zero", "label": "Balance ≥ 0", "done": bal >= 0},
        {"key": "submit", "label": "Submit product", "done": False},
        {"key": "earn", "label": "Earn commission", "done": False},
    ]
    if combo and getattr(combo, "completed", False):
        for s in steps:
            s["done"] = True
    elif bal >= 0 and combo:
        # waiting for submit
        steps[3]["done"] = False
    return steps


def normalize_checklist(checklist):
    """TaskService.withdraw_checklist may return dict or list."""
    if checklist is None:
        return []
    if isinstance(checklist, dict):
        items = checklist.get("items") or checklist.get("checks") or []
        if items:
            return items
        # key: bool map
        out = []
        for k, v in checklist.items():
            if k in ("items", "checks", "ok", "ready", "can_withdraw"):
                continue
            if isinstance(v, dict):
                out.append(v)
            else:
                out.append({"label": str(k).replace("_", " ").title(), "ok": bool(v), "done": bool(v)})
        return out
    if isinstance(checklist, list):
        return checklist
    return []

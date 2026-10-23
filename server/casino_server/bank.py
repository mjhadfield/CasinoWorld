"""
The bank and the lobby's ATM: what a player may withdraw and when, the admin page's Bank settings, and where the
ATMs are on the floor.

A player plays with their cash in hand; the ATM moves money between that and their bank balance (Store.transfer).
Withdrawals come in £50 notes, only while you hold less than `hand_under`, at most `low_cap` a time (`high_cap` once
the bank is at `threshold` or more). The bank may go overdrawn without limit, but while it is you can withdraw only
once every `cooldown_min` minutes (the withdrawal that first takes it overdrawn is allowed, and starts the clock).
Deposits are any amount you hold. Settings are whole pounds (minutes for the wait), kept in meta `bank_settings`.

An ATM is any library asset with `"interact": "atm"` (the Modern lobby's cash machine); you use one on foot,
standing in front of it.
"""
import math

from casino_server import plan

NOTE = 5_000            # £50: withdrawals are in these
REACH = 64.0            # how near an ATM's base you must be (the client offers it from nearer; this allows for lag)
DEFAULT_SETTINGS = {
    "start_bank": 1000,     # a new player's bank, £
    "start_hand": 0,        # and cash in hand, £
    "hand_under": 500,      # withdrawals only while holding less than this, £
    "low_cap": 250,         # the most a withdrawal, £...
    "threshold": 2500,      # ...while the bank's under this, £
    "high_cap": 2000,       # the most a withdrawal at or over it, £
    "cooldown_min": 30,     # overdrawn: minutes between withdrawals
}
_LIMITS = {   # key -> (lowest, highest, what it is)
    "start_bank": (-1_000_000, 1_000_000, "The starting bank"),
    "start_hand": (0, 1_000_000, "The starting cash in hand"),
    "hand_under": (0, 1_000_000, "The cash-in-hand limit"),
    "low_cap": (50, 1_000_000, "A withdrawal limit"),
    "threshold": (0, 10_000_000, "The threshold"),
    "high_cap": (50, 1_000_000, "A withdrawal limit"),
    "cooldown_min": (0, 7 * 24 * 60, "The overdrawn wait"),
}


def settings(store) -> dict:
    saved = store.get_json("bank_settings", {})
    return {**DEFAULT_SETTINGS, **{k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}}


def clean_settings(data: dict) -> dict:
    out = {}
    for key, (lo, hi, what) in _LIMITS.items():
        if key not in data:
            continue
        v = data[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v) or not lo <= v <= hi:
            raise ValueError(f"{what} is a whole number from {lo:,} to {hi:,}.")
        if key in ("low_cap", "high_cap") and v % 50:
            raise ValueError("Withdrawal limits are in £50 notes: a multiple of £50.")
        out[key] = int(v)
    return out


def withdraw_check(bank: int, hand: int, last_withdraw_at: float | None, s: dict, now: float) -> dict:
    """Whether a withdrawal's allowed now: {"can", "why" ("" | "carrying" | "overdrawn"), "cap" (pence), "wait"
    (seconds until the next one, when overdrawn)}."""
    cap = (s["high_cap"] if bank >= s["threshold"] * 100 else s["low_cap"]) * 100
    if hand >= s["hand_under"] * 100:
        return {"can": False, "why": "carrying", "cap": cap, "wait": 0}
    if bank < 0 and last_withdraw_at is not None:
        wait = last_withdraw_at + s["cooldown_min"] * 60 - now
        if wait > 0:
            return {"can": False, "why": "overdrawn", "cap": cap, "wait": math.ceil(wait)}
    return {"can": True, "why": "", "cap": cap, "wait": 0}


def withdraw_problem(amount, check: dict) -> str | None:
    """Why `amount` (pence) can't be withdrawn, or None."""
    if not check["can"]:
        return "You're holding too much to withdraw." if check["why"] == "carrying" else "Overdrawn: wait for the next withdrawal."
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        return "Enter an amount."
    if amount % NOTE:
        nearest = max(NOTE, min(check["cap"], round(amount / NOTE) * NOTE))
        return f"Can't pay £{amount / 100:,.0f}. Try £{nearest // 100:,}."
    if amount > check["cap"]:
        return f"The most you can take is £{check['cap'] // 100:,}."
    return None


def atms() -> list[tuple[float, float]]:
    """Where every ATM on the live floor stands (its base, in the floor's frame)."""
    out = []
    for room in plan.live()["rooms"]:
        if not room.get("placed"):
            continue
        for item in room["items"]:
            a = plan.piece(item["asset"])
            if a and a.get("interact") == "atm":
                out.append((room["x"] + item["x"], room["y"] + item["y"]))
    return out


def near_atm(x: float | None, y: float | None) -> bool:
    if x is None or y is None:
        return False
    return any(math.hypot(x - ax, y - ay) <= REACH for ax, ay in atms())

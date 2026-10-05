"""Text rendering for the Bohnanza environment (pure functions of the game state)."""
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

PHASE_TITLES = {
    "plant": "Phase 1 of 4: plant from your hand",
    "draw_trade": "Phase 2 of 4: turn over and trade",
    "plant_mandatory": "Phase 3 of 4: plant traded and turned-over beans",
    "draw": "Phase 4 of 4: draw",
    "game_over": "Game over",
}


def harvest_coins(payouts: Dict[int, int], count: int) -> int:
    """Coins earned for harvesting `count` beans; `payouts` maps coins -> beans needed."""
    for coins, needed in sorted(payouts.items(), reverse=True):
        if count >= needed:
            return coins
    return 0


def format_beans(beans: Iterable[str]) -> str:
    """'2 Blue, 1 Red' (first-appearance order), or 'nothing' for an empty list."""
    counts = Counter(beans)
    if not counts:
        return "nothing"
    return ", ".join(f"{count} {bean}" for bean, count in counts.items())


def format_field(field: Optional[Tuple[str, int]]) -> str:
    if field is None:
        return "empty"
    bean, count = field
    return f"{bean} x{count}"


def describe_field(field: Optional[Tuple[str, int]], bean_types: Dict[str, Dict[str, Any]]) -> str:
    """'Blue x3 (worth 0 coins; 1 coin at 4 beans)' or 'empty'."""
    if field is None:
        return "empty"
    bean, count = field
    payouts = bean_types[bean]["payouts"]
    worth = harvest_coins(payouts, count)
    upgrades = sorted((needed, coins) for coins, needed in payouts.items() if needed > count)
    if upgrades:
        needed, coins = upgrades[0]
        outlook = f"{coins} coin{'s' if coins != 1 else ''} at {needed} beans"
    else:
        outlook = "the maximum"
    return f"{format_field(field)} (worth {worth} coin{'s' if worth != 1 else ''}; {outlook})"


def beanometer_line(bean_types: Dict[str, Dict[str, Any]]) -> str:
    parts = []
    for bean, config in bean_types.items():
        thresholds = "/".join(str(config["payouts"].get(coins, "-")) for coins in (1, 2, 3, 4))
        parts.append(f"{bean} {thresholds}")
    return "Beanometers (beans needed for 1/2/3/4 coins): " + " | ".join(parts)


def describe_trade(trade_id: int, trade: Dict[str, Any]) -> str:
    audience = "open to everyone" if trade["target"] is None else f"to Player {trade['target']}"
    return f"#{trade_id}: Player {trade['proposer']} offers {format_beans(trade['offer'])} for {format_beans(trade['want'])} ({audience})"


def render_board(game_state: Dict[str, Any], viewer_id: Optional[int], bean_types: Dict[str, Dict[str, Any]], deck_cycles: int) -> str:
    """The table as seen by `viewer_id`: everything public plus the viewer's own hand.

    Other players' hands are shown only as card counts. Pass `viewer_id=None`
    for a spectator view without any hand.
    """
    gs = game_state
    active = gs["active_player"]
    phase = gs["current_phase"]
    rule = "-" * 72
    lines = [
        "=" * 72,
        f"BOHNANZA | Turn {gs['turn_number']} | Active player: Player {active} | {PHASE_TITLES.get(phase, phase)}",
        (
            f"Draw pile: {len(gs['deck'])} cards | Discard pile: {len(gs['discard_pile'])} cards | "
            f"The draw pile has run out {gs['deck_cycles_completed']} of {deck_cycles} times "
            f"(the game ends when it runs out for the {ordinal(deck_cycles)} time)"
        ),
    ]

    if phase == "draw_trade":
        face_up = gs["face_up_cards"]
        lines.append(f"Face-up cards (they belong to Player {active}): {', '.join(face_up) if face_up else 'none left'}")
        pending = [(trade_id, trade) for trade_id, trade in gs["active_trades"].items() if trade["status"] == "pending"]
        if pending:
            lines.append("Open trade offers:")
            lines.extend(f"  {describe_trade(trade_id, trade)}" for trade_id, trade in pending)
        else:
            lines.append("Open trade offers: none")
    waiting = [(pid, beans) for pid, beans in sorted(gs["mandatory_plants"].items()) if beans]
    if waiting:
        lines.append(
            "Beans set aside to be planted in phase 3: "
            + "; ".join(f"Player {pid}: {format_beans(beans)}" for pid, beans in waiting)
        )

    lines.append(rule)
    for pid in sorted(gs["players"]):
        player = gs["players"][pid]
        tags = []
        if pid == viewer_id:
            tags.append("you")
        if pid == active:
            tags.append("active player")
        tag = f" ({', '.join(tags)})" if tags else ""
        coins, hand_size = player["coins"], len(player["hand"])
        lines.append(
            f"Player {pid}{tag}: {coins} coin{'s' if coins != 1 else ''}, "
            f"{hand_size} card{'s' if hand_size != 1 else ''} in hand"
        )
        for number, field in enumerate(player["fields"], start=1):
            lines.append(f"  Field {number}: {describe_field(field, bean_types)}")
    lines.append(rule)

    if viewer_id is not None:
        hand: List[str] = gs["players"][viewer_id]["hand"]
        lines.append(f"Your hand, front to back: {', '.join(hand)}" if hand else "Your hand is empty.")
    lines.append(beanometer_line(bean_types))
    return "\n".join(lines)


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

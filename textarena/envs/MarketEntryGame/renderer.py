import math
import unicodedata
from decimal import Decimal, localcontext
from numbers import Rational


def format_number(value) -> str:
    try:
        numeric = float(value)
    except (OverflowError, TypeError, ValueError):
        numeric = None
    if numeric is not None and math.isfinite(numeric):
        return f"{numeric:g}" if abs(numeric) < 1e12 else f"{numeric:.3e}"
    if isinstance(value, Rational):
        with localcontext() as context:
            context.prec = 8
            decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        return f"{decimal_value:.3E}"
    return str(value)


def format_signed(value) -> str:
    text = format_number(value)
    return text if text.startswith(("-", "+")) else f"+{text}"

def char_display_width(ch: str) -> int:
    """Return display width of a single character (emoji-safe)."""
    # East Asian wide/fullwidth characters
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    # Many emoji lie in these ranges
    if 0x1F300 <= ord(ch) <= 0x1FAFF:
        return 2
    # fallback: normal width
    return 1

def text_display_width(text: str) -> int:
    return sum(char_display_width(ch) for ch in text)

def pad_line(content: str, box_width: int) -> str:
    """Pad content to align borders, emoji-safe."""
    disp_len = text_display_width(content)
    pad_spaces = box_width - 2 - disp_len
    return f"│ {content}{' ' * max(0, pad_spaces)} │"

def create_board_str(game_state: dict) -> str:
    """Create a visual representation of the Market Entry Game state."""
    lines = []
    
    # fixed box widths (match your original formatting)
    header_width = 59
    status_width = 59
    market_width = 59
    standings_width = 59
    quick_width = 59
    
    # Determine phase info
    phase = game_state.get("phase", "conversation")
    current_round = game_state.get("round", 1)
    total_rounds = game_state.get("num_rounds", 5)
    
    if phase == "conversation":
        conv_round = game_state.get("conversation_round", 0) + 1
        total_conv = game_state.get("total_conversation_rounds", 3)
        phase_display = f"💬 Communication ({conv_round}/{total_conv})"
    elif phase == "complete":
        phase_display = "🏁 Game Complete"
    else:
        phase_display = "🎯 Decision Phase"
    
    # Header with game info
    lines.append("╭─────────────────── MARKET ENTRY GAME ─────────────────────╮")
    lines.append(pad_line(f"Round {current_round:>2}/{total_rounds:<2} │ {phase_display}", header_width))
    
    capacity = game_state.get("market_capacity", 2)
    entry_profit = game_state.get("entry_profit", 15)
    overcrowding = game_state.get("overcrowding_penalty", -5)
    safe = game_state.get("safe_payoff", 5)
    
    lines.append(pad_line(
        f"Market Capacity: {capacity} │ Entry: {format_signed(entry_profit)} │ "
        f"Crowd: {format_signed(overcrowding)} │ Safe: {format_signed(safe)}",
        header_width
    ))
    lines.append("╰───────────────────────────────────────────────────────────╯")
    
    # Get alive vs eliminated players
    eliminations = game_state.get("eliminations", [])
    
    # Current round status
    lines.append("┌─ 🎮 CURRENT ROUND STATUS ─────────────────────────────────┐")
    
    if phase == "conversation":
        pending_messages = game_state.get("pending_messages", {})
        lines.append(pad_line("Player Messages Status:", status_width))
        
        total_scores = game_state.get("total_scores", {})
        num_players = len(total_scores) if total_scores else 4
        
        for player_id in range(num_players):
            if player_id in eliminations:
                status = "❌ ELIMINATED"
            elif player_id in pending_messages:
                status = "✅ Submitted (hidden)"
            else:
                status = "⏳ Waiting..."
            lines.append(pad_line(f"Player {player_id}: {status}", status_width))
            
    else:  # decision phase
        decisions = game_state.get("decisions", {})
        pending_decisions = game_state.get("pending_decisions", {})
        lines.append(pad_line("Player Decision Status:", status_width))
        
        total_scores = game_state.get("total_scores", {})
        num_players = len(total_scores) if total_scores else 4
        
        for player_id in range(num_players):
            if player_id in eliminations:
                status = "❌ ELIMINATED"
            elif player_id in decisions and decisions[player_id] is not None:
                decision = decisions[player_id]
                status = f"✅ {'ENTER' if decision == 'E' else 'STAY OUT'}"
            elif player_id in pending_decisions:
                status = "✅ Submitted (hidden)"
            else:
                status = "⏳ Deciding..."
            lines.append(pad_line(f"Player {player_id}: {status}", status_width))
    
    lines.append("└───────────────────────────────────────────────────────────┘")
    
    # Market status visualization (if decisions have been made)
    if phase in ("decision", "complete") and game_state.get("decisions"):
        decisions = game_state.get("decisions", {})
        alive_entries = [pid for pid, dec in decisions.items() if dec == 'E' and pid not in eliminations]
        if any(d is not None for d in decisions.values()):
            num_entries = len(alive_entries)
            lines.append("┌─ 🏪 MARKET STATUS ────────────────────────────────────────┐")
            
            # There can never be more usable slots than players. Capping the
            # visualization keeps very large, but valid, capacities renderable.
            visible_capacity = min(capacity, len(total_scores))
            capacity_bar = "".join(
                "🟢" if i < num_entries else "⚪" for i in range(visible_capacity)
            )
            if capacity > visible_capacity:
                capacity_bar += f" … (capacity {capacity})"
            if num_entries > capacity:
                overflow = num_entries - capacity
                capacity_bar += " +" + "🔴" * overflow + " (OVERCROWDED!)"
            
            lines.append(pad_line(f"Market Occupancy: {capacity_bar}", market_width))
            status_text = (
                "❌ Overcrowded" if num_entries > capacity
                else "✅ Profitable" if num_entries > 0
                else "⚫ Empty"
            )
            lines.append(pad_line(f"Entrants: {num_entries}/{capacity} │ Status: {status_text}", market_width))
            
            if alive_entries:
                entrant_list = f"Players {', '.join(map(str, sorted(alive_entries)))}"
                lines.append(pad_line(f"Who entered: {entrant_list}", market_width))
            
            lines.append("└───────────────────────────────────────────────────────────┘")
    
    # Player standings
    total_scores = game_state.get("total_scores", {})
    if total_scores:
        lines.append("┌─ 🏆 PLAYER STANDINGS ─────────────────────────────────────┐")
        alive_scores = [(pid, score) for pid, score in total_scores.items() if pid not in eliminations]
        eliminated_scores = [(pid, score) for pid, score in total_scores.items() if pid in eliminations]
        alive_scores.sort(key=lambda x: x[1], reverse=True)
        eliminated_scores.sort(key=lambda x: x[1], reverse=True)
        
        for rank, (player_id, score) in enumerate(alive_scores, 1):
            rank_icon = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
            lines.append(
                pad_line(
                    f"{rank_icon} Player {player_id}: {format_number(score)} points",
                    standings_width,
                )
            )
        
        for player_id, score in eliminated_scores:
            lines.append(
                pad_line(
                    f"❌ Player {player_id}: {format_number(score)} points (eliminated)",
                    standings_width,
                )
            )
        
        lines.append("└───────────────────────────────────────────────────────────┘")
    
    # Game mechanics reminder
    lines.append("┌─ ℹ️  QUICK REFERENCE ──────────────────────────────────────┐")
    lines.append(pad_line("Communication: {message}  │  Decision: E or S", quick_width))
    lines.append(pad_line(
        f"Enter: {format_signed(entry_profit)} if ≤{capacity} players, "
        f"{format_signed(overcrowding)} if >{capacity} │ Stay Out: {format_signed(safe)}",
        quick_width
    ))
    lines.append("└───────────────────────────────────────────────────────────┘")
    
    return "\n".join(lines)

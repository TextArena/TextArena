import unicodedata

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

def wrap_display(text: str, width: int):
    """Wrap text by display width instead of len()."""
    lines, line, cur_width = [], "", 0
    for ch in text:
        w = char_display_width(ch)
        if cur_width + w > width:
            lines.append(line)
            line, cur_width = ch, w
        else:
            line += ch
            cur_width += w
    if line:
        lines.append(line)
    return lines

def create_board_str(game_state: dict) -> str:
    """Create a visual representation of the Market Entry Game state."""
    lines = []
    
    # fixed box widths (match your original formatting)
    header_width = 59
    status_width = 59
    fullmsg_width = 59
    market_width = 59
    standings_width = 59
    history_width = 59
    insights_width = 59
    quick_width = 59
    
    # Determine phase info
    phase = game_state.get("phase", "conversation")
    current_round = game_state.get("round", 1)
    total_rounds = game_state.get("num_rounds", 5)
    
    if phase == "conversation":
        conv_round = game_state.get("conversation_round", 0) + 1
        total_conv = game_state.get("total_conversation_rounds", 3)
        phase_display = f"💬 Communication ({conv_round}/{total_conv})"
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
        f"Market Capacity: {capacity} │ Entry: {entry_profit:+3} │ Crowd: {overcrowding:+3} │ Safe: {safe:+3}",
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
                msg = pending_messages[player_id]
                if msg:
                    # Truncate by display width
                    max_len = 40
                    disp_len, short_msg = 0, ""
                    for ch in msg:
                        w = char_display_width(ch)
                        if disp_len + w > max_len:
                            short_msg += "..."
                            break
                        short_msg += ch
                        disp_len += w
                    status = f"💬 \"{short_msg}\""
                else:
                    status = "🤐 Silent"
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
                decision = pending_decisions[player_id]
                status = f"⏳ {'ENTER' if decision == 'E' else 'STAY OUT'} (pending)"
            else:
                status = "⏳ Deciding..."
            lines.append(pad_line(f"Player {player_id}: {status}", status_width))
    
    lines.append("└───────────────────────────────────────────────────────────┘")
    
    # Show full messages if in conversation phase and messages exist
    if phase == "conversation" and game_state.get("pending_messages"):
        has_messages = [pid for pid, msg in game_state["pending_messages"].items() if msg]
        if has_messages:
            lines.append("┌─ 💬 FULL MESSAGES ────────────────────────────────────────┐")
            for player_id in sorted(has_messages):
                msg = game_state["pending_messages"][player_id]
                wrapped = wrap_display(msg, 53)
                lines.append(pad_line(f"P{player_id}: {wrapped[0]}", fullmsg_width))
                for line in wrapped[1:]:
                    lines.append(pad_line(f"    {line}", fullmsg_width))
            lines.append("└───────────────────────────────────────────────────────────┘")
    
    # Market status visualization (if decisions have been made)
    if phase == "decision" and game_state.get("decisions"):
        decisions = game_state.get("decisions", {})
        alive_entries = [pid for pid, dec in decisions.items() if dec == 'E' and pid not in eliminations]
        if any(d is not None for d in decisions.values()):
            num_entries = len(alive_entries)
            lines.append("┌─ 🏪 MARKET STATUS ────────────────────────────────────────┐")
            
            capacity_bar = "".join("🟢" if i < num_entries else "⚪" for i in range(capacity))
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
            lines.append(pad_line(f"{rank_icon} Player {player_id}: {score} points", standings_width))
        
        for player_id, score in eliminated_scores:
            lines.append(pad_line(f"❌ Player {player_id}: {score} points (eliminated)", standings_width))
        
        lines.append("└───────────────────────────────────────────────────────────┘")
    
    # Game mechanics reminder
    lines.append("┌─ ℹ️  QUICK REFERENCE ──────────────────────────────────────┐")
    lines.append(pad_line("Communication: {message}  │  Decision: [E] or [S]", quick_width))
    lines.append(pad_line(
        f"Enter: {entry_profit:+3} if ≤{capacity} players, {overcrowding:+3} if >{capacity} │ Stay Out: {safe:+3}",
        quick_width
    ))
    lines.append("└───────────────────────────────────────────────────────────┘")
    
    return "\n".join(lines)

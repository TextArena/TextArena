from typing import Dict, Any


def get_board_str(game_state: Dict[str, Any], current_player_id: int) -> str:
    """Create a string representation of the current game state."""
    lines = []
    
    # Current game state
    lines.append("=" * 70)
    lines.append("CURRENT GAME STATE")
    lines.append("=" * 70)
    
    # Round and phase info
    current_round = game_state["current_round"]
    current_phase = game_state["current_phase"]
    multiplier = game_state["round_multipliers"][current_round]
    
    lines.append(f"Round: {current_round}/10")
    lines.append(f"Phase: {current_phase.upper()}")
    lines.append(f"Point Multiplier: {multiplier}x")
    lines.append("")
    
    # Phase-specific information
    if current_phase == "talk":
        talk_round = game_state["talk_round"]
        max_talk = game_state["max_talk_rounds"]
        passed_players = game_state["players_passed"]
        
        lines.append("TALK PHASE STATUS:")
        lines.append(f"- Conversation round: {talk_round}/{max_talk}")
        lines.append(f"- Players who passed: {sorted(list(passed_players)) if passed_players else 'None'}")
        
        
        lines.append("")
        
        # Recent talk messages (last 5)
        recent_messages = game_state["talk_messages"][-5:] if game_state["talk_messages"] else []
        if recent_messages:
            lines.append("RECENT MESSAGES:")
            for msg in recent_messages:
                if msg["type"] == "broadcast":
                    lines.append(f"  Player {msg['from']} (Public): {msg['message'][:100]}")
                elif msg["type"] == "whisper":
                    if msg["to"] == current_player_id or msg["from"] == current_player_id:
                        lines.append(f"  Private message from Player {msg['from']} to Player {msg['to']}: {msg['message'][:100]}")
        else:
            lines.append("RECENT MESSAGES: None")
        
        lines.append("")
    
    elif current_phase == "act":
        choices_made = set(game_state["player_choices"].keys())
        waiting_for = [p for p in range(4) if p not in choices_made]
        
        lines.append("ACT PHASE STATUS:")
        lines.append(f"- Players who chose: {sorted(list(choices_made)) if choices_made else 'None'}")
        lines.append(f"- Waiting for: {waiting_for if waiting_for else 'All choices collected'}")
        lines.append("")
    
    # Player scores and status
    lines.append("PLAYER SCORES:")
    lines.append("-" * 70)
    
    player_scores = game_state["player_scores"]
    for player_id in range(4):
        score = player_scores[player_id]
        player_marker = " >>> " if player_id == current_player_id else "     "
        
        # Add status indicators
        status_parts = []
        if current_phase == "talk":
            if player_id in game_state["players_passed"]:
                status_parts.append("PASSED")
            elif player_id == current_player_id:
                status_parts.append("YOUR TURN")
        elif current_phase == "act":
            if player_id in game_state["player_choices"]:
                status_parts.append("CHOSE")
            elif player_id == current_player_id and player_id not in game_state["player_choices"]:
                status_parts.append("YOUR TURN")
        
        status_str = f" ({', '.join(status_parts)})" if status_parts else ""
        lines.append(f"{player_marker}Player {player_id}: {score} points{status_str}")
    
    lines.append("")
    
    # Round history (last 3 rounds)
    round_history = game_state["round_history"]
    if round_history:
        lines.append("RECENT ROUND HISTORY:")
        lines.append("-" * 70)
        
        # Show last 3 completed rounds
        recent_rounds = round_history[-3:] if len(round_history) >= 3 else round_history
        
        for round_data in recent_rounds:
            round_num = round_data["round"]
            choices = round_data["choices"]
            x_count = round_data["x_count"]
            y_count = round_data["y_count"]
            multiplier = round_data["multiplier"]
            results = round_data["results"]
            
            lines.append(f"Round {round_num} ({multiplier}x): {x_count} X's, {y_count} Y's")
            
            # Show choices and points for each player
            for pid in range(4):
                if pid in choices:
                    choice = results[pid]["choice"]
                    points = results[pid]["points"]
                    lines.append(f"  Player {pid}: {choice} -> {points:+d} points")
            
            lines.append("")
    else:
        lines.append("ROUND HISTORY: No completed rounds yet")
        lines.append("")
    
    # Game progress indicator
    lines.append("GAME PROGRESS:")
    lines.append("-" * 70)
    
    # Visual progress bar for rounds
    progress_bar = ""
    for round_num in range(1, 11):
        if round_num < current_round:
            progress_bar += " X "  # Completed round
        elif round_num == current_round:
            progress_bar += " > "  # Current round
        else:
            progress_bar += " . "  # Future round
        
        # Add spacing and markers for communication rounds
        if round_num in {5, 8, 10}:
            progress_bar += " T "  # Talk round marker
        else:
            progress_bar += " "
        
        if round_num < 10:
            progress_bar += ""
    
    lines.append(f"Rounds: {progress_bar}")
    lines.append("Legend: X=Completed >=Current .=Future T=Talk Round")
    lines.append("")
    
    lines.append("=" * 70)
    
    return "\n".join(lines)

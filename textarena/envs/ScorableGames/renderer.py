from typing import Dict

def render_deal_with_scores_and_votes(deal_state: Dict[str, str], issues: Dict[str, Dict], 
                           player_scores: Dict[str, int], player_name: str, 
                           player_votes: Dict[int, str] = None, 
                           player_configs: Dict[int, Dict] = None) -> str:
    """Render the current deal with player's private scores inline and voting status."""
    if not deal_state:
        return "No current deal proposal."
    
    lines = [f"Current Deal & {player_name}'s Scores:"]
    lines.append("=" * 30)
    
    total_score = 0
    for issue_key, option in deal_state.items():
        if issue_key in issues:
            issue_info = issues[issue_key]
            issue_name = issue_info.get('name', issue_key)
            options_desc = issue_info.get('options', {})
            option_desc = options_desc.get(option, option)
            
            # Get player's score for this option
            score = 0
            if issue_key in player_scores and option in player_scores[issue_key]:
                score = player_scores[issue_key][option]
                total_score += score
            
            # Combine description with score
            lines.append(f"{issue_name}: {option} - {option_desc} ({score} points)")
    
    lines.append("=" * 30)
    lines.append(f"Total Score: {total_score} points")
    
    # Add voting status if available
    if player_votes is not None and player_configs is not None:
        lines.append("")
        lines.append("Voting Status:")
        lines.append("-" * 30)
        
        accept_count = 0
        reject_count = 0
        
        for player_id, config in player_configs.items():
            agent_name = config["agent_name"]
            vote = player_votes.get(player_id, "No vote yet")
            lines.append(f"{agent_name}: {vote}")
            
            normalized_vote = vote.strip()
            if normalized_vote == "Accept":
                accept_count += 1
            elif normalized_vote == "Reject":
                reject_count += 1
        
        lines.append("-" * 30)
        lines.append(f"Summary: {accept_count} Accept, {reject_count} Reject")
    
    return "\n".join(lines)

def render_game_issues(issues: Dict[str, Dict]) -> str:
    """Render the available issues and options."""
    lines = ["Available Issues and Options:"]
    lines.append("=" * 30)
    
    for issue_key, issue_info in issues.items():
        issue_name = issue_info.get('name', issue_key)
        lines.append(f"\n{issue_name} ({issue_key}):")
        
        options = issue_info.get('options', {})
        for option_key, option_desc in options.items():
            lines.append(f"  {option_key}: {option_desc}")
    
    return "\n".join(lines)

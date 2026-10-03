from typing import Dict, List, Any, Optional


def get_board_str(player_resources: Dict[int, List[str]], 
                     resource_history: Dict[str, List[int]], 
                     proposals: Dict[int, Dict], 
                     game_variant: str) -> str:
    """Render the current game state including resources, history, and proposals."""
    lines = []
    
    # Game state header (without revealing variant)
    lines.append("GAME STATE")
    lines.append("=" * 20)
    lines.append("")
    
    # Individual player survival progress
    if game_variant == "distributive":
        lines.append("INDIVIDUAL SURVIVAL PROGRESS (need 4 resources to survive):")
        survival_threshold = 4
    else:  # integrative
        lines.append("INDIVIDUAL SURVIVAL PROGRESS (need 5 resources to survive):")
        survival_threshold = 5
    
    for player_id in range(5):  # Assuming 5 players
        player_resources_owned = set()
        for resource, history in resource_history.items():
            if player_id in history:
                player_resources_owned.add(resource)
        
        progress = f"{len(player_resources_owned)} out of 5 resources"
        
        if len(player_resources_owned) >= survival_threshold:
            lines.append(f"Player {player_id}: {progress} - SURVIVED!")
        else:
            lines.append(f"Player {player_id}: {progress}")
    
    lines.append("")
    
    # Current resource ownership
    lines.append("CURRENT RESOURCE OWNERSHIP:")
    lines.append("=" * 30)
    resources = ["food", "water", "shelter", "medicine", "clothing"]
    
    for resource in resources:
        owner = None
        for pid, owned_resources in player_resources.items():
            if resource in owned_resources:
                owner = pid
                break
        
        if owner is not None:
            lines.append(f"{resource.capitalize()}: Player {owner}")
        else:
            lines.append(f"{resource.capitalize()}: No owner")
    
    lines.append("")
    
    # Resource possession history
    lines.append("RESOURCE POSSESSION HISTORY:")
    lines.append("=" * 30)
    for resource in resources:
        history = resource_history.get(resource, [])
        if history:
            history_str = " -> ".join([f"Player {pid}" for pid in history])
            lines.append(f"{resource.capitalize()}: {history_str}")
        else:
            lines.append(f"{resource.capitalize()}: No history")
    
    lines.append("")
    
    # Active proposals
    if proposals:
        lines.append("ACTIVE PROPOSALS:")
        lines.append("=" * 30)
        for proposal_id, proposal in proposals.items():
            proposer = proposal["proposer"]
            coins = proposal["coins"]
            resource = proposal["resource"]
            round_num = proposal["round"]
            
            # Find who can accept
            resource_owner = None
            for pid, owned_resources in player_resources.items():
                if resource in owned_resources:
                    resource_owner = pid
                    break
            
            if resource_owner is not None:
                lines.append(f"Proposal {proposal_id}: Player {proposer} offers {coins} coins for {resource} (Player {resource_owner} can accept) - Round {round_num}")
            else:
                lines.append(f"Proposal {proposal_id}: Player {proposer} offers {coins} coins for {resource} (No current owner) - Round {round_num}")
    else:
        lines.append("ACTIVE PROPOSALS: None")
    
    return "\n".join(lines)

def render_resources_and_coins(player_id: int, 
                              player_resources: Dict[int, List[str]], 
                              player_coins: Dict[int, int]) -> str:
    """Render a player's current resources and coins."""
    lines = []
    
    lines.append("YOUR STATUS")
    lines.append("=" * 15)
    
    # Display player's resources (list)
    player_resource_list = player_resources.get(player_id, [])
    if player_resource_list:
        resources_str = ", ".join(player_resource_list)
        lines.append(f"Your resources: {resources_str}")
    else:
        lines.append("Your resources: None")
    
    lines.append(f"Your coins: {player_coins.get(player_id, 0)}")
    lines.append("")
    
    lines.append("ALL PLAYERS COINS:")
    lines.append("=" * 20)
    for pid in sorted(player_coins.keys()):
        coins = player_coins[pid]
        if pid == player_id:
            lines.append(f"Player {pid} (YOU): {coins} coins")
        else:
            lines.append(f"Player {pid}: {coins} coins")
    
    return "\n".join(lines)
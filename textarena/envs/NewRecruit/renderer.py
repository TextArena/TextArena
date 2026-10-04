from typing import Dict, Any, Optional, List, Tuple


def _get_choice_letters(issue_choices: Dict[str, list]) -> Dict[str, str]:
    """
    Create a mapping of letters to choices for an issue.
    
    Args:
        issue_choices (Dict[str, list]): The choices for an issue.
        
    Returns:
        Dict[str, str]: A dictionary mapping letters to choices.
    """
    letters = ['A', 'B', 'C', 'D', 'E']
    choice_letters = {}
    for i, choice in enumerate(issue_choices.keys()):
        if i < len(letters):
            choice_letters[choice] = letters[i]
    return choice_letters


def create_board_str(game_state: Dict[str, Any], player_id: Optional[int] = None) -> str:
    """
    Create a string representation of the game board.
    
    Args:
        game_state (Dict[str, Any]): The current game state.
        player_id (Optional[int]): The ID of the player viewing the board. If provided,
                                  shows that player's preferences.
    
    Returns:
        str: The string representation of the game board.
    """
    # Define the issues and their categories; only for system reference, not shown to any player
    issues = {
        "distributive": ["Salary", "Signing Bonus"],
        "compatible": ["Job Assignment", "Company Car"],
        "integrative": ["Starting Date", "Vacation Days", "Moving Expense Reimbursement", "Insurance Coverage"]
    }
    
    # Start building the board string
    board_str = []
    
    # Add header
    board_str.append("NEW RECRUIT NEGOTIATION GAME")
    board_str.append("")
    
    # Add roles
    board_str.append("Player 0: Recruiter")
    board_str.append("Player 1: Candidate")
    board_str.append("")
    
    # Add current turn information
    if player_id is not None:
        current_role = game_state["roles"][player_id]
        board_str.append(f"Current Player: {player_id} ({current_role})")
        board_str.append("")
    
    # Add player preferences if player_id is provided
    if player_id is not None:
        board_str.append(f"YOUR PREFERENCES (Player {player_id}):")
        board_str.append("")
        
        # Add all issues without categorization
        all_issues = issues["distributive"] + issues["compatible"] + issues["integrative"]
        for issue in all_issues:
            board_str.append(f"{issue}:")
            issue_choices = _get_issue_choices(issue)
            choice_letters = _get_choice_letters(issue_choices)
            for choice, values in issue_choices.items():
                points = values[player_id]
                letter = choice_letters.get(choice, "")
                board_str.append(f"  {letter}. {choice}: {points} points")
            board_str.append("")
    
    # Add current proposal if there is one
    if game_state["current_proposal"]:
        proposer_id = game_state["current_proposal"]["proposer_id"]
        proposer_role = game_state["roles"][proposer_id]
        board_str.append(f"CURRENT PROPOSAL FROM PLAYER {proposer_id} ({proposer_role}):")
        board_str.append("")
        
        # Add rationale if it exists
        if "current_rationale" in game_state and game_state["current_rationale"]:
            board_str.append(f"Rationale: {game_state['current_rationale']}")
            board_str.append("")
        
        # Add choices with letter choices
        for issue, choice in game_state["current_proposal"]["choices"].items():
            issue_choices = _get_issue_choices(issue)
            choice_letters = _get_choice_letters(issue_choices)
            letter = choice_letters.get(choice, "")
            if letter:
                board_str.append(f"- {issue}: {letter}. {choice}")
            else:
                board_str.append(f"- {issue}: {choice}")
        
        # If player_id is provided, show the points for this proposal
        if player_id is not None:
            points = _calculate_score(player_id, game_state["current_proposal"]["choices"])
            board_str.append("")
            board_str.append(f"Total points for you: {points}")
        
        # Add instructions
        board_str.append("")
        if player_id != proposer_id:
            board_str.append("You can reply with 'Accept' or 'Reject' for this proposal.")
    else:
        board_str.append("NO CURRENT PROPOSAL")
        board_str.append("")
        board_str.append("Write your rationale, then put Propose CCAACCCC on the final line.")
        board_str.append("where each letter (A-E) corresponds to a choice for each issue.")
    
    # Add proposal history
    if game_state["proposal_history"]:
        board_str.append("")
        board_str.append("PROPOSAL HISTORY:")
        
        for i, proposal in enumerate(game_state["proposal_history"][-3:]):  # Show last 3 proposals
            proposer_id = proposal["proposer_id"]
            proposer_role = game_state["roles"][proposer_id]
            status = "Accepted" if proposal["accepted"] else "Rejected/Pending"
            board_str.append(f"Proposal {i+1} from Player {proposer_id} ({proposer_role}): {status}")
    
    # Add footer
    board_str.append("")
    board_str.append("The game ends when a proposal is accepted or after the maximum turns.")
    board_str.append("If no proposal is accepted, both players get 0 points.")
    
    return "\n".join(board_str)


def _get_issue_choices(issue: str) -> Dict[str, list]:
    """
    Get the choices and point values for a specific issue.
    
    Args:
        issue (str): The issue name.
        
    Returns:
        Dict[str, list]: A dictionary mapping choices to point values.
    """
    # This is the same point value dictionary as defined in env.py
    point_value_dict = {
        # distributive
        "Salary": {
            "$60000": [-6000, 0],
            "$58000": [-4500, -1500],
            "$56000": [-3000, -3000],
            "$54000": [-1500, -4500],
            "$52000": [0, -6000]
        },
        "Signing Bonus": {
            "10%": [0, 4000],
            "8%": [1000, 3000],
            "6%": [2000, 2000],
            "4%": [3000, 1000],
            "2%": [4000, 0]
        },
        # compatible
        "Job Assignment": {
            "Division A": [0, 0],
            "Division B": [-600, -600],
            "Division C": [-1200, -1200],
            "Division D": [-1800, -1800],
            "Division E": [-2400, -2400]
        },
        "Company Car": {
            "LUX EX2": [1200, 1200],
            "MOD 250": [900, 900],
            "RAND XTR": [600, 600],
            "DE PAS 450": [300, 300],
            "PALO LSR": [0, 0]
        },
        # integrative
        "Starting Date": {
            "Jun 1": [1600, 0],
            "Jun 15": [1200, 1000],
            "Jul 1": [800, 2000],
            "Jul 15": [400, 3000],
            "Aug 1": [0, 4000]
        },
        "Vacation Days": {
            "30 days": [0, 1600],
            "25 days": [1000, 1200],
            "20 days": [2000, 800],
            "15 days": [3000, 400],
            "10 days": [4000, 0]
        },
        "Moving Expense Reimbursement": {
            "100%": [0, 3200],
            "90%": [200, 2400],
            "80%": [400, 1600],
            "70%": [600, 800],
            "60%": [800, 0]
        },
        "Insurance Coverage": {
            "Allen Insurance": [0, 800],
            "ABC Insurance": [800, 600],
            "Good Health Insurance": [1600, 400],
            "Best Insurance Co.": [2400, 200],
            "Insure Alba": [3200, 0]
        },
    }
    
    return point_value_dict.get(issue, {})


def _calculate_score(player_id: int, proposal: Dict[str, str]) -> int:
    """
    Calculate the score for a player based on a proposal.
    
    Args:
        player_id (int): The ID of the player.
        proposal (Dict[str, str]): The proposal dictionary.
        
    Returns:
        int: The score for the player.
    """
    score = 0
    for issue, choice in proposal.items():
        issue_choices = _get_issue_choices(issue)
        if choice in issue_choices:
            score += issue_choices[choice][player_id]
    return score

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

class GamePhase(Enum):
    Play = "play" # A player is doing an initial action like income, foreign aid, etc
    QueryWhichToKeep = "query_which_to_keep" # We are querying the source player about which cards they want to keep after an exchange
    QueryWhichToReveal = "query_which_to_reveal" # A player chooses which influence to lose
    QueryForBlockOrChallenge = "query_for_block_or_challenge" # We are querying all other players about whether they want to challenge or block an action
    QueryToChallengeTheBlocker = "query_to_challenge_the_blocker" # We are querying the other players if they want to challenge the blocker's claim

class CoupActionType(Enum):
    """
    Each of the actions below is annotated with whether it is blockable or not.
    And what card a player claims to have when they make the action.
    """
    Income = "income"
    Coup = "coup"
    ForeignAid = "foreign aid"
    Tax = "tax"
    Assassinate = "assassinate"
    Exchange = "exchange"
    Steal = "steal"

    # Special action for when a player plays an Ambassador on themselves.
    # This is a bit of a hack to make the game work, but it's not a real action in the game.
    # Tells us which two cards they want to keep after the exchange
    Keep = "keep"
    Reveal = "reveal"

    # Counteractions
    PASS = "pass"
    BULLSHIT = "bullshit"

    BlockForeignAid = "block foreign aid"
    BlockStealAmbassador = "block steal ambassador"
    BlockStealCaptain = "block steal captain"
    BlockAssassinate = "block assassinate"

    
@dataclass
class ActionMetadata:
    """Metadata about an action taken in the game"""
    action_type: CoupActionType
    source_player_id: int  # The id of the player who is the initiator of the action
    target_player_id: Optional[int] = None  # The id of the player who is the target of the action

    players_to_query: Optional[List[int]] = None  # ONLY FOR QueryForBlockOrChallenge Phase

    blocker_player_id: Optional[int] = None  # The id of the player who blocked the action
    block_type: Optional[CoupActionType] = None  # The specific block type used (e.g., BlockStealCaptain vs BlockStealAmbassador)
    blocker_challenger_player_id: Optional[int] = None  # The id of the player who challenged the blocker's claim to have whatever card they used to block
    challenger_player_id: Optional[int] = None  # The id of the player who challenged the original action

    cards_to_keep: Optional[List[str]] = None  # ONLY FOR QueryWhichToKeep Phase
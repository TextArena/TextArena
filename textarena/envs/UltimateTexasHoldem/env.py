import re
import random
from typing import Tuple, Dict, Any, Optional, List

import textarena as ta
from textarena.envs.UltimateTexasHoldem.renderer import create_board_str


class UltimateTexasHoldemEnv(ta.Env):
    """Ultimate Texas Hold'em - Single player vs dealer poker game."""
    
    # Action patterns - simplified to [1x], [2x], [4x]
    _PLAY_BET_4X_RE = re.compile(r"\[4x?\]|\[play\s+bet\s+4x?\]|\[play\s+4x?\s+bet\]|\[play_bet_4x\]", re.IGNORECASE)
    _PLAY_BET_2X_RE = re.compile(r"\[2x?\]|\[play\s+bet\s+2x?\]|\[play\s+2x?\s+bet\]|\[play_bet_2x\]", re.IGNORECASE)
    _PLAY_BET_1X_RE = re.compile(r"\[1x?\]|\[play\s+bet\s+1x?\]|\[play\s+1x?\s+bet\]|\[play_bet_1x\]", re.IGNORECASE)
    _CHECK_RE = re.compile(r"\[check\]|\[c\]", re.IGNORECASE)
    _FOLD_RE = re.compile(r"\[fold\]|\[f\]", re.IGNORECASE)
    _SKIP_RE = re.compile(r"\[skip\]|\[s\]", re.IGNORECASE)
    
    def __init__(self, max_turns: int = 1000, start_chips: int = 1000, ante_amount: int = 25):
        super().__init__()
        self.max_turns = max_turns
        self.start_chips = start_chips
        self.ante_amount = ante_amount
        
        # Card setup
        self.suits = ["♠", "♥", "♦", "♣"]
        self.ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        self.rank_values = {r: i + 2 for i, r in enumerate(self.ranks)}
        
        # Game phases and action tree
        self.game_phases = {
            "pre_round": "PRE-ROUND",
            "pre_flop": "PRE-FLOP", 
            "flop": "FLOP",
            "river": "RIVER",
            "showdown": "SHOWDOWN"
        }
        
        # Legal action tree structure (populated dynamically per phase)
        self.legal_action_tree = {
            "pre_flop": ["play_bet_4x", "check"],
            "flop_no_action": ["skip"],            # When 4x placed pre-flop
            "flop": ["play_bet_2x", "check"],     # When no 4x placed
            "river_no_action": ["skip"],           # When 4x or 2x already placed
            "river": ["play_bet_1x", "fold"],     # When no prior play bet
            # SHOWDOWN phase is automatic - no legal actions needed
        }

    def get_board_str(self):
        return create_board_str(self.state.game_state)

    def reset(self, num_players: int = 1, seed: Optional[int] = None):
        if num_players != 1:
            raise ValueError("UltimateTexasHoldem is a single-player game")
        
        self.state = ta.SinglePlayerState(num_players=1, max_turns=self.max_turns, seed=seed)
        
        game_state = {
            "chips": self.start_chips,
            "current_round": 0,
            "current_phase": "pre_round",
            "player_hand": [],
            "dealer_hand": [],
            "community_cards": [],
            "visible_community_cards": [],
            "ante_bet": 0,
            "blind_bet": 0,
            "play_bet": 0,
            "total_bet": 0,
            "round_complete": False,
            "legal_actions": [],
            "folded": False,
        }
        
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self._start_new_round()
        return self.state

    def _start_new_round(self):
        gs = self.state.game_state
        gs["current_round"] += 1
        gs["current_phase"] = "pre_round"
        gs["round_complete"] = False
        
        deck = self._create_deck()
        random.shuffle(deck)
        
        gs["player_hand"] = [deck.pop(), deck.pop()]
        gs["dealer_hand"] = [deck.pop(), deck.pop()]
        gs["community_cards"] = [deck.pop() for _ in range(5)]
        gs["visible_community_cards"] = []
        
        gs["ante_bet"] = self.ante_amount
        gs["blind_bet"] = self.ante_amount
        gs["play_bet"] = 0
        gs["total_bet"] = gs["ante_bet"] + gs["blind_bet"]
        gs["chips"] -= gs["total_bet"]
        gs["folded"] = False  # Reset folded flag for new round
        
        gs["current_phase"] = "pre_flop"
        gs["legal_actions"] = self.legal_action_tree["pre_flop"][:]
        
        self.state.add_observation(message=self.m("board", "round_start", round=gs['current_round'], ante=gs['ante_bet'], blind=gs['blind_bet'], chips=gs['chips']), observation_type=ta.ObservationType.GAME_MESSAGE)
        self.state.add_observation(message=self.m("board", "your_hand", hand=self._cards_str(gs["player_hand"])), observation_type=ta.ObservationType.GAME_BOARD)

    def _create_deck(self) -> List[Dict[str, str]]:
        return [{"rank": r, "suit": s} for s in self.suits for r in self.ranks]

    @staticmethod
    def _cards_str(cards: List[Dict[str, str]]) -> str:
        return ", ".join(f"{c['rank']}{c['suit']}" for c in cards)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        gs = self.state.game_state
        phase = gs["current_phase"]

        rules = self.m("player_prompt", "rules", start_chips=self.start_chips, ante=self.ante_amount, ante4=self.ante_amount*4, ante2=self.ante_amount*2)

        hand = self._cards_str(gs['player_hand']) if gs['player_hand'] else self.m("player_prompt", "no_cards")
        state_info = self.m(
            "player_prompt", "state",
            round=gs['current_round'],
            chips=gs['chips'],
            hand=hand,
            ante=gs['ante_bet'],
            blind=gs['blind_bet'],
            play=gs['play_bet'],
            phase=self.game_phases[phase],
            actions=', '.join([f'[{action}]' for action in gs.get('legal_actions', [])]),
        )
        return rules.render(_pid=player_id) + state_info.render(_pid=player_id)

    def step(self, action: str) -> Tuple[bool, Dict[str, Any]]:
        gs = self.state.game_state
        # Check if game is already done (set by set_outcome)
        if self.state.done:
            return self.state.step()
        
        # Check for game completion from showdown
        if gs.get("game_complete", False):
            if gs.get("winner") == "player":
                self.state.set_outcome(reward=1.0, reason=self.m("outcome", "reward_win", winner_rounds=gs['current_round'], chips=gs['chips']))
            else:
                self.state.set_outcome(reward=-1.0, reason=self.m("outcome", "reward_lose", round=gs['current_round']))
            return self.state.step()
        
        # Only check round completion at the start of each step (not chip depletion)
        if gs["current_round"] >= self.max_turns:
            # Player won - completed all rounds with chips
            self.state.add_observation(message=self.m("outcome", "game_over_win", max_turns=self.max_turns, chips=gs['chips']), observation_type=ta.ObservationType.GAME_MESSAGE)
            self.state.set_outcome(reward=1.0, reason=self.m("outcome", "reward_win_max", max_turns=self.max_turns, chips=gs['chips']))
            return self.state.step()

        self.state.add_observation(from_id=0, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        parsed = self._parse_action(action)

        if parsed is None:
            # Get current legal actions for better error feedback
            current_actions = gs.get("legal_actions", [])
            available_actions = ", ".join([f"[{action}]" for action in current_actions])

            error_reason = self.m("invalid_move", "reason", available=available_actions)
            self.state.set_invalid_move(reason=error_reason)
            error_reason_text = error_reason.render(_pid=0)

            # Add observation about invalid move with available actions
            self.state.add_observation(
                message=self.m("invalid_move", "message", available=available_actions),
                observation_type=ta.ObservationType.GAME_MESSAGE
            )

            # Don't call self.state.step() here as it would reset made_invalid_move
            # Instead, return a tuple indicating the game should continue
            return (False, {"invalid_move": True, "reason": error_reason_text})
        
        self._execute_action(parsed)
        return self.state.step()

    def _parse_action(self, action: str) -> Optional[str]:
        gs = self.state.game_state
        phase = gs["current_phase"]
        
        if phase == "pre_flop":
            if self._PLAY_BET_4X_RE.search(action): return "play_bet_4x"
            if self._CHECK_RE.search(action): return "check"
        elif phase == "flop":
            if gs["play_bet"] == 100:
                if self._SKIP_RE.search(action): return "skip"
            else:
                if self._PLAY_BET_2X_RE.search(action): return "play_bet_2x"
                if self._CHECK_RE.search(action): return "check"
        elif phase == "river":
            if gs["play_bet"] in (100, 50):
                if self._SKIP_RE.search(action): return "skip"
            else:
                if self._PLAY_BET_1X_RE.search(action): return "play_bet_1x"
                if self._FOLD_RE.search(action): return "fold"
        elif phase == "showdown":
            if self._SKIP_RE.search(action): return "skip"
        return None

    def _execute_action(self, parsed: str):
        gs = self.state.game_state
        phase = gs["current_phase"]
        
        if phase == "pre_flop":
            if parsed == "play_bet_4x":
                gs["play_bet"] = 100
                gs["chips"] -= 100
                gs["total_bet"] += 100
                # reveal flop
                gs["visible_community_cards"] = gs["community_cards"][:3]
                self.state.add_observation(message=self.m("board", "flop_revealed", cards=self._cards_str(gs['visible_community_cards'])), observation_type=ta.ObservationType.GAME_MESSAGE)
                gs["current_phase"] = "flop"
                gs["legal_actions"] = self.legal_action_tree["flop_no_action"][:]
            elif parsed == "check":
                # reveal flop
                gs["visible_community_cards"] = gs["community_cards"][:3]
                self.state.add_observation(message=self.m("board", "flop_revealed", cards=self._cards_str(gs['visible_community_cards'])), observation_type=ta.ObservationType.GAME_MESSAGE)
                gs["current_phase"] = "flop"
                gs["legal_actions"] = self.legal_action_tree["flop"][:]
            return
        
        if phase == "flop":
            if parsed == "skip":
                # reveal remaining two and move to river
                gs["visible_community_cards"] = gs["community_cards"]
                self.state.add_observation(message=self.m("board", "river_revealed", cards=self._cards_str(gs['community_cards'][3:])), observation_type=ta.ObservationType.GAME_MESSAGE)
                gs["current_phase"] = "river"
                # Set correct legal actions based on play bet
                if gs["play_bet"] >= 50:  # 4x or 2x bet already placed
                    gs["legal_actions"] = self.legal_action_tree["river_no_action"][:]
                else:
                    gs["legal_actions"] = self.legal_action_tree["river"][:]
                return
            if parsed == "play_bet_2x":
                gs["play_bet"] = 50
                gs["chips"] -= 50
                gs["total_bet"] += 50
                # reveal remaining two and move to river
                gs["visible_community_cards"] = gs["community_cards"]
                self.state.add_observation(message=self.m("board", "river_revealed", cards=self._cards_str(gs['community_cards'][3:])), observation_type=ta.ObservationType.GAME_MESSAGE)
                gs["current_phase"] = "river"
                gs["legal_actions"] = self.legal_action_tree["river_no_action"][:]
                return
            if parsed == "check":
                # move to river without play bet
                gs["visible_community_cards"] = gs["community_cards"]
                self.state.add_observation(message=self.m("board", "river_revealed", cards=self._cards_str(gs['community_cards'][3:])), observation_type=ta.ObservationType.GAME_MESSAGE)
                gs["current_phase"] = "river"
                gs["legal_actions"] = self.legal_action_tree["river"][:]
                return
        
        if phase == "river":
            if parsed == "skip":
                gs["current_phase"] = "showdown"
                # Immediately resolve showdown - no waiting for player input
                self._resolve_showdown_and_maybe_continue()
                return
            if parsed == "play_bet_1x":
                gs["play_bet"] = 25
                gs["chips"] -= 25
                gs["total_bet"] += 25
                gs["current_phase"] = "showdown"
                # Immediately resolve showdown - no waiting for player input
                self._resolve_showdown_and_maybe_continue()
                return
            if parsed == "fold":
                # mark folded by setting play_bet=0 and annotating
                self.state.add_observation(message=self.m("action", "folded"), observation_type=ta.ObservationType.GAME_MESSAGE)
                gs["folded"] = True  # Mark that player folded
                gs["current_phase"] = "showdown"
                # Immediately resolve showdown - no waiting for player input
                self._resolve_showdown_and_maybe_continue()
                return
        
        # SHOWDOWN phase is now handled automatically in RIVER phase
        # No need to wait for player input

    def _reveal_community_cards(self):
        # kept for compatibility if needed by wrappers; not used in new flow
        pass

    def _resolve_showdown_and_maybe_continue(self):
        gs = self.state.game_state
        # Show all cards and evaluate hands
        dealer_cards = ", ".join(f"{c['rank']}{c['suit']}" for c in gs["dealer_hand"])
        community_cards = ", ".join(f"{c['rank']}{c['suit']}" for c in gs["community_cards"])
        
        # Evaluate best hands for both player and dealer
        player_best_hand = self._evaluate_hand(gs["player_hand"] + gs["community_cards"])
        dealer_best_hand = self._evaluate_hand(gs["dealer_hand"] + gs["community_cards"])
        
        # Get hand names
        player_hand_name = self._get_hand_name(player_best_hand)
        dealer_hand_name = self._get_hand_name(dealer_best_hand)
        
        self.state.add_observation(message=self.m("showdown", "dealer_hand", cards=dealer_cards), observation_type=ta.ObservationType.GAME_MESSAGE)
        self.state.add_observation(message=self.m("showdown", "community_cards", cards=community_cards), observation_type=ta.ObservationType.GAME_MESSAGE)
        # Get the best 5-card combination for display
        player_best_cards = self._get_best_five_cards(gs["player_hand"] + gs["community_cards"])
        dealer_best_cards = self._get_best_five_cards(gs["dealer_hand"] + gs["community_cards"])
        
        player_cards_str = ", ".join([f"{c['rank']}{c['suit']}" for c in player_best_cards])
        dealer_cards_str = ", ".join([f"{c['rank']}{c['suit']}" for c in dealer_best_cards])
        
        self.state.add_observation(message=self.m("showdown", "player_best", name=player_hand_name, cards=player_cards_str), observation_type=ta.ObservationType.GAME_MESSAGE)
        self.state.add_observation(message=self.m("showdown", "dealer_best", name=dealer_hand_name, cards=dealer_cards_str), observation_type=ta.ObservationType.GAME_MESSAGE)
        
        # Calculate results using separate functions (now return chip amounts)
        if gs.get("folded", False):
            # Player folded - lose ANTE and BLIND bets, PLAY bet is 0 (already handled)
            ante_winnings = 0
            blind_winnings = 0
            play_winnings = 0
        else:
            # Normal showdown - calculate all bets
            ante_winnings = self._calculate_ante_result(gs["ante_bet"], gs["player_hand"], gs["dealer_hand"])
            blind_winnings = self._calculate_blind_result(gs["blind_bet"], gs["player_hand"], gs["dealer_hand"])
            play_winnings = self._calculate_play_result(gs["play_bet"], gs["player_hand"], gs["dealer_hand"])
        
        # Add winnings to chips
        gs["chips"] += ante_winnings + blind_winnings + play_winnings
        total_winnings = ante_winnings + blind_winnings + play_winnings
        
        # Report results with proper categorization
        if gs.get("folded", False):
            # Player folded - report losses
            self.state.add_observation(message=self.m("showdown", "ante_lost_folded", ante=gs['ante_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)
            self.state.add_observation(message=self.m("showdown", "blind_lost_folded", blind=gs['blind_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)
        else:
            # Normal showdown - report results
            if ante_winnings > gs["ante_bet"]:
                self.state.add_observation(message=self.m("showdown", "ante_won", amount=ante_winnings - gs['ante_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)
            elif ante_winnings == gs["ante_bet"]:
                self.state.add_observation(message=self.m("showdown", "ante_pushed", ante=gs['ante_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)
            else:
                self.state.add_observation(message=self.m("showdown", "ante_lost", ante=gs['ante_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)

            if blind_winnings > gs["blind_bet"]:
                self.state.add_observation(message=self.m("showdown", "blind_won", amount=blind_winnings - gs['blind_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)
            elif blind_winnings == gs["blind_bet"]:
                self.state.add_observation(message=self.m("showdown", "blind_pushed", blind=gs['blind_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)
            else:
                self.state.add_observation(message=self.m("showdown", "blind_lost", blind=gs['blind_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)

        if gs["play_bet"] > 0:
            if play_winnings > gs["play_bet"]:
                self.state.add_observation(message=self.m("showdown", "play_won", amount=play_winnings - gs['play_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)
            elif play_winnings == gs["play_bet"]:
                self.state.add_observation(message=self.m("showdown", "play_pushed", play=gs['play_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)
            else:
                self.state.add_observation(message=self.m("showdown", "play_lost", play=gs['play_bet']), observation_type=ta.ObservationType.GAME_MESSAGE)

        # Calculate net result
        net = total_winnings - gs["total_bet"]
        self.state.add_observation(message=(self.m("showdown", "net_gain", round=gs['current_round'], net=net) if net>0 else self.m("showdown", "net_loss", round=gs['current_round'], net=net)), observation_type=ta.ObservationType.GAME_MESSAGE)

        # Add a small separator to ensure showdown output is visible
        self.state.add_observation(message=self.m("showdown", "separator"), observation_type=ta.ObservationType.GAME_MESSAGE)
        
        # Check end conditions BEFORE starting new round to ensure showdown output is visible
        if gs["chips"] <= 0:
            # Player lost - out of chips
            self.state.add_observation(message=self.m("outcome", "game_over_lose"), observation_type=ta.ObservationType.GAME_MESSAGE)
            # Mark game as complete but don't call set_outcome yet to ensure messages are visible
            gs["game_complete"] = True
            gs["winner"] = "dealer"
            return
        if gs["current_round"] >= self.max_turns:
            # Player won - completed all rounds with chips
            self.state.add_observation(message=self.m("outcome", "game_over_win", max_turns=self.max_turns, chips=gs['chips']), observation_type=ta.ObservationType.GAME_MESSAGE)
            # Mark game as complete but don't call set_outcome yet to ensure messages are visible
            gs["game_complete"] = True
            gs["winner"] = "player"
            return
        
        # Start next round only if game continues
        self._start_new_round()

    # Separate bet result functions for easy customization
    def _calculate_ante_result(self, bet_amount: int, player_hand: List[Dict], dealer_hand: List[Dict]) -> int:
        """
        Calculate ANTE bet result.
        Args:
            bet_amount: Amount of the ante bet
            player_hand: List of player's cards [{"rank": "A", "suit": "♠"}, ...]
            dealer_hand: List of dealer's cards [{"rank": "K", "suit": "♥"}, ...]
        Returns:
            Amount of chips won.
        """
        player_best_hand = self._evaluate_hand(player_hand + self.state.game_state["community_cards"])
        dealer_best_hand = self._evaluate_hand(dealer_hand + self.state.game_state["community_cards"])

        dealer_qualifies = dealer_best_hand[0] >= 2
        # Check if dealer qualifies (needs at least a pair)
        if not dealer_qualifies:
            # Dealer doesn't qualify - PUSH (return bet)
            return bet_amount

        # Dealer qualifies -  compare hand strengths (higher tuple wins)
        if player_best_hand > dealer_best_hand:
            return bet_amount * 2  # 1:1 payout (bet + winnings)
        elif player_best_hand < dealer_best_hand:
            return 0  # Lose bet
        else:
            return bet_amount  # Tie - PUSH (return bet)
    
    def _calculate_blind_result(self, bet_amount: int, player_hand: List[Dict], dealer_hand: List[Dict]) -> int:
        """
        Calculate BLIND bet result.
        Args:
            bet_amount: Amount of the blind bet
            player_hand: List of player's cards [{"rank": "A", "suit": "♠"}, ...]
            dealer_hand: List of dealer's cards [{"rank": "K", "suit": "♥"}, ...]
        Returns:
            Amount of chips won.
        """
        
        # Dealer qualifies - compare hands
        player_best_hand = self._evaluate_hand(player_hand + self.state.game_state["community_cards"])
        dealer_best_hand = self._evaluate_hand(dealer_hand + self.state.game_state["community_cards"])
        
        if player_best_hand < dealer_best_hand:
            return 0  # Player loses
        elif player_best_hand == dealer_best_hand:
            return bet_amount  # Tie - PUSH (return bet)
        else:
            # Player wins - calculate payout based on hand strength
            hand_score = player_best_hand[0]  # First element is hand category
            return self._get_blind_payout(bet_amount, hand_score)+bet_amount
    
    def _get_blind_payout(self, bet_amount: int, hand_score: int) -> int:
        """
        Calculate BLIND bet payout based on hand strength.
        Args:
            bet_amount: Amount of the blind bet
            hand_score: Hand category score from _evaluate_hand
        Returns:
            Amount of chips won as additional payout.
        """
        # Hand categories from _evaluate_hand (higher = better)
        # 10: Royal Flush, 9: Straight Flush, 8: Four of a Kind, 7: Full House, 6: Flush, 5: Straight
        if hand_score >= 10:  # Royal Flush
            return bet_amount * 500
        elif hand_score >= 9:  # Straight Flush
            return bet_amount * 50
        elif hand_score >= 8:  # Four of a Kind
            return bet_amount * 10
        elif hand_score >= 7:  # Full House
            return bet_amount * 3
        elif hand_score >= 6:  # Flush
            return bet_amount * 3
        elif hand_score >= 5:  # Straight
            return bet_amount * 1
        else:
            # Less than straight - no payout
            return 0
    
    def _calculate_play_result(self, bet_amount: int, player_hand: List[Dict], dealer_hand: List[Dict]) -> int:
        """
        Calculate PLAY bet result by comparing player vs dealer hands.
        Args:
            bet_amount: Amount of the play bet
            player_hand: List of player's cards [{"rank": "A", "suit": "♠"}, ...]
            dealer_hand: List of dealer's cards [{"rank": "K", "suit": "♥"}, ...]
        Returns:
            Amount of chips won.
        """
        if bet_amount == 0:
            return 0
        
        # PLAY bet is unaffected by dealer qualification - direct hand comparison
        player_best_hand = self._evaluate_hand(player_hand + self.state.game_state["community_cards"])
        dealer_best_hand = self._evaluate_hand(dealer_hand + self.state.game_state["community_cards"])
        
        # Compare hands (higher tuple wins)
        if player_best_hand > dealer_best_hand:
            return bet_amount * 2  # Player wins
        elif player_best_hand == dealer_best_hand:
            return bet_amount  # Tie - PUSH (return bet)
        else:
            return 0  # Dealer wins or tie (dealer wins in case of tie)

    def _evaluate_hand(self, cards: List[Dict[str, str]]) -> Tuple[int, List[int]]:
        """
        Evaluate the best 5-card poker hand from 7 cards (2 hole + 5 community).
        Returns (category_rank, tiebreak_list) where higher tuple wins.
        Based on Poker environment's _evaluate_hand function.
        """
        if len(cards) < 5:
            return (0, [])  # Invalid hand
        
        # Get all possible 5-card combinations and find the best one
        from itertools import combinations
        
        best_hand = (0, [])
        for five_cards in combinations(cards, 5):
            hand_score = self._evaluate_five_card_hand(five_cards)
            if hand_score > best_hand:
                best_hand = hand_score
        
        return best_hand
    
    def _evaluate_five_card_hand(self, cards: List[Dict[str, str]]) -> Tuple[int, List[int]]:
        """
        Evaluate a 5-card poker hand.
        Returns (category_rank, tiebreak_list) where higher tuple wins.
        """
        ranks = [self.rank_values[card["rank"]] for card in cards]
        suits = [card["suit"] for card in cards]
        
        # Count occurrences
        rank_counts = {}
        suit_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        for suit in suits:
            suit_counts[suit] = suit_counts.get(suit, 0) + 1
        
        # Check for flush
        flush = any(count >= 5 for count in suit_counts.values())
        
        # Check for straight
        unique_ranks = sorted(set(ranks))
        straight = False
        straight_high = 0
        if len(unique_ranks) >= 5:
            # Check for wheel (A-2-3-4-5)
            if {14, 2, 3, 4, 5}.issubset(set(unique_ranks)):
                straight = True
                straight_high = 5
            else:
                # Check for regular straight
                for i in range(len(unique_ranks) - 4):
                    if unique_ranks[i+4] - unique_ranks[i] == 4:
                        straight = True
                        straight_high = unique_ranks[i+4]
                        break
        
        # Royal flush (10) - A-K-Q-J-10 of same suit
        if straight and flush and straight_high == 14:  # Ace high straight flush
            return (10, [14])
        
        # Straight flush (9)
        if straight and flush:
            return (9, [straight_high])
        
        # Four of a kind (8)
        for rank, count in rank_counts.items():
            if count == 4:
                kicker = max(r for r in ranks if r != rank)
                return (8, [rank, kicker])
        
        # Full house (7)
        three_rank = None
        pair_rank = None
        for rank, count in rank_counts.items():
            if count == 3 and three_rank is None:
                three_rank = rank
            elif count >= 2 and pair_rank is None and rank != three_rank:
                pair_rank = rank
        if three_rank and pair_rank:
            return (7, [three_rank, pair_rank])
        
        # Flush (6)
        if flush:
            flush_ranks = sorted([r for r, s in zip(ranks, suits) if s == max(suit_counts, key=suit_counts.get)], reverse=True)
            return (6, flush_ranks[:5])
        
        # Straight (5)
        if straight:
            return (5, [straight_high])
        
        # Three of a kind (4)
        for rank, count in rank_counts.items():
            if count == 3:
                kickers = sorted([r for r in ranks if r != rank], reverse=True)[:2]
                return (4, [rank] + kickers)
        
        # Two pair (3)
        pairs = [r for r, count in rank_counts.items() if count == 2]
        if len(pairs) >= 2:
            pairs.sort(reverse=True)
            kicker = max(r for r in ranks if r not in pairs)
            return (3, pairs[:2] + [kicker])
        
        # One pair (2)
        for rank, count in rank_counts.items():
            if count == 2:
                kickers = sorted([r for r in ranks if r != rank], reverse=True)[:3]
                return (2, [rank] + kickers)
        
        # High card (1)
        return (1, sorted(ranks, reverse=True)[:5])
    
    def _get_hand_name(self, hand_score: Tuple[int, List[int]]) -> str:
        """
        Convert hand score tuple to readable hand name.
        Args:
            hand_score: Tuple (category_rank, tiebreak_list)
        Returns:
            String representation of the hand
        """
        category, tiebreaks = hand_score
        hand_name_keys = {
            10: "royal_flush",
            9: "straight_flush",
            8: "four_of_a_kind",
            7: "full_house",
            6: "flush",
            5: "straight",
            4: "three_of_a_kind",
            3: "two_pair",
            2: "one_pair",
            1: "high_card"
        }
        return self.m("hand_names", hand_name_keys.get(category, "unknown"))
    
    def _get_best_five_cards(self, cards: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Get the best 5-card combination from 7 cards.
        Args:
            cards: List of 7 cards (2 hole + 5 community)
        Returns:
            List of 5 cards that form the best hand
        """
        if len(cards) < 5:
            return cards
        
        from itertools import combinations
        
        best_hand = None
        best_score = (0, [])
        
        for five_cards in combinations(cards, 5):
            hand_score = self._evaluate_five_card_hand(five_cards)
            if hand_score > best_score:
                best_score = hand_score
                best_hand = list(five_cards)
        
        return best_hand if best_hand else cards[:5] 
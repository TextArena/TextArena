import re
from typing import Tuple, Dict, Any, Optional, List, Union

import textarena as ta
from textarena.envs.UltimateTexasHoldem.renderer import create_board_str


class UltimateTexasHoldemEnv(ta.GameEnv):
    """Ultimate Texas Hold'em - Single player vs dealer poker game."""

    min_players = 1
    max_players = 1
    mdp_includes_actions = False

    # Action patterns - bare actions ('1x', '2x', '4x', ...).
    # A whitespace run must be consumable by only one \s*, as retrying every split of a long run is quadratic.
    _PLAY_BET_4X_RE = re.compile(r"^(?:4x?|play\s+bet\s+4x?|play\s+4x?\s+bet|play_bet_4x)$", re.IGNORECASE)
    _PLAY_BET_3X_RE = re.compile(r"^(?:3x?|play\s+bet\s+3x?|play\s+3x?\s+bet|play_bet_3x)$", re.IGNORECASE)
    _PLAY_BET_2X_RE = re.compile(r"^(?:2x?|play\s+bet\s+2x?|play\s+2x?\s+bet|play_bet_2x)$", re.IGNORECASE)
    _PLAY_BET_1X_RE = re.compile(r"^(?:1x?|play\s+bet\s+1x?|play\s+1x?\s+bet|play_bet_1x)$", re.IGNORECASE)
    _CHECK_RE = re.compile(r"^(?:check|c)$", re.IGNORECASE)
    _FOLD_RE = re.compile(r"^(?:fold|f)$", re.IGNORECASE)
    _SKIP_RE = re.compile(r"^(?:skip|s)$", re.IGNORECASE)

    max_rounds = ta.Param(1000, "The number of rounds to survive.", min=1)
    start_chips = ta.Param(1000, "The starting chips. They must cover at least one Ante and Blind.", min=1)
    ante_amount = ta.Param(25, "The Ante and the Blind. Play bets are multiples of it.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.start_chips < 2 * self.ante_amount:
            raise ValueError("start_chips must cover the initial ante and blind")

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
            "pre_flop": ["play_bet_4x", "play_bet_3x", "check"],
            "flop_no_action": ["skip"],            # When 4x placed pre-flop
            "flop": ["play_bet_2x", "check"],     # When no 4x placed
            "river_no_action": ["skip"],           # When 4x or 2x already placed
            "river": ["play_bet_1x", "fold"],     # When no prior play bet
            # SHOWDOWN phase is automatic - no legal actions needed
        }

    def get_board_str(self):
        return create_board_str(self.state.game_state)

    def setup(self) -> Dict[str, Any]:
        return {
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
            "deck": [],
            "max_rounds": self.max_rounds,
            "game_complete": False,
            "winner": None,
        }

    def on_start(self):
        self._start_new_round()

    def _start_new_round(self):
        gs = self.game_state
        gs["current_round"] += 1
        gs["current_phase"] = "pre_round"
        gs["round_complete"] = False

        deck = self._create_deck()
        self.rng.shuffle(deck)

        gs["player_hand"] = [deck.pop(), deck.pop()]
        gs["dealer_hand"] = [deck.pop(), deck.pop()]
        gs["community_cards"] = [deck.pop() for _ in range(5)]
        gs["deck"] = deck
        gs["visible_community_cards"] = []

        gs["ante_bet"] = self.ante_amount
        gs["blind_bet"] = self.ante_amount
        gs["play_bet"] = 0
        gs["total_bet"] = gs["ante_bet"] + gs["blind_bet"]
        gs["chips"] -= gs["total_bet"]
        gs["folded"] = False  # Reset folded flag for new round

        gs["current_phase"] = "pre_flop"
        gs["legal_actions"] = self.legal_action_tree["pre_flop"][:]

        self.broadcast(f"🎮 Round {gs['current_round']} started! Bets: ANTE ${gs['ante_bet']}, BLIND ${gs['blind_bet']}. You have {gs['chips']} chips remaining.", ta.ObservationType.GAME_MESSAGE)

    def _create_deck(self) -> List[Dict[str, str]]:
        return [{"rank": r, "suit": s} for s in self.suits for r in self.ranks]

    @staticmethod
    def _cards_str(cards: List[Dict[str, str]]) -> str:
        return ", ".join(f"{card['rank']}{card['suit']}" for card in cards)

    def prompt(self, player_id: int) -> str:
        rules = (
            "🎯 ULTIMATE TEXAS HOLD'EM - Single Player vs Dealer\n\n"
            "📖 GAME OVERVIEW:\n"
            f"• You start with {self.start_chips} chips\n"
            "• Single deck of 52 cards (2♠-A♠, 2♥-A♥, 2♦-A♦, 2♣-A♣)\n"
            "• You play against the dealer (house)\n"
            "• Each round follows the Ultimate Texas Hold'em structure: you post ANTE and BLIND bets, receive 2 hole cards, decide on optional PLAY bets across the betting phases, then reveal community cards and compare your best 5-card hand against the dealer’s. Your goal is to maximize your winnings (when you have the better hand), while minimizing your losses (when you have the worse hand).\n"
            f"• Game ends when you cannot continue funding play (LOSS) or complete {self.max_rounds} rounds with chips (WIN)\n\n"

            "💰 BETTING STRUCTURE:\n"
            f"• ANTE: Mandatory ${self.ante_amount} bet every round\n"
            f"• BLIND: Mandatory ${self.ante_amount} bet every round\n"
            f"• PLAY: Optional bet during gameplay. Throughout the round, you may choose ONLY ONE of the following: (${self.ante_amount*3} or ${self.ante_amount*4} if done at PRE-FLOP, ${self.ante_amount*2} if done at FLOP, or ${self.ante_amount} if done at RIVER. Can also fold at river, giving up on the hand, and making no bet.)\n\n"

            "🎴 CARD DEALING:\n"
            "• You receive 2 face-up cards (your hole cards)\n"
            "• Dealer receives 2 face-down cards (hidden from you)\n"
            "• 5 community cards are dealt face-down initially\n"
            "• Community cards are revealed progressively through the game phases\n\n"

            "🏆 DEALER QUALIFICATION:\n"
            "• Dealer must have at least a PAIR (2 cards of same rank) to qualify, using the 2 cards in their hand and the 5 community cards.\n"
            "• Dealer qualification affects the betting outcomes, as will be explained later.\n\n"

            "🎮 GAME PHASES & ACTIONS:\n"
            "📋 PRE-FLOP:\n"
            f"  • Actions: '3x' (${self.ante_amount*3}), '4x' (${self.ante_amount*4}), or 'check'\n"
            f"  • '3x': Place ${self.ante_amount*3} PLAY bet, reveals first 3 community cards\n"
            f"  • '4x': Place ${self.ante_amount*4} PLAY bet, reveals first 3 community cards\n"
            f"  • 'check': No additional bet, reveals first 3 community cards\n\n"

            "📋 FLOP:\n"
            f"  • If 4x bet placed: Only 'skip' available (auto-reveals last 2 community cards)\n"
            f"  • If no 4x bet: '2x' (${self.ante_amount*2}) or 'check'\n"
            f"  • '2x': Place ${self.ante_amount*2} PLAY bet, reveals last 2 community cards\n"
            f"  • 'check': No additional bet, reveals last 2 community cards\n\n"

            "📋 RIVER:\n"
            f"  • If 4x or 2x bet placed: Only 'skip' available (auto-proceeds to showdown)\n"
            f"  • If no prior PLAY bet: '1x' (${self.ante_amount}) or 'fold'\n"
            f"  • '1x': Place ${self.ante_amount} PLAY bet, proceeds to showdown\n"
            f"  • 'fold': Give up hand, lose ANTE and BLIND bets\n\n"

            "📋 SHOWDOWN:\n"
            "  • All cards revealed and evaluated\n"
            "  • Best 5-card hand from 7 cards (2 hole + 5 community)\n"
            "  • Bets settled according to payout rules\n\n"

            "💎 BET PAYOUTS:\n"
            "📊 ANTE BET:\n"
            "  • Dealer doesn't qualify: PUSH (bet returned)\n"
            "  • Dealer qualifies & you win: 1:1 payout (bet + winnings)\n"
            "  • Dealer qualifies & you lose: Bet lost\n"
            "  • Tie: PUSH (bet returned)\n\n"

            "📊 BLIND BET:\n"
            "  • Unaffected by dealer qualification\n"
            "  • You win: Bet returned and additional payout based on your hand strength\n"
            "  • You lose: Bet lost\n"
            "  • Tie: PUSH (bet returned)\n\n"

            "📊 BLIND BET PAY TABLE:\n"
            f"  • Royal Flush: 500:1 (${self.ante_amount * 500})\n"
            f"  • Straight Flush: 50:1 (${self.ante_amount * 50})\n"
            f"  • Four of a Kind: 10:1 (${self.ante_amount * 10})\n"
            f"  • Full House: 3:1 (${self.ante_amount * 3})\n"
            f"  • Flush: 3:2 (${self.ante_amount * 1.5:g})\n"
            f"  • Straight: 1:1 (${self.ante_amount * 1})\n"
            "  • Less than Straight: No additional payout\n\n"

            "📊 PLAY BET:\n"
            "  • Unaffected by dealer qualification\n"
            "  • Direct comparison: Your best hand vs Dealer's best hand\n"
            "  • You win: 1:1 payout (bet + winnings)\n"
            "  • You lose: Bet lost\n"
            "  • Tie: PUSH (bet returned)\n\n"

            "🎯 POKER HAND RANKINGS (Best to Worst):\n"
            "  1. Royal Flush: A-K-Q-J-10 of same suit\n"
            "  2. Straight Flush: 5 consecutive cards of same suit\n"
            "  3. Four of a Kind: 4 cards of same rank\n"
            "  4. Full House: 3 of a kind + 2 of a kind\n"
            "  5. Flush: 5 cards of same suit\n"
            "  6. Straight: 5 consecutive cards\n"
            "  7. Three of a Kind: 3 cards of same rank\n"
            "  8. Two Pair: 2 pairs of different ranks\n"
            "  9. One Pair: 2 cards of same rank\n"
            "  10. High Card: Highest card wins\n\n"

            "⌨️  ACTION COMMANDS:\n"
            f"• '4x' or 'play bet 4x': Place ${self.ante_amount*4} PLAY bet\n"
            f"• '3x' or 'play bet 3x': Place ${self.ante_amount*3} PLAY bet\n"
            f"• '2x' or 'play bet 2x': Place ${self.ante_amount*2} PLAY bet\n"
            f"• '1x' or 'play bet 1x': Place ${self.ante_amount} PLAY bet\n"
            "• 'check' or 'c': Check (no additional bet)\n"
            "• 'fold' or 'f': Fold (give up hand)\n"
            "• 'skip' or 's': Skip to next phase (when no action needed)\n\n"

            "💡 STRATEGY TIPS:\n"
            "• Strong starting hands (pairs, high cards) often justify 4x bets\n"
            "• Consider dealer qualification - weak hands may push if dealer doesn't qualify\n"
            "• BLIND bet can be very profitable with strong hands (Royal Flush = 500:1!)\n"
            f"• Watch your chip stack! If a round leaves you with less than ${2 * self.ante_amount} for the next ANTE and BLIND, you lose.\n\n"

            "⚠️  IMPORTANT NOTES:\n"
            "• ANTE and BLIND bets are mandatory every round\n"
            "• PLAY bets are optional and strategic\n"
            "• Make sure you input the correct action, and only one action at a time.\n"
            "• Before every decision you are shown your cards, the revealed community cards, your bets and the available actions.\n\n"
        )
        return rules

    _ACTION_NAMES = {
        "play_bet_4x": "4x", "play_bet_3x": "3x", "play_bet_2x": "2x", "play_bet_1x": "1x",
        "check": "check", "fold": "fold", "skip": "skip",
    }

    def _available_actions(self) -> str:
        return ", ".join(f"'{self._ACTION_NAMES[action]}'" for action in self.game_state["legal_actions"])

    def render(self, player_id: int) -> str:
        gs = self.game_state
        hidden = len(gs["community_cards"]) - len(gs["visible_community_cards"])
        community = self._cards_str(gs["visible_community_cards"]) or "none revealed"
        lines = [
            f"Round {gs['current_round']} of {self.max_rounds} - {self.game_phases[gs['current_phase']]}",
            f"Chips: {gs['chips']} (excluding the bets below)",
            f"Bets: Ante ${gs['ante_bet']}, Blind ${gs['blind_bet']}, Play ${gs['play_bet']}",
            f"Your hand: {self._cards_str(gs['player_hand'])}",
            f"Community cards: {community}" + (f" ({hidden} still hidden)" if hidden else ""),
            "Dealer's hand: hidden",
        ]
        if not self.state.done:
            lines.append(f"Available actions: {self._available_actions()}")
        return "\n".join(lines)

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        parsed = self._parse_action(action)

        if parsed is None:
            return self.invalid(f"Invalid action for current phase. Available actions: {self._available_actions()}")

        wager = {
            "play_bet_4x": 4 * self.ante_amount,
            "play_bet_3x": 3 * self.ante_amount,
            "play_bet_2x": 2 * self.ante_amount,
            "play_bet_1x": self.ante_amount,
        }.get(parsed, 0)
        if wager > gs["chips"]:
            return self.invalid(
                f"Insufficient chips for a ${wager} play bet; you have ${gs['chips']}."
            )

        self._execute_action(parsed)
        if gs.get("game_complete", False):
            return self._final_outcome()
        return None

    def _final_outcome(self) -> ta.Outcome:
        gs = self.game_state
        if gs.get("winner") == "player":
            return self.outcome(
                {0: 1.0},
                reason=f"Player completed {gs['current_round']} rounds with ${gs['chips']} chips",
            )
        return self.outcome(
            {0: 0.0},
            reason=f"Player could not continue after round {gs['current_round']}",
        )

    def _parse_action(self, action: str) -> Optional[str]:
        gs = self.game_state
        phase = gs["current_phase"]

        if phase == "pre_flop":
            if self._PLAY_BET_4X_RE.search(action): return "play_bet_4x"
            if self._PLAY_BET_3X_RE.search(action): return "play_bet_3x"
            if self._CHECK_RE.search(action): return "check"
        elif phase == "flop":
            if gs["play_bet"] > 0:
                if self._SKIP_RE.search(action): return "skip"
            else:
                if self._PLAY_BET_2X_RE.search(action): return "play_bet_2x"
                if self._CHECK_RE.search(action): return "check"
        elif phase == "river":
            if gs["play_bet"] > 0:
                if self._SKIP_RE.search(action): return "skip"
            else:
                if self._PLAY_BET_1X_RE.search(action): return "play_bet_1x"
                if self._FOLD_RE.search(action): return "fold"
        return None

    def _execute_action(self, parsed: str):
        gs = self.game_state
        phase = gs["current_phase"]

        if phase == "pre_flop":
            if parsed in {"play_bet_4x", "play_bet_3x"}:
                multiplier = 4 if parsed == "play_bet_4x" else 3
                gs["play_bet"] = multiplier * self.ante_amount
                gs["chips"] -= gs["play_bet"]
                gs["total_bet"] += gs["play_bet"]
                # reveal flop
                gs["visible_community_cards"] = gs["community_cards"][:3]
                self.broadcast(f"🃏 FLOP revealed: {self._cards_str(gs['visible_community_cards'])}", ta.ObservationType.GAME_MESSAGE)
                gs["current_phase"] = "flop"
                gs["legal_actions"] = self.legal_action_tree["flop_no_action"][:]
            elif parsed == "check":
                # reveal flop
                gs["visible_community_cards"] = gs["community_cards"][:3]
                self.broadcast(f"🃏 FLOP revealed: {self._cards_str(gs['visible_community_cards'])}", ta.ObservationType.GAME_MESSAGE)
                gs["current_phase"] = "flop"
                gs["legal_actions"] = self.legal_action_tree["flop"][:]
            return

        if phase == "flop":
            if parsed == "skip":
                # reveal remaining two and move to river
                gs["visible_community_cards"] = gs["community_cards"]
                self.broadcast(f"🃏 RIVER revealed: {self._cards_str(gs['community_cards'][3:])}", ta.ObservationType.GAME_MESSAGE)
                gs["current_phase"] = "river"
                # Set correct legal actions based on play bet
                if gs["play_bet"] > 0:
                    gs["legal_actions"] = self.legal_action_tree["river_no_action"][:]
                else:
                    gs["legal_actions"] = self.legal_action_tree["river"][:]
                return
            if parsed == "play_bet_2x":
                gs["play_bet"] = 2 * self.ante_amount
                gs["chips"] -= gs["play_bet"]
                gs["total_bet"] += gs["play_bet"]
                # reveal remaining two and move to river
                gs["visible_community_cards"] = gs["community_cards"]
                self.broadcast(f"🃏 RIVER revealed: {self._cards_str(gs['community_cards'][3:])}", ta.ObservationType.GAME_MESSAGE)
                gs["current_phase"] = "river"
                gs["legal_actions"] = self.legal_action_tree["river_no_action"][:]
                return
            if parsed == "check":
                # move to river without play bet
                gs["visible_community_cards"] = gs["community_cards"]
                self.broadcast(f"🃏 RIVER revealed: {self._cards_str(gs['community_cards'][3:])}", ta.ObservationType.GAME_MESSAGE)
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
                gs["play_bet"] = self.ante_amount
                gs["chips"] -= gs["play_bet"]
                gs["total_bet"] += gs["play_bet"]
                gs["current_phase"] = "showdown"
                # Immediately resolve showdown - no waiting for player input
                self._resolve_showdown_and_maybe_continue()
                return
            if parsed == "fold":
                # mark folded by setting play_bet=0 and annotating
                self.broadcast("🃏 You folded.", ta.ObservationType.GAME_MESSAGE)
                gs["folded"] = True  # Mark that player folded
                gs["current_phase"] = "showdown"
                # Immediately resolve showdown - no waiting for player input
                self._resolve_showdown_and_maybe_continue()
                return

    def _resolve_showdown_and_maybe_continue(self):
        gs = self.game_state
        # Show all cards and evaluate hands
        dealer_cards = ", ".join(f"{c['rank']}{c['suit']}" for c in gs["dealer_hand"])
        community_cards = ", ".join(f"{c['rank']}{c['suit']}" for c in gs["community_cards"])

        # Evaluate best hands for both player and dealer
        player_best_hand = self._evaluate_hand(gs["player_hand"] + gs["community_cards"])
        dealer_best_hand = self._evaluate_hand(gs["dealer_hand"] + gs["community_cards"])

        # Get hand names
        player_hand_name = self._get_hand_name(player_best_hand)
        dealer_hand_name = self._get_hand_name(dealer_best_hand)

        self.broadcast(f"🏁 SHOWDOWN! Dealer's hand: {dealer_cards}", ta.ObservationType.GAME_MESSAGE)
        self.broadcast(f"🃏 Community cards: {community_cards}", ta.ObservationType.GAME_MESSAGE)
        # Get the best 5-card combination for display
        player_best_cards = self._get_best_five_cards(gs["player_hand"] + gs["community_cards"])
        dealer_best_cards = self._get_best_five_cards(gs["dealer_hand"] + gs["community_cards"])

        player_cards_str = ", ".join([f"{c['rank']}{c['suit']}" for c in player_best_cards])
        dealer_cards_str = ", ".join([f"{c['rank']}{c['suit']}" for c in dealer_best_cards])

        self.broadcast(f"🎴 Player's best hand: {player_hand_name} ({player_cards_str})", ta.ObservationType.GAME_MESSAGE)
        self.broadcast(f"🎴 Dealer's best hand: {dealer_hand_name} ({dealer_cards_str})", ta.ObservationType.GAME_MESSAGE)

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
            self.broadcast(f"❌ ANTE bet LOST! -${gs['ante_bet']} (folded)", ta.ObservationType.GAME_MESSAGE)
            self.broadcast(f"❌ BLIND bet LOST! -${gs['blind_bet']} (folded)", ta.ObservationType.GAME_MESSAGE)
        else:
            # Normal showdown - report results
            if ante_winnings > gs["ante_bet"]:
                self.broadcast(f"✅ ANTE bet WON! +${ante_winnings - gs['ante_bet']}", ta.ObservationType.GAME_MESSAGE)
            elif ante_winnings == gs["ante_bet"]:
                self.broadcast(f"🔄 ANTE bet PUSHED! ${gs['ante_bet']} returned", ta.ObservationType.GAME_MESSAGE)
            else:
                self.broadcast(f"❌ ANTE bet LOST! -${gs['ante_bet']}", ta.ObservationType.GAME_MESSAGE)

            if blind_winnings > gs["blind_bet"]:
                self.broadcast(f"✅ BLIND bet WON! +${blind_winnings - gs['blind_bet']}", ta.ObservationType.GAME_MESSAGE)
            elif blind_winnings == gs["blind_bet"]:
                self.broadcast(f"🔄 BLIND bet PUSHED! ${gs['blind_bet']} returned", ta.ObservationType.GAME_MESSAGE)
            else:
                self.broadcast(f"❌ BLIND bet LOST! -${gs['blind_bet']}", ta.ObservationType.GAME_MESSAGE)

        if gs["play_bet"] > 0:
            if play_winnings > gs["play_bet"]:
                self.broadcast(f"✅ PLAY bet WON! +${play_winnings - gs['play_bet']}", ta.ObservationType.GAME_MESSAGE)
            elif play_winnings == gs["play_bet"]:
                self.broadcast(f"🔄 PLAY bet PUSHED! ${gs['play_bet']} returned", ta.ObservationType.GAME_MESSAGE)
            else:
                self.broadcast(f"❌ PLAY bet LOST! -${gs['play_bet']}", ta.ObservationType.GAME_MESSAGE)

        # Calculate net result
        net = total_winnings - gs["total_bet"]
        self.broadcast((f"🎉 Round {gs['current_round']} completed! Net gain: +${net}" if net > 0 else f"💸 Round {gs['current_round']} completed! Net loss: ${net}"), ta.ObservationType.GAME_MESSAGE)

        # Add a small separator to ensure showdown output is visible
        self.broadcast("─" * 50, ta.ObservationType.GAME_MESSAGE)

        # Check end conditions BEFORE starting new round to ensure showdown output is visible
        if gs["chips"] <= 0:
            # Player lost - out of chips
            self.broadcast("🏁 GAME OVER! You're out of chips. Dealer wins!", ta.ObservationType.GAME_MESSAGE)
            gs["game_complete"] = True
            gs["winner"] = "dealer"
            gs["legal_actions"] = []
            gs["round_complete"] = True
            return
        if gs["current_round"] >= self.max_rounds:
            # Player won - completed all rounds with chips
            self.broadcast(f"🏁 GAME OVER! {self.max_rounds} rounds completed. You have ${gs['chips']} chips - YOU WIN!", ta.ObservationType.GAME_MESSAGE)
            gs["game_complete"] = True
            gs["winner"] = "player"
            gs["legal_actions"] = []
            gs["round_complete"] = True
            return
        if gs["chips"] < 2 * self.ante_amount:
            self.broadcast(
                "🏁 GAME OVER! You cannot cover the next round's ANTE and BLIND.",
                ta.ObservationType.GAME_MESSAGE,
            )
            gs["game_complete"] = True
            gs["winner"] = "dealer"
            gs["legal_actions"] = []
            gs["round_complete"] = True
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
        player_best_hand = self._evaluate_hand(player_hand + self.game_state["community_cards"])
        dealer_best_hand = self._evaluate_hand(dealer_hand + self.game_state["community_cards"])

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

    def _calculate_blind_result(self, bet_amount: int, player_hand: List[Dict], dealer_hand: List[Dict]) -> Union[int, float]:
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
        player_best_hand = self._evaluate_hand(player_hand + self.game_state["community_cards"])
        dealer_best_hand = self._evaluate_hand(dealer_hand + self.game_state["community_cards"])

        if player_best_hand < dealer_best_hand:
            return 0  # Player loses
        elif player_best_hand == dealer_best_hand:
            return bet_amount  # Tie - PUSH (return bet)
        else:
            # Player wins - calculate payout based on hand strength
            hand_score = player_best_hand[0]  # First element is hand category
            return self._get_blind_payout(bet_amount, hand_score) + bet_amount

    def _get_blind_payout(self, bet_amount: int, hand_score: int) -> Union[int, float]:
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
            return bet_amount * 1.5
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
        player_best_hand = self._evaluate_hand(player_hand + self.game_state["community_cards"])
        dealer_best_hand = self._evaluate_hand(dealer_hand + self.game_state["community_cards"])

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
        hand_names = {
            10: "Royal Flush",
            9: "Straight Flush",
            8: "Four of a Kind",
            7: "Full House",
            6: "Flush",
            5: "Straight",
            4: "Three of a Kind",
            3: "Two Pair",
            2: "One Pair",
            1: "High Card"
        }
        return hand_names.get(category, "Unknown Hand")

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

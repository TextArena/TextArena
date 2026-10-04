import re
from typing import Any, Dict, Optional, Union

import textarena as ta


class LeTrucEnv(ta.GameEnv):
    """
    Minimal 2-player 'Le Truc'.
    • Deck = 40 cards (remove 8s/9s/10s). Rank order: 3 2 A K Q J 7 6 5 4.
    • Each gets 3 cards. Suits do not affect trick strength.
    • At any time before a trick result a player may 'raise' to increase hand value by +1. Opponent may 'accept' or 'fold'.
    • First to 12 match-points wins.
    """
    min_players = 2
    max_players = 2

    order = ["3", "2", "A", "K", "Q", "J", "7", "6", "5", "4"]

    def __init__(self):
        self.action_space = re.compile(
            r"""^\s*\[?\s*
                (?P<verb>play|raise|accept|fold)            # action keyword
                (?:\s+(?P<card>(10|[234567JQKA])))?         # optional rank
            \s*\]?\s*$""",
            re.IGNORECASE | re.VERBOSE,
        )
        # Build the 40-card deck (a 52-card deck without 8s, 9s, or 10s).
        suits = "♣♦♥♠"
        self.deck = [r + s for r in self.order for s in suits]

    def setup(self) -> Dict[str, Any]:
        return {
            "match_points": {0: 0, 1: 0},
            "hand_points": 1,
            "hand_leader": 0,
        }

    def on_start(self):
        self._deal_hand()

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Le Truc. Win tricks with the stronger rank "
            "(3, 2, A, K, Q, J, 7, 6, 5, 4), and be first to 12 match points. "
            "Play a held rank with 'play <rank>', increase the current hand value with "
            "'raise', or answer a pending raise with exactly 'accept' or 'fold'. "
            "Suits do not affect trick strength."
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        led = gs["led_card"][1] if gs["led_card"] is not None else "None"
        pending = (
            f"Pending raise by Player {gs['raiser']}; reply 'accept' or 'fold'."
            if gs["raiser"] is not None
            else "No raise is pending."
        )
        return (
            f"Match points: P0={gs['match_points'][0]}, P1={gs['match_points'][1]}\n"
            f"Current hand value: {gs['hand_points']}\n"
            f"Your cards: {' '.join(gs['hands'][player_id])}\n"
            f"Led card: {led}; trick winners: {gs['tricks']}\n{pending}"
        )

    def get_board_str(self) -> str:
        """Return the acting player's private board for registered board wrappers."""
        return self.render(self.state.current_player_id)

    def _deal_hand(self):
        gs = self.game_state
        d = self.deck.copy()
        self.rng.shuffle(d)
        gs["hands"] = {0: d[:3], 1: d[3:6]}
        gs["undealt_cards"] = d[6:]
        gs["tricks"] = []
        gs["played_cards"] = []
        gs["led_card"] = None
        gs["led_to"] = None
        gs["raiser"] = None
        gs["pending_raise_value"] = None

        for pid in (0, 1):
            self.message(pid, f"### New hand worth {gs['hand_points']} pt(s)\nYour cards: {' '.join(gs['hands'][pid])}", ta.ObservationType.GAME_BOARD)

    def _rank_idx(self, card: str) -> int: return self.order.index(card[:-1])

    def _hand_winner(self) -> Optional[int]:
        """Resolve a hand, using the first trick only as the final tie-break."""
        tricks = self.game_state["tricks"]
        if len(tricks) < 2:
            return None
        if len(tricks) == 2:
            non_tied = [winner for winner in tricks if winner is not None]
            if not non_tied:
                return None
            if len(non_tied) == 1 or non_tied[0] == non_tied[1]:
                return non_tied[0]
            return None
        wins = {pid: tricks.count(pid) for pid in (0, 1)}
        if wins[0] >= 2:
            return 0
        if wins[1] >= 2:
            return 1
        # If each player won once and the third trick was tied, the player
        # who captured the earlier trick wins. If all three tied, the hand
        # is void and neither player scores.
        return next((winner for winner in tricks if winner is not None), None)

    def _start_next_hand(self):
        gs = self.game_state
        gs["hand_points"] = 1
        gs["hand_leader"] = 1 - gs["hand_leader"]
        self._deal_hand()
        self.set_next_player(gs["hand_leader"])

    def _award_hand(self, winner: int) -> Optional[ta.Outcome]:
        gs = self.game_state
        gs["match_points"][winner] += gs["hand_points"]
        if gs["match_points"][winner] >= 12:
            return self.winner(winner, reason="Reached 12 points.")
        self._start_next_hand()
        return None

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        pid = player_id
        gs = self.game_state

        m = self.action_space.match(action)
        if not m:
            return self.invalid("Unrecognised action.")
        verb = m.group("verb").lower()
        rank_arg = m.group("card")

        if verb != "play" and rank_arg is not None:
            return self.invalid(f"'{verb}' does not take a card argument.")
        if gs.get("raiser") is not None and verb not in {"accept", "fold"}:
            return self.invalid("A raise is pending; you must reply with 'accept' or 'fold'.")

        if verb == "raise":
            gs["raiser"] = pid
            gs["pending_raise_value"] = gs["hand_points"] + 1
            self.broadcast(
                f"P{pid} proposes raising the hand from {gs['hand_points']} to "
                f"{gs['pending_raise_value']} pts. Opponent must 'accept' or 'fold'.",
                ta.ObservationType.GAME_MESSAGE,
            )
            return None  # default rotation: the opponent must respond

        if verb == "accept":
            if gs.get("raiser") is None or pid == gs["raiser"]:
                return self.invalid("No raise to accept.")

            raiser = gs["raiser"]
            gs["hand_points"] = gs["pending_raise_value"]
            gs["raiser"] = None
            gs["pending_raise_value"] = None
            # resume with whoever still has to follow suit first;
            # if no trick is underway, the raiser leads
            self.set_next_player(gs["led_to"] if gs["led_card"] is not None else raiser)
            return None

        if verb == "fold":
            if gs.get("raiser") is None or pid == gs["raiser"]:
                return self.invalid("Cannot fold now.")

            winner = 1 - pid
            # Refusing a raise concedes the hand at its previously accepted
            # value, not at the newly proposed value.
            gs["match_points"][winner] += gs["hand_points"]
            self.broadcast(
                f"P{pid} folds. P{winner} gains {gs['hand_points']} match point(s).",
                ta.ObservationType.GAME_MESSAGE,
            )
            if gs["match_points"][winner] >= 12:
                return self.winner(winner, reason="Reached 12 points after opponent folded.")
            self._start_next_hand()
            return None

        if verb == "play":
            rank = rank_arg
            if rank is None:
                return self.invalid("Unrecognised action.")
            rank = rank.upper()

            # ensure player owns that rank (ignore suits in input)
            if rank not in [c[:-1] for c in gs["hands"][pid]]:
                return self.invalid("You don't hold that rank (suits ignored in input).")

            # pick the first matching suit in hand
            idx = next(i for i, c in enumerate(gs["hands"][pid]) if c.startswith(rank))
            card_str = gs["hands"][pid].pop(idx)
            gs["played_cards"].append(card_str)

            if gs["led_card"] is None:
                # lead the trick
                gs["led_card"] = (pid, card_str)
                gs["led_to"] = 1 - pid
                self.broadcast(f"P{pid} leads {card_str}.", ta.ObservationType.GAME_MESSAGE)
                return None  # default rotation: opponent follows
            else:
                # follow, decide trick winner
                lead_pid, lead_card = gs["led_card"]
                lead_strength = self._rank_idx(lead_card)
                follow_strength = self._rank_idx(card_str)
                if follow_strength < lead_strength:
                    win_pid = pid
                elif follow_strength > lead_strength:
                    win_pid = lead_pid
                else:
                    win_pid = None

                gs["tricks"].append(win_pid)
                if win_pid is None:
                    self.broadcast(
                        f"P{pid} plays {card_str}. The trick is tied.",
                        ta.ObservationType.GAME_MESSAGE,
                    )
                else:
                    self.broadcast(f"P{pid} plays {card_str}. Trick to P{win_pid}.", ta.ObservationType.GAME_MESSAGE)

                gs["led_card"] = None
                gs["led_to"] = None
                winner = self._hand_winner()
                if winner is not None:
                    return self._award_hand(winner)
                if len(gs["tricks"]) == 3:
                    self.broadcast(
                        "All three tricks were tied. The hand is void and no points are scored.",
                        ta.ObservationType.GAME_MESSAGE,
                    )
                    self._start_next_hand()
                    return None
                # A tied trick is followed by the same leader; otherwise the
                # trick winner leads the next trick.
                self.set_next_player(lead_pid if win_pid is None else win_pid)
                return None

        # should never reach here
        return self.invalid("Unrecognised action.")

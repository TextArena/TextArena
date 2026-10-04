import re
from typing import Any, Dict, List, Optional, Union

import textarena as ta


class LeTrucEnv(ta.GameEnv):
    """
    Two-player Le Truc (Catalan/Spanish 40-card variant).
    • Deck = 40 cards (a 52-card deck without 8s, 9s or 10s). Rank order high->low: 3 2 A K Q J 7 6 5 4.
    • Each hand both players get 3 cards and play up to three one-card tricks. The higher rank wins a
      trick regardless of suit; equal ranks tie ("spoilt") and the same player leads again.
    • A hand is won by taking two tricks, or by winning the first decided trick when another trick is
      spoilt. If all three tricks are spoilt, nobody scores.
    • The non-dealer ("mano") leads the first trick and the deal alternates every hand.
    • A hand is worth 1 point. On their turn a player may 'raise' ("truc"): 1 -> 2, then +2 per raise,
      capped at 12. The opponent must 'accept', 'fold' or re-'raise'; folding concedes the hand at the
      stake as it stood before that raise.
    • First to 12 match points wins.
    """
    min_players = 2
    max_players = 2

    order = ["3", "2", "A", "K", "Q", "J", "7", "6", "5", "4"]  # strongest first
    target_points = 12
    max_stake = 12

    _ACTION_RE = re.compile(
        r"^(?P<verb>play|raise|accept|fold)(?:\s+(?P<rank>10|[2-9AKQJ]))?$",
        re.IGNORECASE,
    )

    def __init__(self, max_turns: Optional[int] = None):
        if max_turns is not None and (type(max_turns) is not int or max_turns < 1):
            raise ValueError("max_turns must be None or a positive integer.")
        self.max_turns = max_turns
        suits = "♣♦♥♠"
        self.deck = [rank + suit for rank in self.order for suit in suits]

    def setup(self) -> Dict[str, Any]:
        return {"match_points": {0: 0, 1: 0}, "hand_number": 0, "dealer": 1}  # Player 0 leads the first hand

    def on_start(self):
        self.set_current_player(self._deal_hand())

    def prompt(self, player_id: int) -> str:
        turn_limit_rule = (
            ""
            if self.max_turns is None
            else (
                f"\n- If {self.max_turns} actions pass before anyone reaches {self.target_points}, "
                "the player with more match points wins; equal points draw."
            )
        )
        return (
            f"You are Player {player_id} in Le Truc, a two-player trick-taking card game. "
            f"The first player to reach {self.target_points} match points wins.\n"
            "Cards and tricks:\n"
            "- 40-card deck (no 8s, 9s or 10s), ranked from highest to lowest: 3 2 A K Q J 7 6 5 4. Suits never matter.\n"
            "- Each hand you get 3 cards and play up to three one-card tricks. The non-dealer leads the first trick, "
            "and the deal alternates every hand.\n"
            "- The higher rank wins a trick and its winner leads the next one. Equal ranks spoil (tie) the trick "
            "and the same player leads again.\n"
            "- Win the hand by taking two tricks, or by winning the first decided trick when another trick is spoilt. "
            "If all three tricks are spoilt, nobody scores.\n"
            "Stakes:\n"
            f"- A hand is worth 1 point. On your turn you may raise ('truc'): 1 -> 2, then +2 per raise, up to {self.max_stake}.\n"
            "- Your opponent must then accept, fold, or raise again. Whoever folds concedes the hand, and the raiser "
            f"scores the stake from before that raise.{turn_limit_rule}\n"
            "Actions (reply with exactly one; your legal actions are listed every turn):\n"
            "- 'play <rank>': play a card of that rank from your hand, e.g. 'play K' or 'play 3'\n"
            "- 'raise': raise the stake\n"
            "- 'accept': accept your opponent's raise\n"
            "- 'fold': refuse your opponent's raise and concede the hand"
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        points = gs["match_points"]
        lines = [
            f"Match points: P0={points[0]}, P1={points[1]} (first to {self.target_points} wins)",
            f"Hand {gs['hand_number']}: dealer P{gs['dealer']}, first lead P{1 - gs['dealer']}. Hand value: {gs['stake']} pt(s)",
        ]
        if gs["raiser"] is not None:
            reraise = (
                f", or 'raise' to {self._next_stake(gs['pending_raise_value'])}"
                if gs["pending_raise_value"] < self.max_stake
                else ""
            )
            lines.append(
                f"Pending raise: P{gs['raiser']} raised to {gs['pending_raise_value']}. 'accept' to play for "
                f"{gs['pending_raise_value']}, 'fold' to concede {gs['stake']}{reraise}."
            )
        tricks = "; ".join(
            f"{number}) P{leader} {lead_card} vs P{1 - leader} {follow_card}: "
            + ("spoilt" if winner is None else f"P{winner} won")
            for number, ((leader, lead_card, follow_card), winner) in enumerate(zip(gs["trick_cards"], gs["tricks"]), start=1)
        )
        lines.append(f"Tricks this hand: {tricks or 'none yet'}")
        if gs["led_card"] is not None:
            leader, card = gs["led_card"]
            lines.append(f"Current trick: P{leader} led {card}.")
        lines.append(f"Your cards: {' '.join(gs['hands'][player_id])}")
        if not self.state.done:
            lines.append("Legal actions: " + ", ".join(f"'{action}'" for action in self._legal_actions(player_id)))
        return "\n".join(lines)

    def get_board_str(self) -> str:
        """Return the acting player's private board for the spectator renderer."""
        return self.render(self.state.current_player_id)

    def on_turn_limit(self) -> ta.Outcome:
        points = self.game_state["match_points"]
        if points[0] == points[1]:
            return self.draw(reason=f"The turn limit was reached with both players on {points[0]} match points.")
        leader = 0 if points[0] > points[1] else 1
        return self.winner(leader, reason=f"Player {leader} leads on match points ({points[0]}-{points[1]}) at the turn limit.")

    # ------------------------------------------------------------- helpers
    def _rank_idx(self, card: str) -> int:
        return self.order.index(card[:-1])

    def _next_stake(self, stake: int) -> int:
        return 2 if stake == 1 else min(stake + 2, self.max_stake)

    @staticmethod
    def _hand_winner(tricks: List[Optional[int]]) -> Optional[int]:
        """Winner of a hand from its completed tricks (None = spoilt), or None while undecided.

        A spoilt trick counts for whoever won the first decided trick, so two tricks, or one trick
        plus a spoilt one, take the hand. Three spoilt tricks also return None: the hand is void.
        """
        first = next((winner for winner in tricks if winner is not None), None)
        if first is None:
            return None
        spoilt = tricks.count(None)
        if tricks.count(first) + spoilt >= 2:
            return first
        if tricks.count(1 - first) >= 2:
            return 1 - first
        return None

    def _legal_actions(self, player_id: int) -> List[str]:
        gs = self.game_state
        if gs["raiser"] is not None:
            actions = ["accept", "fold"]
            if gs["pending_raise_value"] < self.max_stake:
                actions.append("raise")
            return actions
        actions = list(dict.fromkeys(f"play {card[:-1]}" for card in gs["hands"][player_id]))
        if gs["stake"] < self.max_stake:
            actions.append("raise")
        return actions

    def _deal_hand(self) -> int:
        """Deal a fresh hand and return its leader, the non-dealer ("mano")."""
        gs = self.game_state
        deck = self.deck.copy()
        self.rng.shuffle(deck)
        gs["hand_number"] += 1
        gs.update({
            "stake": 1,                   # accepted value of the current hand
            "raiser": None,               # player whose raise is awaiting an answer
            "pending_raise_value": None,  # stake that raise proposes
            "raise_origin": None,         # player whose card turn the raise negotiation interrupted
            "hands": {0: deck[:3], 1: deck[3:6]},
            "undealt_cards": deck[6:],
            "played_cards": [],
            "led_card": None,             # (leader, card) while a trick is in progress
            "tricks": [],                 # winner of each completed trick, None if spoilt
            "trick_cards": [],            # (leader, lead card, follow card) of each completed trick
        })
        mano = 1 - gs["dealer"]
        for pid in (0, 1):
            self.message(
                pid,
                f"### Hand {gs['hand_number']} (worth 1 pt): Player {gs['dealer']} deals and Player {mano} leads.\n"
                f"Your cards: {' '.join(gs['hands'][pid])}",
                ta.ObservationType.GAME_MESSAGE,
            )
        return mano

    def _start_next_hand(self):
        self.game_state["dealer"] = 1 - self.game_state["dealer"]
        self.set_next_player(self._deal_hand())

    def _award_hand(self, winner: int) -> Optional[ta.Outcome]:
        gs = self.game_state
        points = gs["match_points"]
        points[winner] += gs["stake"]
        self.broadcast(
            f"Hand won by P{winner} (+{gs['stake']} pt(s)). Score - P0: {points[0]}, P1: {points[1]}.",
            ta.ObservationType.GAME_MESSAGE,
        )
        if points[winner] >= self.target_points:
            return self.winner(winner, reason=f"Player {winner} reached {self.target_points} match points.")
        self._start_next_hand()
        return None

    # ------------------------------------------------------------- actions
    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        match = self._ACTION_RE.match(action)
        if match is None:
            return self.invalid("Unrecognised action. Reply with one legal action, e.g. 'play K', 'raise', 'accept' or 'fold'.")
        verb = match.group("verb").lower()
        rank = match.group("rank")
        if verb != "play" and rank is not None:
            return self.invalid(f"'{verb}' does not take a card.")
        if verb == "play":
            return self._play(player_id, rank)
        if verb == "raise":
            return self._raise(player_id)
        if verb == "accept":
            return self._accept(player_id)
        return self._fold(player_id)

    def _raise(self, pid: int) -> Optional[ta.Invalid]:
        gs = self.game_state
        reraise = gs["raiser"] is not None
        if reraise and gs["pending_raise_value"] >= self.max_stake:
            return self.invalid(f"The pending raise is already the maximum of {self.max_stake} points; reply 'accept' or 'fold'.")
        if not reraise and gs["stake"] >= self.max_stake:
            return self.invalid(f"The hand is already worth the maximum of {self.max_stake} points; you cannot raise.")
        if reraise:
            gs["stake"] = gs["pending_raise_value"]  # a re-raise accepts the standing offer
        else:
            gs["raise_origin"] = pid
        gs["raiser"] = pid
        gs["pending_raise_value"] = self._next_stake(gs["stake"])
        opponent = 1 - pid
        announcement = f"accepts {gs['stake']} and raises again" if reraise else "calls truc"
        reply = "'accept', 'fold' or 'raise'" if gs["pending_raise_value"] < self.max_stake else "'accept' or 'fold'"
        self.broadcast(
            f"P{pid} {announcement}: the hand would be worth {gs['pending_raise_value']} pts. "
            f"P{opponent} must reply {reply}; folding concedes {gs['stake']} pt(s).",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        self.set_next_player(opponent)
        return None

    def _accept(self, pid: int) -> Optional[ta.Invalid]:
        gs = self.game_state
        if gs["raiser"] is None:
            return self.invalid("There is no raise to accept.")
        origin = gs["raise_origin"]
        gs.update({"stake": gs["pending_raise_value"], "raiser": None, "pending_raise_value": None, "raise_origin": None})
        self.broadcast(
            f"P{pid} accepts: the hand is worth {gs['stake']} pts. P{origin} continues.",
            ta.ObservationType.GAME_ACTION_DESCRIPTION,
        )
        self.set_next_player(origin)
        return None

    def _fold(self, pid: int) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if gs["raiser"] is None:
            return self.invalid("You can only fold in response to a raise.")
        self.broadcast(f"P{pid} folds and concedes the hand.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return self._award_hand(gs["raiser"])  # scores the stake from before the refused raise

    def _play(self, pid: int, rank: Optional[str]) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if gs["raiser"] is not None:
            return self.invalid("A raise is pending: reply 'accept', 'fold' or 'raise' before playing a card.")
        if rank is None:
            return self.invalid("Name the rank to play, e.g. 'play K'.")
        rank = rank.upper()
        if rank not in self.order:
            return self.invalid("The Le Truc deck has no 8s, 9s or 10s.")
        hand = gs["hands"][pid]
        index = next((i for i, card in enumerate(hand) if card[:-1] == rank), None)
        if index is None:
            return self.invalid(f"You have no {rank} in your hand (your cards: {' '.join(hand)}).")
        card = hand.pop(index)
        gs["played_cards"].append(card)

        if gs["led_card"] is None:
            gs["led_card"] = (pid, card)
            self.broadcast(f"P{pid} leads {card}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            self.set_next_player(1 - pid)
            return None

        leader, lead_card = gs["led_card"]
        gs["led_card"] = None
        if self._rank_idx(card) == self._rank_idx(lead_card):
            trick_winner = None
            self.broadcast(f"P{pid} plays {card}. Equal ranks: the trick is spoilt.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        else:
            trick_winner = pid if self._rank_idx(card) < self._rank_idx(lead_card) else leader
            self.broadcast(f"P{pid} plays {card}. Trick to P{trick_winner}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        gs["tricks"].append(trick_winner)
        gs["trick_cards"].append((leader, lead_card, card))

        hand_winner = self._hand_winner(gs["tricks"])
        if hand_winner is not None:
            return self._award_hand(hand_winner)
        if len(gs["tricks"]) == 3:
            points = gs["match_points"]
            self.broadcast(
                f"All three tricks were spoilt: nobody scores this hand. Score - P0: {points[0]}, P1: {points[1]}.",
                ta.ObservationType.GAME_MESSAGE,
            )
            self._start_next_hand()
            return None
        self.set_next_player(leader if trick_winner is None else trick_winner)
        return None

import random, re
from typing import Dict, Any, Optional, Tuple
import textarena as ta

# TODO work in progress
class LeTrucEnv(ta.Env):
    """
    Minimal 2-player 'Le Truc'.
    • Deck = 32 cards (remove 8s/9s/10s). Rank order: 3 2 A K Q J 7 6 5 4.
    • Each gets 3 cards. Trick winner is highest card of led suit.
    • At any time before a trick result a player may [raise] to increase hand value by +1. Opponent may [accept] or [fold].
    • First to 12 match-points wins (or earlier if someone folds).
    """
    order = ["3", "2", "A", "K", "Q", "J", "7", "6", "5", "4"]

    def __init__(self):
        super().__init__()
        self.action_space = re.compile(
            r"""\[
                (?P<verb>play|raise|accept|fold)            # action keyword
                (?:\s+(?P<card>(10|[234567JQKA])))?         # optional rank
            \]""",
            re.IGNORECASE | re.VERBOSE,
        )
        # build the 32-card deck
        suits = "♣♦♥♠"
        self.deck = [r + s for r in self.order for s in suits]

    def reset(self, num_players: int = 2, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={"match_points": {0: 0, 1: 0}, "hand_points": 1}, player_prompt_function=self._prompt)
        self._deal_hand()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return "a summary of the game rules"
    

    def _deal_hand(self):
        gs = self.state.game_state
        d = self.deck.copy()
        random.shuffle(d)
        gs["hands"] = {0: d[:3], 1: d[3:6]}
        gs["tricks"] = []
        gs["led_card"] = None
        gs["raiser"] = None
        self.state.manually_set_current_player_id(0)

        for pid in (0, 1):
            self.state.add_observation(to_id=pid, message=f"### New hand worth {gs['hand_points']} pt(s)\nYour cards: {' '.join(gs['hands'][pid])}", observation_type=ta.ObservationType.GAME_BOARD)

    def _rank_idx(self, card: str) -> int: return self.order.index(card[:-1])

    def step(self, action: str) -> Tuple[bool, Dict[str, Any]]:
        pid = self.state.current_player_id
        gs  = self.state.game_state
        self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        m = self.action_space.search(action)
        if not m: self.state.set_invalid_move(reason="Unrecognised action."); return self.state.step()
        verb  = m.group("verb").lower()
        if verb == "raise":
            if gs.get("raiser") is not None:
                self.state.set_invalid_move("Already raised.")
                return self.state.step()

            gs["hand_points"] += 1
            gs["raiser"] = pid
            self.state.current_player_id = 1 - pid
            self.state.add_observation(message=f"P{pid} raises - hand now {gs['hand_points']} pts. Opponent must '[accept]' or '[fold]'.", observation_type=ta.ObservationType.GAME_MESSAGE)
            return self.state.step()

        if verb == "accept":
            if gs.get("raiser") is None or pid == gs["raiser"]:
                self.state.set_invalid_move(reason="No raise to accept.")
                return self.state.step()

            gs["raiser"] = None
            # resume with whoever still has to follow suit first
            self.state.current_player_id = gs.get("led_to", pid)
            return self.state.step()

        if verb == "fold":
            if gs.get("raiser") is None or pid == gs["raiser"]:
                self.state.set_invalid_move(reason="Cannot fold now.")
                return self.state.step()

            winner = 1 - pid
            gs["match_points"][winner] += gs["hand_points"]
            self.state.set_winner(winner, reason="Opponent folded.")
            return self.state.step()

        if verb == "play":
            rank = m.group("card").upper()

            # ensure player owns that rank (ignore suits in input)
            if rank not in [c[:-1] for c in gs["hands"][pid]]:
                self.state.set_invalid_move(reason="You don't hold that rank (suits ignored in input).")
                return self.state.step()

            # pick the first matching suit in hand
            idx = next(i for i, c in enumerate(gs["hands"][pid]) if c.startswith(rank))
            card_str = gs["hands"][pid].pop(idx)

            if gs["led_card"] is None:
                # lead the trick
                gs["led_card"] = (pid, card_str)
                gs["led_to"]   = 1 - pid
                self.state.current_player_id = 1 - pid
                self.state.add_observation(message=f"P{pid} leads {card_str}.", observation_type=ta.ObservationType.GAME_MESSAGE)
            else:
                # follow, decide trick winner
                lead_pid, lead_card = gs["led_card"]
                win_pid = pid if self._rank_idx(card_str) > self._rank_idx(lead_card) else lead_pid

                gs["tricks"].append(win_pid)
                self.state.add_observation(message=f"P{pid} plays {card_str}. Trick to P{win_pid}.", observation_type=ta.ObservationType.GAME_MESSAGE)

                gs["led_card"] = None
                if len(gs["tricks"]) == 3:                                  # hand over
                    winner = 0 if gs["tricks"].count(0) > 1 else 1
                    gs["match_points"][winner] += gs["hand_points"]
                    if gs["match_points"][winner] >= 12:                    # match over
                        self.state.set_winner(winner, "Reached 12 points.")
                        return self.state.step()

                    # new hand
                    gs["hand_points"] = 1
                    self._deal_hand()
                    return self.state.step(rotate_player=False)
                self.state.current_player_id = win_pid
            return self.state.step(rotate_player=False)
        # should never reach here
        self.state.set_invalid_move("Unrecognised action.")
        return self.state.step()

# import random, re
# from typing import Dict, Any, Optional, Tuple
# import textarena as ta


# class LeducHoldemEnv(ta.Env):
#     """
#     Two-player Leduc Hold’em (6-card deck: JJQQKK in 2 suits).
#     • Ante 1 chip -> each gets 1 private card.
#     • Pre-flop betting (check/bet/raise/call/fold; fixed bet = 2 chips, max 2 raises).
#     • Reveal one public card -> second betting round (bet = 4 chips).
#     • Showdown: pair > high card; ties split pot.
#     """
#     def __init__(self, starting_bank: int = 100, max_rounds: int = 5):
#         super().__init__()
#         self.starting_bank = starting_bank
#         self.deck = [r for r in range(3) for _ in range(2)] # deck = two of each rank 0-2  (0=J, 1=Q, 2=K)
#         self.bet_sizes = [2, 4] # round-0 / round-1 fixed bet
#         self.max_rounds = max_rounds
#         self.action_space = re.compile(r"\[(check|call|bet|raise|fold)]", re.I)

#     @staticmethod
#     def _rank_to_str(r: int) -> str: return ["J", "Q", "K"][r]

#     def _legal(self, gs): # returns list of legal strings (ordered for deterministic output)
#         if gs["current_bet"] == 0:          return ["check", "bet"]
#         elif gs["raises_this_round"] < 2:   return ["call", "raise", "fold"]
#         else:                               return ["call", "fold"]

#     def reset(self, num_players: int = 2, seed: Optional[int] = None):
#         self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
#         game_state = {"round": 0, "pot": 0, "player_bank": {0: self.starting_bank, 1: self.starting_bank}, "player_cards": {}, "board_card": None, "current_bet": 0, "raises_this_round": 0, "starting_player": 0}
#         self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
#         self._deal_new_hand()

#     def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
#         return self.m("player_prompt", "intro", player_id=player_id)

#     def _deal_new_hand(self):
#         gs = self.state.game_state
#         # check if we have reached the round limit
#         if gs.get("hands_dealt", 0) >= self.max_rounds:
#             self._declare_match_winner(self.m("outcome", "hand_limit"))
#             return
#         if any(bank < self.bet_sizes[0] for bank in gs["player_bank"].values()):
#             busted = 0 if gs["player_bank"][0] < self.bet_sizes[0] else 1
#             self.state.set_winner(1 - busted, self.m("outcome", "busted", busted=busted))
#             return
#         gs["hands_dealt"] = gs.get("hands_dealt", 0) + 1

#         gs.update({"round": 0, "pot": 2, "current_bet": 0, "raises_this_round": 0})
#         for pid in (0, 1): gs["player_bank"][pid] -= 1
#         deck = self.deck.copy()
#         random.shuffle(deck)
#         gs["player_cards"] = {0: deck.pop(), 1: deck.pop()}
#         gs["board_card"] = deck.pop()

#         # alternate first player
#         gs["starting_player"] ^= 1
#         self.state.manually_set_current_player_id(gs["starting_player"])

#         # private observations
#         for pid in (0, 1): self.state.add_observation(to_id=pid, message=self.m("board", "new_hand", card=self._rank_to_str(gs['player_cards'][pid])), observation_type=ta.ObservationType.GAME_MESSAGE)
#         self._announce_legal(self.state.current_player_id)

#     def step(self, action: str) -> Tuple[bool, Dict[str, Any]]:
#         pid = self.state.current_player_id
#         gs = self.state.game_state
#         self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
#         m = self.action_space.search(action)
#         if not m:
#             self.state.set_invalid_move(reason = self.m("invalid_move", "wrong_format"))
#             return self.state.step()

#         move = m.group(1).lower()
#         if move not in self._legal(gs):
#             self.state.set_invalid_move(reason = self.m("invalid_move", "illegal_now", allowed=self._legal(gs)))
#             return self.state.step()

#         bet_unit = self.bet_sizes[gs["round"]]

#         if move == "check":
#             if gs.get("prev_check"):
#                 self._next_round_or_showdown()
#                 return self.state.step(rotate_player=False)
#             gs["prev_check"] = True
#             self.state.add_observation(message=self.m("action", "check", pid=pid), observation_type=ta.ObservationType.GAME_MESSAGE)
#             self._announce_legal(1-pid)
#             return self.state.step(rotate_player=True)
#         gs["prev_check"] = False

#         if move == "bet":
#             gs["current_bet"] = bet_unit
#             gs["raises_this_round"] = 0
#             self._commit_chips(pid, bet_unit)
#             self.state.add_observation(message=self.m("action", "bet", pid=pid, amount=bet_unit), observation_type=ta.ObservationType.GAME_MESSAGE)
#         elif move == "raise":
#             gs["raises_this_round"] += 1
#             gs["current_bet"] += bet_unit
#             self._commit_chips(pid, bet_unit)
#             self.state.add_observation(message=self.m("action", "raise", pid=pid, amount=bet_unit), observation_type=ta.ObservationType.GAME_MESSAGE)
#         elif move == "call":
#             to_call = gs["current_bet"]
#             self._commit_chips(pid, to_call)
#             self.state.add_observation(message=self.m("action", "call", pid=pid, amount=to_call), observation_type=ta.ObservationType.GAME_MESSAGE)
#             self._next_round_or_showdown()
#             return self.state.step(rotate_player=False)
#         elif move == "fold":
#             self._award(1-pid, reason=self.m("action", "fold", pid=pid))
#             return self.state.step(rotate_player=False)

#         # continue betting
#         self._announce_legal(1-pid)
#         return self.state.step(rotate_player=True)

#     def _commit_chips(self, pid: int, amount: int):
#         gs = self.state.game_state
#         gs["player_bank"][pid] -= amount
#         gs["pot"] += amount

#     def _announce_legal(self, to_pid: int):
#         legal = ", ".join(f"'[{a}]'" for a in self._legal(self.state.game_state))
#         self.state.add_observation(to_id=to_pid, message=self.m("board", "valid_actions", legal=legal), observation_type=ta.ObservationType.GAME_BOARD)

#     def _next_round_or_showdown(self):
#         gs = self.state.game_state
#         if gs["round"] == 0:                   # flop round begins
#             gs.update({"round": 1, "current_bet": 0, "raises_this_round": 0, "prev_check": False})
#             card = self._rank_to_str(gs["board_card"])
#             self.state.add_observation(message=self.m("board", "flop", card=card), observation_type=ta.ObservationType.GAME_MESSAGE)
#             self.state.manually_set_current_player_id(gs["starting_player"])
#             self._announce_legal(gs["starting_player"])
#         else: self._showdown()

#     def _rank_strength(self, private: int, board: int) -> Tuple[int, int]: return (private == board, private) # returns (pair?, high_rank)

#     def _showdown(self):
#         gs = self.state.game_state
#         pair0, high0 = self._rank_strength(gs["player_cards"][0], gs["board_card"])
#         pair1, high1 = self._rank_strength(gs["player_cards"][1], gs["board_card"])
#         if pair0 != pair1:      winner = 0 if pair0 else 1
#         elif high0 != high1:    winner = 0 if high0 > high1 else 1
#         else:                   self._split_pot(reason=self.m("showdown", "tie")); return
#         self._award(winner, reason=self.m("showdown", "wins", winner=winner))
        
#     def _split_pot(self, reason):
#         gs = self.state.game_state
#         split = gs["pot"] // 2
#         gs["player_bank"][0] += split
#         gs["player_bank"][1] += gs["pot"] - split
#         self.state.add_observation(message=reason, observation_type=ta.ObservationType.GAME_MESSAGE)
#         self._deal_new_hand()

#     def _award(self, winner: int, reason):
#         gs = self.state.game_state
#         gs["player_bank"][winner] += gs["pot"]
#         message = self.m("outcome", "banks", reason=reason, b0=gs['player_bank'][0], b1=gs['player_bank'][1])
#         self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_MESSAGE)
#         self._deal_new_hand()

#     def _declare_match_winner(self, reason):
#         b0, b1 = self.state.game_state["player_bank"].values()
#         if b0 > b1:     self.state.set_winner(0, self.m("outcome", "match_winner", reason=reason, hi=b0, lo=b1))
#         elif b1 > b0:   self.state.set_winner(1, self.m("outcome", "match_winner", reason=reason, hi=b1, lo=b0))
#         else:           self.state.set_draw(self.m("outcome", "match_draw", reason=reason))

import random, re
from typing import Dict, Any, Optional, Tuple
import textarena as ta


class LeducHoldemEnv(ta.Env):
    """
    Two-player Leduc Hold’em (6-card deck: JJQQKK in 2 suits).
    • Ante 1 chip -> each gets 1 private card.
    • Pre-flop betting (check/bet/raise/call/fold; fixed bet = 2 chips, max 2 raises).
    • Reveal one public card -> second betting round (bet = 4 chips).
    • Showdown: pair > high card; ties split pot.
    """
    def __init__(self, starting_bank: int = 100, max_rounds: int = 5):
        super().__init__()
        self.starting_bank = starting_bank
        self.deck = [r for r in range(3) for _ in range(2)] # deck = two of each rank 0-2  (0=J, 1=Q, 2=K)
        self.bet_sizes = [2, 4] # round-0 / round-1 fixed bet
        self.max_rounds = max_rounds
        self.action_space = re.compile(r"\[(check|call|bet|raise|fold)]", re.I)

    @staticmethod
    def _rank_to_str(r: int) -> str: return ["J", "Q", "K"][r]

    def _legal(self, gs): # returns list of legal strings (ordered for deterministic output)
        if gs["current_bet"] == 0:          return ["check", "bet"]
        elif gs["raises_this_round"] < 2:   return ["call", "raise", "fold"]
        else:                               return ["call", "fold"]

    def reset(self, num_players: int = 2, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state = {"round": 0, "pot": 0, "player_bank": {0: self.starting_bank, 1: self.starting_bank}, "player_cards": {}, "board_card": None, "current_bet": 0, "raises_this_round": 0, "committed": {0: 0, 1: 0}, "starting_player": 0}
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self._deal_new_hand()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id)

    def _deal_new_hand(self):
        gs = self.state.game_state
        # check if we have reached the round limit
        if gs.get("hands_dealt", 0) >= self.max_rounds:
            self._declare_match_winner(self.m("outcome", "hand_limit"))
            return
        if any(bank < self.bet_sizes[0] for bank in gs["player_bank"].values()):
            busted = 0 if gs["player_bank"][0] < self.bet_sizes[0] else 1
            self.state.set_winner(1 - busted, self.m("outcome", "busted", busted=busted))
            return
        gs["hands_dealt"] = gs.get("hands_dealt", 0) + 1

        # FIX #2: reset prev_check so a round-closing check from the previous
        # hand can't leak into this one; also reset per-round commitments (FIX #1).
        gs.update({"round": 0, "pot": 2, "current_bet": 0, "raises_this_round": 0, "prev_check": False, "committed": {0: 0, 1: 0}})
        for pid in (0, 1): gs["player_bank"][pid] -= 1
        deck = self.deck.copy()
        random.shuffle(deck)
        gs["player_cards"] = {0: deck.pop(), 1: deck.pop()}
        gs["board_card"] = deck.pop()

        # alternate first player
        gs["starting_player"] ^= 1
        self.state.manually_set_current_player_id(gs["starting_player"])

        # private observations
        for pid in (0, 1): self.state.add_observation(to_id=pid, message=self.m("board", "new_hand", card=self._rank_to_str(gs['player_cards'][pid])), observation_type=ta.ObservationType.GAME_MESSAGE)
        self._announce_legal(self.state.current_player_id)

    def step(self, action: str) -> Tuple[bool, Dict[str, Any]]:
        pid = self.state.current_player_id
        gs = self.state.game_state
        self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        m = self.action_space.search(action)
        if not m:
            self.state.set_invalid_move(reason = self.m("invalid_move", "wrong_format"))
            return self.state.step()

        move = m.group(1).lower()
        if move not in self._legal(gs):
            self.state.set_invalid_move(reason = self.m("invalid_move", "illegal_now", allowed=self._legal(gs)))
            return self.state.step()

        bet_unit = self.bet_sizes[gs["round"]]

        if move == "check":
            if gs.get("prev_check"):
                self.state.add_observation(message=self.m("action", "check", pid=pid), observation_type=ta.ObservationType.GAME_MESSAGE)
                self._next_round_or_showdown()
                return self.state.step(rotate_player=False)
            gs["prev_check"] = True
            self.state.add_observation(message=self.m("action", "check", pid=pid), observation_type=ta.ObservationType.GAME_MESSAGE)
            self._announce_legal(1-pid)
            return self.state.step(rotate_player=True)
        gs["prev_check"] = False

        if move == "bet":
            # FIX #1: track per-player commitment for this betting round
            gs["current_bet"] = bet_unit
            gs["raises_this_round"] = 0
            self._commit_chips(pid, bet_unit)
            self.state.add_observation(message=self.m("action", "bet", pid=pid, amount=bet_unit), observation_type=ta.ObservationType.GAME_MESSAGE)
        elif move == "raise":
            # FIX #1: a raiser must first match the outstanding bet, then add the raise
            to_call = gs["current_bet"] - gs["committed"][pid]
            pay = to_call + bet_unit
            gs["raises_this_round"] += 1
            gs["current_bet"] += bet_unit
            self._commit_chips(pid, pay)
            self.state.add_observation(message=self.m("action", "raise", pid=pid, amount=pay), observation_type=ta.ObservationType.GAME_MESSAGE)
        elif move == "call":
            # FIX #1: a caller only owes the difference between the current bet
            # and what they have already committed this round
            to_call = gs["current_bet"] - gs["committed"][pid]
            self._commit_chips(pid, to_call)
            self.state.add_observation(message=self.m("action", "call", pid=pid, amount=to_call), observation_type=ta.ObservationType.GAME_MESSAGE)
            self._next_round_or_showdown()
            return self.state.step(rotate_player=False)
        elif move == "fold":
            self._award(1-pid, reason=self.m("action", "fold", pid=pid))
            return self.state.step(rotate_player=False)

        # continue betting
        self._announce_legal(1-pid)
        return self.state.step(rotate_player=True)

    def _commit_chips(self, pid: int, amount: int):
        gs = self.state.game_state
        gs["player_bank"][pid] -= amount
        gs["pot"] += amount
        gs["committed"][pid] += amount  # FIX #1

    def _announce_legal(self, to_pid: int):
        legal = ", ".join(f"'[{a}]'" for a in self._legal(self.state.game_state))
        self.state.add_observation(to_id=to_pid, message=self.m("board", "valid_actions", legal=legal), observation_type=ta.ObservationType.GAME_BOARD)

    def _next_round_or_showdown(self):
        gs = self.state.game_state
        if gs["round"] == 0:                   # flop round begins
            # FIX #1: commitments reset each betting round
            gs.update({"round": 1, "current_bet": 0, "raises_this_round": 0, "prev_check": False, "committed": {0: 0, 1: 0}})
            card = self._rank_to_str(gs["board_card"])
            self.state.add_observation(message=self.m("board", "flop", card=card), observation_type=ta.ObservationType.GAME_MESSAGE)
            self.state.manually_set_current_player_id(gs["starting_player"])
            self._announce_legal(gs["starting_player"])
        else: self._showdown()

    def _rank_strength(self, private: int, board: int) -> Tuple[int, int]: return (private == board, private) # returns (pair?, high_rank)

    def _showdown(self):
        gs = self.state.game_state
        pair0, high0 = self._rank_strength(gs["player_cards"][0], gs["board_card"])
        pair1, high1 = self._rank_strength(gs["player_cards"][1], gs["board_card"])
        if pair0 != pair1:      winner = 0 if pair0 else 1
        elif high0 != high1:    winner = 0 if high0 > high1 else 1
        else:                   self._split_pot(reason=self.m("showdown", "tie")); return
        self._award(winner, reason=self.m("showdown", "wins", winner=winner))

    def _split_pot(self, reason):
        gs = self.state.game_state
        split = gs["pot"] // 2
        gs["player_bank"][0] += split
        gs["player_bank"][1] += gs["pot"] - split
        self.state.add_observation(message=reason, observation_type=ta.ObservationType.GAME_MESSAGE)
        self._deal_new_hand()

    def _award(self, winner: int, reason):
        gs = self.state.game_state
        gs["player_bank"][winner] += gs["pot"]
        message = self.m("outcome", "banks", reason=reason, b0=gs['player_bank'][0], b1=gs['player_bank'][1])
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_MESSAGE)
        self._deal_new_hand()

    def _declare_match_winner(self, reason):
        b0, b1 = self.state.game_state["player_bank"].values()
        if b0 > b1:     self.state.set_winner(0, self.m("outcome", "match_winner", reason=reason, hi=b0, lo=b1))
        elif b1 > b0:   self.state.set_winner(1, self.m("outcome", "match_winner", reason=reason, hi=b1, lo=b0))
        else:           self.state.set_draw(self.m("outcome", "match_draw", reason=reason))
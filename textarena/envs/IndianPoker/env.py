import re, random
from typing import Dict, Any, Optional, Tuple

import textarena as ta
# from textarena.envs.IndianPoker.renderer import create_board_str # TODO


class IndianPokerEnv(ta.Env):
    def __init__(self, max_rounds: int=1, starting_chips: int=100):
        super().__init__()
        self.ante = 1
        self.max_rounds = max_rounds
        self.starting_bank = starting_chips
        self.full_deck = list(range(52))

    @staticmethod
    def _rank(card: int) -> int: return (card % 13) + 2 # 0-51 → 2-14
    @staticmethod
    def _rank_to_str(card: int) -> str: return ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"][(card % 13)]
    # def get_board_str(self): return create_board_str(self.state.game_state)

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={"player_chips": {0: self.starting_bank, 1: self.starting_bank}, "current_round": 0, "starting_player": 0}, player_prompt_function=self._prompt)
        self._init_round()

    def _init_round(self):
        gs = self.state.game_state
        gs["current_round"] += 1

        # check if match finished
        if gs["current_round"] > self.max_rounds:
            bank0, bank1 = gs["player_chips"].values()
            if bank0 > bank1:   self.state.set_winner(0, self.m("outcome", "p0_wins", bank0=bank0, bank1=bank1))
            elif bank1 > bank0: self.state.set_winner(1, self.m("outcome", "p1_wins", bank1=bank1, bank0=bank0))
            else:               self.state.set_draw(self.m("outcome", "draw"))
            return

        deck = self.full_deck.copy()
        random.shuffle(deck)
        gs["player_cards"] = {0: deck[0], 1: deck[1]}

        gs["pot"] = self.ante * 2
        for pid in (0, 1): gs["player_chips"][pid] -= self.ante

        # per-round betting bookkeeping
        gs["current_bets"] = {0: 0, 1: 0} # chips committed this round
        gs["highest_bet"] = 0 # current bet to match
        gs["prev_action"] = None # track check-check

        # rotate first player
        gs["starting_player"] = 1-gs["starting_player"]
        self.state.manually_set_current_player_id(gs["starting_player"])
        for pid in (0, 1):
            self.state.add_observation(to_id=pid, message=self.m("round", "announce", current_round=gs['current_round'], max_rounds=self.max_rounds, card=self._rank_to_str(gs['player_cards'][1-pid])), observation_type=ta.ObservationType.GAME_MESSAGE)
        self._announce_actions(self.state.current_player_id)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id, ante=self.ante, max_rounds=self.max_rounds)
    
    def _find_token(self, msg: str):
        patterns = [("check", re.compile(r"\[check\]", re.I)), ("fold", re.compile(r"\[fold\]", re.I)), ("call", re.compile(r"\[call\]", re.I)), ("bet", re.compile(r"\[bet (\d+)\]", re.I)), ("raise", re.compile(r"\[raise (\d+)\]", re.I))]
        found = [(name, m) for name, rx in patterns if (m := rx.search(msg))]
        if len(found) != 1: return None, None # none or ambiguous
        name, match = found[0]
        amt  = int(match.group(1)) if name in ("bet", "raise") else None
        return name, amt

    def step(self, action: str) -> Tuple[bool, Dict[str, Any]]:
        pid = self.state.current_player_id
        gs = self.state.game_state
        self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        def chips_to_call() -> int: return gs["highest_bet"] - gs["current_bets"][pid]

        move, amount = self._find_token(action)
        if move is None:
            self.state.set_invalid_move(self.m("invalid_move", "ambiguous"))
            return self.state.step()

        to_call = chips_to_call()

        # legality checks
        if move == "check" and to_call != 0:            self.state.set_invalid_move(self.m("invalid_move", "cannot_check"));          return self.state.step()
        if move in ("bet", "raise") and amount <= 0:    self.state.set_invalid_move(self.m("invalid_move", "amount_min"));                 return self.state.step()
        if move == "bet" and to_call != 0:              self.state.set_invalid_move(self.m("invalid_move", "cannot_bet"));  return self.state.step()
        if move == "call" and to_call == 0:             self.state.set_invalid_move(self.m("invalid_move", "nothing_to_call"));       return self.state.step()
        if move == "raise" and to_call == 0:            self.state.set_invalid_move(self.m("invalid_move", "no_bet_to_raise"));  return self.state.step()
        
        # bankroll check
        cost = 0
        if move == "bet":       cost = amount
        elif move == "call":    cost = to_call
        elif move == "raise":   cost = to_call + amount

        if cost > gs["player_chips"][pid]:              self.state.set_invalid_move(self.m("invalid_move", "insufficient"));             return self.state.step()

        rotate = True
        token = f"{move}{' ' + str(amount) if amount else ''}"
        self.state.add_observation(message=self.m("game_action", "action", player_id=pid, token=token), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)

        if move == "check":
            gs["prev_action"], rotate = ("check", True)
            if gs["prev_action"] == "check" and gs.get("second_check"): # second consecutive check -> showdown
                self._showdown()
                rotate = False
            else:
                gs["second_check"] = True

        elif move == "bet":
            gs["second_check"] = False
            gs["highest_bet"] = amount
            gs["current_bets"][pid] += amount
            gs["player_chips"][pid] -= amount
            gs["pot"] += amount
            gs["prev_action"] = "bet"

        elif move == "call":
            gs["second_check"] = False
            gs["current_bets"][pid] += to_call
            gs["player_chips"][pid] -= to_call
            gs["pot"] += to_call
            self._showdown()
            rotate = False

        elif move == "raise":
            gs["second_check"] = False
            new_bet = gs["highest_bet"] + amount
            chips_needed = new_bet - gs["current_bets"][pid]
            gs["highest_bet"] = new_bet
            gs["current_bets"][pid] += chips_needed
            gs["player_chips"][pid] -= chips_needed
            gs["pot"] += chips_needed
            gs["prev_action"] = "raise"

        elif move == "fold":
            self._end_round(1-pid, self.m("message", "folded", player_id=pid))
            rotate = False

        # prompt next player if round continues
        if rotate: self._announce_actions(1-pid)
        return self.state.step(rotate_player=rotate)

    def _announce_actions(self, to_pid: int):
        gs = self.state.game_state
        to_call = gs["highest_bet"] - gs["current_bets"][to_pid]
        if to_call == 0:    legal = self.m("board", "actions_no_bet")
        else:               legal = self.m("board", "actions_facing_bet", to_call=to_call)
        self.state.add_observation(to_id=to_pid, message=self.m("board", "possible_actions", legal=legal), observation_type=ta.ObservationType.GAME_BOARD)

    def _end_round(self, winner: int, reason: str):
        gs = self.state.game_state
        gs["player_chips"][winner] += gs["pot"]
        self.state.add_observation(message=self.m("message", "round_result", reason=reason, pot=gs['pot'], winner=winner, p0=gs['player_chips'][0], p1=gs['player_chips'][1]), observation_type=ta.ObservationType.GAME_MESSAGE)
        self._init_round()

    def _showdown(self):
        gs = self.state.game_state
        c0, c1 = gs["player_cards"][0], gs["player_cards"][1]
        r0, r1 = self._rank(c0), self._rank(c1)

        if r0 > r1:     self._end_round(0, self.m("message", "showdown_win", card_win=self._rank_to_str(c0), card_lose=self._rank_to_str(c1)))
        elif r1 > r0:   self._end_round(1, self.m("message", "showdown_win", card_win=self._rank_to_str(c1), card_lose=self._rank_to_str(c0)))
        else:  # tie – split pot
            split = gs["pot"] // 2
            gs["player_chips"][0] += split
            gs["player_chips"][1] += gs["pot"] - split
            self.state.add_observation(message=self.m("message", "showdown_tie", card=self._rank_to_str(c0), split=split), observation_type=ta.ObservationType.GAME_MESSAGE)
            self._init_round()
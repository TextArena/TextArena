import re
from typing import Any, Dict, Optional, Union

import textarena as ta


class HighSocietyEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    broadcast_actions = False  # sealed bids: raw actions are echoed only to their author

    def __init__(self):
        self.money_cards = list(range(1, 12))   # 1-11
        self.action_space = re.compile(
            r"^\s*(?P<legacy>\[)?\s*(?P<bid>11|10|[1-9])\s*(?(legacy)\])\s*$",
            re.IGNORECASE,
        )

    @staticmethod
    def _intlist_to_str(lst): return " ".join(str(x) for x in sorted(lst))

    def setup(self) -> Dict[str, Any]:
        deck = list(range(1, 11))
        self.rng.shuffle(deck)
        return {"round": 0, "prestige_deck": deck, "player_money": {0: self.money_cards.copy(), 1: self.money_cards.copy()}, "player_prestige": {0: 0, 1: 0}, "pending_bids": {}, "starting_player": 0}

    def on_start(self):
        self._next_auction()

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a game of HighSociety (2-player version).\n"
            f"Game flow:  Ten prestige cards are auctioned one after another.\n"
            f"Bidding:    Each auction, secretly choose a money card 1-11 and reveal.\n"
            f"            • Higher bid wins the prestige card and discards that money card.\n"
            f"            • Lower bid keeps their money card.\n"
            f"            • Tie -> both bids are returned and the same prestige card is re-auctioned.\n"
            f"Scoring:    After all ten auctions, add **remaining cash + prestige points**.\n"
            f"            Higher *net-worth* wins (exact tie -> draw).\n\n"
            f"**Action syntax**  →  bid a single card like '7' or '11'."
        )

    def _next_auction(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        if not gs["prestige_deck"]: return self._end_match()
        gs["round"] += 1
        prize = gs["prestige_deck"].pop()
        gs["current_prize"] = prize
        gs["pending_bids"] = {}
        for pid in (0, 1):
            self.message(pid, f"\n### Auction {gs['round']}/10  |  Prestige card: {prize}", ta.ObservationType.GAME_MESSAGE)
            self.message(pid, f"Your remaining money cards: {self._intlist_to_str(gs['player_money'][pid])}", ta.ObservationType.GAME_BOARD)
        return None

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        match = self.action_space.fullmatch(action)
        if match is None: return self.invalid("Submit exactly one money card from 1 to 11.")
        bid = int(match.group("bid"))
        if bid not in gs["player_money"][player_id]: return self.invalid("You no longer have that money card.")
        gs["pending_bids"][player_id] = bid
        if len(gs["pending_bids"]) == 1: return None  # wait for opponent (default rotation)
        # both bids in
        bid0, bid1 = gs["pending_bids"][0], gs["pending_bids"][1]
        prize = gs["current_prize"]
        if bid0 == bid1:  # tie -> redraw bids
            self.broadcast("Tie - bids returned. Rebid!", ta.ObservationType.GAME_MESSAGE)
            gs["pending_bids"] = {}
            return None
        winner = 0 if bid0 > bid1 else 1
        gs["player_prestige"][winner] += prize
        gs["player_money"][winner].remove(gs["pending_bids"][winner])  # pay cost
        self.broadcast(f"P0 bid {bid0}, P1 bid {bid1}. Player {winner} wins prestige {prize} (total {gs['player_prestige'][winner]}).", ta.ObservationType.GAME_MESSAGE)
        outcome = self._next_auction()
        if outcome is not None: return outcome
        self.set_next_player(player_id)  # the second bidder opens the next auction
        return None

    def _end_match(self) -> ta.Outcome:
        def networth(pid: int) -> int: return self.game_state["player_prestige"][pid] + sum(self.game_state["player_money"][pid])
        nw0, nw1 = networth(0), networth(1)
        if nw0 > nw1:   return self.winner(0, f"Net-worth {nw0} > {nw1}")
        elif nw1 > nw0: return self.winner(1, f"Net-worth {nw1} > {nw0}")
        else:           return self.draw(f"Both net-worth {nw0} – exact tie.")

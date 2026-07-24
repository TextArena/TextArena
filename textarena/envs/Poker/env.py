import re, random
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import textarena as ta
from textarena.envs.Poker.renderer import create_board_str


class PokerEnv(ta.Env):
    _CHECK_RE = re.compile(r"\[check\]", re.IGNORECASE)
    _FOLD_RE = re.compile(r"\[fold\]", re.IGNORECASE)
    _CALL_RE = re.compile(r"\[call.*\]", re.IGNORECASE)
    _BET_RE = re.compile(r"\[bet (\d+)\]", re.IGNORECASE)
    _RAISE_RE = re.compile(r"\[raise (\d+)\]", re.IGNORECASE)

    def __init__(self, num_rounds: int = 10, starting_chips: int = 1_000, small_blind: int = 10, big_blind: int = 20):
        self.num_rounds = num_rounds
        self.starting_chips = starting_chips
        self.small_blind = small_blind
        self.big_blind = big_blind

        self.suits = ["♠", "♥", "♦", "♣"]
        self.ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        self.rank_values = {r: i + 2 for i, r in enumerate(self.ranks)}

    def get_board_str(self):
        gs = self.state.game_state
        return create_board_str(community_cards=gs["visible_community_cards"], pot=gs["pot"], player_chips=gs["player_chips"], player_hands=gs["player_hands"], bets=gs["player_bets"])

    def _rotate_players(self):
        gs = self.state.game_state
        def can_act(pid: int) -> bool: return pid not in gs["folded_players"] and pid not in gs["all_in_players"] and self.state.is_player_alive(pid) and gs["player_chips"][pid] > 0
        next_pid = self.state.next_alive_player(predicate=can_act)
        alive_players = [pid for pid in range(self.state.num_players) if self.state.is_player_alive(pid) and gs["player_chips"][pid] > 0]

        if next_pid is not None: self.state.manually_set_current_player_id(new_player_id=next_pid)
        else: self._handle_hand_completion() # No eligible players left to act; finish the hand

    def _check_and_eliminate(self, pid: int):
        """Mark a zero-stack player as all-in; eliminate later if they stay broke."""
        if self.state.game_state["player_chips"][pid] == 0:
            self.state.game_state["all_in_players"].add(pid)

    def reset(self, num_players: int, seed: Optional[int] = None):
        assert 2 <= num_players <= 15, "The number of players has to be 2≤x≤15"
        self.state = ta.FFAMultiPlayerState(num_players=num_players, seed=seed)
        gs = {
            "round": 1, "betting_round": 0, "player_chips": {pid: self.starting_chips for pid in range(num_players)}, "player_hands": {pid: [] for pid in range(num_players)},
            "community_cards": [], "visible_community_cards": [], "pot": 0, "current_bet": 0, "player_bets": {pid: 0 for pid in range(num_players)}, "button": 0, "folded_players": set(),
            "all_in_players": set(), "checked_players": set(), "round_turn": 0, "game_complete": False, "last_bettor": -1, "bet_round_complete": False,
        }
        self.state.reset(game_state=gs, player_prompt_function=self._prompt)
        self.state.add_observation(message=f"Starting a new {self.num_rounds}-round Texas Hold'em game with {num_players} players.", observation_type=ta.ObservationType.GAME_MESSAGE)
        self._reset_round()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are Player {player_id} in a {self.state.num_players}-player Texas Hold'em Poker game.\nGame Information:\n"
            f"- {self.num_rounds} hands total\n- Starting stack: {self.starting_chips} chips\n- Blinds: {self.small_blind}/{self.big_blind}\n\n"
            "Available actions (exact tokens):\n"
            "  '[Check]'  - when no bet is live\n"
            "  '[Call]'   - match the current bet\n"
            "  '[Fold]'   - discard your hand\n"
            "  '[Bet N]'  - open for N chips\n"
            "  '[Raise N]'- raise by N chips\n"
        )

    def _create_deck(self): return [{"rank": r, "suit": s} for s in self.suits for r in self.ranks]

    def _reset_round(self, force: bool = False):
        self._eliminate_busted_players()
        gs = self.state.game_state
        n = self.state.num_players
        deck = self._create_deck()
        random.shuffle(deck)
        for pid in range(n): gs["player_hands"][pid] = [deck.pop(), deck.pop()]

        gs["community_cards"] = [deck.pop() for _ in range(5)]
        gs["visible_community_cards"] = []
        gs["pot"] = 0
        gs["current_bet"] = 0
        gs["player_bets"] = {pid: 0 for pid in range(n)}
        gs["folded_players"] = set()
        gs["all_in_players"] = set()
        gs["checked_players"] = set()
        gs["round_turn"] = 0
        gs["last_bettor"] = -1
        gs["bet_round_complete"] = False

        btn = gs["button"]
        if n == 2:
            sbp = btn
            bbp = (btn + 1) % n
            next_player = sbp
        else:
            sbp = (btn + 1) % n
            bbp = (btn + 2) % n
            next_player = self._get_next_active_player(bbp)
 
        def post_blind(pid: int, amount: int):
            amt = min(amount, gs["player_chips"][pid])
            gs["player_chips"][pid] -= amt
            gs["player_bets"][pid]  += amt
            gs["pot"] += amt
            if gs["player_chips"][pid] == 0: gs["all_in_players"].add(pid)
            return amt

        sb = post_blind(sbp, self.small_blind)
        bb = post_blind(bbp, self.big_blind)
        gs["current_bet"] = max(sb, bb)
        self.state.manually_set_current_player_id(new_player_id=next_player, force=force)
        self._observe_current_pot()

    def _observe_current_pot(self):
        gs = self.state.game_state
        n  = self.state.num_players
        comm = ", ".join(f"{c['rank']}{c['suit']}" for c in gs["visible_community_cards"])
        betting_round_names = {0: "Pre‑flop", 1: "Flop", 2: "Turn", 3: "River"}
        btn = gs["button"]
        sb  = (btn + 1) % n
        bb  = (btn + 2) % n
        lines = []
        for pid in range(n):
            roles = []
            if pid == btn: roles.append("Dealer")
            if pid == sb:  roles.append("SB")
            if pid == bb:  roles.append("BB")
            role_txt = f" ({'/'.join(roles)})" if roles else ""
            if pid in gs["folded_players"]: status = "folded"
            elif pid in gs["all_in_players"]: status = "all-in"
            else: status = "active"
            lines.append(f"P{pid}{role_txt}: {gs['player_chips'][pid]:.2f} chips | bet {gs['player_bets'][pid]:.2f} | {status}")

        hole = gs["player_hands"][self.state.current_player_id]
        msg  = (
            f"===== Hand {gs['round']} / {self.num_rounds} - {betting_round_names[gs['betting_round']]} =====\n"
            f"Pot: {gs['pot']} | Current bet: {gs['current_bet']}\nVisible board: [{comm}]\n" + "\n".join(lines) +
            f"\nYour hole: {hole[0]['rank']}{hole[0]['suit']}, {hole[1]['rank']}{hole[1]['suit']}\n"
            "=============================================="
        )
        self.state.add_observation(to_id=self.state.current_player_id, message=msg, observation_type=ta.ObservationType.GAME_BOARD)


    def _handle_invalid(self, reason: str):
        eliminated_by_invalid = self.state.set_invalid_move(reason=reason)
        if eliminated_by_invalid:
            # distribute pot to everybody and set player chips to 0 (i.e. eliminated)
            self.state.add_observation(message=f"Player {self.state.current_player_id} was eliminated by invalid move.", observation_type=ta.ObservationType.GAME_MESSAGE)
            # self.state.add_elimination(pid=self.state.current_player_id)
            self.state.game_state["player_chips"][self.state.current_player_id] = 0
            alive = [pid for pid in range(self.state.num_players) if self.state.is_player_alive(pid) and pid!=self.state.current_player_id]

            for pid in alive:
                self.state.game_state["player_chips"][pid] += self.state.game_state["pot"]/len(alive)

            self.state.game_state["pot"] = 0
            self._eliminate_busted_players()
            self._reset_round(force=True)


    def step(self, action: str) -> Tuple[bool, ta.Info]:
        if self.state.game_state["game_complete"] or self.state.done:
            # player_eliminated = self.state.set_invalid_move(reason="The game is already complete.")
            self._handle_invalid(reason="The game is already complete.")
            return self.state.step(rotate_player=False)
        
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        valid_action_processed = self._process_betting_action(action=action, player_id=self.state.current_player_id)
        if not valid_action_processed or self.state.made_invalid_move: # Immediately halt all further logic clearly:
            return self.state.step(rotate_player=False)

        # Only proceed if action was definitely valid
        self._rotate_players()
        if not self.state.made_invalid_move: self._observe_current_pot()
        return self.state.step(rotate_player=False)

    def _parse_action(self, action: str) -> Tuple[str, Optional[int]]:
        gs = self.state.game_state
        gs["round_turn"] += 1
        if self._CHECK_RE.search(action):                       return "check", None
        if self._FOLD_RE.search(action):                        return "fold", None
        if self._CALL_RE.search(action):                        return "call", None
        if (m := self._BET_RE.search(action)) is not None:      return "bet", int(m.group(1))
        if (m := self._RAISE_RE.search(action)) is not None:    return "raise", int(m.group(1))
        return "invalid", None

    def _process_betting_action(self, action: str, player_id: int):
        a_type, amount = self._parse_action(action)
        if a_type == "invalid": 
            self._handle_invalid(reason="Invalid poker action."); return False
            # self.state.set_invalid_move(reason="Invalid poker action."); return False
        self._apply_action(player_id, a_type, amount)
        if self.state.made_invalid_move: return False  # clearly propagate invalid moves back
        if self.state.game_state["game_complete"]: return False
        if self._is_betting_round_complete() and not self._is_hand_over(): self._advance_game_phase()
        return True

    def _apply_action(self, pid: int, a_type: str, bet_amt: Optional[int]):
        gs = self.state.game_state
        def pay(player: int, chips: int):
            gs["player_chips"][player] -= chips
            gs["player_bets"][player]  += chips
            gs["pot"] += chips
            self._check_and_eliminate(player)

        if a_type == "fold":
            gs["folded_players"].add(pid)
            self.state.add_observation(message=f"Player {pid} folds.", observation_type=ta.ObservationType.GAME_MESSAGE)
            if self._is_hand_over(): self._handle_hand_completion()
            return

        if a_type == "check":
            if gs["current_bet"] > gs["player_bets"][pid]:self.state.set_invalid_move(reason="Cannot check facing a bet."); return
            gs["checked_players"].add(pid)
            self.state.add_observation(message=f"Player {pid} checks.", observation_type=ta.ObservationType.GAME_MESSAGE)
            if gs["last_bettor"] == -1 or self._next_player_would_be_after_last_bettor(pid): gs["bet_round_complete"] = True
            return

        if a_type == "call":
            due = gs["current_bet"] - gs["player_bets"][pid]
            if due <= 0:  # already covered → treat as check
                gs["checked_players"].add(pid)
                if gs["last_bettor"] == -1 or self._next_player_would_be_after_last_bettor(pid):
                    gs["bet_round_complete"] = True
                return
            pay_amount = min(due, gs["player_chips"][pid])
            pay(pid, pay_amount)
            if pay_amount < due:  # all‑in call short
                gs["all_in_players"].add(pid)
            self.state.add_observation(message=f"Player {pid} calls {pay_amount}.", observation_type=ta.ObservationType.GAME_MESSAGE)
            if gs["last_bettor"] == -1 or self._next_player_would_be_after_last_bettor(pid): gs["bet_round_complete"] = True
            return

        gs["bet_round_complete"] = False
        cur_contrib = gs["player_bets"][pid]
        target_total = bet_amt if a_type == "bet" else gs["current_bet"] + bet_amt
        needed = target_total - cur_contrib
        if needed <= 0 or (a_type == "raise" and target_total <= gs["current_bet"]): 
            self._handle_invalid(reason="Raise must exceed current bet."); return
            # self.state.set_invalid_move(reason="Raise must exceed current bet."); return
        pay_amount = min(needed, gs["player_chips"][pid])
        pay(pid, pay_amount)
        if gs["player_bets"][pid] > gs["current_bet"]:
            gs["current_bet"] = gs["player_bets"][pid]
            gs["last_bettor"] = pid
        if pay_amount < needed:  # player went all‑in without covering raise fully
            gs["all_in_players"].add(pid)
        verb = "bets" if a_type == "bet" else "raises"
        self.state.add_observation(message=f"Player {pid} {verb} to {gs['player_bets'][pid]}.", observation_type=ta.ObservationType.GAME_MESSAGE)

    def _next_player_would_be_after_last_bettor(self, pid: int) -> bool:
        gs = self.state.game_state
        nxt = self._get_next_active_player(pid)
        if gs["last_bettor"] == -1: return nxt == self._get_first_active_player_of_round()
        if gs["player_chips"][gs["last_bettor"]] == 0: return True
        return nxt == gs["last_bettor"] or self._player_comes_after(nxt, gs["last_bettor"])

    def _get_first_active_player_of_round(self) -> int:
        gs = self.state.game_state
        if gs["betting_round"] == 0: return self._get_next_active_player((gs["button"] + 2) % self.state.num_players)
        return self._get_next_active_player((gs["button"] + 1) % self.state.num_players)

    def _player_comes_after(self, pid: int, ref: int) -> bool:
        n = self.state.num_players
        i = ref
        while True:
            i = (i + 1) % n
            if i == pid: return True
            if i == ref: return False  # full loop

    def _get_next_active_player(self, cur: int) -> int:
        gs = self.state.game_state
        n = self.state.num_players
        i = (cur + 1) % n
        while i != cur:
            if (gs["player_chips"][i] > 0 and i not in gs["folded_players"] and i not in gs["all_in_players"]): return i
            i = (i + 1) % n
        return cur

    def _is_hand_over(self) -> bool:
        gs = self.state.game_state
        n  = self.state.num_players
        active = [pid for pid in range(n) if pid not in gs["folded_players"] and gs["player_chips"][pid] > 0]
        for pid in range(n):
            if gs["player_chips"][pid] == 0 and pid not in gs["folded_players"]: gs["all_in_players"].add(pid)
        if len(active) <= 1: return True
        return all(pid in gs["all_in_players"] for pid in active)

    def _is_betting_round_complete(self):
        gs = self.state.game_state
        active = [pid for pid in range(self.state.num_players) if pid not in gs["folded_players"] and pid not in gs["all_in_players"] and gs["player_chips"][pid] > 0]
        if len(active) <= 1: return True
        if gs["current_bet"] == 0: return all(pid in gs["checked_players"] for pid in active)
        all_matched = all(gs["player_bets"][pid] == gs["current_bet"] for pid in active)
        return all_matched and gs["bet_round_complete"]

    def _advance_game_phase(self):
        gs = self.state.game_state
        if gs["betting_round"] < 3:
            gs["betting_round"] += 1
            gs["current_bet"] = 0
            gs["player_bets"] = {pid: 0 for pid in range(self.state.num_players)}
            gs["checked_players"] = set()
            gs["last_bettor"] = -1
            gs["bet_round_complete"] = False

            if gs["betting_round"] == 1:    gs["visible_community_cards"] = gs["community_cards"][:3]
            elif gs["betting_round"] == 2:  gs["visible_community_cards"] = gs["community_cards"][:4]
            elif gs["betting_round"] == 3:  gs["visible_community_cards"] = gs["community_cards"][:5]

            self.state.manually_set_current_player_id(new_player_id=self._get_first_active_player_of_round())
            return
        # all betting rounds finished → showdown
        self._handle_showdown()
        self._handle_post_hand_or_game_end()

    def _eliminate_busted_players(self):
        gs = self.state.game_state
        for pid, chips in gs["player_chips"].items():
            if chips == 0 and self.state.is_player_alive(pid):
                self.state.add_elimination(pid)

    def _handle_hand_completion(self):
        gs = self.state.game_state
        gs["visible_community_cards"] = gs["community_cards"]
        self._handle_showdown()
        self._handle_post_hand_or_game_end()

    def _handle_post_hand_or_game_end(self):
        gs = self.state.game_state
        alive = [pid for pid in range(self.state.num_players) if self.state.is_player_alive(pid)]
        if len(alive) <= 1 or gs["round"] >= self.num_rounds:
            self.determine_winner()
            gs["game_complete"] = True
            return
        gs["round"] += 1
        gs["betting_round"] = 0
        gs["button"] = (gs["button"] + 1) % self.state.num_players
        self._reset_round()

    def _handle_showdown(self):
        gs = self.state.game_state

        # 1)  Which players are still “in” the hand?
        active = [pid for pid in range(self.state.num_players) if pid not in gs["folded_players"]]

        # ── single-player showdown: everyone else folded ─────────────────
        if len(active) == 1:
            winner = active[0]
            gs["player_chips"][winner] += gs["pot"]
            self.state.add_observation(message=f"Player {winner} wins the pot of {gs['pot']} chips (all others folded).", observation_type=ta.ObservationType.GAME_MESSAGE)
            gs["pot"] = 0
            self._eliminate_busted_players()
            return

        # 2)  Multi-way showdown – reveal hands and evaluate -------------
        reveal = []
        for pid in active:
            h = gs["player_hands"][pid]
            reveal.append(f"Player {pid}: {h[0]['rank']}{h[0]['suit']} {h[1]['rank']}{h[1]['suit']}")
        community_cards = ", ".join(f'{card["rank"]}{card["suit"]}' for card in gs['community_cards'])
        self.state.add_observation(message=f"Showdown round {self.state.game_state['round']}:\n" + "\n".join(reveal) + f"\nCommunity cards: {community_cards}", observation_type=ta.ObservationType.GAME_MESSAGE)

        # Evaluate best 5-card hand for each player
        scores = {pid: self._evaluate_hand(gs["player_hands"][pid] + gs["community_cards"]) for pid in active}
        best_score = max(scores.values())
        winners = [pid for pid, sc in scores.items() if sc == best_score]

        # 3)  Award the pot ---------------------------------------------
        pot = gs["pot"]
        if len(winners) == 1:
            gs["player_chips"][winners[0]] += pot
            self.state.add_observation(message=f"Player {winners[0]} wins the pot of {pot} chips.", observation_type=ta.ObservationType.GAME_MESSAGE)
        else:
            share = pot // len(winners)
            for w in winners: gs["player_chips"][w] += share
            # house rule: odd chip (if any) to first winner
            remainder = pot - share * len(winners)
            if remainder: gs["player_chips"][winners[0]] += remainder
            self.state.add_observation(message=f"Tie between players {winners}. Each receives {share} chips.", observation_type=ta.ObservationType.GAME_MESSAGE)

        gs["pot"] = 0
        self._eliminate_busted_players()

    def _evaluate_hand(self, cards: List[Dict[str, str]]) -> Tuple[int, List[int]]:
        """Return (category_rank, tiebreak_list).  Higher tuple wins."""
        ranks = [self.rank_values[c["rank"]] for c in cards]
        suits = [c["suit"] for c in cards]
        r_counter = Counter(ranks)
        s_counter = Counter(suits)

        # Flush?
        flush_suit = next((s for s, cnt in s_counter.items() if cnt >= 5), None)
        distinct = sorted(set(ranks))
        straight, straight_hi = self._check_straight(distinct)

        # 9  Straight flush
        if flush_suit and straight:
            flush_cards = sorted({r for r, s in zip(ranks, suits) if s == flush_suit})
            sf, sf_hi = self._check_straight(flush_cards)
            if sf: return 9, [sf_hi]

        # 8  Quads
        if 4 in r_counter.values():
            quad = max(r for r, c in r_counter.items() if c == 4)
            kicker = max(r for r in ranks if r != quad)
            return 8, [quad, kicker]

        # 7  Full house
        if 3 in r_counter.values():
            triple = max(r for r, c in r_counter.items() if c == 3)
            pair_candidates = [r for r, c in r_counter.items() if c >= 2 and r != triple]
            if pair_candidates:
                pair = max(pair_candidates)
                return 7, [triple, pair]

        # 6  Flush
        if flush_suit:
            flush_cards = sorted((r for r, s in zip(ranks, suits) if s == flush_suit), reverse=True)
            return 6, flush_cards[:5]

        # 5  Straight
        if straight:
            return 5, [straight_hi]

        # 4  Trips
        if 3 in r_counter.values():
            triple = max(r for r, c in r_counter.items() if c == 3)
            kickers = sorted((r for r in ranks if r != triple), reverse=True)
            return 4, [triple] + kickers[:2]

        # 3  Two-pair
        pairs = [r for r, c in r_counter.items() if c == 2]
        if len(pairs) >= 2:
            pairs.sort(reverse=True)
            kicker = max(r for r in ranks if r not in pairs)
            return 3, pairs[:2] + [kicker]

        # 2  One-pair
        if len(pairs) == 1:
            p = pairs[0]
            kickers = sorted((r for r in ranks if r != p), reverse=True)
            return 2, [p] + kickers[:3]

        # 1  High card
        return 1, sorted(ranks, reverse=True)[:5]

    def _check_straight(self, sorted_ranks: List[int]) -> Tuple[bool, int]:
        if len(sorted_ranks) < 5:
            return False, -1
        # Wheel
        if {14, 2, 3, 4, 5}.issubset(sorted_ranks):
            return True, 5
        for i in range(len(sorted_ranks) - 4):
            seq = sorted_ranks[i:i + 5]
            if seq[-1] - seq[0] == 4:
                return True, seq[-1]
        return False, -1

    def determine_winner(self):
        """End the tournament and assign final rewards."""
        self._set_outcome()
        self.state.game_state["game_complete"] = True

    def _set_outcome(self):
        """ Linear rewards in [-1, 1] identical to LiarsDice: the earlier a player busts, the lower their reward; chip-leaders split the top. """
        ranking = list(self.state.elimination_order)

        # survivors (never eliminated) ordered by chip stack (low → high)
        survivors = [pid for pid in range(self.state.num_players) if pid not in ranking]
        survivors.sort(key=lambda p: self.state.game_state["player_chips"][p])
        ranking.extend(survivors)

        rewards = {pid: -1.0 + 2.0 * idx / (self.state.num_players - 1) for idx, pid in enumerate(ranking)}
        self.state.set_game_outcome(reward_dict=rewards, reason=f"Final ranking (low→high): {ranking}. Winner: Player {ranking[-1]}")


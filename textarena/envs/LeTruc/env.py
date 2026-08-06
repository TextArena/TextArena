import random, re
from typing import Dict, Any, Optional, List, Tuple
import textarena as ta


class LeTrucEnv(ta.Env):
    """Two-player Le Truc (Catalan/Spanish 40-card variant).

    Deck: 40 cards in four French suits (♣♦♥♠); rank order high->low is
    ``3 2 A K Q J 7 6 5 4`` -- the Spanish ``3 2 1 Rey Caballo Sota 7 6 5 4``
    mapped onto K/Q/J. (Removing the 8s, 9s and 10s from a 52-card pack leaves
    exactly these 40 cards.)

    Each hand both players receive 3 cards and play up to three one-card tricks.
    The higher rank wins a trick regardless of suit; equal ranks tie ("spoilt")
    and the same player leads again. A hand is won by taking two tricks, or by
    winning the first trick when the other is tied -- a spoilt trick counts for
    whoever won the first trick. If all three tricks tie, neither player scores.

    A hand is worth 1 point. On their turn a player may ``[raise]`` ("truc") to
    increase the stake: 1->2, then +2 for each further raise, up to 12. The
    opponent must ``[accept]``, ``[fold]`` or re-``[raise]``; a player who folds
    concedes the hand and the raiser scores the stake as it stood *before* that
    raise. First to 12 points wins the match.
    """
    order = ["3", "2", "A", "K", "Q", "J", "7", "6", "5", "4"]

    def __init__(self):
        super().__init__()
        self.action_space = re.compile(
            r"""\[
                (?P<verb>play|raise|accept|fold)            # action keyword
                (?:\s+(?P<card>[234567JQKA]))?              # optional rank (play)
            \]""",
            re.IGNORECASE | re.VERBOSE,
        )
        # build the 40-card deck
        suits = "♣♦♥♠"
        self.deck = [r + s for r in self.order for s in suits]

    # ── setup ───────────────────────────────────────────────────────────────
    def reset(self, num_players: int = 2, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        # dealer starts at 1 so the first hand's non-dealer leader is player 0.
        self.state.reset(game_state={"match_points": {0: 0, 1: 0}, "stake": 1, "dealer": 1}, player_prompt_function=self._prompt)
        self._deal_hand()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro")

    def _deal_hand(self):
        gs = self.state.game_state
        d = self.deck.copy()
        random.shuffle(d)
        gs["hands"]         = {0: d[:3], 1: d[3:6]}
        gs["trick_results"] = []            # per completed trick: 0, 1, or None (tie/spoilt)
        gs["led"]           = None          # (leader_pid, card_str) while a trick is in progress
        gs["pending"]       = None          # {"offerer": pid, "proposed": int} while a raise is unanswered
        gs["raise_origin"]  = None          # pid whose turn-to-play a raise negotiation interrupted
        leader = 1 - gs["dealer"]           # the non-dealer ("mano") leads
        gs["leader"]  = leader
        gs["dealer"]  = 1 - gs["dealer"]    # alternate the deal for the next hand
        for pid in (0, 1):
            self.state.add_observation(to_id=pid, message=self.m("board", "new_hand", points=gs["stake"], cards=" ".join(gs["hands"][pid])), observation_type=ta.ObservationType.GAME_BOARD)
        self.state.manually_set_current_player_id(leader)
        self._announce_legal(leader)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _rank_idx(self, card: str) -> int:
        return self.order.index(card[:-1])

    def _next_stake(self, stake: int) -> int:
        # First raise lifts the stake 1->2; every further raise adds 2, capped at 12.
        return 2 if stake == 1 else min(stake + 2, 12)

    def _effective_stake(self) -> int:
        """The stake a raise would build on: the standing proposal if one exists
        (a re-raise implicitly accepts it), otherwise the agreed stake.

        FIX: the raise cap must be checked against THIS value, not gs["stake"].
        Checking gs["stake"] allowed a no-op "raise" from a pending 12 (stake 10),
        which flipped the accept-12/fold-10 decision onto the opponent as
        accept-12/fold-12 -- a strict exploit.
        """
        gs = self.state.game_state
        return gs["pending"]["proposed"] if gs["pending"] is not None else gs["stake"]

    def _legal(self, pid: int) -> List[str]:
        gs = self.state.game_state
        if gs["pending"] is not None:                       # pid must answer a standing raise
            acts = ["accept", "fold"]
            if self._effective_stake() < 12: acts.append("raise")   # FIX: was gs["stake"] < 12
            return acts
        acts = []
        for c in gs["hands"][pid]:                          # otherwise pid is to play a card
            a = f"play {c[:-1]}"
            if a not in acts: acts.append(a)                # dedupe duplicate ranks
        if self._effective_stake() < 12: acts.append("raise")
        return acts

    def _announce_legal(self, pid: int):
        legal = ", ".join(f"'[{a}]'" for a in self._legal(pid))
        self.state.add_observation(to_id=pid, message=self.m("board", "valid_actions", legal=legal), observation_type=ta.ObservationType.GAME_BOARD)

    def _resolve(self, results: List[Optional[int]]):
        """Decide the hand from completed-trick outcomes.

        results holds one entry per completed trick: 0/1 for a trick won outright,
        None for a spoilt (tied) trick. A spoilt trick is credited to whoever won
        the first non-tied trick, so:
          * two effective tricks  -> that player wins;
          * win-one + spoilt-one  -> the first-trick winner wins (decided early);
          * all three spoilt      -> nobody scores (void).
        Returns 0/1 (winner), None (void, only after three tricks), or the string
        'undecided' when more tricks are needed.
        """
        first_winner = next((r for r in results if r is not None), None)
        spoilt = sum(1 for r in results if r is None)
        eff = {0: 0, 1: 0}
        for r in results:
            if r is not None: eff[r] += 1
        if first_winner is not None: eff[first_winner] += spoilt
        if eff[0] >= 2: return 0
        if eff[1] >= 2: return 1
        if len(results) == 3: return None       # three tricks played, no majority -> all tied
        return "undecided"

    # ── main ───────────────────────────────────────────────────────────────
    def step(self, action: str) -> Tuple[bool, Dict[str, Any]]:
        pid = self.state.current_player_id
        self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        m = self.action_space.search(action)
        if not m:
            return self._invalid("unrecognised")
        verb = m.group("verb").lower()
        if verb == "raise":  return self._do_raise(pid)
        if verb == "accept": return self._do_accept(pid)
        if verb == "fold":   return self._do_fold(pid)
        return self._do_play(pid, m.group("card"))

    def _invalid(self, key: str):
        self.state.set_invalid_move(reason=self.m("invalid_move", key))
        return self.state.step()

    def _do_raise(self, pid: int):
        gs = self.state.game_state
        if gs["pending"] is not None and gs["pending"]["offerer"] == pid:
            return self._invalid("already_raised")           # your offer is still standing
        if self._effective_stake() >= 12:                    # FIX: was gs["stake"] >= 12
            return self._invalid("max_stake")
        if gs["pending"] is not None:
            gs["stake"] = gs["pending"]["proposed"]          # re-raise implicitly accepts the standing offer
        else:
            gs["raise_origin"] = pid                          # remember whose card-turn we interrupted
        proposed = self._next_stake(gs["stake"])
        gs["pending"] = {"offerer": pid, "proposed": proposed}
        self.state.add_observation(message=self.m("action", "raise", pid=pid, points=proposed), observation_type=ta.ObservationType.GAME_MESSAGE)
        responder = 1 - pid
        self.state.manually_set_current_player_id(responder)
        self._announce_legal(responder)
        return self.state.step(rotate_player=False)

    def _do_accept(self, pid: int):
        gs = self.state.game_state
        if gs["pending"] is None or gs["pending"]["offerer"] == pid:
            return self._invalid("no_raise_to_accept")
        gs["stake"] = gs["pending"]["proposed"]
        gs["pending"] = None
        origin = gs["raise_origin"]
        gs["raise_origin"] = None
        self.state.add_observation(message=self.m("action", "accept", pid=pid, points=gs["stake"]), observation_type=ta.ObservationType.GAME_MESSAGE)
        self.state.manually_set_current_player_id(origin)     # the interrupted player now plays
        self._announce_legal(origin)
        return self.state.step(rotate_player=False)

    def _do_fold(self, pid: int):
        gs = self.state.game_state
        if gs["pending"] is None or gs["pending"]["offerer"] == pid:
            return self._invalid("cannot_fold")
        winner = 1 - pid                                      # the raiser wins the hand
        self.state.add_observation(message=self.m("outcome", "folded"), observation_type=ta.ObservationType.GAME_MESSAGE)
        # gs["stake"] is still the value agreed *before* the pending raise -- exactly
        # what a fold concedes.
        return self._award_hand(winner)

    def _do_play(self, pid: int, card_group: Optional[str]):
        gs = self.state.game_state
        if gs["pending"] is not None:
            return self._invalid("must_respond")
        if card_group is None:
            return self._invalid("unrecognised")
        rank = card_group.upper()
        if rank not in [c[:-1] for c in gs["hands"][pid]]:
            return self._invalid("wrong_rank")
        idx = next(i for i, c in enumerate(gs["hands"][pid]) if c[:-1] == rank)
        card_str = gs["hands"][pid].pop(idx)

        if gs["led"] is None:                                 # lead the trick
            gs["led"] = (pid, card_str)
            self.state.add_observation(message=self.m("action", "lead", pid=pid, card=card_str), observation_type=ta.ObservationType.GAME_MESSAGE)
            follower = 1 - pid
            self.state.manually_set_current_player_id(follower)
            self._announce_legal(follower)
            return self.state.step(rotate_player=False)

        # follow -> resolve the trick (lower rank index == stronger card)
        lead_pid, lead_card = gs["led"]
        if self._rank_idx(card_str) < self._rank_idx(lead_card):   trick_winner = pid
        elif self._rank_idx(card_str) > self._rank_idx(lead_card): trick_winner = lead_pid
        else:                                                      trick_winner = None   # spoilt
        gs["led"] = None
        gs["trick_results"].append(trick_winner)
        if trick_winner is None:
            self.state.add_observation(message=self.m("action", "spoilt", pid=pid, card=card_str), observation_type=ta.ObservationType.GAME_MESSAGE)
        else:
            self.state.add_observation(message=self.m("action", "play", pid=pid, card=card_str, winner=trick_winner), observation_type=ta.ObservationType.GAME_MESSAGE)

        decision = self._resolve(gs["trick_results"])
        if decision == "undecided":
            next_leader = trick_winner if trick_winner is not None else gs["leader"]  # spoilt -> same leader
            gs["leader"] = next_leader
            self.state.manually_set_current_player_id(next_leader)
            self._announce_legal(next_leader)
            return self.state.step(rotate_player=False)
        if decision is None:
            return self._void_hand()
        return self._award_hand(decision)

    # ── hand endings ─────────────────────────────────────────────────────────
    def _award_hand(self, winner: int):
        gs = self.state.game_state
        gs["match_points"][winner] += gs["stake"]
        p0, p1 = gs["match_points"][0], gs["match_points"][1]
        self.state.add_observation(message=self.m("outcome", "hand_won", winner=winner, points=gs["stake"], p0=p0, p1=p1), observation_type=ta.ObservationType.GAME_MESSAGE)
        if gs["match_points"][winner] >= 12:
            self.state.set_winner(winner, reason=self.m("outcome", "reached_twelve"))
            return self.state.step()
        gs["stake"] = 1
        self._deal_hand()
        return self.state.step(rotate_player=False)

    def _void_hand(self):
        gs = self.state.game_state
        p0, p1 = gs["match_points"][0], gs["match_points"][1]
        self.state.add_observation(message=self.m("outcome", "void", p0=p0, p1=p1), observation_type=ta.ObservationType.GAME_MESSAGE)
        gs["stake"] = 1
        self._deal_hand()
        return self.state.step(rotate_player=False)
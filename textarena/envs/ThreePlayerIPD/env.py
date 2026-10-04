import itertools
import math
import re
from typing import Any, Dict, Optional, Tuple, Union

import textarena as ta


def _is_renderable(value: Any) -> bool:
    try:
        str(value)
    except (OverflowError, ValueError):
        return False
    return True


class ThreePlayerIPDEnv(ta.GameEnv):
    min_players = 3
    max_players = 3
    broadcast_actions = False  # raw actions echoed only to their author; chat is re-broadcast cleaned

    def __init__(self, num_rounds: int=5, communication_turns: int=3, cooperate_reward: int=3, defect_reward: int=5, sucker_reward: int=0, mutual_defect_reward: int=1):
        if isinstance(num_rounds, bool) or not isinstance(num_rounds, int) or num_rounds < 1 or not _is_renderable(num_rounds):
            raise ValueError("num_rounds must be a positive integer")
        if isinstance(communication_turns, bool) or not isinstance(communication_turns, int) or communication_turns < 0 or not _is_renderable(communication_turns):
            raise ValueError("communication_turns must be a non-negative integer")
        payoffs = {
            "cooperate_reward": cooperate_reward,
            "defect_reward": defect_reward,
            "sucker_reward": sucker_reward,
            "mutual_defect_reward": mutual_defect_reward,
        }
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or (isinstance(value, float) and not math.isfinite(value))
            or not _is_renderable(value)
            for value in payoffs.values()
        ):
            raise ValueError("payoff values must be finite numbers")
        self.num_rounds = num_rounds
        self.conversation_rounds = communication_turns
        self.R, self.T, self.S, self.P = (cooperate_reward, defect_reward, sucker_reward, mutual_defect_reward) # pay-off constants
        self.token_pat = re.compile(r"(?<!\d)(\d+)\s+(cooperate|defect)", re.I)

    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players
        return {
            "round": 1, "num_rounds": self.num_rounds, "phase": "conversation", "conversation_round": 0, "total_conversation_rounds": self.conversation_rounds,
            "decisions": {p: {q: None for q in range(num_players) if q != p} for p in range(num_players)},
            "scores": {p: 0 for p in range(num_players)}, "acted": {p: False for p in range(num_players)},
        }

    def on_start(self):
        gs = self.game_state
        if gs["total_conversation_rounds"] == 0:
            gs["phase"] = "decision"
            self.broadcast(
                f"─── Starting Round {gs['round']} ───\tSubmit your private decisions now.",
                ta.ObservationType.GAME_MESSAGE,
            )
        else:
            self.broadcast(f"─── Starting Round {gs['round']} ───\tYou can converse freely for the next {gs['total_conversation_rounds']} rounds.", ta.ObservationType.GAME_MESSAGE)

    def prompt(self, player_id: int) -> str:
        gs = self.game_state
        first, second = [pid for pid in range(self.state.num_players) if pid != player_id]
        return (
            f"You are Player {player_id} in a 3-player Iterated Prisoner's Dilemma. The match lasts {gs['num_rounds']} rounds.\n"
            f"Round structure:\n"
            f"• {gs['total_conversation_rounds']} free-chat turns\n"
            f"• 1 decision turn - submit one token per opponent: '<opp-id> cooperate' or '<opp-id> defect' (i.e. '{first} defect {second} cooperate'; the default is 'cooperate'). \n"
            f"Pair-wise payoff matrix (applied to each unordered pair):\n"
            f"  - Both cooperate  ->  {self.R}\n"
            f"  - Both defect     ->  {self.P}\n"
            f"  - You defect, they cooperate -> {self.T}\n"
            f"  - You cooperate, they defect -> {self.S}\n"
            "Rewards follow the final ranking by total score: highest +1, lowest -1, middle 0. "
            "Two players tied ahead of the third both get +1, two tied behind both get -1, and a three-way tie gives everyone 0.\n"
            "Two invalid moves in a row forfeit the match: you get -1 and both opponents get +1.\n"
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        match self.game_state["phase"]:
            case "conversation":    return self._conversation_phase(player_id, msg=action)
            case "decision":        return self._decision_phase(player_id, msg=action)

    def _clean_message(self, msg: str) -> str:
        """Collapse whitespace and remove sender labels such as '[GAME]' so chat cannot impersonate other senders."""
        # Strip again after collapsing whitespace, which can turn '[Player\n1]' into a label.
        return self.strip_role_tags(re.sub(r"\s+", " ", self.strip_role_tags(msg)))

    def _conversation_phase(self, cid: int, msg: str) -> None:
        # broadcast chat to others
        for pid in range(self.state.num_players):
            if pid != cid:
                self.message(pid, self._clean_message(msg), ta.ObservationType.PLAYER_ACTION, from_id=cid)

        # increment counter after the last speaker
        if cid == self.state.num_players - 1:
            gs = self.game_state
            gs["conversation_round"] += 1
            if gs["conversation_round"] >= gs["total_conversation_rounds"]:
                gs["phase"] = "decision"
                self.broadcast(f"Chat finished for round {gs['round']}. Submit your decisions, one token per opponent: `<pid> cooperate` or `<pid> defect`.", ta.ObservationType.GAME_BOARD)
        return None

    def _decision_phase(self, cid: int, msg: str) -> Optional[ta.Outcome]:
        gs = self.game_state
        parsed, reason = self._parse_decisions(cid, msg)
        if parsed is None:
            return self.invalid(reason)
        # Parse completely before mutating so malformed compound actions are atomic.
        gs["decisions"][cid].update(parsed)
        gs["acted"][cid] = True  # player has taken their decision turn

        # When every player has *acted* once, resolve round.
        if all(gs["acted"].values()):
            # fill unspecified edges with *cooperate*
            for p, row in gs["decisions"].items():
                for q in row:
                    if row[q] is None:
                        row[q] = "cooperate"
            self._resolve_round()

            # next round or finish
            gs["round"] += 1
            if gs["round"] > gs["num_rounds"]:
                return self._end_game()
            # reset for next round
            gs.update({
                "phase": "conversation", "conversation_round": 0, "acted": {p: False for p in range(self.state.num_players)},
                "decisions": {p: {q: None for q in range(self.state.num_players) if q != p} for p in range(self.state.num_players)},
            })
            if gs["total_conversation_rounds"] == 0:
                gs["phase"] = "decision"
                self.broadcast(f"─── Starting Round {gs['round']} ───\tSubmit your private decisions now.", ta.ObservationType.GAME_MESSAGE)
            else:
                self.broadcast(f"─── Starting Round {gs['round']} ───\tYou can converse freely for the next {gs['total_conversation_rounds']} rounds.", ta.ObservationType.GAME_MESSAGE)
        return None

    def _parse_decisions(self, player_id: int, msg: str) -> Tuple[Optional[Dict[int, str]], Optional[str]]:
        """Parse decision tokens without silently ignoring malformed or duplicate targets."""
        parsed: Dict[int, str] = {}
        cursor = 0
        matches = list(self.token_pat.finditer(msg))
        if not matches:
            if msg.strip():
                return None, "Submit decisions as '<player-id> cooperate' or '<player-id> defect'."
            return parsed, None  # every omitted opponent defaults to cooperate

        for index, match in enumerate(matches):
            separator = msg[cursor:match.start()]
            separator_pattern = r"\s*" if index == 0 else r"[\s,;]+"
            if not re.fullmatch(separator_pattern, separator):
                return None, "Decision tokens may only be separated by spaces, commas, or semicolons."
            target_token = match.group(1).lstrip("0") or "0"
            if len(target_token) > 1:
                return None, f"Player {match.group(1)} is not a valid opponent."
            target = int(target_token)
            if target == player_id:
                return None, "You cannot submit a decision against yourself."
            if target not in self.game_state["decisions"][player_id]:
                return None, f"Player {target} is not a valid opponent."
            if target in parsed:
                return None, f"Submit exactly one decision for Player {target}."
            parsed[target] = match.group(2).lower()
            cursor = match.end()
        if not re.fullmatch(r"\s*", msg[cursor:]):
            return None, "Unexpected text after the decision tokens."
        return parsed, None

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        # Continuing after removing one participant would leave unresolved
        # pairwise decisions in every remaining round.
        return self.loser(player_id, reason=f"Player {player_id} forfeited after repeated invalid decisions: {reason}")

    def _pair_payoff(self, a: str, b: str) -> Tuple[int, int]:
        if a == b == "cooperate":   return self.R, self.R
        if a == b == "defect":      return self.P, self.P
        return (self.S, self.T) if a == "cooperate" else (self.T, self.S) # one cooperates, one defects

    def _resolve_round(self):
        gs = self.game_state
        decisions = gs["decisions"]
        round_gain = {p: 0 for p in decisions}

        # compute pair-wise rewards
        message = f"### Round {gs['round']} - Results:"
        for i, j in itertools.combinations(range(self.state.num_players), 2):
            pi, pj = self._pair_payoff(decisions[i][j], decisions[j][i])
            round_gain[i] += pi
            round_gain[j] += pj
            message += f"\n\t Player {i} vs Player {j} chose to {decisions[i][j]} and {decisions[j][i]} respectively (Player {i} gained {pi}, Player {j} gained {pj})"
        message += f"\n-> Current scores: "
        for p, inc in round_gain.items(): gs["scores"][p] += inc # accumulate scores
        message += "; ".join([f"Player {p} ({gs['scores'][p]})" for p in range(self.state.num_players)])
        self.broadcast(message+"\n", ta.ObservationType.GAME_MESSAGE)

    def _end_game(self) -> ta.Outcome:
        scores = self.game_state["scores"]
        ranked = sorted(scores, key=lambda p: (scores[p], -p))  # deterministic
        groups: list[list[int]] = []
        for pid in ranked:
            if not groups or scores[pid] != scores[groups[-1][0]]:  groups.append([pid])
            else:                                                   groups[-1].append(pid)
        G = len(groups)
        reward_dict: Dict[int, float] = {}
        if G == 1: reward_dict = {pid: 0.0 for pid in groups[0]} # complete draw
        else:
            for g_idx, grp in enumerate(groups):   # worst idx 0 … best idx G-1
                r = -1.0 + 2.0 * g_idx / (G - 1)   # evenly spaced in [-1, +1]
                for pid in grp: reward_dict[pid] = r
        return self.outcome(reward_dict, reason="Final scores: " + ", ".join(f"P{p}={scores[p]}" for p in sorted(scores)) + f".  Ranking groups (worst→best): {groups}")

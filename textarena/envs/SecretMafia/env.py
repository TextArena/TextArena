from enum import Enum
import re, random
from typing import Any, Dict, Optional, List, Union
import textarena as ta

class Phase(Enum):
    NIGHT_MAFIA = "Night-Mafia"
    NIGHT_DOCTOR = "Night-Doctor"
    NIGHT_DETECTIVE = "Night-Detective"
    DAY_DISCUSSION = "Day-Discussion"
    DAY_VOTING = "Day-Voting"

class Role:
    name: str = "Role"
    team: str = "Unknown"
    description: str = ""
    def get_prompt(self, player_id: int, player_roles: Dict[int, str], num_players: int, num_discussion_rounds: int) -> str: raise NotImplementedError

    @staticmethod
    def rules(num_discussion_rounds: int) -> str:
        return (
            "\nHow a game flows:\n"
            "- Night: the Mafia secretly vote on a non-Mafia victim; then the Doctor protects one other player "
            "and the Detective investigates one other player.\n"
            "- Day: the night's result is announced (who was killed, if anyone; roles are never revealed), followed by "
            f"{num_discussion_rounds} round{'' if num_discussion_rounds == 1 else 's'} of public discussion in which every living player speaks in turn. "
            "Then every living player votes publicly by replying with a player number; the player with the most "
            "votes is eliminated, and ties are broken at random.\n"
            "- The Village wins once every Mafia member is eliminated; the Mafia win as soon as they make up at least "
            "half of the living players.\n"
        )

class Villager(Role):
    name = "Villager"
    team = "Village"
    description = "A regular villager. Your goal is to identify and eliminate all Mafia members through voting during the day."
    def get_prompt(self, player_id, player_roles, num_players, num_discussion_rounds):
        return (
            f"Welcome to Secret Mafia! You are Player {player_id}.\n"
            f"Your role: {self.name}\nTeam: {self.team}\nDescription: {self.description}\n\n"
            f"Players: {', '.join([f'Player {i}' for i in range(num_players)])}\n\n"
            f"During DAY phase: Speak freely and vote. Everything you say during discussions is broadcast to all players.\n"
            f"During NIGHT phase: you have no special actions.\n"
            f"Win by identifying and eliminating all Mafia members.\n"
        ) + self.rules(num_discussion_rounds)

class Mafia(Role):
    name = "Mafia"
    team = "Mafia"
    description = "A Mafia member. Eliminate villagers and gain majority."
    def get_prompt(self, player_id, player_roles, num_players, num_discussion_rounds):
        teammates = [f"Player {pid}" for pid, r in player_roles.items() if r == "Mafia" and pid != player_id]
        team_line = f"Your fellow Mafia: {', '.join(teammates)}." if teammates else "You are the only Mafia member."
        return (
            f"Welcome to Secret Mafia! You are Player {player_id}.\n"
            f"Your role: {self.name}\nTeam: {self.team}\nDescription: {self.description}\n\n"
            f"Players: {', '.join([f'Player {i}' for i in range(num_players)])}\n\n"
            f"{team_line}\n\n"
            f"During DAY phase: Speak freely and vote.\n"
            f"During NIGHT phase: reply with the player number, e.g. 'Player X' or just 'X', to vote and eliminate a villager. "
            f"Only your fellow Mafia see these votes; the most-voted target is attacked.\n"
            f"Win by eliminating villagers until Mafia equal or outnumber them.\n"
        ) + self.rules(num_discussion_rounds)

class Doctor(Role):
    name = "Doctor"
    team = "Village"
    description = "Protect one player each night from Mafia elimination."
    def get_prompt(self, player_id, player_roles, num_players, num_discussion_rounds):
        return (
            f"Welcome to Secret Mafia! You are Player {player_id}.\n"
            f"Your role: {self.name}\nTeam: {self.team}\nDescription: {self.description}\n\n"
            f"Players: {', '.join([f'Player {i}' for i in range(num_players)])}\n\n"
            f"During DAY phase: Speak freely and vote.\n"
            f"During NIGHT phase: reply with the player number, e.g. 'Player X' or just 'X', to protect a player. "
            f"You cannot protect yourself.\n"
            f"Win by identifying and eliminating all Mafia members.\n"
        ) + self.rules(num_discussion_rounds)

class Detective(Role):
    name = "Detective"
    team = "Village"
    description = "Investigate players to find Mafia members."
    def get_prompt(self, player_id, player_roles, num_players, num_discussion_rounds):
        return (
            f"Welcome to Secret Mafia! You are Player {player_id}.\n"
            f"Your role: {self.name}\nTeam: {self.team}\nDescription: {self.description}\n\n"
            f"Players: {', '.join([f'Player {i}' for i in range(num_players)])}\n\n"
            f"During DAY phase: Speak freely and vote.\n"
            f"During NIGHT phase: reply with the player number, e.g. 'Player X' or just 'X', to investigate. "
            f"You cannot investigate yourself.\n"
            f"You'll learn immediately if the target is Mafia.\n"
            f"Win by identifying and eliminating all Mafia members.\n"
        ) + self.rules(num_discussion_rounds)

class VoteHandler:
    @staticmethod
    def parse(text: str) -> Optional[int]:
        m = SecretMafiaEnv.voting_pattern.fullmatch(text.strip())
        if not m:
            return None
        try:
            return int(m.group(1))
        except ValueError:
            return None
    @staticmethod
    def tally(votes: Dict[int, int], rng: random.Random) -> Optional[int]:
        if not votes: return None
        # Count votes per target
        counts: Dict[int, int] = {}
        for target in votes.values():
            counts[target] = counts.get(target, 0) + 1
        top_score = max(counts.values()) # Highest vote count
        top_players = [pid for pid, c in counts.items() if c == top_score] # All players who received the top score (could be 1 or many)
        return rng.choice(top_players) # Randomly resolve ties

class SecretMafiaEnv(ta.GameEnv):
    min_players = 6
    max_players = 15

    voting_pattern = re.compile(r"(?:player\s*)?([0-9]{1,2})", re.IGNORECASE)  # fullmatch on stripped text
    _ROLE_FACTORY = {
        "Villager":  Villager,
        "Mafia":     Mafia,
        "Doctor":    Doctor,
        "Detective": Detective,
    }
    mafia_ratio = ta.Param(
        0.25, "The share of players who are Mafia, rounded to the nearest whole number (at least 1). It must leave "
              "room for the Doctor and Detective and keep the Mafia in the minority, otherwise `reset` raises an error.",
        check=lambda ratio: 0 < ratio < 1, rule="a number greater than 0 and less than 1",
    )
    discussion_rounds = ta.Param(3, "The discussion rounds before each day vote.", min=1)

    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players
        self._assign_roles(num_players)
        for pid, role_name in self.player_roles.items():
            self.set_role(pid, role_name)  # secret roles, carried in game_info for RL training
        return {
            "phase": Phase.NIGHT_MAFIA,
            "day_number": 1,
            "alive_players": list(range(num_players)),
            "player_roles": self.player_roles,
            "num_discussion_rounds": self.discussion_rounds,
            "votes": {},
            "pending_elimination": None,
            "unannounced_eliminations": [],
            "next_player_ids": [],
        }

    @property
    def phase(self) -> Phase:
        return self.game_state["phase"]

    def on_start(self):
        self._send_phase_prompts()
        self.set_current_player(self.game_state["next_player_ids"].pop())

    def _assign_roles(self, num_players: int):
        self.player_roles = {}
        self.roles_by_pid = {}
        num_mafia = max(1, round(num_players * self.mafia_ratio))
        if num_mafia > num_players - 2:
            raise ValueError(
                f"mafia_ratio={self.mafia_ratio} assigns {num_mafia} Mafia but "
                "the game must also contain a Doctor and Detective."
            )
        if num_mafia >= num_players - num_mafia:
            raise ValueError(
                f"mafia_ratio={self.mafia_ratio} assigns {num_mafia} Mafia, "
                "but Mafia must begin in the minority."
            )
        role_pool = ["Mafia"] * num_mafia + ["Doctor", "Detective"]
        role_pool += ["Villager"] * (num_players - len(role_pool))
        self.rng.shuffle(role_pool)

        for pid, r_name in enumerate(role_pool):
            self.player_roles[pid] = r_name
            self.roles_by_pid[pid] = self._ROLE_FACTORY[r_name]()

    def prompt(self, player_id: int) -> str:
        role_obj = self.roles_by_pid[player_id]
        return role_obj.get_prompt(player_id=player_id, player_roles=self.player_roles, num_players=self.state.num_players, num_discussion_rounds=self.discussion_rounds)

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        return None  # who sees an action depends on the phase; echoes are emitted inside apply

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        phase_dispatch = {
            Phase.DAY_DISCUSSION: self._handle_discussion, Phase.DAY_VOTING: self._handle_day_vote, Phase.NIGHT_MAFIA: self._handle_mafia_vote,
            Phase.NIGHT_DOCTOR: self._handle_doctor_action, Phase.NIGHT_DETECTIVE: self._handle_detective_action,
        }
        # Votes are parsed from the same label-free text that is echoed to the other players.
        result = phase_dispatch[self.phase](player_id, self.strip_role_tags(action).strip())
        if isinstance(result, ta.Invalid):
            return result
        return self._advance(self.set_next_player)

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        # Repeated invalid move: the player is killed off and the game moves on. Only the Mafia, Doctor and Detective
        # act at night, so an announcement then would reveal a role; it waits for daybreak unless the game is over.
        at_night = self.phase in (Phase.NIGHT_MAFIA, Phase.NIGHT_DOCTOR, Phase.NIGHT_DETECTIVE)
        outcome = self._eliminate_player(player_id, "was eliminated for repeated invalid moves", announce=not at_night)
        if outcome is not None:
            self._announce_night_eliminations()
            return outcome
        if at_night and self.player_roles[player_id] == "Mafia":
            for mafia in self.game_state["alive_players"]:
                if self.player_roles[mafia] == "Mafia":
                    self.message(mafia, f"Your fellow Mafia member Player {player_id} was eliminated for repeated invalid moves. The other players learn this at daybreak.", ta.ObservationType.GAME_MESSAGE)
        def assign(pid: int):
            self.set_next_player(pid)
        return self._advance(assign)

    def _advance(self, assign) -> Optional[ta.Outcome]:
        """Rotate to the next queued player, or resolve the phase and start the next one."""
        gs = self.game_state
        if gs["next_player_ids"]:
            assign(gs["next_player_ids"].pop())
            return None

        # Phase complete - evaluate votes / killings, decide next phase, queue players
        outcome = None
        if self.phase == Phase.DAY_VOTING:
            outcome = self._resolve_day_votes()
        elif self.phase == Phase.NIGHT_MAFIA:
            self._store_mafia_target()

        # When night sequence ends (Doctor or Detective -> Day)
        next_phase = self._compute_next_phase()
        if self.phase in (Phase.NIGHT_MAFIA, Phase.NIGHT_DOCTOR, Phase.NIGHT_DETECTIVE):
            if next_phase == Phase.DAY_DISCUSSION:
                outcome = self._resolve_night_outcome()

        # Check if game has concluded
        if outcome is not None:
            return outcome

        # Advance to next phase
        if self.phase == Phase.DAY_VOTING:
            gs["day_number"] += 1
        gs["phase"] = next_phase
        self._send_phase_prompts()
        assign(gs["next_player_ids"].pop())
        return None

    def _compute_next_phase(self) -> Phase:
        doctor_alive     = any(self.player_roles[p] == "Doctor"    for p in self.game_state["alive_players"])
        detective_alive  = any(self.player_roles[p] == "Detective" for p in self.game_state["alive_players"])
        match self.phase:
            case Phase.NIGHT_MAFIA:     return Phase.NIGHT_DOCTOR if doctor_alive else (Phase.NIGHT_DETECTIVE if detective_alive else Phase.DAY_DISCUSSION)
            case Phase.NIGHT_DOCTOR:    return Phase.NIGHT_DETECTIVE if detective_alive else Phase.DAY_DISCUSSION
            case Phase.NIGHT_DETECTIVE: return Phase.DAY_DISCUSSION
            case Phase.DAY_DISCUSSION:  return Phase.DAY_VOTING
            case Phase.DAY_VOTING:      return Phase.NIGHT_MAFIA
            case _:                     raise RuntimeError("Unknown phase")

    def _send_phase_prompts(self):
        gs = self.game_state
        alive = gs["alive_players"]
        next_player_ids: List[int] = []

        if self.phase == Phase.NIGHT_MAFIA:
            mafia = [p for p in alive if self.player_roles[p] == "Mafia"]
            targets = [p for p in alive if p not in mafia]
            for p in mafia:
                self.message(p, f"Night has fallen. Mafia, agree on a victim by replying with their player number.\nValid targets: {', '.join(str(t) for t in targets)}", ta.ObservationType.GAME_MESSAGE)
            next_player_ids = self.rng.sample(mafia, k=len(mafia))

        elif self.phase == Phase.NIGHT_DOCTOR:
            doc = next(p for p in alive if self.player_roles[p] == "Doctor")
            opts = ", ".join(str(t) for t in self._publicly_alive() if t != doc)
            self.message(doc, f"Night phase - reply with the player number of the player to protect: {opts}", ta.ObservationType.GAME_MESSAGE)
            next_player_ids = [doc]

        elif self.phase == Phase.NIGHT_DETECTIVE:
            det = next(p for p in alive if self.player_roles[p] == "Detective")
            opts = ", ".join(str(t) for t in self._publicly_alive() if t != det)
            self.message(det, f"Night phase - reply with the player number of the player to investigate: {opts}", ta.ObservationType.GAME_MESSAGE)
            next_player_ids = [det]

        elif self.phase == Phase.DAY_DISCUSSION:
            rounds = self.discussion_rounds
            self.broadcast(f"Day breaks. Discuss for {rounds} round{'' if rounds == 1 else 's'}, then a vote will follow.", ta.ObservationType.GAME_MESSAGE)
            players = self.rng.sample(alive, k=len(alive))
            next_player_ids = players * rounds

        elif self.phase == Phase.DAY_VOTING:
            opts = ", ".join(str(p) for p in alive)
            self.broadcast(f"Voting phase - submit one vote by replying with the player number, e.g. '3'. Valid: {opts}", ta.ObservationType.GAME_MESSAGE)
            next_player_ids = self.rng.sample(alive, k=len(alive))

        gs["next_player_ids"] = next_player_ids

    def _echo_action(self, from_pid: int, action: str, to_id: int = -1):
        """Echo a player action that apply() has already stripped of sender labels."""
        self.state.add_event(from_pid, action, ta.ObservationType.PLAYER_ACTION, to_id=to_id)

    def _handle_discussion(self, pid: int, action: str) -> None:
        self._echo_action(pid, action)  # discussions are public
        return None

    def _handle_day_vote(self, pid: int, action: str):
        return self._record_vote(pid, action, broadcast_to_all=True)

    def _handle_mafia_vote(self, pid: int, action: str):
        valid_targets = [
            target
            for target in self.game_state["alive_players"]
            if self.player_roles[target] != "Mafia"
        ]
        return self._record_vote(
            pid,
            action,
            broadcast_to_mafia_only=True,
            valid_targets=valid_targets,
        )

    def _handle_doctor_action(self, pid: int, action: str) -> Optional[ta.Invalid]:
        target = VoteHandler.parse(action)
        if target is None or target == pid or target not in self._publicly_alive():
            return self.invalid(self._target_hint("Invalid protection target", [p for p in self._publicly_alive() if p != pid]))

        # save target
        if target == self.game_state["pending_elimination"]:
            self.game_state["pending_elimination"] = None
        self._echo_action(pid, action, to_id=pid)  # only the doctor sees their own action
        return None

    def _handle_detective_action(self, pid: int, action: str) -> Optional[ta.Invalid]:
        target = VoteHandler.parse(action)
        if target is None or target == pid or target not in self._publicly_alive():
            return self.invalid(self._target_hint("Invalid investigation target", [p for p in self._publicly_alive() if p != pid]))
        is_mafia = self.player_roles[target] == "Mafia"
        result = f"Player {target} IS{' ' if is_mafia else ' NOT '}a Mafia member."
        self.message(pid, result, ta.ObservationType.GAME_MESSAGE)  # investigation result stays private
        return None

    def _record_vote(
        self,
        pid: int,
        action: str,
        *,
        broadcast_to_all: bool = False,
        broadcast_to_mafia_only: bool = False,
        valid_targets: Optional[List[int]] = None,
    ) -> Optional[ta.Invalid]:
        target = VoteHandler.parse(action)
        valid_targets = self.game_state["alive_players"] if valid_targets is None else valid_targets
        if target is None or target not in valid_targets:
            return self.invalid(self._target_hint("Vote not in valid format or invalid target", valid_targets))

        self.game_state["votes"][pid] = target

        if broadcast_to_all:
            self._echo_action(pid, action)
        elif broadcast_to_mafia_only:
            mafia = [p for p in self.game_state["alive_players"] if self.player_roles[p] == "Mafia"]
            for m in mafia:
                self._echo_action(pid, action, to_id=m)  # night votes are visible to the mafia only
        return None

    @staticmethod
    def _target_hint(problem: str, targets: List[int]) -> str:
        example = targets[0] if targets else 0
        return f"{problem}. Reply with just a player number, e.g. '{example}'. Valid: {', '.join(map(str, targets))}."

    def _resolve_day_votes(self) -> Optional[ta.Outcome]:
        target = VoteHandler.tally(self.game_state["votes"], rng=self.rng)
        self.game_state["votes"].clear()
        if target is None:
            self.broadcast("No consensus - nobody was eliminated.", ta.ObservationType.GAME_MESSAGE)
            return None
        return self._eliminate_player(target, "was eliminated by vote")

    def _store_mafia_target(self):
        self.game_state["pending_elimination"] = VoteHandler.tally(self.game_state["votes"], rng=self.rng)
        self.game_state["votes"].clear()

    def _resolve_night_outcome(self) -> Optional[ta.Outcome]:
        tgt = self.game_state["pending_elimination"]
        self.game_state["pending_elimination"] = None
        outcome = None
        if tgt is None:
            self.broadcast("No one was killed tonight.", ta.ObservationType.GAME_MESSAGE)
        else:
            outcome = self._eliminate_player(tgt, "was killed during the night")
        self._announce_night_eliminations()
        return outcome

    def _publicly_alive(self) -> List[int]:
        """Living players plus anyone eliminated tonight, whose elimination stays secret until daybreak."""
        return sorted(self.game_state["alive_players"] + self.game_state["unannounced_eliminations"])

    def _announce_night_eliminations(self):
        for pid in self.game_state["unannounced_eliminations"]:
            self.broadcast(f"Player {pid} was eliminated for repeated invalid moves.", ta.ObservationType.GAME_MESSAGE)
        self.game_state["unannounced_eliminations"] = []

    def _eliminate_player(self, pid: int, reason: str, announce: bool = True) -> Optional[ta.Outcome]:
        if pid in self.game_state["alive_players"]:
            self.game_state["alive_players"].remove(pid)
        self.eliminate(pid)
        self.game_state["next_player_ids"] = [
            queued_pid for queued_pid in self.game_state["next_player_ids"] if queued_pid != pid
        ]
        self.game_state["votes"].pop(pid, None)
        self.game_state["votes"] = {
            voter: target
            for voter, target in self.game_state["votes"].items()
            if target != pid
        }
        if self.game_state["pending_elimination"] == pid:
            self.game_state["pending_elimination"] = None
        if announce:
            self.broadcast(f"Player {pid} {reason}.", ta.ObservationType.GAME_MESSAGE)
        else:
            self.game_state["unannounced_eliminations"].append(pid)
        return self._check_win()

    def _check_win(self) -> Optional[ta.Outcome]:
        alive = self.game_state["alive_players"]
        mafia_alive = [p for p in alive if self.player_roles[p] == "Mafia"]

        if not mafia_alive:
            villagers = [p for p in range(self.state.num_players) if self.player_roles[p] != "Mafia"]
            return self.winner(villagers, reason="All Mafia were eliminated. Village wins!")
        elif len(mafia_alive) >= len(alive) / 2:
            mafia = [p for p in range(self.state.num_players) if self.player_roles[p] == "Mafia"]
            return self.winner(mafia, reason="Mafia reached parity with villagers. Mafia wins!")
        return None

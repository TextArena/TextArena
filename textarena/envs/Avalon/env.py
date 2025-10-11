import ast
from enum import Enum
import re, random
from typing import Set, Tuple, Dict, Optional, List, Type, TypeVar
import textarena as ta

MISSION_WIN_THRESHOLD = 3
CONSECUTIVE_PROPOSAL_FAIL_THRESHOLD = 5
MIN_PLAYERS = 5
MAX_PLAYERS = 10
DEFAULT_VOTE = "approve"
DEFAULT_MISSION_ACTION = "success"

AVALON_RULES = """
You are playing Avalon: The Resistance, a hidden role deduction game.  

Players are divided into two sides:
- Good: The Loyal Servants of Arthur
- Evil: The Minions of Mordred

Only Evil players are told who each other are.
Good players are not told the sides of other players.

Gameplay Rules
1. Team Proposal
Each round, a Leader proposes a mission team of a certain size.  

2. Voting
Everyone votes to approve or reject the team.
A majority is required for the proposal to be accepted. 
If the team is rejected, leadership passes to the next player, who proposes their own team.
If five teams in a row are rejected, Evil automatically wins.

3. Mission Phase
If a team is approved, members of the team secretly decide whether the mission passes or fails.  
  - Good players must choose “Success”  
  - Evil players can choose either “Success” or “Fail”  
The actions are shuffled then revealed, players do not know which actions other players chose.
If all are Success, the mission passes.
If there is at least one Fail, the mission fails.
Certain missions may require two Fails to fail, depending on the number of players in the game. You will be told when missions require two Fails to fail.

Roles
Players will be given one of the following roles:

- Merlin (Good): Merlin secretly knows who all the Evil players are. The catch: if Good completes 3 missions, Evil gets one last chance to win by guessing who Merlin is. If they guess right, Evil wins instead. Merlin's job is to guide Good without being too obvious.
- Servant (Good): A regular Good player. They don't have any extra information.
- Minion (Evil): A regular Evil player. They know who the other Evil players are. Their job is to trick Good into trusting them, sneak onto missions, and secretly Fail them.

Win conditions:
- Good wins if they succeed in 3 out of 5 missions AND Merlin is not correctly guessed by Evil.
- Evil wins if they fail 3 out of 5 missions OR if they correctly identify Merlin at the end.
"""

SERVANT_NAME = "Servant"
MERLIN_NAME = "Merlin"
PERCIVAL_NAME = "Percival"
MINION_NAME = "Minion"
MORGANA_NAME = "Morgana"
MORDRED_NAME = "Mordred"
OBERON_NAME = "Oberon"

EVIL_NAMES = {MINION_NAME, MORGANA_NAME, MORDRED_NAME, OBERON_NAME}

class Phase(Enum):
    DISCUSSION = "Discussion"
    TEAM_PROPOSAL = "Team-Proposal"
    VOTING = "Voting"
    MISSION = "Mission"
    GUESS_MERLIN = "Guess-Merlin"

class Role:
    name: str = "Role"
    team: str = "Unknown"
    description: str = ""
    def get_prompt(self, player_id: int, player_roles: Dict[int, str], num_players: int, num_discussion_rounds: int) -> str:
        return self.base_prompt(player_id, player_roles, num_players)

    def base_prompt(self, player_id: int, player_roles: Dict[int, str], num_players: int) -> str:
        """Common header text used by all role prompts."""
        return (
            f"{AVALON_RULES}\n"
            f"---\n"
            f"There are {num_players} players in this game: {', '.join([f'Player {i}' for i in range(num_players)])}\n\n"
            f"You are Player {player_id}.\n"
            f"Role: {self.name}\nTeam: {self.team}\nDescription: {self.description}\n"
            f"{self.team_prompt(player_roles)}\n"
        )
    
    def team_prompt(self, player_roles: Dict[int, str]) -> str:
        """Return the team's win condition message"""
        has_merlin = "Merlin" in player_roles.values()

        if self.team == "Good":
            return (
                "Win conditions:\n"
                f"You win if your team succeeds in 3 out of 5 missions"
                + (" AND Merlin is not correctly guessed by Evil" if has_merlin else "")
            )
        elif self.team == "Evil":
            return (
                "Win conditions:\n"
                f"You win if your team fails 3 out of 5 missions"
                + (" OR if your team correctly identifies Merlin at the end after Good succeeds 3 out of 5 missions" if has_merlin else "")
            )
        else:
            raise ValueError("Unknown team configuration")
    
    def evil_prompt(self, player_id: int, player_roles: Dict[int, str], num_players: int) -> str:
        return self.base_prompt(player_id, player_roles, num_players) + evil_players_prompt(player_id, player_roles)


class Servant(Role):
    name = SERVANT_NAME
    team = "Good"
    description = "You are a Loyal Servant of Arthur, a regular member of the Good side. You have no special abilities."

class Merlin(Role):
    name = MERLIN_NAME
    team = "Good"
    description = (
        "You are Merlin. You secretly know who all the Evil players are. "
        "Guide Good subtly without revealing yourself; if Evil guesses that you are Merlin at the end, they win."
    )
    def get_prompt(
            self, player_id: int, player_roles: Dict[int, str], num_players: int, num_discussion_rounds: int
        ) -> str:
            evil_players = get_evil_players(player_id, player_roles, include_oberon=False)
            has_mordred = MORDRED_NAME in player_roles.values()
            return (
                self.base_prompt(player_id, player_roles, num_players) +
                f"\nYou secretly know the Evil players: {', '.join(evil_players)}.\n"
                f"except you do not know who Mordred is" if has_mordred else ""
            )


class Percival(Role):
    name = PERCIVAL_NAME
    team = "Good"
    description = "You are Percival. You know who Merlin is, but Morgana may appear as Merlin to you alongside the real Merlin if they are in the game."

    def get_prompt(
        self, player_id: int, player_roles: Dict[int, str], num_players: int, num_discussion_rounds: int
    ) -> str:
        possible_merlins = [
            f"Player {pid}" for pid, role in player_roles.items() if role in {MERLIN_NAME, MORGANA_NAME}
        ]
        merlin_info = (
            f"One of these players is Merlin: {', '.join(possible_merlins)}.\n"
            "Morgana also appears as Merlin, so be cautious." if len(possible_merlins) > 1 else
            f"{possible_merlins[0]} is Merlin." if possible_merlins else "Merlin is not in this game."
        )
        return self.base_prompt(player_id, player_roles, num_players) + "\n" + merlin_info + "\n"


class Minion(Role):
    name = MINION_NAME
    team = "Evil"
    description = "You are a Minion of Mordred, a regular member of the Evil side. You have no special abilities."

    def get_prompt(
        self, player_id: int, player_roles: Dict[int, str], num_players: int, num_discussion_rounds: int
    ) -> str:
        return self.evil_prompt(player_id, player_roles, num_players)


class Morgana(Role):
    name = MORGANA_NAME
    team = "Evil"
    description = "You are Morgana. You appear as Merlin to Percival and work to deceive the Good."

    def get_prompt(
        self, player_id: int, player_roles: Dict[int, str], num_players: int, num_discussion_rounds: int
    ) -> str:
        return self.evil_prompt(player_id, player_roles, num_players) + (
            "You appear as Merlin to Percival\n"
        )


class Mordred(Role):
    name = MORDRED_NAME
    team = "Evil"
    description = "You are Mordred. Merlin cannot see you, making you hidden from Good."

    def get_prompt(
        self, player_id: int, player_roles: Dict[int, str], num_players: int, num_discussion_rounds: int
    ) -> str:
        return self.base_prompt(player_id, player_roles, num_players) + evil_players_prompt(player_id, player_roles)


class Oberon(Role):
    name = OBERON_NAME
    team = "Evil"
    description = "You are Oberon. You are Evil but unknown to your teammates."

    def get_prompt(
        self, player_id: int, player_roles: Dict[int, str], num_players: int, num_discussion_rounds: int
    ) -> str:
        return self.base_prompt(player_id, player_roles, num_players) + (
            "\nYou do not know who the other Evil players are, and they do not know you.\n"
        )

def get_evil_pids(player_id: int, player_roles: Dict[int, str], include_oberon: bool = False) -> list[int]:
    evil_pids = [pid for pid, role in player_roles.items() if role in EVIL_NAMES and (include_oberon or role != OBERON_NAME) and pid != player_id]
    return evil_pids

def get_evil_players(player_id: int, player_roles: Dict[int, str], include_oberon: bool = False) -> list[str]:
    evil_pids = get_evil_pids(player_id, player_roles, include_oberon=include_oberon)
    evil_players = [f"Player {pid}" for pid in evil_pids]
    return evil_players

def evil_players_prompt(player_id: int, player_roles: Dict[int, str]) -> str:
    has_oberon = OBERON_NAME in player_roles.values()
    evil_players = get_evil_players(player_id, player_roles, include_oberon=False)
    return f"The Evil players are: {', '.join(evil_players)}." + "Oberon is hidden from you.\n" if has_oberon else ""

class Villager(Role):
    name = "Villager"
    team = "Village"
    description = "A regular villager. Your goal is to identify and eliminate all Mafia members through voting during the day."
    def get_prompt(self, player_id, player_roles, num_players, num_discussion_rounds):
        return (
            f"Welcome to Secret Mafia! You are Player {player_id}.\n"
            f"Your role: {self.name}\nTeam: {self.team}\nDescription: {self.description}\n\n"
            f"Players: {', '.join([f'Player {i}' for i in range(num_players)])}\n\n"
            f"The game progresses through Day and Night phases.\n"
            f"- During the Day phase, there are {num_discussion_rounds} rounds of discussion followed by voting.\n"
            f"- During discussions, everything you say is automatically broadcasted to all players.\n"
            f"- After discussions, all players must vote to eliminate one player.\n"
            f"- During the Night phase, you have no special actions.\n\n"
            f"The game ends when either all Mafia members are eliminated (Village wins) or\n"
            f"Mafia members equal or outnumber Villagers (Mafia wins).\n"
        )

class Mafia(Role):
    name = "Mafia"
    team = "Mafia"
    description = "A Mafia member. Eliminate villagers and gain majority."
    def get_prompt(self, player_id, player_roles, num_players, num_discussion_rounds):
        teammates = [f"Player {pid}" for pid, r in player_roles.items() if r == "Mafia"]
        return (
            f"Welcome to Secret Mafia! You are Player {player_id}.\n"
            f"Your role: {self.name}\nTeam: {self.team}\nDescription: {self.description}\n\n"
            f"Players: {', '.join([f'Player {i}' for i in range(num_players)])}\n\n"
            f"Your teammates are: {', '.join(teammates)}.\n\n"
            f"During DAY phase: Speak freely and vote.\n"
            f"During NIGHT phase: '[Player X]' to vote and eliminate a villager.\n"
            f"Win by eliminating villagers until Mafia equal or outnumber them.\n"
        )

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
            f"During NIGHT phase: '[Player X]' to protect a player.\n"
            f"Win by identifying and eliminating all Mafia members.\n"
        )

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
            f"During NIGHT phase: '[Player X]' to investigate.\n"
            f"You'll learn immediately if the target is Mafia.\n"
            f"Win by identifying and eliminating all Mafia members.\n"
        )

T = TypeVar("T")

def parse_typed_list(list_str: str, typ: Type[T]) -> Optional[List[T]]:
    """
    Parses a Python-style list string (e.g. "[1, 2, 3]") into a typed Python list.
    Returns None if parsing or type conversion fails.
    """
    try:
        value = ast.literal_eval(list_str)
        if isinstance(value, list):
            return [typ(x) for x in value]
    except Exception:
        return None

class AvalonParser:
    # https://regex101.com/r/DD2CJI/1
    team_proposal_pattern = re.compile(r"<team>\s*(.+?)\s*</team>", re.IGNORECASE)

    # https://regex101.com/r/eWYQa5/1
    vote_pattern = re.compile(r"<vote>\s*(approve|reject)\s*</vote>", re.IGNORECASE)

    # https://regex101.com/r/rA2EEB/1
    action_pattern = re.compile(r"<action>\s*(success|fail)\s*</action>", re.IGNORECASE)

    # https://regex101.com/r/stpyKo/1
    merlin_guess_pattern = re.compile(r"<merlin_guess>\s*(\d+)\s*</merlin_guess>", re.IGNORECASE)

    @staticmethod
    def parse_team_proposal(text: str) -> Optional[List[int]]:
        """
        Parses a team proposal from text.
        Returns the team proposal, or None if not found.
        """
        m = AvalonParser.team_proposal_pattern.search(text)
        list_str = m.group(1)
        team_proposal = parse_typed_list(list_str, typ=int)
        return team_proposal

    @staticmethod
    def parse_team_vote(text: str) -> Optional[str]:
        """
        Parses a team proposal vote from text.
        Returns 'approve' or 'reject', or None if not found.
        """
        m = AvalonParser.vote_pattern.search(text)
        return m.group(1).lower() if m else None

    @staticmethod
    def parse_mission_action(text: str) -> Optional[str]:
        """
        Parses a mission action from text.
        Returns 'success' or 'fail', or None if not found.
        """
        m = AvalonParser.action_pattern.search(text)
        return m.group(1).lower() if m else None
    
    @staticmethod
    def parse_merlin_guess(text: str) -> Optional[int]:
        """
        Parses the pid of a merlin guess from text.
        Returns pid of the merlin guess, or None if not found.
        """
        m = AvalonParser.action_pattern.search(text)
        return int(m.group(1)) if m else None

def is_mission_success(mission_actions: Dict[int, str]) -> bool:
    success = all(action == "success" for action in mission_actions.values())
    return success

def is_team_proposal_passed(votes: Dict[int, str]) -> bool:
    approve_count = sum(1 for v in votes.values() if v == "approve")
    reject_count = len(votes) - approve_count

    success = approve_count > reject_count
    return success

class VoteHandler:
    @staticmethod
    def parse(text: str) -> Optional[int]:
        m = AvalonEnv.voting_pattern.search(text)
        return int(m.group(1)) if m else None
    @staticmethod
    def tally(votes: Dict[int, int]) -> Optional[int]:
        if not votes: return None
        # Count votes per target
        counts: Dict[int, int] = {}
        for target in votes.values():
            counts[target] = counts.get(target, 0) + 1
        top_score = max(counts.values()) # Highest vote count
        top_players = [pid for pid, c in counts.items() if c == top_score] # All players who received the top score (could be 1 or many)
        return random.choice(top_players) # Randomly resolve ties

class AvalonEnv(ta.Env):
    voting_pattern = re.compile(r".*\[(?:player\s*)?(\d+)\].*", re.IGNORECASE)
    _ROLE_FACTORY = {
        SERVANT_NAME:  Servant,
        MERLIN_NAME:   Merlin,
        PERCIVAL_NAME: Percival,
        MINION_NAME:   Minion,
        MORGANA_NAME:  Morgana,
        MORDRED_NAME:  Mordred,
        OBERON_NAME:   Oberon,
    }
    def __init__(self, mafia_ratio: float = 0.25, discussion_rounds: int = 3):
        """
        Args:
            mafia_ratio (float): Ratio of Mafia members to total players (default: 0.25)
            discussion_rounds (int): The number of discussion rounds
        """
        self.mafia_ratio = mafia_ratio
        self.discussion_rounds = discussion_rounds

    def reset(self, num_players: int, special_roles: Optional[Set[str]] = None, seed: Optional[int] = None):
        assert MIN_PLAYERS <= num_players <= MAX_PLAYERS, f"Player count must be between {MIN_PLAYERS} and {MAX_PLAYERS}."
        self.state = ta.TeamMultiPlayerState(num_players=num_players, seed=seed)
        self._assign_roles(num_players, special_roles=special_roles)
        self.phase: Phase = Phase.DISCUSSION
        game_state = {
            "phase": self.phase,
            "mission_index": 0,
            "day_number": 1,
            "alive_players": list(range(num_players)),
            "player_roles": self.player_roles,
            "num_discussion_rounds": self.discussion_rounds,
            "consecutive_failed_team_proposals": 0,
            "votes": {},
            "mission_actions": {},
            "mission_successes": 0,
            "mission_failures": 0,
            "guess_merlin": False,
            "pending_elimination": None,
        }
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt, secret_roles=self.player_roles)
        self._send_phase_prompts() # populate self.next_player_ids
        self.state.manually_set_current_player_id(self.next_player_ids.pop())
    

    def _assign_roles(self, num_players: int, special_roles: Optional[Set[str]] = None):
        self.player_roles = {}
        self.roles = {}                              # <- NEW

        role_pool = generate_roles(num_players, special_roles=special_roles)
        for pid, r_name in enumerate(role_pool):
            self.player_roles[pid] = r_name
            self.roles[pid] = self._ROLE_FACTORY[r_name]()

    def _prompt(self, player_id: int, game_state: dict) -> str:
        role_obj: Role = self.roles[player_id]
        return role_obj.get_prompt(player_id = player_id, player_roles = self.player_roles, num_players = self.state.num_players, num_discussion_rounds = self.discussion_rounds)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        pid = self.state.current_player_id
        phase_dispatch = {
            Phase.DISCUSSION: self._handle_discussion,
            Phase.TEAM_PROPOSAL: self._handle_team_proposal,
            Phase.VOTING: self._handle_vote, 
            Phase.MISSION: self._handle_mission,
        }
        phase_dispatch[self.phase](pid, action)
        self._after_player_action() # rotate / advance phase
        return self.state.step(rotate_player=False)

    def _after_player_action(self):
        if self.state.made_invalid_move: return
        # If players still queued, just rotate.
        if self.next_player_ids:
            self.state.manually_set_current_player_id(self.next_player_ids.pop())
            return

        # Phase complete ─ evaluate votes / killings, decide next phase, queue players
        match self.phase:
            case Phase.VOTING:
                self._resolve_votes()
            case Phase.MISSION:
                self._resolve_mission_outcome()

        # Check if game has concluded
        if self.state.done: return

        # Advance to next phase
        self.phase = self._compute_next_phase()
        self.state.game_state["phase"] = self.phase
        self._send_phase_prompts()
        self.state.manually_set_current_player_id(self.next_player_ids.pop())
    
    def _vote_passed(self) -> bool:
        return is_team_proposal_passed(self.state.game_state["votes"])

    def _compute_next_phase(self) -> Phase:
        match self.phase:
            case Phase.DISCUSSION:
                return Phase.TEAM_PROPOSAL
            case Phase.TEAM_PROPOSAL:
                return Phase.VOTING
            case Phase.VOTING:
                return Phase.MISSION if self._vote_passed() else Phase.DISCUSSION
            case Phase.MISSION:
                # Check if Good won and evil needs to guess Merlin
                if self.state.game_state["guess_merlin"]:
                    return Phase.GUESS_MERLIN
                return Phase.DISCUSSION
            case _:
                raise RuntimeError("Unknown phase")
                

    def _send_phase_prompts(self):
        gs = self.state.game_state
        alive = gs["alive_players"]
        self.next_player_ids: List[int] = []

        if self.phase == Phase.NIGHT_MAFIA:
            mafia = [p for p in alive if self.player_roles[p] == "Mafia"]
            targets = [p for p in alive if p not in mafia]
            for p in mafia:
                self.state.add_observation(to_id=p, message=f"Night has fallen. Mafia, agree on a victim.\nValid targets: {', '.join(f'[{t}]' for t in targets)}", observation_type=ta.ObservationType.GAME_MESSAGE)
            self.next_player_ids = random.sample(mafia, k=len(mafia))

        elif self.phase == Phase.NIGHT_DOCTOR:
            doc = next(p for p in alive if self.player_roles[p] == "Doctor")
            opts = ", ".join(f"[{t}]" for t in alive if t != doc)
            self.state.add_observation(to_id=doc, message=f"Night phase - choose one player to protect: {opts}", observation_type=ta.ObservationType.GAME_MESSAGE)
            self.next_player_ids = [doc]

        elif self.phase == Phase.NIGHT_DETECTIVE:
            det = next(p for p in alive if self.player_roles[p] == "Detective")
            opts = ", ".join(f"[{t}]" for t in alive if t != det)
            self.state.add_observation(to_id=det, message=f"Night phase - choose one player to investigate: {opts}", observation_type=ta.ObservationType.GAME_MESSAGE)
            self.next_player_ids = [det]

        elif self.phase == Phase.DAY_DISCUSSION:
            rounds = self.discussion_rounds
            self.state.add_observation(to_id=-1, message=f"Day breaks. Discuss for {rounds} rounds, then a vote will follow.", observation_type=ta.ObservationType.GAME_MESSAGE)
            players = random.sample(alive, k=len(alive))
            self.next_player_ids = players * rounds

        elif self.phase == Phase.DAY_VOTING:
            opts = ", ".join(f"[{p}]" for p in alive)
            self.state.add_observation(to_id=-1, message=f"Voting phase - submit one vote in format [X]. Valid: {opts}", observation_type=ta.ObservationType.GAME_MESSAGE)
            self.next_player_ids = random.sample(alive, k=len(alive))

    def _handle_discussion(self, pid: int, action: str):
        self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
    
    def _handle_team_proposal(self, pid: int, action: str):
        self._record_team_proposal(pid, action)
    
    def _handle_vote(self, pid: int, action: str):
        self._record_vote(pid, action)
    
    def _handle_mission(self, pid: int, action: str):
        self._record_mission_action(pid, action)

    def _handle_day_vote(self, pid: int, action: str):      self._record_vote(pid, action, broadcast_to_all=True)
    def _handle_mafia_vote(self, pid: int, action: str):    self._record_vote(pid, action, broadcast_to_mafia_only=True)
    def _handle_doctor_action(self, pid: int, action: str):
        target = VoteHandler.parse(action)
        if target is None or target not in self.state.game_state["alive_players"]:
            fatal = self._mark_invalid(pid, "Invalid protection target.")
            if not fatal: 
                return
            else: # player was eliminated by invalid move
                self.state.made_invalid_move = False  # such that we can rotate off the player 
                return

        # save target
        if target == self.state.game_state["pending_elimination"]:
            self.state.game_state["pending_elimination"] = None
        self.state.add_observation(from_id=pid, to_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

    def _handle_detective_action(self, pid: int, action: str):
        target = VoteHandler.parse(action)
        if target is None or target not in self.state.game_state["alive_players"]:
            fatal = self._mark_invalid(pid, "Invalid investigation target.")
            if not fatal: return
            else:# player was eliminated by invalid move
                self.state.made_invalid_move = False  # such that we can rotate off the player 
                return
        is_mafia = self.player_roles[target] == "Mafia"
        result = f"Player {target} IS{' ' if is_mafia else ' NOT '}a Mafia member."
        self.state.add_observation(to_id=pid, message=result, observation_type=ta.ObservationType.GAME_MESSAGE)
    
    def _get_mission_team_size(self) -> int:
        return get_mission_team_size(self.state.num_players, self.state.game_state["mission_index"])
    
    def _is_valid_team_proposal(self, team_proposal: List[int]) -> bool:
        team = set(team_proposal)
        team_size = self._get_mission_team_size()
        return len(team) == team_size and 0 <= min(team) and max(team) < self.state.num_players
    
    def _record_team_proposal(self, pid: int, action: str):
        team_proposal = AvalonParser.parse_team_proposal(action)
        if team_proposal is None or not self._is_valid_team_proposal(team_proposal):
            fatal = self.state.set_invalid_move("Invalid team proposal")
            if not fatal:
                return
            # Too many invalid attempts, use default team
            team_size = self._get_mission_team_size()
            team_proposal = list(range(team_size)) 

        self.state.game_state["team_proposal"][pid] = team_proposal
        self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
    
    def _record_vote(self, pid: int, action: str):
        vote = AvalonParser.parse_team_vote(action)
        if vote is None:
            fatal = self.state.set_invalid_move("Vote not in valid format")
            if not fatal:
                return
            # Too many invalid votes, use default vote
            vote = DEFAULT_VOTE

        self.state.game_state["votes"][pid] = vote
        self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
    
    def _record_mission_action(self, pid: int, action: str):
        action = AvalonParser.parse_mission_action(action)
        if action is None:
            fatal = self.state.set_invalid_move("Mission action not in valid format")
            if not fatal:
                return
            # Too many invalid actions, use default action
            action = DEFAULT_MISSION_ACTION

        self.state.game_state["mission_actions"][pid] = action

    # def _record_vote(self, pid: int, action: str, *, broadcast_to_all=False, broadcast_to_mafia_only=False):
    #     target = VoteHandler.parse(action)
    #     if target is None or target not in self.state.game_state["alive_players"]:
    #         fatal = self._mark_invalid(pid, "Vote not in valid format or invalid target.")
    #         if not fatal: return
    #         else: # player was eliminated by invalid move
    #             self.state.made_invalid_move = False  # such that we can rotate off the player 
    #             return


    #     self.state.game_state["votes"][pid] = target

    #     if broadcast_to_all:
    #         self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
    #     elif broadcast_to_mafia_only:
    #         mafia = [p for p in self.state.game_state["alive_players"] if self.player_roles[p] == "Mafia"]
    #         for m in mafia:
    #             self.state.add_observation(from_id=pid, to_id=m, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

    def _mark_invalid(self, pid: int, reason: str):
        fatal = self.state.set_invalid_move(reason)
        if fatal: self._eliminate_player(self.state.current_player_id, "has been eliminated by making an invalid move.")
        return fatal 
    
        # if self.state.set_invalid_move(reason):
        #     # repeated invalid move by player, kill'em
        #     self._eliminate_player(self.state.current_player_id, "has been eliminated by making an invalid move.")

            # # TODO kill player off
            # others = [p for p in range(self.state.num_players) if p != pid]
            # self.state.set_winners(player_ids=others, reason=f"Player {pid} made an invalid move.")

    def _resolve_votes(self):
        vote_passed = self._vote_passed()
        self.state.game_state["votes"].clear()
        if not vote_passed:
            self.state.game_state["consecutive_failed_team_proposals"] += 1
            self.state.add_observation(message="No consensus - the team proposal was not passed.", observation_type=ta.ObservationType.GAME_MESSAGE)
            return
        self.state.game_state["consecutive_failed_team_proposals"] = 0
    
    def _is_mission_success(self) -> bool:
        return is_mission_success(self.state.game_state["mission_actions"])
    
    def _resolve_mission_outcome(self):
        success = self._is_mission_success()
        self.state.game_state["mission_actions"].clear()
        if success:
            self.state.game_state["mission_successes"] += 1
            message = "Mission Succeeded. All actions were success."
        else:
            self.state.game_state["mission_failures"] += 1
            message = "Mission Failed. At least one action was fail"
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_MESSAGE)
        
    def _store_mafia_target(self):
        self.state.game_state["pending_elimination"] = VoteHandler.tally(self.state.game_state["votes"])
        self.state.game_state["votes"].clear()

    def _resolve_night_outcome(self):
        tgt = self.state.game_state["pending_elimination"]
        self.state.game_state["pending_elimination"] = None
        if tgt is None:
            self.state.add_observation(message="No one was killed tonight.", observation_type=ta.ObservationType.GAME_MESSAGE)
        else:
            self._eliminate_player(tgt, "was killed during the night")

    def _eliminate_player(self, pid: int, reason: str):
        if pid in self.state.game_state["alive_players"]:
            self.state.game_state["alive_players"].remove(pid)
        self.state.add_observation(message=f"Player {pid} {reason}.", observation_type=ta.ObservationType.GAME_MESSAGE)
        self._check_win()
    
    def _good_pids(self) -> List[int]:
        return [p for p in range(self.state.num_players) if self.player_roles[p] not in EVIL_NAMES]

    def _evil_pids(self) -> List[int]:
        return [p for p in range(self.state.num_players) if self.player_roles[p] in EVIL_NAMES]

    def _set_good_winners(self, reason: str):
        pids = self._good_pids()
        self.state.set_winners(player_ids=pids, reason=reason + "\nGood wins!")

    def _set_evil_winners(self, reason: str):
        pids = self._evil_pids()
        self.state.set_winners(player_ids=pids, reason=reason + "\nEvil wins!")
    
    def _set_guess_merlin(self):
        self.state.game_state["guess_merlin"] = True
        self.state.add_observation(message=f"{MISSION_WIN_THRESHOLD} missions succeeded. Evil has a chance to win by correctly guessing who Merlin is", observation_type=ta.ObservationType.GAME_MESSAGE)

    def _check_win(self):
        if self.state.game_state["consecutive_failed_team_proposals"] >= CONSECUTIVE_PROPOSAL_FAIL_THRESHOLD:
            self._set_evil_winners(reason=f"{CONSECUTIVE_PROPOSAL_FAIL_THRESHOLD} team proposals were rejected in a row.")
        elif self.state.game_state["mission_failures"] >= MISSION_WIN_THRESHOLD:
            self._set_evil_winners(reason=f"{MISSION_WIN_THRESHOLD} missions failed.")
        elif self.state.game_state["mission_successes"] >= MISSION_WIN_THRESHOLD:
            if MERLIN_NAME in self.player_roles.values():
                self._set_guess_merlin()
            else:
                self._set_good_winners(reason=f"{MISSION_WIN_THRESHOLD} missions succeeded.")

def generate_roles(num_players: int, special_roles: Optional[Set[str]] = None) -> list[str]:
    num_good, num_evil = get_side_sizes(num_players)
    if special_roles is None:
        special_roles = set()
    for role in special_roles:
        if role in EVIL_NAMES:
            num_evil -= 1
        else:
            num_good -= 1
    
    if num_good < 0 or num_evil < 0:
        raise ValueError("Too many special roles for the player count.")
    
    roles = list(special_roles)
    roles.extend([SERVANT_NAME] * num_good)
    roles.extend([MINION_NAME] * num_evil)
    random.shuffle(roles)
    return roles

def get_side_sizes(num_players: int) -> tuple[int, int]:
    """
    Return (good, evil) player counts for Avalon
    given the total number of players.

    Number of players for each side from:
    https://avalon-game.com/wiki/rules/#:~:text=Recommended%20Roles%20Setup
    """
    distribution = {
        5: (3, 2),
        6: (4, 2),
        7: (4, 3),
        8: (5, 3),
        9: (6, 3),
        10: (6, 4),
    }

    if num_players not in distribution:
        raise ValueError("Number of players must be between 5 and 10.")

    return distribution[num_players]

def get_mission_team_size(num_players: int, mission_index: int) -> int:
    """
    Returns the team size for a given number of players and mission index.

    Mission team sizes from:
    https://avalon-game.com/wiki/rules/#:~:text=Mission%20Team%20Size
    
    Parameters:
        num_players (int): Number of players (5-10)
        mission_index (int): Mission index (0-4)
    
    Returns:
        int: Team size
    """
    team_sizes = {
        5: [2, 3, 2, 3, 3],
        6: [2, 3, 4, 3, 4],
        7: [2, 3, 3, 4, 4],
        8: [3, 4, 4, 5, 5],
        9: [3, 4, 4, 5, 5],
        10: [3, 4, 4, 5, 5]
    }
    
    if num_players not in team_sizes:
        raise ValueError("Number of players must be between 5 and 10.")
    if not 0 <= mission_index < 5:
        raise ValueError("Mission index must be between 0 and 4 inclusive.")
    
    return team_sizes[num_players][mission_index]

def is_valid_team_proposal(team_proposal: List[int], num_players: int, mission_index: int) -> bool:
    team = set(team_proposal)
    team_size = get_mission_team_size(num_players, mission_index)
    return len(team) == team_size and 0 <= min(team) and max(team) < num_players
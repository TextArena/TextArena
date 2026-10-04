import re, string
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.ColonelBlotto.renderer import create_game_str

class ColonelBlottoEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    broadcast_actions = False  # allocations are hidden: raw actions echoed only to their author

    def __init__(self, num_fields: int = 3, num_total_units: int = 20, num_rounds: int = 10):
        """
        Args:
            num_fields (int): Number of fields to fight over (2-26).
            num_total_units (int): Total units each player can allocate per round.
            num_rounds (int): Maximum number of rounds before the game ends.
        """
        if not isinstance(num_fields, int) or isinstance(num_fields, bool) or not 2 <= num_fields <= 26:
            raise ValueError("num_fields must be an integer between 2 and 26")
        if not isinstance(num_total_units, int) or isinstance(num_total_units, bool) or num_total_units < num_fields:
            raise ValueError("num_total_units must be an integer at least as large as num_fields")
        if not isinstance(num_rounds, int) or isinstance(num_rounds, bool) or num_rounds <= 0:
            raise ValueError("num_rounds must be a positive integer")
        self.num_fields = num_fields
        self.field_names = list(string.ascii_uppercase[:self.num_fields])
        self.num_total_units = num_total_units
        self.num_rounds = num_rounds

    def get_board_str(self):  # TODO have to re-check
        return create_game_str(game_state=self.game_state)

    def _fresh_player_state(self) -> Dict[str, Any]:
        return {'units_remaining': self.num_total_units, 'current_allocation': {field_name: 0 for field_name in self.field_names}, 'allocation_complete': False}

    def setup(self) -> Dict[str, Any]:
        return {
            'fields': [{'name': field_name, 'value': 1, 'player_0_units': 0, 'player_1_units': 0} for field_name in self.field_names],
            'current_round': 1, 'scores': {0: 0, 1: 0},
            'player_states': {0: self._fresh_player_state(), 1: self._fresh_player_state()},
            'phase': 'allocation', 'last_battle': None,
        }

    def roles(self) -> Dict[int, str]:
        return {0: "Commander Alpha", 1: "Commander Beta"}

    def on_start(self):
        self._render_game_state()

    def _render_game_state(self):
        lines = []
        lines.append(f"=== COLONEL BLOTTO - Round {self.game_state['current_round']}/{self.num_rounds} ===")
        lines.append(f"Rounds Won - Commander Alpha: {self.game_state['scores'][0]}, Commander Beta: {self.game_state['scores'][1]}")
        lines.append(f"Available fields: {', '.join(self.field_names)}")
        lines.append(f"Units to allocate: {self.num_total_units}")
        lines.append("Format: A4 B2 C2")
        self.broadcast("\n".join(lines), ta.ObservationType.GAME_BOARD)

    def prompt(self, player_id: int) -> str:
        role = "Commander Alpha" if player_id == 0 else "Commander Beta"
        return (
            f"You are {role} in a game of ColonelBlotto. Each round, you have to allocate exactly {self.num_total_units} units across fields: {', '.join(self.field_names)}\n"
            f"Format: A4 B2 C2\nWin the majority of fields to win the round!"
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        allocation_dict = self._parse_allocation_input(action)
        validation_result = self._validate_allocation(allocation_dict)
        if validation_result != "Allocation is good.":
            return self.invalid(validation_result)

        # Process valid allocation
        for field in gs['fields']:
            field[f'player_{player_id}_units'] = allocation_dict[field['name']]
            gs['player_states'][player_id]['current_allocation'][field['name']] = allocation_dict[field['name']]

        gs['player_states'][player_id]['units_remaining'] = 0
        gs['player_states'][player_id]['allocation_complete'] = True

        # Check if both players have allocated
        if gs['player_states'][1 - player_id]['allocation_complete']:
            self._resolve_battle()
            outcome = self._check_gameover()
            if outcome is None:
                self._render_game_state()
            return outcome
        return None

    def _parse_allocation_input(self, action_string: str) -> Optional[Dict[str, int]]:
        if not action_string or not action_string.strip(): return None
        raw = action_string.strip()
        legacy_match = re.fullmatch(r"\[\s*([^\[\]]+?)\s*\]", raw)
        if legacy_match:
            s = legacy_match.group(1).strip()
        elif "[" in raw or "]" in raw:
            return None
        else:
            s = raw
        if not s: return None
        token_re = re.compile(r"([A-Za-z])\s*:?\s*(\d+)", re.IGNORECASE)
        matches = list(token_re.finditer(s))
        if not matches: return None
        allocations: Dict[str, int] = {}
        for m in matches:
            field = m.group(1).upper()
            if field in allocations: return None
            try: units = int(m.group(2))
            except ValueError: return None
            allocations[field] = units
        leftovers = token_re.sub("", s)
        leftovers = re.sub(r"[\s,]+", "", leftovers)
        if leftovers: return None
        for fname in self.field_names: allocations.setdefault(fname, 0)
        return allocations

    def _validate_allocation(self, allocation_dict: Optional[Dict[str, int]]) -> str:
        """Validate allocation dictionary, allowing omitted fields (now 0 by default)."""
        if allocation_dict is None:                                                 return "Invalid input format. Use: A:5, B:10, C:5"
        if any(f not in self.field_names for f in allocation_dict):                 return f"Invalid field name(s). Valid fields: {', '.join(self.field_names)}"
        if any(not isinstance(u, int) or u < 0 for u in allocation_dict.values()):  return "All allocations must be non-negative integers."
        if sum(allocation_dict.values()) != self.num_total_units:                   return f"You have to allocate exactly {self.num_total_units} units. Current sum: {sum(allocation_dict.values())}"
        return "Allocation is good."

    def _resolve_battle(self):
        """Calculate battle results and determine round winner"""
        gs = self.game_state
        # Determine field winners
        field_winners = []
        for field in gs['fields']:
            p0_units = field['player_0_units']
            p1_units = field['player_1_units']
            if p0_units > p1_units:     field_winners.append(0)
            elif p1_units > p0_units:   field_winners.append(1)
            else:                       field_winners.append(None)  # Tie

        # Extract battle results
        p0_wins = field_winners.count(0)
        p1_wins = field_winners.count(1)

        # Add battle summary as observation
        p0_allocations = ", ".join(f"{field['name']}: {field['player_0_units']:<2}" for field in gs["fields"])
        p1_allocations = ", ".join(f"{field['name']}: {field['player_1_units']:<2}" for field in gs["fields"])
        message = f"\nRound {gs['current_round']}\nCommander Alpha allocated: {p0_allocations}\nCommander Beta allocated:  {p1_allocations}\n"
        if p0_wins > p1_wins:   message += f"Winner: Commander Alpha";  gs['scores'][0] += 1
        elif p0_wins < p1_wins: message += f"Winner: Commander Beta";   gs['scores'][1] += 1
        else:                   message += f"Tie!"
        gs['last_battle'] = {
            'round': gs['current_round'],
            'fields': [dict(field) for field in gs['fields']],
        }
        self.broadcast(message, ta.ObservationType.GAME_MESSAGE)

        # increment round counter
        gs['current_round'] += 1

        # Reset player states and field allocations
        for player_id in [0, 1]: gs["player_states"][player_id] = self._fresh_player_state()
        for field in gs['fields']: field['player_0_units'] = 0; field['player_1_units'] = 0

    def _check_gameover(self) -> Optional[ta.Outcome]:
        """Check if the game should end"""
        current_round = self.game_state['current_round']
        scores = self.game_state['scores']

        # Check if max rounds reached
        outcome = None
        if current_round > self.num_rounds:
            if scores[0] > scores[1]:   outcome = self.winner(0, reason=f"Commander Alpha wins {scores[0]}-{scores[1]} after {self.num_rounds} rounds!")
            elif scores[1] > scores[0]: outcome = self.winner(1, reason=f"Commander Beta wins {scores[1]}-{scores[0]} after {self.num_rounds} rounds!")
            else:                       outcome = self.draw(reason=f"Game ends in a {scores[0]}-{scores[1]} tie after {self.num_rounds} rounds!")

        # Check for early victory (majority of possible rounds)
        if outcome is None:
            rounds_needed_to_win = (self.num_rounds // 2) + 1
            if scores[0] >= rounds_needed_to_win:   outcome = self.winner(0, reason=f"Commander Alpha wins {scores[0]}-{scores[1]} (majority achieved)!")
            elif scores[1] >= rounds_needed_to_win: outcome = self.winner(1, reason=f"Commander Beta wins {scores[1]}-{scores[0]} (majority achieved)!")
        if outcome is not None:
            self.game_state['phase'] = 'results'
        return outcome

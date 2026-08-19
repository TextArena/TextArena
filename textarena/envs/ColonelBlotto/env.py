import re, string, copy
from typing import Any, Dict, Optional, Tuple

import textarena as ta
from textarena.envs.ColonelBlotto.renderer import create_game_str

class ColonelBlottoEnv(ta.Env):
    def __init__(self, num_fields: int = 3, num_total_units: int = 20, num_rounds: int = 10):
        """
        Args:
            num_fields (int): Number of fields to fight over (2-26).
            num_total_units (int): Total units each player can allocate per round.
            num_rounds (int): Maximum number of rounds before the game ends.
        """
        self.num_fields = min(max(num_fields, 2), 26)
        self.field_names = list(string.ascii_uppercase[:self.num_fields])
        self.num_total_units = max(num_total_units, self.num_fields)
        self.num_rounds = num_rounds
        self._player_states = {'units_remaining': self.num_total_units, 'current_allocation': {field_name: 0 for field_name in self.field_names}, 'allocation_complete': False}

    def get_board_str(self):  # TODO have to re-check
        return create_game_str(game_state=self.state.game_state)

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state = {
            'fields': [{'name': field_name, 'value': 1, 'player_0_units': 0, 'player_1_units': 0} for field_name in self.field_names],
            'current_round': 1, 'scores': {0: 0, 1: 0},
            'player_states': {0: copy.copy(self._player_states), 1: copy.copy(self._player_states)}
        }
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt, role_mapping={0: self.m("player_prompt", "commander_alpha"), 1: self.m("player_prompt", "commander_beta")})
        self._render_game_state()
        # self.state.add_observation(message=f"Game started!\n{self._render_game_state()}", observation_type=ta.ObservationType.GAME_BOARD)

    def _render_game_state(self) -> str:
        message = self.m("game_state", "header_round", current_round=self.state.game_state['current_round'], num_rounds=self.num_rounds, alpha_score=self.state.game_state['scores'][0], beta_score=self.state.game_state['scores'][1], field_names=", ".join(self.field_names), num_total_units=self.num_total_units)
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_BOARD)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        role = self.m("player_prompt", "commander_alpha") if player_id == 0 else self.m("player_prompt", "commander_beta")
        return self.m("player_prompt", "intro", role=role, num_total_units=self.num_total_units, field_names=", ".join(self.field_names))

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, to_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        self._execute_player_move(action)
        self._check_gameover()
        # self.state.add_observation(to_id=1-self.state.current_player_id, message=f"Current game state:\n{self._render_game_state()}", observation_type=ta.ObservationType.GAME_BOARD)
        return self.state.step()

    def _execute_player_move(self, action: str):
        """Parse the action to find the requested allocation. If valid, make the allocation, otherwise set it as an invalid move"""            
        allocation_dict = self._parse_allocation_input(action)
        validation_result = self._validate_allocation(allocation_dict)
        
        if validation_result != self.m("invalid_move", "good_allocations"):
            self.state.set_invalid_move(reason=validation_result)
            return
            
        # Process valid allocation
        player_id = self.state.current_player_id
        for field in self.state.game_state['fields']:
            field[f'player_{player_id}_units'] = allocation_dict[field['name']]
            self.state.game_state['player_states'][player_id]['current_allocation'][field['name']] = allocation_dict[field['name']]
        
        self.state.game_state['player_states'][player_id]['units_remaining'] = 0
        self.state.game_state['player_states'][player_id]['allocation_complete'] = True
        
        # Check if both players have allocated
        other_player = 1 - player_id
        if self.state.game_state['player_states'][other_player]['allocation_complete']:
            self._resolve_battle()

    def _parse_allocation_input(self, action_string: str) -> Optional[Dict[str, int]]:
        if not action_string or not action_string.strip(): return None
        raw = action_string.strip()
        bracket_match = re.search(r"\[([^\]]+)\]", raw)
        # s = bracket_match.group(1) if bracket_match else raw
        s = (bracket_match.group(1) if bracket_match else raw).strip()
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
        # leftovers = token_re.sub("", s)
        # leftovers = re.sub(r"[\s,]+", "", leftovers)
        # if leftovers: return None
        for fname in self.field_names: allocations.setdefault(fname, 0)
        return allocations

    def _validate_allocation(self, allocation_dict: Optional[Dict[str, int]]) -> str:
        """Validate allocation dictionary, allowing omitted fields (now 0 by default)."""
        if allocation_dict is None:                                                 return self.m("invalid_move", "wrong_format")
        if any(f not in self.field_names for f in allocation_dict):                 return self.m("invalid_move", "invalid_field", field_names=", ".join(self.field_names))
        if any(not isinstance(u, int) or u < 0 for u in allocation_dict.values()):  return self.m("invalid_move", "wrong_allocation_value")
        if sum(allocation_dict.values()) != self.num_total_units:                   return self.m("invalid_move", "incorrect_total_units", num_total_units=self.num_total_units, current_sum=sum(allocation_dict.values()))
        return self.m("invalid_move", "good_allocations")

    def _resolve_battle(self):
        """Calculate battle results and determine round winner"""
        # Determine field winners
        field_winners = []
        for field in self.state.game_state['fields']:
            p0_units = field['player_0_units']
            p1_units = field['player_1_units']
            if p0_units > p1_units:     field_winners.append(0)
            elif p1_units > p0_units:   field_winners.append(1)
            else:                       field_winners.append(None)  # Tie
        
        # Extract battle results
        p0_wins = field_winners.count(0)
        p1_wins = field_winners.count(1)
        
        # Add battle summary as observation
        p0_allocations = ", ".join(f"{field['name']}: {field['player_0_units']:<2}" for field in self.state.game_state["fields"])
        p1_allocations = ", ".join(f"{field['name']}: {field['player_1_units']:<2}" for field in self.state.game_state["fields"])
        
        message = self.m("round_battle", "field_result", current_round=self.state.game_state['current_round'], p0_allocations=p0_allocations, p1_allocations=p1_allocations)
        if p0_wins > p1_wins:   full_message = self.m("round_battle", "winner_alpha", message=message);  self.state.game_state['scores'][0] += 1
        elif p0_wins < p1_wins: full_message =  self.m("round_battle", "winner_beta", message=message);   self.state.game_state['scores'][1] += 1
        else:                   full_message = self.m("round_battle", "tie", message=message)
        self.state.add_observation(message=full_message, observation_type=ta.ObservationType.GAME_MESSAGE)

        # increment round counter
        self.state.game_state['current_round'] += 1

        # Reset player states and field allocations
        for player_id in [0, 1]: self.state.game_state["player_states"][player_id] = copy.copy(self._player_states)
        for field in self.state.game_state['fields']: field['player_0_units'] = 0; field['player_1_units'] = 0
        self._render_game_state()

    def _check_gameover(self):
        """Check if the game should end"""
        current_round = self.state.game_state['current_round']
        scores = self.state.game_state['scores']
        
        # Check if max rounds reached
        if current_round > self.num_rounds:
            if scores[0] > scores[1]:   self.state.set_winner(player_id=0, reason=self.m("outcome", "winner_alpha", score_0=scores[0], score_1=scores[1], num_rounds=self.num_rounds))
            elif scores[1] > scores[0]: self.state.set_winner(player_id=1, reason=self.m("outcome", "winner_beta", score_1=scores[1], score_0=scores[0], num_rounds=self.num_rounds))
            else:                       self.state.set_draw(reason=self.m("outcome", "draw", score_0=scores[0], score_1=scores[1], num_rounds=self.num_rounds))
            return
        
        # Check for early victory (majority of possible rounds)
        rounds_needed_to_win = (self.num_rounds // 2) + 1
        if scores[0] >= rounds_needed_to_win:   self.state.set_winner(player_id=0, reason=self.m("outcome", "early_winner_alpha", scores_0=scores[0], scores_1=scores[1]))
        elif scores[1] >= rounds_needed_to_win: self.state.set_winner(player_id=1, reason=self.m("outcome", "early_winner_beta", scores_1=scores[1], scores_0=scores[0]))
        
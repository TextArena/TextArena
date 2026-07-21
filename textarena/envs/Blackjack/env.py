import random
from typing import Dict, Tuple, Optional, Any, List

import textarena as ta

class BlackjackEnv(ta.Env):
    def __init__(self, num_hands: int):
        super().__init__()
        self.num_hands = num_hands
        self.ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
        self.suits = ['♠','♥','♦','♣']

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed)
        game_state = {"hand_number": 1, "num_hands": self.num_hands, "player_hand": [], "dealer_hand": [], "results_summary": {"win":0, "lose":0, "draw":0}}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self._deal_initial_cards() # deal first hand
        self._observe_state()

    def _draw_card(self) -> str: return f"{random.choice(self.ranks)}{random.choice(self.suits)}" # infinite deck
    def _deal_initial_cards(self):
        self.state.game_state["player_hand"] = [self._draw_card(), self._draw_card()]
        self.state.game_state["dealer_hand"] = [self._draw_card(), self._draw_card()]

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro")

    def _hand_score(self, hand: List[str]) -> int:
        total, aces = 0, 0
        for card in hand:
            rank = card[:-1]
            if rank in ['J','Q','K']:   total += 10
            elif rank == 'A':           total += 11; aces += 1
            else:                       total += int(rank)
        while total > 21 and aces: # downgrade aces from 11 → 1 as needed
            total -= 10; aces -= 1
        return total

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        if "[hit]" in action.lower():
            self._handle_hit()
            self._observe_state()  # only observe if valid
        elif "[stand]" in action.lower():
            self._handle_stand()
            self._observe_state()  # only observe if valid
        else:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "wrong_format"))
            # Do not call _observe_state()
        return self.state.step()

    def _handle_hit(self):
        self.state.game_state["player_hand"].append(self._draw_card())
        if self._hand_score(self.state.game_state["player_hand"]) > 21: # player busts → record loss, then advance
            self.state.game_state["results_summary"]["lose"] += 1
            self._advance_or_finish("bust")

    def _handle_stand(self):
        while self._hand_score(self.state.game_state["dealer_hand"]) < 17: # dealer draws until ≥17
            self.state.game_state["dealer_hand"].append(self._draw_card())
        # compare scores
        p = self._hand_score(self.state.game_state["player_hand"])
        d = self._hand_score(self.state.game_state["dealer_hand"])
        if d > 21 or p > d:     self.state.game_state["results_summary"]["win"] += 1;   outcome = "win"
        elif p == d:            self.state.game_state["results_summary"]["draw"] += 1;  outcome = "draw"
        else:                   self.state.game_state["results_summary"]["lose"] += 1;  outcome = "lose"
        self._advance_or_finish(outcome)

    def _advance_or_finish(self, outcome: str):
        """After a hand ends, either start the next one or finish env."""
        message = self.m("game_message", "hand_result", hand_number=self.state.game_state['hand_number'], outcome=outcome, player_score=self._hand_score(self.state.game_state['player_hand']), dealer_score=self._hand_score(self.state.game_state['dealer_hand']))
        self.state.add_observation(from_id=ta.GAME_ID, to_id=-1, message=message, observation_type=ta.ObservationType.GAME_MESSAGE)
        if self.state.game_state["hand_number"] < self.state.game_state["num_hands"]: # prepare next hand
            self.state.game_state["hand_number"] += 1
            self.state.game_state["player_hand"].clear()
            self.state.game_state["dealer_hand"].clear()
            self._deal_initial_cards()
        else: # determine winner
            wins = self.state.game_state["results_summary"]["win"]
            losses= self.state.game_state["results_summary"]["lose"]
            draws = self.state.game_state["results_summary"]["draw"]
            self.state.add_observation(to_id=-1, message=self.m("game_message", "all_complete", num_hands=self.state.game_state['num_hands'], wins=wins, losses=losses, draws=draws), observation_type=ta.ObservationType.GAME_MESSAGE)
            self.state.set_outcome(reward=wins/(losses+wins+draws), reason=self.m("outcome", "game_over", losses=losses, wins=wins, draws=draws))

    def _observe_state(self):
        gs = self.state.game_state
        score = self._hand_score(gs['player_hand'])
        msg = self.m("board", "current_state", hand_number=gs['hand_number'], num_hands=gs['num_hands'], player_hand=', '.join(gs['player_hand']), score=score, dealer_card=gs['dealer_hand'][0])
        self.state.add_observation(to_id=-1, message=msg, observation_type=ta.ObservationType.GAME_MESSAGE)

    def _get_percentage_completion(self) -> float:
        """ Returns a reward based on win rate over total expected hands, preventing reward hacking by early exit. """
        gs = self.state.game_state
        if gs["num_hands"] == 0: return 0.0  # fallback safeguard
        return (gs["results_summary"]["win"] + 0.5 * gs["results_summary"]["draw"]) / gs["num_hands"]
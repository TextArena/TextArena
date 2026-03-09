import re, random
from typing import Tuple, Dict, Any, Optional

import textarena as ta
from textarena.envs.KuhnPoker.renderer import create_board_str


class KuhnPokerEnv(ta.Env):
    def __init__(self, max_rounds: int = 1):
        super().__init__()
        self.ante = 1
        self.max_rounds = max_rounds
        self.deck = [0, 1, 2]  # 0=J, 1=Q, 2=K
        self.legal_action_tree = {"check": {"check": "showdown", "bet": {"fold": "loser", "call": "showdown"}}, "bet": {"fold": "loser", "call": "showdown"}}

    def get_board_str(self): return create_board_str(self.state.game_state)
    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state = {"pot": None, "player_chips": {0: 0, 1: 0}, "current_round": 0, "starting_player": 0}
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self._init_round() # Initialize the first round

    def _init_round(self):
        self.state.game_state["current_round"] += 1
        if self.state.game_state["current_round"] > self.max_rounds: # check if game is complete
            # determine winner
            if self.state.game_state["player_chips"][0] > self.state.game_state["player_chips"][1]: self.state.set_winner(player_id=0, reason=f"Player 0 won by having more chips at the end of all {self.max_rounds} rounds.")
            elif self.state.game_state["player_chips"][0] < self.state.game_state["player_chips"][1]: self.state.set_winner(player_id=1, reason=f"Player 1 won by having more chips at the end of all {self.max_rounds} rounds.")
            else: self.state.set_draw(reason=f"At the end of {self.max_rounds} rounds, both players had the same number of chips.")
            return

        random.shuffle(self.deck) # shuffle the deck
        self.state.game_state["player_cards"] = {0: self.deck[0], 1: self.deck[1]} # assign player cards
        # reset pot
        self.state.game_state["pot"] = self.ante * 2
        self.state.game_state["player_chips"][0] -= self.ante
        self.state.game_state["player_chips"][1] -= self.ante
        # increment round counter
        self.state.game_state["current_legal_action_tree"] = self.legal_action_tree.copy()

        # set starting player
        starting_player = 1 - self.state.game_state["starting_player"]
        self.state.game_state["starting_player"] = starting_player 
        self.state.manually_set_current_player_id(new_player_id=starting_player)

        for player_id in range(2):
            message = f"### Starting round {self.state.game_state['current_round']} out of {self.max_rounds} rounds. Your card is: '{self._rank_to_str(self.state.game_state['player_cards'][player_id])}'"
            self.state.add_observation(message=message, to_id=player_id, observation_type=ta.ObservationType.GAME_MESSAGE)
            if player_id == starting_player:
                message = f"Your available actions are: " + ', '.join(f"'[{k}]'" for k in self.state.game_state["current_legal_action_tree"].keys())
            self.state.add_observation(to_id=player_id, message=message, observation_type=ta.ObservationType.GAME_BOARD)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are Player {player_id} in a {self.max_rounds} round game of Kuhn Poker.\n"
            f"Game Rules:\n"
            f"- Kuhn Poker uses a 3-card deck with J, Q, K (J lowest, K highest)\n"
            f"- Each player antes {self.ante} chip and receives 1 card each round "
            f"(note that the cards are dealt without replacement, so you cannot have the same card as your opponent).\n"
            f"- Game continues for {self.max_rounds} rounds\n"
            f"- The player with the most chips after all rounds wins\n\n"
            f"Action Rules:\n"
            f"- '[check]': Pass without betting (only if no bet is on the table)\n"
            f"- '[bet]': Add 1 chip to the pot (only if no bet is on the table)\n"
            f"- '[call]': Match an opponent's bet by adding 1 chip to the pot\n"
            f"- '[fold]': Surrender your hand and let your opponent win the pot\n"
        )
    def step(self, action: str) -> Tuple[bool, Dict[str, Any]]:
        rotate_player = True
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.compile(r"\[(Check|Bet|Fold|Call)\]", re.IGNORECASE).search(action.strip()) # Regular expression to capture valid actions: e.g. [Check], [Bet], [Fold], [Call]
        if not match: # Invalid action
            self.state.set_invalid_move(reason="Action must be [Check], [Bet], [Call], or [Fold].")
            return self.state.step()

        move = match.group(1).lower()  # 'check', 'bet', 'fold', 'call'
        if move not in self.state.game_state["current_legal_action_tree"].keys():
            legal_actions = ', '.join([f"[{k}]" for k in self.state.game_state["current_legal_action_tree"].keys()])
            self.state.set_invalid_move(reason=f"Action must be {legal_actions}.")
            return self.state.step()

        # execute move
        self.state.add_observation(message=f"Player {self.state.current_player_id}, submitted move: '[{move}]'.", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if move in ("bet", "call"):
            self.state.game_state["player_chips"][self.state.current_player_id] -= self.ante
            self.state.game_state["pot"] += self.ante
        self.state.game_state["current_legal_action_tree"] = self.state.game_state["current_legal_action_tree"][move]
        # check if round loser / showdown
        if self.state.game_state["current_legal_action_tree"] == "loser":
            self._set_round_winner(player_id=1-self.state.current_player_id, reason=f"Player {self.state.current_player_id} has folded."); rotate_player=False
        elif self.state.game_state["current_legal_action_tree"] == "showdown":
            self._handle_showdown(); rotate_player=False
        else: # show valid next actions
            legal_actions = ', '.join([f"'[{k}]'" for k in self.state.game_state["current_legal_action_tree"].keys()])
            self.state.add_observation(to_id=1-self.state.current_player_id, message=f"Your available actions are: {legal_actions}", observation_type=ta.ObservationType.GAME_BOARD)
        return self.state.step(rotate_player=rotate_player)

    def _set_round_winner(self, player_id: int, reason: str):
        self.state.game_state["player_chips"][player_id] += self.state.game_state["pot"]
        reason += f" Current scores: Player 0: '{self.state.game_state['player_chips'][0]}'; Player 1: '{self.state.game_state['player_chips'][1]}'"
        self.state.add_observation(message=reason, observation_type=ta.ObservationType.GAME_MESSAGE) # initialize the next cound
        self._init_round() # start next round

    def _rank_to_str(self, rank: int) -> str:
        """Convert the numeric rank to a string 'J', 'Q', or 'K'."""
        return {0: 'J', 1: 'Q', 2: 'K'}.get(rank, '?')

    def _handle_showdown(self):
        card_p0, card_p1 = self.state.game_state["player_cards"][0], self.state.game_state["player_cards"][1]
        winner = 0 if card_p0 > card_p1 else 1 # Determine and announce the winner
        winner_card, loser_card = (card_p0, card_p1) if winner == 0 else (card_p1, card_p0)
        reason = (
            f"Showdown: Player {winner}'s {self._rank_to_str(winner_card)} beats "
            f"Player {1 - winner}'s {self._rank_to_str(loser_card)}. "
            f"Player {winner} wins pot of {self.state.game_state['pot']} chips."
        )
        self._set_round_winner(player_id=winner, reason=reason)




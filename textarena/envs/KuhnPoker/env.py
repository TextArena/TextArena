import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.KuhnPoker.renderer import create_board_str


class KuhnPokerEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False

    max_rounds = ta.Param(1, "The number of rounds in the match.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ante = 1
        self.legal_action_tree = {"check": {"check": "showdown", "bet": {"fold": "loser", "call": "showdown"}}, "bet": {"fold": "loser", "call": "showdown"}}

    def get_board_str(self):
        """Return a public board that never exposes either private card."""
        return create_board_str(self.state.game_state)

    def render(self, player_id: int) -> str:
        """Render the acting player's card (keeping the opponent's hidden) and their legal actions."""
        board = create_board_str(self.game_state, viewer_id=player_id)
        if self.state.done:
            return board
        legal_actions = ', '.join(f"'{k}'" for k in self.game_state["current_legal_action_tree"].keys())
        return f"{board}\nYour available actions are: {legal_actions}"

    def setup(self) -> Dict[str, Any]:
        return {"pot": None, "player_chips": {0: 0, 1: 0}, "current_round": 0, "starting_player": 0, "deck": [0, 1, 2]}  # 0=J, 1=Q, 2=K

    def on_start(self):
        self._init_round()  # deal the first round (never ends the game here)
        self.set_current_player(self.game_state["starting_player"])  # round 1 starts with player 1

    def _init_round(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        if gs["current_round"] >= self.max_rounds:  # check if game is complete
            # determine winner
            if gs["player_chips"][0] > gs["player_chips"][1]: return self.winner(0, reason=f"Player 0 won by having more chips at the end of all {self.max_rounds} rounds.")
            elif gs["player_chips"][0] < gs["player_chips"][1]: return self.winner(1, reason=f"Player 1 won by having more chips at the end of all {self.max_rounds} rounds.")
            else: return self.draw(reason=f"At the end of {self.max_rounds} rounds, both players had the same number of chips.")
        gs["current_round"] += 1

        self.rng.shuffle(gs["deck"])  # shuffle the deck
        gs["player_cards"] = {0: gs["deck"][0], 1: gs["deck"][1]}  # assign player cards
        # reset pot
        gs["pot"] = self.ante * 2
        gs["player_chips"][0] -= self.ante
        gs["player_chips"][1] -= self.ante
        gs["current_legal_action_tree"] = self.legal_action_tree.copy()

        # set starting player (alternates every round)
        starting_player = 1 - gs["starting_player"]
        gs["starting_player"] = starting_player

        for player_id in range(2):
            message = f"### Starting round {gs['current_round']} out of {self.max_rounds} rounds. Your card is: '{self._rank_to_str(gs['player_cards'][player_id])}'"
            self.message(player_id, message, ta.ObservationType.GAME_MESSAGE)
        return None

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a {self.max_rounds} round game of Kuhn Poker.\n"
            f"Game Rules:\n"
            f"- Kuhn Poker uses a 3-card deck with J, Q, K (J lowest, K highest)\n"
            f"- Each player antes {self.ante} chip and receives 1 card each round "
            f"(note that the cards are dealt without replacement, so you cannot have the same card as your opponent).\n"
            f"- Game continues for {self.max_rounds} rounds\n"
            f"- The player with the most chips after all rounds wins\n\n"
            f"Action Rules:\n"
            f"- 'check': Pass without betting (only if no bet is on the table)\n"
            f"- 'bet': Add 1 chip to the pot (only if no bet is on the table)\n"
            f"- 'call': Match an opponent's bet by adding 1 chip to the pot\n"
            f"- 'fold': Surrender your hand and let your opponent win the pot\n"
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        match = re.compile(r"^(Check|Bet|Fold|Call)$", re.IGNORECASE).match(action.strip())
        if not match:  # Invalid action
            return self.invalid("Action must be 'check', 'bet', 'call', or 'fold'.")

        move = match.group(1).lower()  # 'check', 'bet', 'fold', 'call'
        if move not in gs["current_legal_action_tree"].keys():
            legal_actions = ', '.join([f"'{k}'" for k in gs["current_legal_action_tree"].keys()])
            return self.invalid(f"Action must be {legal_actions}.")

        # execute move
        self.broadcast(f"Player {player_id}, submitted move: '{move}'.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if move in ("bet", "call"):
            gs["player_chips"][player_id] -= 1
            gs["pot"] += 1
        gs["current_legal_action_tree"] = gs["current_legal_action_tree"][move]
        # check if round loser / showdown
        if gs["current_legal_action_tree"] == "loser":
            return self._set_round_winner(player_id=1 - player_id, reason=f"Player {player_id} has folded.")
        elif gs["current_legal_action_tree"] == "showdown":
            return self._handle_showdown()
        return None  # the opponent responds; their board lists the legal actions

    def _set_round_winner(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        gs = self.game_state
        pot = gs["pot"]
        gs["player_chips"][player_id] += pot
        gs["pot"] = 0
        reason += f" Current scores: Player 0: '{gs['player_chips'][0]}'; Player 1: '{gs['player_chips'][1]}'"
        self.broadcast(reason, ta.ObservationType.GAME_MESSAGE)
        outcome = self._init_round()  # start next round (or return the final outcome)
        if outcome is None:
            self.set_next_player(gs["starting_player"])
        return outcome

    def _rank_to_str(self, rank: int) -> str:
        """Convert the numeric rank to a string 'J', 'Q', or 'K'."""
        return {0: 'J', 1: 'Q', 2: 'K'}.get(rank, '?')

    def _handle_showdown(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        card_p0, card_p1 = gs["player_cards"][0], gs["player_cards"][1]
        winner = 0 if card_p0 > card_p1 else 1  # Determine and announce the winner
        winner_card, loser_card = (card_p0, card_p1) if winner == 0 else (card_p1, card_p0)
        reason = (
            f"Showdown: Player {winner}'s {self._rank_to_str(winner_card)} beats "
            f"Player {1 - winner}'s {self._rank_to_str(loser_card)}. "
            f"Player {winner} wins pot of {gs['pot']} chips."
        )
        return self._set_round_winner(player_id=winner, reason=reason)

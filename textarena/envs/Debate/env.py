import os, json, random
import importlib.resources
from typing import Optional, Dict, Any, Tuple

import textarena as ta
from textarena.envs.Debate.renderer import create_board_str

class DebateEnv(ta.Env):
    def __init__(self, max_turns: Optional[int]=4, jury_class: Optional[Any]=None, jury_size: Optional[int]=5, topics_path: Optional[str]=None):
        """
        Args:
            max_turns (int, optional): Number of turns total (for both players). Must be even.
            jury_class (Any, optional): A Jury class or factory function that returns a Jury-like object. Defaults to OpenRouterJury if None.
            jury_size (int, optional): Number of models in the jury. Defaults to 5.
            topics_path (str, optional): Path to the JSON file containing debate topics. Defaults to "textarena/envs/two_player/Debate/topics.json".
        """
        if jury_class is None:
            # Import from the submodule: OpenRouterJury is not re-exported from the
            # utils package __init__, so `from textarena.envs.utils import ...` raises
            # ImportError. This matches how textarena.envs.__init__ imports it.
            from textarena.envs.utils.jury import OpenRouterJury
            jury_class = OpenRouterJury
        assert max_turns % 2 == 0, f"Please use an even number of max turns. Current: {max_turns}"
        self.max_turns = max_turns
        self._load_topics(topics_path)
        self.jury = jury_class(jury_size=jury_size, options=["Affirmative", "Negative"])

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)
    def _load_topics(self, topics_path: Optional[str]):
        try:
            if topics_path is not None: # Use provided path
                if not os.path.exists(topics_path): raise FileNotFoundError(f"Topics data file not found at: {topics_path}")
                with open(topics_path, "r", encoding="utf-8") as file: self.topics = json.load(file)["topics"]
            else: # Use package resource
                with importlib.resources.files('textarena.envs.Debate').joinpath('topics.json').open('r') as file: self.topics = json.load(file)["topics"]
        except Exception as e: raise FileNotFoundError(f"Failed to load topics data: {str(e)}")
        if not self.topics: raise ValueError("Debate topics list is empty.")

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        affirmative_player_id = random.choice([0, 1])
        game_state = {
            "arguments": {0: [], 1: []}, "topic": random.choice(self.topics),
            "sides": {affirmative_player_id: "Affirmative", 1-affirmative_player_id: "Negative"},
            "votes": {"pre-debate": {"Affirmative": 0, "Negative": 0}, "post-debate": {"Affirmative": 0, "Negative": 0}}
        }
        # Get pre-debate jury vote
        game_state["votes"]["pre-debate"] = self._evaluate_debate(topic=game_state["topic"], debate_transcript=None)
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are Player {player_id} in the Debate game.\nTopic: {game_state['topic']}\nYour position: {game_state['sides'][player_id]}\n"
            f"You will have {self.max_turns} total turns (shared between both players) to present your arguments. On your turn, type your argument.\n"
        )

    def _evaluate_debate(self, topic: str, debate_transcript: Optional[str]=None) -> Dict[str, float]:
        prompt = f"Debate Topic: {topic}\n"
        if debate_transcript: prompt += f"Debate Transcript:\n{debate_transcript}\nPlease vote for either 'Affirmative' or 'Negative'."
        else: prompt += "No debate has occurred yet. Please vote based solely on the topic.\nVote for either 'Affirmative' or 'Negative'."
        return self.jury.evaluate(context=prompt)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        self.state.game_state["arguments"][self.state.current_player_id].append(action)
        if self.state.turn >= self.state.max_turns - 1: # Check if the debate has ended
            winner_id = self._determine_debate_winner()
            if winner_id is None:
                self.state.set_draw(reason="The jury's opinion did not favor either side more.")
            else:
                self.state.set_winner(player_id=winner_id, reason=f"Player {winner_id} wins by gaining more support.")
        return self.state.step()

    def _determine_debate_winner(self) -> Optional[int]:
        transcript_lines = []
        max_rounds = max(len(self.state.game_state["arguments"][0]), len(self.state.game_state["arguments"][1]))
        for i in range(max_rounds):
            if i < len(self.state.game_state["arguments"][0]): transcript_lines.append(f"Player 0 ({self.state.game_state['sides'][0]}): {self.state.game_state['arguments'][0][i]}")
            if i < len(self.state.game_state["arguments"][1]): transcript_lines.append(f"Player 1 ({self.state.game_state['sides'][1]}): {self.state.game_state['arguments'][1][i]}")
        debate_transcript = "\n".join(transcript_lines)

        # Conduct post-debate voting
        post_votes = self._evaluate_debate(topic=self.state.game_state["topic"], debate_transcript=debate_transcript)
        self.state.game_state["votes"]["post-debate"] = post_votes

        # Calculate vote gains
        pre_votes = self.state.game_state["votes"]["pre-debate"]
        gain_aff = post_votes["Affirmative"] - pre_votes["Affirmative"]
        gain_neg = post_votes["Negative"] - pre_votes["Negative"]

        # Determine winner or tie
        if gain_aff > gain_neg:     winner_side = "Affirmative"
        elif gain_neg > gain_aff:   winner_side = "Negative"
        else: return None  # tie

        # Map winning side to player ID
        for pid, side in self.state.game_state["sides"].items():
            if side == winner_side: return pid
        return None

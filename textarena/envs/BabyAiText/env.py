import inspect
import math
from numbers import Real
from typing import Any, Dict, Mapping, Optional, Union

import textarena as ta
from copy import deepcopy

try:
    import gym
except ImportError:
    gym = None

try:
    import babyai_text
except ImportError:
    babyai_text = None

try:
    from babyai.bot import Bot
except ImportError:
    Bot = None


class BabyAiTextEnv(ta.GameEnv):
    """Environment for BabyAI-text game"""

    min_players = 1
    max_players = 1
    snapshot_excluded_attributes = ("baby_ai_text_env",)
    max_action_chars = 64

    def __init__(
        self,
        env_name: str = "BabyAI-MixedTestLocal-v0",
        max_turns: int = 20,
        seed: Optional[int] = None,
        backend=None,
        bot_class=None,
    ) -> None:
        """
        Initialize the 'BabyAI-Text' game environment.

        Args:
            env_name (str): The name of the environment, currently supported are: BabyAI-MixedTestLocal-v0,
            BabyAI-MixedTrainLocal-v0.
            max_turns (int)
        """
        if not isinstance(env_name, str) or not env_name.strip():
            raise ValueError("env_name must be a non-empty string.")
        if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer.")
        self.max_turns = max_turns
        self.name_environment = env_name
        if backend is None:
            if gym is None or babyai_text is None:
                raise ImportError(
                    "BabyAiText requires the optional gym, gym-minigrid, and babyai-text packages. "
                    "Install them from the BabyAI-Text project, or inject a compatible backend."
                )
            try:
                try:
                    self.baby_ai_text_env = gym.make(env_name, seed=seed)
                except TypeError:
                    self.baby_ai_text_env = gym.make(env_name)
            except Exception as exc:
                raise RuntimeError(f"Unable to create BabyAI-Text environment {env_name!r}: {exc}") from exc
        else:
            self.baby_ai_text_env = backend
        self._bot_class = bot_class if bot_class is not None else Bot
        self.seed = seed
        self.action_space = ["turn left", "turn right", "go forward", "pick up", "drop", "toggle"]
        self._reset_seed = None

    def _capture_backend_state(self):
        try:
            return "object", deepcopy(self.baby_ai_text_env)
        except Exception:
            try:
                return "dict", deepcopy(self.baby_ai_text_env.__dict__)
            except Exception:
                return None

    def _restore_backend_state(self, snapshot) -> bool:
        if snapshot is None:
            return False
        mode, value = snapshot
        backend = self.baby_ai_text_env
        if mode == "dict":
            backend.__dict__.clear()
            backend.__dict__.update(deepcopy(value))
        elif (
            type(backend) is type(value)
            and hasattr(backend, "__dict__")
            and hasattr(value, "__dict__")
        ):
            backend.__dict__.clear()
            backend.__dict__.update(deepcopy(value.__dict__))
        else:
            self.baby_ai_text_env = deepcopy(value)
        return True

    def snapshot(self) -> Dict[str, Any]:
        snapshot = super().snapshot()
        backend_resource = self._capture_backend_state()
        if backend_resource is None:
            raise RuntimeError("BabyAI-Text backend state cannot be snapshotted.")
        snapshot["backend_resource"] = backend_resource
        return snapshot

    def restore(self, snapshot: Dict[str, Any]):
        if "backend_resource" not in snapshot:
            raise ValueError("BabyAI-Text snapshot is missing backend state.")
        super().restore(snapshot)
        if not self._restore_backend_state(snapshot["backend_resource"]):
            raise RuntimeError("BabyAI-Text backend state could not be restored.")

    def reset(self, num_players: int, seed: Optional[int] = None):
        # A failed backend reset must not destroy the prior playable episode.
        previous_state = getattr(self, "state", None)
        previous_rng = getattr(self, "rng", None)
        previous_reset_seed = self._reset_seed
        backend_snapshot = self._capture_backend_state()
        self._reset_seed = seed
        try:
            return super().reset(num_players=num_players, seed=seed)
        except Exception:
            self._restore_backend_state(backend_snapshot)
            self._reset_seed = previous_reset_seed
            if previous_state is None:
                self.__dict__.pop("state", None)
            else:
                self.state = previous_state
            if previous_rng is None:
                self.__dict__.pop("rng", None)
            else:
                self.rng = previous_rng
            raise

    def setup(self) -> Dict[str, Any]:
        """ Reset the underlying 'BabyAI-Text' gym environment to its initial state """
        effective_seed = self._reset_seed if self._reset_seed is not None else self.seed
        try:
            if effective_seed is None:
                reset_result = self.baby_ai_text_env.reset()
            else:
                try:
                    signature = inspect.signature(self.baby_ai_text_env.reset)
                    signature.bind(seed=effective_seed)
                except (TypeError, ValueError):
                    seed_method = getattr(self.baby_ai_text_env, "seed", None)
                    if callable(seed_method):
                        seed_method(effective_seed)
                    reset_result = self.baby_ai_text_env.reset()
                else:
                    reset_result = self.baby_ai_text_env.reset(seed=effective_seed)
        except Exception as exc:
            raise RuntimeError(f"BabyAI-Text backend reset failed: {exc}") from exc

        if isinstance(reset_result, Mapping):
            game_state = dict(reset_result)
        elif (
            isinstance(reset_result, tuple)
            and len(reset_result) == 2
            and isinstance(reset_result[0], Mapping)
            and isinstance(reset_result[1], Mapping)
        ):
            game_state = dict(reset_result[0]) | dict(reset_result[1])
        else:
            raise RuntimeError("BabyAI-Text reset must return a mapping or a pair of mappings.")
        if not isinstance(game_state.get("mission"), str) or not game_state["mission"].strip():
            raise RuntimeError("BabyAI-Text reset did not provide a non-empty mission.")
        if "descriptions" not in game_state:
            raise RuntimeError("BabyAI-Text reset did not provide descriptions.")
        self._description_text(game_state["descriptions"])
        return game_state

    def prompt(self, player_id: int) -> str:
        """ Generate the initial prompt for the player, providing them with their goal and available actions """
        game_state = self.game_state
        descriptions = self._description_text(game_state["descriptions"])
        actions = ", ".join(self.action_space)
        prompt = (
            f"You are playing 'BabyAI-Text'.\n"
            f"Your goal is to {game_state['mission']}.\n"
            f"Available actions are {actions}.\n"
            f"{descriptions} \n"
            "On your turn, simply type your message.\n"
        )
        if self.state.max_turns:
            prompt += f"The game lasts for {self.state.max_turns} turns in total.\n"
        return prompt

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        if not isinstance(action, str) or len(action) > self.max_action_chars:
            return None
        return super().action_echo_target(player_id, action)

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """ Process the player's action """
        if not isinstance(action, str):
            return self.invalid("The action must be text.")
        if len(action) > self.max_action_chars:
            return self.invalid(f"Actions are limited to {self.max_action_chars} characters.")
        normalized_action = action.strip().lower()
        try:
            action_id = self.action_space.index(normalized_action)
        except ValueError:
            observation = "Invalid action"
            self.message(player_id, observation, ta.ObservationType.GAME_MESSAGE)
            self.step_info.update({'observations': observation, 'reward': -1, 'info': {}})
            return self.invalid(
                f"Unknown action. Choose one of: {', '.join(self.action_space)}."
            )

        backend_snapshot = self._capture_backend_state()
        try:
            step_result = self.baby_ai_text_env.step(action_id)
            if not isinstance(step_result, tuple) or len(step_result) not in (4, 5):
                raise RuntimeError("BabyAI-Text step must return a 4-tuple or 5-tuple.")
            if len(step_result) == 4:
                obs, reward, done_value, info = step_result
                done = self._coerce_done(done_value, "done")
                effective_reward = reward
            else:
                obs, reward, terminated, truncated, info = step_result
                terminated = self._coerce_done(terminated, "terminated")
                truncated = self._coerce_done(truncated, "truncated")
                done = terminated or truncated
                effective_reward = -1 if truncated and not terminated else reward
            if isinstance(reward, bool) or not isinstance(reward, Real) or not math.isfinite(float(reward)):
                raise RuntimeError("BabyAI-Text backend returned a non-finite numeric reward.")
            if not isinstance(info, Mapping):
                raise RuntimeError("BabyAI-Text backend info must be a mapping.")

            proposed_state = dict(self.game_state)
            if isinstance(obs, Mapping):
                proposed_state.update(dict(obs))
            for key in ("mission", "descriptions"):
                if key in info:
                    proposed_state[key] = info[key]
            if not isinstance(proposed_state.get("mission"), str) or not proposed_state["mission"].strip():
                raise RuntimeError("BabyAI-Text backend returned an invalid mission.")
            new_description = self._description_text(proposed_state.get("descriptions", ""))
            step_info = {'observations': obs, 'reward': effective_reward, 'info': dict(info)}
        except Exception as exc:
            if not self._restore_backend_state(backend_snapshot):
                raise RuntimeError(
                    "BabyAI-Text backend step failed and its state could not be restored."
                ) from exc
            return self.retryable("BabyAI-Text backend could not process the action.")

        self.game_state.clear()
        self.game_state.update(proposed_state)
        self.message(player_id, new_description, ta.ObservationType.GAME_MESSAGE)
        self.step_info.update(step_info)
        if done:
            return self.outcome(
                {0: effective_reward},
                reason=f"Episode finished. Reward: {effective_reward}",
            )
        return None

    @staticmethod
    def _description_text(descriptions) -> str:
        if isinstance(descriptions, str):
            return descriptions
        if isinstance(descriptions, (list, tuple)) and all(
            isinstance(description, str) for description in descriptions
        ):
            return ". ".join(descriptions)
        raise RuntimeError("BabyAI-Text descriptions must be text or a sequence of text.")

    @staticmethod
    def _coerce_done(value, name: str) -> bool:
        if isinstance(value, bool):
            return value
        value_type = type(value)
        if value_type.__name__ == "bool_" and value_type.__module__.startswith("numpy"):
            return bool(value)
        raise RuntimeError(f"BabyAI-Text backend {name} flag must be boolean.")

    def on_turn_limit(self) -> ta.Outcome:
        self.step_info["reward"] = -1
        return self.outcome({0: -1}, reason="The turn limit was reached before completing the mission.")

    def get_board_str(self):
        backend_view = getattr(getattr(self.baby_ai_text_env, "env", None), "env", self.baby_ai_text_env)
        return (
            f"Goal: {self.game_state.get('mission', 'Unknown')}\n"
            f"{backend_view}\nInventory: {self.get_inventory()}\nTurn: {self.state.turn}"
        )

    def gold_path(self, max_steps: int = 1000):
        actions = []
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
            raise ValueError("max_steps must be a positive integer.")
        if self._bot_class is None:
            raise RuntimeError("The optional babyai package is required to compute a gold path.")
        try:
            env_copy = deepcopy(self.baby_ai_text_env)
            bot = self._bot_class(env_copy)
            done = False
            action = None
            for _ in range(max_steps):
                action = bot.replan(action)
                if str(action) == "Actions.done":
                    break
                action_int = int(action)
                if not 0 <= action_int < len(self.action_space):
                    raise RuntimeError(f"BabyAI bot returned invalid action index {action_int}.")
                actions.append(self.action_space[action_int])
                step_result = env_copy.step(action_int)
                if len(step_result) == 4:
                    _, _, done, _ = step_result
                elif len(step_result) == 5:
                    _, _, terminated, truncated, _ = step_result
                    done = bool(terminated or truncated)
                else:
                    raise RuntimeError("BabyAI-Text step must return a 4-tuple or 5-tuple.")
                if done:
                    break
            else:
                raise RuntimeError(f"BabyAI bot did not finish within {max_steps} steps.")
        except Exception as exc:
            raise RuntimeError(f"Unable to compute a BabyAI gold path: {exc}") from exc
        return actions

    def get_inventory(self):
        carrying = getattr(self.baby_ai_text_env, "carrying", None)
        if carrying is not None:
            color = getattr(carrying, "color", None)
            item_type = getattr(carrying, "type", None)
            if color is not None and item_type is not None:
                return f"{color} {item_type}"
            return str(carrying)
        return "empty"

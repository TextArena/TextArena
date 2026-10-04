import random
from typing import Callable, Optional, List, Dict

import textarena as ta

# The OpenRouter model behind every LLM jury and game master. It decides game outcomes, so it is part of the rules
# of the -v1 games that use it; changing it is a version bump for Debate, ScenarioPlanning, GuessWho and TwentyQuestions.
DEFAULT_JUDGE_MODEL = "qwen/qwen3.8-27b"
default_models = [DEFAULT_JUDGE_MODEL]

JUROR_SYSTEM_PROMPT = (
    "You are a fair and impartial juror. You will be given a context and a list of "
    "possible options. Please select the single most appropriate option from the list, "
    "responding with only that exact option name (e.g., 'Affirmative', 'Negative', etc.)."
)

class OpenRouterJury:
    """
    A jury composed of multiple OpenRouterAgent jurors that each vote on a given context.

    Attributes:
        available_models (List[str]): A list of model names that jurors may use.
        jury (List[ta.agents.OpenRouterAgent]): A list of juror agents.
        options (List[str]): The possible options jurors may select.
    """

    def __init__(
        self,
        options: List[str],
        jury_size: int = 5,
        model_names: Optional[List[str]] = None,
        *,
        seed: Optional[int] = None,
        rng: Optional[random.Random] = None,
        agent_factory: Optional[Callable[..., ta.Agent]] = None,
    ):
        """
        Initialize an OpenRouterJury instance.

        Args:
            options (List[str]): The list of possible choices jurors can vote on.
            jury_size (int): The number of jurors.
            model_names (Optional[List[str]]): A list of model names to choose from.
                Defaults to `default_models`.
        """
        if not options:
            raise ValueError("A jury requires at least one voting option.")
        if jury_size < 1:
            raise ValueError(f"jury_size must be positive, received {jury_size}")
        self.available_models = list(model_names) if model_names is not None else list(default_models)
        if not self.available_models:
            raise ValueError("A jury requires at least one available model.")
        self.rng = rng if rng is not None else random.Random(seed)
        factory = agent_factory or ta.agents.OpenRouterAgent
        self.jury = []
        for _ in range(jury_size):
            model_name = self.rng.choice(self.available_models)
            juror = factory(model_name=model_name, system_prompt=JUROR_SYSTEM_PROMPT)
            self.jury.append(juror)
        self.options = list(options)

    def _create_juror_prompt(self, context: str) -> str:
        """
        Create the prompt that will be sent to each juror.

        Args:
            context (str): The debate context or question to evaluate.

        Returns:
            str: A formatted string instructing the juror to choose one of the options.
        """
        options_formatted = ", ".join([f"'{option}'" for option in self.options])
        prompt = (
            f"Based on the following context, choose the single best option.\n\n"
            f"Context: {context}\n\n"
            f"Options: {options_formatted}\n\n"
            f"Please respond with only one of the above options."
        )
        return prompt

    def evaluate(self, context: str) -> Dict[str, float]:
        """
        Evaluate the provided context by asking each juror to vote.

        Args:
            context (str): The text or debate content to evaluate.

        Returns:
            Dict[str, float]: A dictionary mapping each option to its normalized vote count.
                The values sum to 1.0 if any valid votes were cast; otherwise they remain 0
                if no valid votes were identified.
        """
        result_dict = {option: 0 for option in self.options}
        num_casted_votes = 0
        failures = []

        jury_prompt = self._create_juror_prompt(context=context)

        for juror in self.jury:
            try:
                judgement = juror(jury_prompt)
                normalized = judgement.strip().casefold()
                chosen_option = next(
                    (option for option in self.options if option.casefold() == normalized),
                    None,
                )

                if chosen_option:
                    result_dict[chosen_option] += 1
                    num_casted_votes += 1
                else:
                    failures.append(f"invalid vote {judgement!r}")
            except Exception as exc:
                failures.append(f"{type(exc).__name__}: {exc}")

        if failures:
            raise RuntimeError(
                f"{len(failures)} of {len(self.jury)} jurors failed to cast a valid vote: "
                + "; ".join(failures)
            )

        # Normalize
        if num_casted_votes > 0:
            for key in result_dict.keys():
                result_dict[key] /= num_casted_votes
        return result_dict

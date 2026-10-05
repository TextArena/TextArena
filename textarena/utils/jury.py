import random
import re
from typing import Callable, Optional, List, Dict

import textarena as ta

# The OpenRouter model behind every LLM jury and game master. It decides game outcomes, so it is part of the rules
# of the -v1 games that use it; changing it is a version bump for Debate, ScenarioPlanning, GuessWho and TwentyQuestions.
DEFAULT_JUDGE_MODEL = "qwen/qwen3.8-27b"
default_models = [DEFAULT_JUDGE_MODEL]

JUROR_SYSTEM_PROMPT = (
    "You are a fair and impartial juror. You will be given a context and a list of "
    "possible options. Select the single most appropriate option from the list and "
    "respond with only that exact option, with no other text."
)

_VOTE_LABEL = re.compile(r"^(?:vote|answer|option|choice)\s*:\s*", re.IGNORECASE)
_VOTE_WRAPPING = "\"'“”‘’_[]().,!"


def _parse_vote(reply: str, options: List[str]) -> Optional[str]:
    """The option a reply names, allowing quotes, markdown emphasis, brackets, a trailing period or comma, and a
    'Vote:' or 'Answer:' label; None if the reply is anything else, such as an option followed by an explanation."""
    text = reply.replace("*", "").replace("`", "").strip().strip(_VOTE_WRAPPING).strip()
    text = _VOTE_LABEL.sub("", text).strip(_VOTE_WRAPPING).strip().casefold()
    return next((option for option in options if option.casefold() == text), None)


class OpenRouterJury:
    """
    A jury composed of multiple OpenRouterAgent jurors that each vote on a given context.

    Attributes:
        available_models (List[str]): A list of model names that jurors may use.
        jury (List[ta.agents.OpenRouterAgent]): A list of juror agents.
        options (List[str]): The possible options jurors may select.
        vote_attempts (int): How often a juror is asked before an unusable reply counts as a failed vote.
    """
    vote_attempts = 2

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
            Dict[str, float]: The share of the votes each option received; the shares sum to 1.

        Raises:
            RuntimeError: If any juror fails to cast a valid vote, so that a game can retry the whole vote.
        """
        result_dict = {option: 0 for option in self.options}
        failures = []

        jury_prompt = self._create_juror_prompt(context=context)

        for juror in self.jury:
            # Only an unusable reply is asked again: model agents already retry failed requests.
            for attempt in range(self.vote_attempts):
                try:
                    judgement = juror(jury_prompt)
                except Exception as exc:
                    failures.append(f"{type(exc).__name__}: {exc}")
                    break
                chosen_option = _parse_vote(judgement, self.options)
                if chosen_option is not None:
                    result_dict[chosen_option] += 1
                    break
                if attempt == self.vote_attempts - 1:
                    failures.append(f"invalid vote {judgement!r}")

        if failures:
            raise RuntimeError(
                f"{len(failures)} of {len(self.jury)} jurors failed to cast a valid vote: "
                + "; ".join(failures)
            )

        return {option: votes / len(self.jury) for option, votes in result_dict.items()}

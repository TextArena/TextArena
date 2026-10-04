import logging, os, time
from typing import Optional

from textarena.core import Agent, extract_action

__all__ = ["HumanAgent", "OpenAIAgent", "OpenRouterAgent", "TinkerAgent"]
logger = logging.getLogger(__name__)
STANDARD_GAME_PROMPT = (
    "You are a competitive game player. Make sure you read the game instructions carefully. "
    "You may reason freely in your response, but you must provide your final action inside "
    "<action>...</action> tags, e.g. <action>your action here</action>. "
    "Only the content inside the tags is submitted to the game."
)


class HumanAgent(Agent):
    """ Human agent class that allows the user to input actions manually """

    def __call__(self, observation: str) -> str:
        print("\n\n+++ +++ +++") # for easies visualization of what is part of each turns observation
        return extract_action(input(f"Current observations: {observation}\nPlease enter the action: "))


class _ModelAgent(Agent):
    """ An agent backed by a remote model: retries failed requests and submits the model's <action> tag. """

    def __init__(self, system_prompt: Optional[str], verbose: bool, retries: int = 3, retry_delay: float = 5):
        self.system_prompt = system_prompt
        self.verbose = verbose
        self.retries = retries
        self.retry_delay = retry_delay

    def generate(self, observation: str) -> str:
        """ The model's full response to one observation. """
        raise NotImplementedError

    def __call__(self, observation: str) -> str:
        if not isinstance(observation, str):
            raise ValueError(f"Observation must be a string. Received type: {type(observation)}")
        for attempt in range(1, self.retries + 1):
            try:
                response = self.generate(observation)
                break
            except Exception as e:
                logger.warning("%s request attempt %d of %d failed: %s", type(self).__name__, attempt, self.retries, e)
                if attempt == self.retries:
                    raise
                time.sleep(self.retry_delay)
        if self.verbose:
            logger.info("Observation: %s\nResponse: %s", observation, response)
        return extract_action(response)


class OpenAIAgent(_ModelAgent):
    """ Agent for any OpenAI-compatible chat completions API: OpenAI, OpenRouter, vLLM, or a local server. """

    def __init__(self, model_name: str, base_url: Optional[str] = None, api_key: Optional[str] = None,
                 api_key_env: str = "OPENAI_API_KEY", system_prompt: Optional[str] = STANDARD_GAME_PROMPT,
                 verbose: bool = False, **kwargs):
        """
        Args:
            model_name (str): The name of the model.
            base_url (Optional[str]): The API endpoint, e.g. "http://localhost:8000/v1" for a vLLM server.
                Defaults to OpenAI's API.
            api_key (Optional[str]): The API key; read from the `api_key_env` environment variable if omitted.
            system_prompt (Optional[str]): The system prompt to use (default: STANDARD_GAME_PROMPT)
            verbose (bool): If True, every observation and response is logged at INFO level.
            **kwargs: Additional keyword arguments passed to `chat.completions.create` (e.g. temperature).
        """
        super().__init__(system_prompt=system_prompt, verbose=verbose)
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(f'{type(self).__name__} needs the openai package: pip install "textarena[agents]"')
        api_key = api_key or os.getenv(api_key_env)
        if not api_key:
            raise ValueError(f"API key not found. Pass api_key or set the {api_key_env} environment variable.")
        self.model_name = model_name
        self.kwargs = kwargs
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def generate(self, observation: str) -> str:
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": observation}]
        response = self.client.chat.completions.create(model=self.model_name, messages=messages, n=1, **self.kwargs)
        return response.choices[0].message.content.strip()


class OpenRouterAgent(OpenAIAgent):
    """ OpenAIAgent preset for OpenRouter; reads the key from OPENROUTER_API_KEY. """

    def __init__(self, model_name: str, system_prompt: Optional[str] = STANDARD_GAME_PROMPT, verbose: bool = False, **kwargs):
        super().__init__(model_name, base_url="https://openrouter.ai/api/v1", api_key_env="OPENROUTER_API_KEY",
                         system_prompt=system_prompt, verbose=verbose, **kwargs)


class TinkerAgent(_ModelAgent):
    """ Agent class using the Tinker API (Thinking Machines) to sample from base or fine-tuned models.

    Point it at a base model (e.g. model_name="Qwen/Qwen3-8B") or at weights saved from a
    Tinker training run (e.g. model_path="tinker://run-id/weights/checkpoint-001"), which makes
    it easy to evaluate checkpoints you fine-tuned on TextArena games.
    """
    def __init__(self, model_name: Optional[str]=None, model_path: Optional[str]=None,
                 system_prompt: Optional[str]=STANDARD_GAME_PROMPT, max_tokens: int=1024,
                 temperature: float=0.7, verbose: bool=False, **sampling_kwargs):
        """
        Args:
            model_name (Optional[str]): Name of the base model to sample from (e.g. "Qwen/Qwen3-8B").
            model_path (Optional[str]): Path to saved model weights (e.g. "tinker://run-id/weights/checkpoint-001").
                Provide exactly one of model_name / model_path.
            system_prompt (Optional[str]): The system prompt to use (default: STANDARD_GAME_PROMPT).
            max_tokens (int): The maximum number of tokens to generate.
            temperature (float): The sampling temperature.
            verbose (bool): If True, every observation and response is logged at INFO level.
            **sampling_kwargs: Additional keyword arguments passed to tinker.types.SamplingParams (e.g. top_p, stop).
        """
        super().__init__(system_prompt=system_prompt, verbose=verbose)
        if (model_name is None) == (model_path is None):
            raise ValueError("Provide exactly one of 'model_name' (a base model) or 'model_path' (a tinker:// checkpoint).")
        self.model_name = model_name
        self.model_path = model_path

        try:
            import tinker
            from tinker import types
        except ImportError:
            raise ImportError("Tinker package is required for TinkerAgent. Install it with: pip install tinker")
        self._types = types

        if not os.getenv("TINKER_API_KEY"):
            raise ValueError("Tinker API key not found. Please set the TINKER_API_KEY environment variable.")

        self.service_client = tinker.ServiceClient()
        self.sampling_client = self.service_client.create_sampling_client(base_model=model_name, model_path=model_path)
        self.tokenizer = self.sampling_client.get_tokenizer()
        self.sampling_params = types.SamplingParams(max_tokens=max_tokens, temperature=temperature, **sampling_kwargs)

    def _build_prompt(self, observation: str):
        """ Build a tinker ModelInput, using the model's chat template when available. """
        if getattr(self.tokenizer, "chat_template", None):
            messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": observation}]
            token_ids = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)
        else: # base model without a chat template: fall back to a plain-text prompt
            token_ids = self.tokenizer.encode(f"{self.system_prompt}\n\n{observation}\n")
        return self._types.ModelInput.from_ints(token_ids)

    def generate(self, observation: str) -> str:
        prompt = self._build_prompt(observation)
        result = self.sampling_client.sample(prompt=prompt, sampling_params=self.sampling_params, num_samples=1).result()
        return self.tokenizer.decode(result.sequences[0].tokens, skip_special_tokens=True).strip()

import asyncio
from abc import ABC, abstractmethod
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from textarena.core import Agent
import textarena as ta

from textarena.agents.deeprole_integrator import (
    DeepRoleIntegrator,
    dr_normalize_observation,
    dr_parse_game_states,
    dr_phase_str,
)
from textarena.agents.deeprole_llm import (
    _InstrumentedDeepRoleIntegrator,
    _TRLLLMBackend,
    _dr_make_llm_backend,
    _dr_build_hidden_state_table,
    _dr_player_evil_probs,
    _dr_strategy_summary,
    _dr_format_strategy,
    _dr_build_llm_prompt,
    dr_parse_llm_result,
    LLMResult,
    TokenLogprob,
    # Merlin-guess additions
    _dr_is_guess_merlin_phase,
    _dr_player_merlin_probs,
    _dr_get_evil_teammate,
    _dr_build_merlin_guess_prompt,
    dr_parse_merlin_guess,
    _dr_heuristic_merlin_guess,
    _dr_is_belief_informative,
    _dr_parse_teammate_from_obs,
)

# Shared backend cache — avoids reloading the same model weights into GPU
# memory when multiple DeepRoleLLMAgent instances share the same settings.
_DR_LLM_BACKEND_CACHE: Dict[Tuple, Any] = {}

# Lighter CFR budgets for DeepRoleLLMAgent when fast_deeprole=True
_DEEPROLE_LLM_DEFAULT_FAST_ITERATIONS      = 50
_DEEPROLE_LLM_DEFAULT_FAST_WAIT_ITERATIONS = 25

__all__ = [
    "HumanAgent", "OpenRouterAgent", "GeminiAgent", "OpenAIAgent", "HFLocalAgent", "CerebrasAgent",
    "AWSBedrockAgent", "AnthropicAgent", "GroqAgent", "OllamaAgent", "LlamaCppAgent",
    "DeepRoleAgent", "DeepRoleLLMAgent", "DeepRole_LLM",
    "TinkerDistilAgent",
]

STANDARD_GAME_PROMPT = "You are a competitive game player. Make sure you read the game instructions carefully, and always follow the required format."


# ===========================================================================
# Existing agents (unchanged)
# ===========================================================================

class HumanAgent(Agent):
    """ Human agent class that allows the user to input actions manually """
    def __init__(self):
        super().__init__()

    def __call__(self, observation: str) -> str:
        print("\n\n+++ +++ +++")
        return input(f"Current observations: {observation}\nPlease enter the action: ")


class OpenRouterAgent(Agent):
    """ Agent class using the OpenRouter API to generate responses. """
    def __init__(self, model_name: str, system_prompt: Optional[str] = STANDARD_GAME_PROMPT, verbose: bool = False, **kwargs):
        super().__init__()
        self.model_name = model_name
        self.verbose = verbose
        self.system_prompt = system_prompt
        self.kwargs = kwargs
        try:
            from openai import OpenAI
            from openai._exceptions import OpenAIError
        except ImportError:
            raise ImportError("OpenAI package is required for OpenRouterAgent. Install it with: pip install openai")
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key not found. Please set the OPENROUTER_API_KEY environment variable.")
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    def _make_request(self, observation: str) -> str:
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": observation}]
        response = self.client.chat.completions.create(model=self.model_name, messages=messages, n=1, stop=None, **self.kwargs)
        return response.choices[0].message.content.strip()

    def _retry_request(self, observation: str, retries: int = 3, delay: int = 15) -> str:
        last_exception = None
        for attempt in range(1, retries + 1):
            try:
                response = self._make_request(observation)
                if self.verbose:
                    print(f"\nObservation: {observation}\nResponse: {response}")
                return response
            except Exception as e:
                last_exception = e
                print(f"Attempt {attempt} failed with error: {e}")
                if attempt < retries:
                    time.sleep(delay)
        raise last_exception

    def __call__(self, observation: str) -> str:
        if not isinstance(observation, str):
            raise ValueError(f"Observation must be a string. Received type: {type(observation)}")
        return self._retry_request(observation)


class GeminiAgent(Agent):
    """Agent class using the Google Gemini API to generate responses."""
    def __init__(self, model_name: str, system_prompt: Optional[str]=STANDARD_GAME_PROMPT, verbose: bool=False, generation_config: Optional[dict]=None):
        super().__init__()
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.verbose = verbose
        try: import google.generativeai as genai
        except ImportError: raise ImportError("Google Generative AI package is required for GeminiAgent. Install it with: pip install google-generativeai")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: raise ValueError("Gemini API key not found. Please set the GEMINI_API_KEY environment variable.")
        genai.configure(api_key=api_key)
        if generation_config is None:
            generation_config = {"temperature": 1, "top_p": 0.95, "top_k": 40, "max_output_tokens": 8192, "response_mime_type": "text/plain"}
        self.generation_config = generation_config
        self.model = genai.GenerativeModel(model_name=self.model_name, generation_config=self.generation_config)

    def _make_request(self, observation: str) -> str:
        response = self.model.generate_content(f"Instructions: {self.system_prompt}\n\n{observation}")
        if self.verbose: print(f"\nObservation: {observation}\nResponse: {response.text}")
        return response.text.strip()

    def _retry_request(self, observation: str, retries: int = 3, delay: int = 5) -> str:
        last_exception = None
        for attempt in range(1, retries + 1):
            try:
                return self._make_request(observation)
            except Exception as e:
                last_exception = e
                print(f"Attempt {attempt} failed with error: {e}")
                if attempt < retries:
                    time.sleep(delay)
        raise last_exception

    def __call__(self, observation: str) -> str:
        if not isinstance(observation, str):
            raise ValueError(f"Observation must be a string. Received type: {type(observation)}")
        return self._retry_request(observation)


class OpenAIAgent(Agent):
    """Agent class using the OpenAI API to generate responses."""
    def __init__(self, model_name: str, system_prompt: Optional[str]=STANDARD_GAME_PROMPT, verbose: bool=False, api_key: str|None=None, base_url: str|None=None, **kwargs):
        super().__init__()
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.verbose = verbose
        self.kwargs = kwargs
        try: from openai import OpenAI
        except ImportError: raise ImportError("OpenAI package is required for OpenAIAgent. Install it with: pip install openai")
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key: raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _make_request(self, observation: str) -> str:
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": observation}]
        completion = self.client.chat.completions.create(model=self.model_name, messages=messages, n=1, stop=None, **self.kwargs)
        return completion.choices[0].message.content.strip()

    def _retry_request(self, observation: str, retries: int=3, delay: int=5) -> str:
        last_exception = None
        for attempt in range(1, retries + 1):
            try:
                response = self._make_request(observation)
                if self.verbose:
                    print(f"\nObservation: {observation}\nResponse: {response}")
                return response
            except Exception as e:
                last_exception = e
                print(f"Attempt {attempt} failed with error: {e}")
                if attempt < retries:
                    time.sleep(delay)
        raise last_exception

    def __call__(self, observation: str) -> str:
        if not isinstance(observation, str):
            raise ValueError(f"Observation must be a string. Received type: {type(observation)}")
        return self._retry_request(observation)


class HFLocalAgent(Agent):
    """ Hugging Face local agent class that uses the Hugging Face Transformers library """
    def __init__(self, model_name: str, device: str = "auto", quantize: bool = False, max_new_tokens: int = 1024, hf_kwargs: dict = None):
        super().__init__()
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
        except ImportError:
            raise ImportError("Transformers library is required for HFLocalAgent. Install it with: pip install transformers")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if quantize: self.model = AutoModelForCausalLM.from_pretrained(model_name, load_in_8bit=True, device_map=device, **hf_kwargs)
        else: self.model = AutoModelForCausalLM.from_pretrained(model_name, device_map=device, **hf_kwargs)
        self.system_prompt = STANDARD_GAME_PROMPT
        self.pipeline = pipeline('text-generation', max_new_tokens=max_new_tokens, model=self.model, tokenizer=self.tokenizer)

    def __call__(self, observation: str) -> str:
        try:
            response = self.pipeline(self.system_prompt+"\n"+observation, num_return_sequences=1, return_full_text=False)
            return response[0]['generated_text'].strip()
        except Exception as e:
            return f"An error occurred: {e}"


class CerebrasAgent(Agent):
    """ Cerebras agent class that uses the Cerebras API to generate responses """
    def __init__(self, model_name: str, system_prompt: str | None = None):
        super().__init__()
        self.model_name = model_name
        try: from cerebras.cloud.sdk import Cerebras
        except ImportError: raise ImportError("Cerebras SDK is required for CerebrasAgent. Install it with: pip install cerebras-cloud-sdk")
        self.client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))
        self.system_prompt = system_prompt or "You are a competitive game player. Make sure you read the game instructions carefully, and always follow the required format."

    def __call__(self, observation: str) -> str:
        try:
            messages=[{"role": "system", "content": self.system_prompt}, {"role": "user", "content": observation}]
            response = self.client.chat.completions.create(model=self.model_name, messages=messages, top_p=0.9, temperature=0.9)
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"An error occurred: {e}"


class AWSBedrockAgent(Agent):
    """ AWS Bedrock agent class that interacts with Claude via AWS Bedrock Runtime API """
    def __init__(self, model_id: str, region_name: str="us-east-1", system_prompt: Optional[str]=STANDARD_GAME_PROMPT, verbose: bool=False, **kwargs):
        super().__init__()
        self.model_id = model_id
        self.region_name = region_name
        self.system_prompt = system_prompt
        self.verbose = verbose
        self.kwargs = kwargs
        try:
            import boto3
        except ImportError:
            raise ImportError("Boto3 is required for AWSBedrockAgent. Install it with: pip install boto3")
        self.client = boto3.client("bedrock-runtime", region_name=self.region_name)

    def _make_request(self, observation: str) -> str:
        conversation = [{"role": "user", "content": [{"text": observation}]}]
        systemPrompt = [{"text": self.system_prompt}]
        try:
            inference_config = {"maxTokens": 512, "temperature": 0.9, "topP": 0.9, **self.kwargs}
            response = self.client.converse(modelId=self.model_id, messages=conversation, system=systemPrompt, inferenceConfig=inference_config)
            response_text = response["output"]["message"]["content"][0]["text"].strip()
            if self.verbose:
                print(f"\nObservation: {observation}\nResponse: {response_text}")
            return response_text
        except Exception as e:
            return f"ERROR: Can't invoke '{self.model_id}'. Reason: {e}"

    def __call__(self, observation: str) -> str:
        if not isinstance(observation, str):
            raise ValueError(f"Observation must be a string. Received type: {type(observation)}")
        return self._make_request(observation)


class AnthropicAgent(Agent):
    """Agent class using the Anthropic Claude API to generate responses."""
    def __init__(self, model_name: str, system_prompt: Optional[str]=STANDARD_GAME_PROMPT, max_tokens: int=1000, temperature: float=0.9, verbose: bool=False):
        super().__init__()
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.verbose = verbose
        try: import anthropic
        except ImportError: raise ImportError("Anthropic package is required for AnthropicAgent. Install it with: pip install anthropic")
        self.client = anthropic.Anthropic()

    def _make_request(self, observation: str) -> str:
        messages=[{"role": "user", "content": [{"type": "text", "text": observation}]}]
        response = self.client.messages.create(model=self.model_name, max_tokens=self.max_tokens, temperature=self.temperature, system=self.system_prompt, messages=messages)
        return response.content[0].text.strip()

    def _retry_request(self, observation: str, retries: int=3, delay: int=5) -> str:
        last_exception = None
        for attempt in range(1, retries + 1):
            try:
                response = self._make_request(observation)
                if self.verbose:
                    print(f"\nObservation: {observation}\nResponse: {response}")
                return response
            except Exception as e:
                last_exception = e
                print(f"Attempt {attempt} failed with error: {e}")
                if attempt < retries:
                    time.sleep(delay)
        raise last_exception

    def __call__(self, observation: str) -> str:
        if not isinstance(observation, str):
            raise ValueError(f"Observation must be a string. Received type: {type(observation)}")
        return self._retry_request(observation)


class GroqAgent(Agent):
    """Agent class using the Groq API to generate responses."""
    def __init__(self, model_name: str, system_prompt: Optional[str]=STANDARD_GAME_PROMPT, verbose: bool=False, **kwargs):
        super().__init__()
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.verbose = verbose
        self.kwargs = kwargs
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("Groq package is required for GroqAgent. Install it with: pip install groq")
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Groq API key not found. Please set GROQ_API_KEY.")
        self.client = Groq(api_key=api_key)

    def _make_request(self, observation: str) -> str:
        messages=[{"role": "system", "content": self.system_prompt}, {"role": "user", "content": observation}]
        resp = self.client.chat.completions.create(model=self.model_name, messages=messages, n=1, **self.kwargs)
        return resp.choices[0].message.content.strip()

    def _retry_request(self, observation: str, retries: int=3, delay: int=5) -> str:
        last_exc = None
        for i in range(1, retries+1):
            try:
                out = self._make_request(observation)
                if self.verbose: print(f"\nObservation: {observation}\nResponse: {out}")
                return out
            except Exception as e:
                last_exc = e
                print(f"Attempt {i} failed with error: {e}")
                if i < retries: time.sleep(delay)
        raise last_exc

    def __call__(self, observation: str) -> str:
        if not isinstance(observation, str):
            raise ValueError(f"Observation must be a string. Received {type(observation)}")
        return self._retry_request(observation)


class OllamaAgent(Agent):
    """Local agent using the Ollama Python client."""
    def __init__(self, model_name: str, system_prompt: Optional[str]=STANDARD_GAME_PROMPT, host: Optional[str]=None, verbose: bool=False, **kwargs):
        super().__init__()
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.verbose = verbose
        self.kwargs = kwargs
        try:
            from ollama import Client
        except ImportError:
            raise ImportError("Ollama package is required for OllamaAgent. Install it with: pip install ollama")
        host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.client = Client(host=host)

    def _make_request(self, observation: str) -> str:
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": observation}]
        resp = self.client.chat(model=self.model_name, messages=messages, **self.kwargs)
        return resp["message"]["content"].strip()

    def __call__(self, observation: str) -> str:
        if not isinstance(observation, str):
            raise ValueError(f"Observation must be a string. Received {type(observation)}")
        try:
            out = self._make_request(observation)
            if self.verbose: print(f"\nObservation: {observation}\nResponse: {out}")
            return out
        except Exception as e:
            return f"ERROR (Ollama): {e}"


class LlamaCppAgent(Agent):
    """Local agent using llama.cpp Python bindings (llama-cpp-python)."""
    def __init__(self, model_path: str, system_prompt: Optional[str]=STANDARD_GAME_PROMPT, n_ctx: int=8192, n_threads: Optional[int]=None, chat_format: Optional[str]=None, verbose: bool=False, **gen_kwargs):
        super().__init__()
        self.system_prompt = system_prompt
        self.verbose = verbose
        self.gen_kwargs = gen_kwargs
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError("llama-cpp-python is required. Install with: pip install llama-cpp-python")
        self.llm = Llama(model_path=model_path, n_ctx=n_ctx, n_threads=n_threads, chat_format=chat_format)

    def __call__(self, observation: str) -> str:
        if not isinstance(observation, str):
            raise ValueError(f"Observation must be a string. Received {type(observation)}")
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": observation}]
        out = self.llm.create_chat_completion(messages=messages, **self.gen_kwargs)
        text = out["choices"][0]["message"]["content"].strip()
        if self.verbose: print(f"\nObservation: {observation}\nResponse: {text}")
        return text


class DeepRoleAgent(Agent):
    """Avalon (5-player) agent using DeepRole play mode via DeepRoleIntegrator."""
    def __init__(
        self,
        nn_folder: str = "deeprole_zeroing_winprobs",
        binary: str = "deeprole",
        no_zero: bool = False,
        iterations: Optional[int] = None,
        wait_iterations: Optional[int] = None,
    ):
        super().__init__()
        self._integrator = DeepRoleIntegrator(
            nn_folder=nn_folder, binary=binary, no_zero=no_zero,
            iterations=iterations, wait_iterations=wait_iterations,
        )

    def __call__(self, observation) -> str:
        return self._integrator(observation)


# ===========================================================================
# DeepRoleLLMAgent — DeepRole CFR + TRL/local-model belief/commentary layer
# All supporting helpers live in deeprole_llm.py
# ===========================================================================

class DeepRoleLLMAgent(Agent):
    """
    Avalon (5-player) agent combining DeepRole CFR with a locally-run
    TRL-trained (or any HuggingFace) language model.

    On every turn:
      1. DeepRole computes the game-theoretically optimal action via CFR.
      2. Its 60-dim belief vector is marginalised to per-player P(Evil).
      3. The local LLM receives a minimal game-state prompt and returns:
           belief  float[0,1] : its own probability that the team has Evil
           message str        : short in-character reasoning
         The model is explicitly told not to echo the prior estimates.
      4. Generation runs with output_scores=True so native per-token logprobs
         are captured and stored in agent.last_logprobs after every call.
      5. On game-mechanical turns (vote/propose/mission/merlin), DeepRole's
         action is returned. On discussion turns, the LLM's message is used.

    Guess-Merlin phase is handled separately: a dedicated format-restricted
    prompt, a lenient regex parser, and a fallback that picks argmax of
    P(Merlin) marginalised from DeepRole's own belief. Self- and teammate-
    guesses are excluded by construction.

    Post-call attributes
    --------------------
    last_belief            : float | None        – LLM team-evil probability
    last_message           : str   | None        – LLM in-character message
    last_dr_action         : str   | None        – raw DeepRole action
    last_strategy          : dict                – CFR strategy summary
    last_player_evil_probs : list[float]         – per-player P(Evil) from CFR
    last_logprobs          : list[TokenLogprob]  – per-token logprob data

    Parameters
    ----------
    model_name_or_path : str
        HuggingFace Hub name or local path to any TRL-trained model, e.g.
        "Qwen/Qwen3-0.6B" or "/checkpoints/my-grpo-run/checkpoint-500".
    adapter_path : str | None
        Path to a PEFT/LoRA adapter directory produced by TRL's SFTTrainer /
        GRPOTrainer etc.  Applied on top of model_name_or_path.
    device : str
        "cuda" | "cpu" | "auto" (default — uses GPU if available).
    load_in_8bit : bool
        8-bit bitsandbytes quantisation (reduces VRAM).
    load_in_4bit : bool
        4-bit QLoRA quantisation (takes priority over load_in_8bit).
    max_new_tokens : int
        Token budget for generation (default 128).
    temperature : float
        Sampling temperature (default 0.7; set 0.0 for greedy decoding).
    top_logprobs : int
        Top-K alternative tokens to record per position (default 5).
    verbose : bool
        Print per-turn debug summary including truncated logprobs.
    nn_folder, binary, no_zero, iterations, wait_iterations
        Forwarded to DeepRoleIntegrator.
    llm_retries : int
        Retry attempts on generation failure (default 2).
    llm_retry_delay : float
        Seconds between retries (default 5.0).
    skip_llm_for_mechanical : bool
        If True, skip LLM on vote/propose/mission turns; call only for
        discussion phases (saves compute). Guess-Merlin is still routed
        through its dedicated handler.
    fast_deeprole : bool
        Use lighter CFR budgets (50/25) when iterations not set explicitly.
    share_llm_backend : bool
        Reuse the loaded model across agents with identical settings (avoids
        double-loading weights when running multiple agents in the same process).
    """

    def __init__(
        self,
        model_name_or_path: str,
        adapter_path: Optional[str]  = None,
        device: str                  = "auto",
        load_in_8bit: bool           = False,
        load_in_4bit: bool           = False,
        max_new_tokens: int          = 128,
        temperature: float           = 0.7,
        top_logprobs: int            = 5,
        verbose: bool                = False,
        nn_folder: str               = "deeprole_zeroing_winprobs",
        binary: str                  = "deeprole",
        no_zero: bool                = False,
        iterations: Optional[int]    = None,
        wait_iterations: Optional[int] = None,
        llm_retries: int             = 2,
        llm_retry_delay: float       = 5.0,
        skip_llm_for_mechanical: bool = False,
        fast_deeprole: bool          = True,
        share_llm_backend: bool      = True,
    ):
        super().__init__()
        eff_iterations = iterations if iterations is not None else (
            _DEEPROLE_LLM_DEFAULT_FAST_ITERATIONS if fast_deeprole else None
        )
        eff_wait = wait_iterations if wait_iterations is not None else (
            _DEEPROLE_LLM_DEFAULT_FAST_WAIT_ITERATIONS if fast_deeprole else None
        )
        self._integrator = _InstrumentedDeepRoleIntegrator(
            nn_folder=nn_folder, binary=binary, no_zero=no_zero,
            iterations=eff_iterations, wait_iterations=eff_wait,
        )

        # Backend params stored for lazy/cached init
        self._backend_key = (
            model_name_or_path, adapter_path, device,
            load_in_8bit, load_in_4bit, max_new_tokens, temperature, top_logprobs,
        )
        self._backend_kwargs = dict(
            model_name_or_path = model_name_or_path,
            adapter_path       = adapter_path,
            device             = device,
            load_in_8bit       = load_in_8bit,
            load_in_4bit       = load_in_4bit,
            max_new_tokens     = max_new_tokens,
            temperature        = temperature,
            top_logprobs       = top_logprobs,
        )
        self._share_llm_backend       = share_llm_backend
        self._llm: Optional[Any]      = None  # lazy init
        self._verbose                 = verbose
        self._llm_retries             = llm_retries
        self._llm_retry_delay         = llm_retry_delay
        self._skip_llm_for_mechanical = skip_llm_for_mechanical
        self._id_to_hid               = _dr_build_hidden_state_table()

        # Public post-call state
        self.last_belief:            Optional[float]    = None
        self.last_message:           Optional[str]      = None
        self.last_dr_action:         Optional[str]      = None
        self.last_strategy:          Dict[str, Any]     = {}
        self.last_player_evil_probs: List[float]        = [0.0] * 5
        self.last_logprobs:          List[TokenLogprob] = []

    def __call__(self, observation: Union[str, list, tuple]) -> str:
        text = dr_normalize_observation(observation)

        # Pre-parse game state so we can detect end-game phases before
        # deciding which code path to take.
        snaps    = dr_parse_game_states(text)
        gs_early = snaps[-1] if snaps else {}
        is_merlin_guess = _dr_is_guess_merlin_phase(gs_early, text)

        # Step 1 — DeepRole optimal action (always run; we need its belief).
        dr_result = self._integrator(text)

        # Step 2 — extract DeepRole internals
        belief_vec  = self._integrator.exposed_belief
        perspective = self._integrator.exposed_perspective
        node        = self._integrator.exposed_node
        player      = self._integrator.exposed_player
        role        = self._integrator.exposed_role
        dr_action   = self._integrator.exposed_dr_action

        evil_probs = _dr_player_evil_probs(belief_vec, self._id_to_hid)
        strat      = _dr_strategy_summary(node, player, perspective)
        self.last_player_evil_probs = evil_probs
        self.last_strategy          = strat
        self.last_dr_action         = dr_action
        self.last_logprobs          = []

        # Guess-Merlin: always route through the dedicated handler.
        # DeepRole's integrator is not reliable here because the Merlin-
        # guess action sits outside its CFR search tree, so dr_action may be
        # empty, malformed, or a self-targeted tag. _decide_merlin_guess
        # enforces the self + teammate exclusion and guarantees a valid tag.
        if is_merlin_guess:
            return self._decide_merlin_guess(
                player, role, belief_vec, gs_early, text
            )

        # Step 3 — optionally call LLM
        is_mechanical   = dr_action is not None
        should_call_llm = not (self._skip_llm_for_mechanical and is_mechanical)

        if should_call_llm:
            phase = dr_phase_str(gs_early) if gs_early else "unknown"
            sys_p, usr_p = _dr_build_llm_prompt(
                player_id=player, role=role, phase=phase, game_state=gs_early,
                player_evil_probs=evil_probs, dr_action=dr_action,
                observation_text=text,
            )
            belief, message, logprobs = self._call_llm_with_retry(sys_p, usr_p)
            self.last_logprobs = logprobs
        else:
            belief, message = 0.5, ""

        self.last_belief  = belief
        self.last_message = message

        if self._verbose:
            self._print_debug(player, role, dr_action, belief, message, evil_probs, strat)

        # Step 4 — return action
        if is_mechanical:
            return dr_result
        return message if message else dr_result

    # ------------------------------------------------------------------
    # Guess-Merlin handler
    # ------------------------------------------------------------------

    def _decide_merlin_guess(
        self,
        player: int,
        role: str,
        belief_vec: List[float],
        game_state: Dict[str, Any],
        observation_text: str = "",
    ) -> str:
        """Guess-Merlin handler. Rare — runs once per game — so we spend the
        tokens to call the LLM unconditionally (``skip_llm_for_mechanical``
        still applies to routine votes/proposals/missions).

        Teammate identification uses the most reliable signal available:
        DeepRole's posterior if it's actually informative, otherwise we
        parse the observation text directly. When nothing works, we
        exclude only ``self`` — wrongly excluding a teammate is safer
        than wrongly excluding the actual Merlin.

        Every failure path funnels into a heuristic, then a last-ditch
        first-legal-candidate, so the returned tag is always well-formed
        and targets a legal player.
        """
        import random  # local — used only in the uniform-belief fallback

        # --- Teammate identification ----------------------------------
        teammate: Optional[int] = None
        belief_ok = _dr_is_belief_informative(belief_vec)
        if belief_ok:
            try:
                teammate = _dr_get_evil_teammate(belief_vec, self._id_to_hid, player)
            except Exception:
                teammate = None
        if teammate is None:
            try:
                teammate = _dr_parse_teammate_from_obs(observation_text, player)
            except Exception:
                teammate = None

        # --- Build exclusion + candidate set --------------------------
        exclude    = {player} | ({teammate} if teammate is not None else set())
        candidates = [p for p in range(5) if p not in exclude]

        # --- Posterior over Merlin (only meaningful if belief is ok) --
        try:
            merlin_probs = _dr_player_merlin_probs(belief_vec, self._id_to_hid)
        except Exception:
            merlin_probs = [0.0] * 5

        pid: Optional[int] = None

        print(f"[MG P{player}] role={role} teammate={teammate} "
              f"belief_informative={belief_ok} candidates={candidates} "
              f"merlin_probs={[f'{p:.2f}' for p in merlin_probs]}")

        # --- LLM attempt — ALWAYS run, regardless of skip flag --------
        # Merlin-guess is 1 turn/game; compute cost is negligible and the
        # LLM is the only path that can actually reason from game history.
        try:
            sys_p, usr_p = _dr_build_merlin_guess_prompt(
                player_id=player, role=role, teammate_id=teammate,
                candidates=candidates, merlin_probs=merlin_probs,
                game_state=game_state,
                observation_text=observation_text,
            )
            llm = self._ensure_llm_backend()
            for attempt in range(1, self._llm_retries + 2):
                try:
                    result = llm.call(sys_p, usr_p)
                    print(f"[MG P{player}] attempt {attempt} raw LLM text: "
                          f"{result.text!r}")
                    self.last_logprobs = result.logprobs
                    pid = dr_parse_merlin_guess(result.text, 5, exclude)
                    print(f"[MG P{player}] parsed pid={pid} (exclude={exclude})")
                    if pid is not None:
                        self.last_message = result.text.strip()
                        break
                    # Corrective retry with the bad output shown back.
                    usr_p = (
                        f"Your previous response was:\n{result.text[:200]}\n\n"
                        f"That did not contain a valid "
                        f"<merlin_guess>N</merlin_guess> with N in "
                        f"{candidates}. Output ONLY the tag now, e.g. "
                        f"<merlin_guess>"
                        f"{candidates[0] if candidates else 0}"
                        f"</merlin_guess>."
                    )
                except Exception as exc:
                    print(f"[MG P{player}] LLM attempt {attempt} failed: {exc}")
                    if attempt <= self._llm_retries:
                        time.sleep(self._llm_retry_delay)
        except Exception as exc:
            print(f"[MG P{player}] LLM path aborted: {exc}")

        # --- Heuristic fallback ---------------------------------------
        # If belief is informative, argmax of P(Merlin|candidate) is the
        # right thing. If it's uniform, argmax is a deterministic P0 —
        # random among candidates distributes the error and stops the
        # degenerate 'always guess P0' pattern.
        if pid is None:
            try:
                if belief_ok:
                    pid = _dr_heuristic_merlin_guess(merlin_probs, exclude)
                    src = "argmax"
                else:
                    pid = random.choice(candidates) if candidates else player
                    src = "random (uniform belief)"
                print(f"[MG P{player}] heuristic fallback → P{pid}  [{src}]")
            except Exception:
                pid = None

        # --- Final sanity check: guarantee a legal pid ---------------
        if pid is None or not (0 <= pid < 5) or pid in exclude:
            pid = candidates[0] if candidates else (player + 1) % 5
            print(f"[MG P{player}] last-ditch → P{pid}")

        action = f"<merlin_guess>{pid}</merlin_guess>"
        self.last_dr_action = action
        self.last_belief    = merlin_probs[pid] if 0 <= pid < 5 else 0.0
        if self.last_message is None:
            self.last_message = action
        print(f"[MG P{player}] FINAL OUTPUT: {action}")
        return action

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_llm_backend(self) -> Any:
        """Lazily load the model; reuse from cache when share_llm_backend=True."""
        if self._llm is not None:
            return self._llm
        if self._share_llm_backend:
            if self._backend_key not in _DR_LLM_BACKEND_CACHE:
                _DR_LLM_BACKEND_CACHE[self._backend_key] = _dr_make_llm_backend(
                    **self._backend_kwargs
                )
            self._llm = _DR_LLM_BACKEND_CACHE[self._backend_key]
        else:
            self._llm = _dr_make_llm_backend(**self._backend_kwargs)
        return self._llm

    def _call_llm_with_retry(
        self, system: str, user: str
    ) -> Tuple[float, str, List[TokenLogprob]]:
        llm      = self._ensure_llm_backend()
        last_exc: Optional[Exception] = None
        for attempt in range(1, self._llm_retries + 2):
            try:
                result  = llm.call(system, user)
                belief, message = dr_parse_llm_result(result)
                return belief, message, result.logprobs
            except Exception as exc:
                last_exc = exc
                if self._verbose:
                    print(f"[DeepRoleLLMAgent] LLM attempt {attempt} failed: {exc}")
                if attempt <= self._llm_retries:
                    time.sleep(self._llm_retry_delay)
        if self._verbose:
            print(f"[DeepRoleLLMAgent] All retries exhausted: {last_exc}")
        return 0.5, "", []

    def _print_debug(self, player, role, dr_action, belief, message, evil_probs, strat):
        import math
        sep = "─" * 55
        ep  = "  ".join(f"P{i}:{v:.2f}" for i, v in enumerate(evil_probs))
        print(f"\n{sep}")
        print(f"[DeepRoleLLMAgent] P{player} | role={role}")
        print(f"  evil probs  : {ep}")
        print(f"  DR action   : {dr_action or '(discussion)'}")
        print(f"  LLM belief  : {belief:.3f}")
        print(f"  LLM message : {message}")
        print(f"  strategy    :\n{_dr_format_strategy(strat)}")
        if self.last_logprobs:
            parts = [
                f"'{t.token}'({math.exp(t.logprob)*100:.0f}%)"
                for t in self.last_logprobs[:12]
            ]
            print(f"  logprobs    : {'  '.join(parts)}")
        print(sep)


# Alias so callers can use either name
DeepRole_LLM = DeepRoleLLMAgent


# ===========================================================================
# TinkerDistilAgent — Avalon agent backed by a Tinker-hosted LoRA checkpoint
# ===========================================================================
#
# Subclass of DeepRoleLLMAgent that swaps the local-HF _TRLLLMBackend for a
# _TinkerSamplerBackend (OpenAI-compatible client pointing at Tinker's hosted
# sampling endpoint).  Inherits everything else unchanged: DeepRole CFR
# integrator, the Merlin-guess handler, and the prompt builders from
# deeprole_llm.  This guarantees the deployment distribution matches the
# distribution the model was trained on by tinker_multiagent.py.
#
# Tinker docs:
#   https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/

_TINKER_BASE_URL = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"


def _td_extract_logprobs(choice: Any) -> List[TokenLogprob]:
    """Convert OpenAI-shaped ``choice.logprobs.content`` into TokenLogprob list."""
    out: List[TokenLogprob] = []
    try:
        content = choice.logprobs.content   # may be None
        if not content:
            return out
        for tok in content:
            tops: List[Tuple[str, float]] = []
            if getattr(tok, "top_logprobs", None):
                tops = [(t.token, float(t.logprob)) for t in tok.top_logprobs]
            out.append(TokenLogprob(
                token        = tok.token,
                logprob      = float(tok.logprob),
                top_logprobs = tops,
            ))
    except Exception:
        # OpenAI client objects can vary slightly between versions; missing
        # logprobs is non-fatal — just lose the visualisation signal.
        return out
    return out


class _TinkerSamplerBackend:
    """
    Inference-only backend for Tinker-hosted models.  Mirrors
    ``call(system, user) -> LLMResult`` so it drops in transparently for
    DeepRoleLLMAgent's call sites (including the Guess-Merlin retry loop).

    The ``model`` argument must be a Tinker sampler weight path of the form
    ``tinker://UUID:train:0/sampler_weights/NNNNNN``, produced by
    ``training_client.save_weights_for_sampler_async(name=...)`` during
    tinker_multiagent.py training.
    """

    def __init__(
        self,
        model: str,
        max_new_tokens: int = 128,
        temperature: float  = 0.7,
        top_logprobs: int   = 5,
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package required for _TinkerSamplerBackend.\n"
                "Install: pip install openai"
            )

        api_key = os.getenv("TINKER_API_KEY")
        if not api_key:
            raise ValueError(
                "TINKER_API_KEY not set.\n"
                "Get a key at https://tinker-docs.thinkingmachines.ai/tinker/quickstart/"
            )

        self.client         = OpenAI(base_url=_TINKER_BASE_URL, api_key=api_key)
        self.model          = model
        self.max_new_tokens = max_new_tokens
        self.temperature    = temperature
        self.top_logprobs   = top_logprobs

    def call(self, system: str, user: str) -> LLMResult:
        """One blocking sampling call.  Returns text + per-token logprobs."""
        resp = self.client.chat.completions.create(
            model        = self.model,
            messages     = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            max_tokens   = self.max_new_tokens,
            temperature  = self.temperature,
            logprobs     = True,
        )
        choice = resp.choices[0]
        text   = (choice.message.content or "").strip()
        return LLMResult(text=text, logprobs=_td_extract_logprobs(choice))


class TinkerDistilAgent(DeepRoleLLMAgent):
    """
    Avalon (5-player) agent using a Tinker-hosted LoRA checkpoint at
    inference time.  Identical behaviour to ``DeepRoleLLMAgent`` except the
    LLM backend is a Tinker sampler instead of a local HF model.

    Parameters
    ----------
    tinker_model_path : str
        Tinker sampler weight path produced by tinker_multiagent.py training,
        e.g. ``"tinker://UUID:train:0/sampler_weights/000080"``.
    max_new_tokens, temperature, top_logprobs
        LLM generation params (forwarded to Tinker's chat-completions call).
    nn_folder, binary, no_zero, iterations, wait_iterations, fast_deeprole
        Forwarded to the DeepRole CFR integrator (same semantics as the
        parent class).
    skip_llm_for_mechanical, llm_retries, llm_retry_delay, verbose
        Same semantics as ``DeepRoleLLMAgent``.

    Notes
    -----
    No ``model_name_or_path`` / ``adapter_path`` / ``device`` / ``load_in_4bit``
    / ``load_in_8bit`` / ``share_llm_backend`` parameters — those are local-HF
    concepts.  Tinker manages weights server-side.

    Reads ``TINKER_API_KEY`` from the environment.
    """

    def __init__(
        self,
        tinker_model_path: str,
        max_new_tokens: int  = 128,
        temperature: float   = 0.7,
        top_logprobs: int    = 5,
        verbose: bool        = False,
        nn_folder: str       = "deeprole_zeroing_winprobs",
        binary: str          = "deeprole",
        no_zero: bool        = False,
        iterations: Optional[int]    = None,
        wait_iterations: Optional[int] = None,
        llm_retries: int     = 2,
        llm_retry_delay: float = 5.0,
        skip_llm_for_mechanical: bool = False,
        fast_deeprole: bool  = True,
    ):
        if not tinker_model_path:
            raise ValueError(
                "tinker_model_path is required, e.g. "
                "'tinker://UUID:train:0/sampler_weights/000080'."
            )

        # Initialise the parent with placeholder local-model settings so its
        # constructor does NOT actually load a HF model.  We override
        # ``_ensure_llm_backend`` below so the placeholder is never used.
        super().__init__(
            model_name_or_path      = "PLACEHOLDER_NEVER_LOADED",
            adapter_path            = None,
            device                  = "cpu",
            load_in_8bit            = False,
            load_in_4bit            = False,
            max_new_tokens          = max_new_tokens,
            temperature             = temperature,
            top_logprobs            = top_logprobs,
            verbose                 = verbose,
            nn_folder               = nn_folder,
            binary                  = binary,
            no_zero                 = no_zero,
            iterations              = iterations,
            wait_iterations         = wait_iterations,
            llm_retries             = llm_retries,
            llm_retry_delay         = llm_retry_delay,
            skip_llm_for_mechanical = skip_llm_for_mechanical,
            fast_deeprole           = fast_deeprole,
            share_llm_backend       = False,   # Tinker has its own caching
        )

        self._tinker_model_path = tinker_model_path
        self._tinker_kwargs = dict(
            model          = tinker_model_path,
            max_new_tokens = max_new_tokens,
            temperature    = temperature,
            top_logprobs   = top_logprobs,
        )
        self._llm = None

    def _ensure_llm_backend(self) -> Any:
        """Override — return a cached ``_TinkerSamplerBackend`` instance."""
        if self._llm is None:
            self._llm = _TinkerSamplerBackend(**self._tinker_kwargs)
        return self._llm

    def __repr__(self) -> str:
        return f"TinkerDistilAgent(model='{self._tinker_model_path}')"
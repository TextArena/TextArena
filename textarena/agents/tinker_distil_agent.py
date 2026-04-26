"""
tinker_distil_agent.py — TextArena agent that runs Avalon using a Tinker-
hosted LoRA checkpoint for inference (typically one produced by
tinker_multiagent.py).

Design
------
``TinkerDistilAgent`` is a subclass of ``DeepRoleLLMAgent`` that swaps the
local-HF ``_TRLLLMBackend`` for ``_TinkerSamplerBackend`` — an OpenAI-
compatible client pointing at Tinker's hosted sampling endpoint
(https://tinker.thinkingmachines.dev/.../oai/api/v1).

Everything else is inherited unchanged:
  * DeepRole CFR integrator and per-turn belief
  * Minimal prompt format from ``deeprole_llm._dr_build_llm_prompt``
  * Guess-Merlin dedicated handler with teammate exclusion
  * Per-token logprob capture (Tinker's API supports ``logprobs=True``)
  * ``last_*`` post-call attributes for inspection / visualisation

Why subclass instead of building a new agent
--------------------------------------------
The training script ``tinker_multiagent.py`` rolls out games using the same
``_dr_build_llm_prompt`` / ``_dr_build_merlin_guess_prompt`` builders.
Running inference through a class that uses those same builders guarantees
the deployment distribution matches the training distribution.  Subclassing
is the easiest way to enforce that.

Usage
-----
    from textarena.agents import TinkerDistilAgent

    agent = TinkerDistilAgent(
        tinker_model_path="tinker://UUID:train:0/sampler_weights/000080",
        max_new_tokens=128,
        temperature=0.7,
    )

Environment
-----------
    TINKER_API_KEY  — required.

References
----------
  Tinker OpenAI-compat docs:
    https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/
"""

from __future__ import annotations

import os
from typing import Any, Optional

from textarena.agents.basic_agents import DeepRoleLLMAgent  # parent class
from textarena.agents.deeprole_llm import LLMResult, TokenLogprob, _DEFAULT_TOP_K  # noqa: F401


# ---------------------------------------------------------------------------
# Tinker base URL — same constant the training script uses.
# ---------------------------------------------------------------------------

_TINKER_BASE_URL = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"


# ---------------------------------------------------------------------------
# Tinker sampler backend (OpenAI-compatible)
# ---------------------------------------------------------------------------

class _TinkerSamplerBackend:
    """
    Inference-only backend for Tinker-hosted models.  Mirrors the
    ``call(system, user) -> LLMResult`` interface that ``_TRLLLMBackend``
    exposes, so it drops in transparently for ``DeepRoleLLMAgent``'s call
    sites (including the Guess-Merlin retry loop).

    The ``model`` argument must be a Tinker sampler weight path of the form
    ``tinker://UUID:train:0/sampler_weights/NNNNNN``.  These are produced by
    ``training_client.save_weights_for_sampler_async(name=...)`` during
    ``tinker_multiagent.py`` training.
    """

    def __init__(
        self,
        model: str,
        max_new_tokens: int = 128,
        temperature: float  = 0.7,
        top_logprobs: int   = _DEFAULT_TOP_K,
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

    # ------------------------------------------------------------------
    # Core call — matches _TRLLLMBackend's signature
    # ------------------------------------------------------------------

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
            top_logprobs = self.top_logprobs,
        )
        choice = resp.choices[0]
        text   = (choice.message.content or "").strip()
        return LLMResult(text=text, logprobs=_extract_logprobs(choice))


def _extract_logprobs(choice: Any) -> list:
    """Convert OpenAI-shaped ``choice.logprobs.content`` into TokenLogprob list."""
    out: list = []
    try:
        content = choice.logprobs.content   # may be None
        if not content:
            return out
        for tok in content:
            tops = []
            if getattr(tok, "top_logprobs", None):
                tops = [(t.token, float(t.logprob)) for t in tok.top_logprobs]
            out.append(TokenLogprob(
                token        = tok.token,
                logprob      = float(tok.logprob),
                top_logprobs = tops,
            ))
    except Exception:
        # OpenAI client objects can vary slightly between versions;
        # missing logprobs is non-fatal — we just lose the visualisation
        # signal for that call.
        return out
    return out


# ---------------------------------------------------------------------------
# Agent — subclass of DeepRoleLLMAgent
# ---------------------------------------------------------------------------

class TinkerDistilAgent(DeepRoleLLMAgent):
    """
    Avalon (5-player) agent using a Tinker-hosted LoRA checkpoint at
    inference time.  Identical behaviour to ``DeepRoleLLMAgent`` except the
    LLM backend is swapped to ``_TinkerSamplerBackend``.

    Parameters
    ----------
    tinker_model_path : str
        A Tinker sampler weight path produced by
        ``tinker_multiagent.py`` training, e.g.
        ``"tinker://UUID:train:0/sampler_weights/000080"``.
    max_new_tokens, temperature, top_logprobs
        LLM generation params (forwarded to Tinker's chat-completions call).
    nn_folder, binary, no_zero, iterations, wait_iterations, fast_deeprole
        Forwarded to the DeepRole CFR integrator (same semantics as the
        parent class).
    skip_llm_for_mechanical, llm_retries, llm_retry_delay, verbose
        Same semantics as ``DeepRoleLLMAgent``.

    Notes
    -----
    * No ``model_name_or_path``, ``adapter_path``, ``device``, ``load_in_4bit``
      / ``load_in_8bit``, or ``share_llm_backend`` parameters — those are
      local-HF concepts.  Tinker handles weight management itself.
    * Reads ``TINKER_API_KEY`` from the environment.
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
        # constructor does not actually load a HF model.  We override
        # ``_ensure_llm_backend`` below to construct a Tinker backend
        # instead, so the placeholder is never used.
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

        # Override backend construction with Tinker-specific kwargs.
        self._tinker_model_path = tinker_model_path
        self._tinker_kwargs = dict(
            model          = tinker_model_path,
            max_new_tokens = max_new_tokens,
            temperature    = temperature,
            top_logprobs   = top_logprobs,
        )
        # Force a fresh init when the backend is first needed.
        self._llm = None

    # ------------------------------------------------------------------
    # Override only the backend construction.
    # ------------------------------------------------------------------

    def _ensure_llm_backend(self) -> Any:
        """Return a cached ``_TinkerSamplerBackend``; construct on first call."""
        if self._llm is None:
            self._llm = _TinkerSamplerBackend(**self._tinker_kwargs)
        return self._llm

    # ------------------------------------------------------------------
    # Identity / repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"TinkerDistilAgent(model='{self._tinker_model_path}')"

"""
deeprole_llm.py — support layer for DeepRoleLLMAgent.

Key design choices
------------------
* Minimal prompt: the LLM receives only the raw game facts it cannot deduce
  itself (mission score, phase, team, votes, player count). DeepRole's belief
  vector is deliberately withheld from the system prompt to prevent the model
  from simply echoing CFR numbers back; the evil-probability hint is passed as
  a *soft* background note, not as a directive.

* Logprobs: both _TinkerLLMBackend and _OpenAILLMBackend request
  logprobs=True / top_logprobs=5 from the API. The raw logprob data for every
  generated token is returned alongside the text so callers can visualise
  token-level confidence (especially useful for the `belief` float tokens).

  Returned as: LLMResult(text, logprobs)
  where logprobs is a list of TokenLogprob(token, logprob, top_logprobs).

Public surface used by basic_agents.py
---------------------------------------
  _InstrumentedDeepRoleIntegrator
  _dr_make_llm_backend(provider, model, max_tokens, temperature)
  _dr_build_hidden_state_table()
  _dr_player_evil_probs(belief, id_to_hid)
  _dr_strategy_summary(node, player, perspective)
  _dr_format_strategy(summary)
  _dr_build_llm_prompt(*, player_id, role, phase, game_state,
                         player_evil_probs, dr_action, observation_text)
  _dr_parse_llm_result(result)  -> (belief, message)
  _dr_is_game_action(text)
  LLMResult
  TokenLogprob
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from textarena.agents.deeprole_integrator import (
    DeepRoleIntegrator,
    _DEEPROLE_EVIL,
    build_hidden_state_tables,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NUM_PLAYERS       = 5
_NUM_HIDDEN_STATES = 60  # 5 × 4 × 3 ordered (merlin, assassin, minion) assignments
_TINKER_BASE_URL   = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"
_TOP_LOGPROBS      = 5   # how many alternative tokens to record at each position


# ---------------------------------------------------------------------------
# Logprob data types
# ---------------------------------------------------------------------------

@dataclass
class TokenLogprob:
    """Logprob data for a single generated token."""
    token:       str
    logprob:     float
    top_logprobs: List[Tuple[str, float]] = field(default_factory=list)
    """Top-K (token, logprob) alternatives at this position."""


@dataclass
class LLMResult:
    """Return value from every backend .call()."""
    text:     str
    logprobs: List[TokenLogprob] = field(default_factory=list)
    """Per-token logprob data; empty list when the API does not support it."""


# ---------------------------------------------------------------------------
# Instrumented integrator
# ---------------------------------------------------------------------------

class _InstrumentedDeepRoleIntegrator(DeepRoleIntegrator):
    """
    Thin subclass of DeepRoleIntegrator that mirrors its private state into
    public attributes after every __call__.

    exposed_belief      : list[float]   60-dim normalised belief vector
    exposed_perspective : int           perspective index used this turn
    exposed_node        : dict          raw CFR JSON node (may be {})
    exposed_player      : int           player id
    exposed_role        : str           bf-role string (e.g. "servant")
    exposed_dr_action   : str | None    game-action string, or None if discussion
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.exposed_belief:      List[float]       = [1.0 / _NUM_HIDDEN_STATES] * _NUM_HIDDEN_STATES
        self.exposed_perspective: int               = 0
        self.exposed_node:        Dict[str, Any]    = {}
        self.exposed_player:      int               = 0
        self.exposed_role:        str               = "servant"
        self.exposed_dr_action:   Optional[str]     = None

    def __call__(self, observation: Union[str, list, tuple]) -> str:
        result                   = super().__call__(observation)
        self.exposed_belief      = list(self._belief)
        self.exposed_perspective = self._perspective
        self.exposed_node        = dict(self._node)
        self.exposed_player      = self._player
        self.exposed_role        = self._role
        self.exposed_dr_action   = result if _dr_is_game_action(result) else None
        return result


# ---------------------------------------------------------------------------
# LLM backends
# ---------------------------------------------------------------------------

def _extract_logprobs(choice) -> List[TokenLogprob]:
    """
    Convert an OpenAI-compatible choice.logprobs into List[TokenLogprob].
    Returns [] safely when the API omits logprob data.
    """
    try:
        content = choice.logprobs.content  # list of ChatCompletionTokenLogprob
        if not content:
            return []
        out = []
        for tok in content:
            tops = []
            if tok.top_logprobs:
                tops = [(t.token, t.logprob) for t in tok.top_logprobs]
            out.append(TokenLogprob(token=tok.token, logprob=tok.logprob, top_logprobs=tops))
        return out
    except Exception:
        return []


class _TinkerLLMBackend:
    """
    Tinker OpenAI-compatible inference backend with logprobs support.

    Auth  : TINKER_API_KEY env var.
    Model : a Tinker sampler weight path, e.g.
            "tinker://UUID:train:0/sampler_weights/000080"
    Docs  : https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/
    """

    def __init__(self, model: str, max_tokens: int, temperature: float):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("pip install openai")
        api_key = os.getenv("TINKER_API_KEY")
        if not api_key:
            raise ValueError(
                "TINKER_API_KEY not set. "
                "See https://tinker-docs.thinkingmachines.ai/tinker/quickstart/"
            )
        self.client      = OpenAI(base_url=_TINKER_BASE_URL, api_key=api_key)
        self.model       = model
        self.max_tokens  = max_tokens
        self.temperature = temperature

    def call(self, system: str, user: str) -> LLMResult:
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            logprobs=True,
            top_logprobs=_TOP_LOGPROBS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        choice = resp.choices[0]
        return LLMResult(
            text=choice.message.content.strip(),
            logprobs=_extract_logprobs(choice),
        )


class _OpenAILLMBackend:
    """Standard OpenAI Chat Completions backend with logprobs support."""

    def __init__(self, model: str, max_tokens: int, temperature: float):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("pip install openai")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set.")
        self.client      = OpenAI(api_key=api_key)
        self.model       = model
        self.max_tokens  = max_tokens
        self.temperature = temperature

    def call(self, system: str, user: str) -> LLMResult:
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            logprobs=True,
            top_logprobs=_TOP_LOGPROBS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        choice = resp.choices[0]
        return LLMResult(
            text=choice.message.content.strip(),
            logprobs=_extract_logprobs(choice),
        )


def _dr_make_llm_backend(
    provider: str,
    model: Optional[str],
    max_tokens: int,
    temperature: float,
) -> Union[_TinkerLLMBackend, _OpenAILLMBackend]:
    """
    Return the appropriate LLM backend.

    provider : "tinker" (default) | "openai"
    model    : for Tinker, a required sampler weight path
               "tinker://UUID:train:0/sampler_weights/NNNNNN";
               for OpenAI, a model name (defaults to "gpt-4o-mini").
    """
    if provider == "tinker":
        if model is None:
            raise ValueError(
                "A Tinker sampler weight path is required when llm_provider='tinker'. "
                "Example: model='tinker://UUID:train:0/sampler_weights/000080'\n"
                "See https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/"
            )
        return _TinkerLLMBackend(model, max_tokens, temperature)
    if provider == "openai":
        return _OpenAILLMBackend(model or "gpt-4o-mini", max_tokens, temperature)
    raise ValueError(f"Unknown provider {provider!r}. Use 'tinker' or 'openai'.")


# ---------------------------------------------------------------------------
# Belief / strategy helpers
# ---------------------------------------------------------------------------

def _dr_is_game_action(text: str) -> bool:
    return bool(re.search(r"<(team|vote|action|merlin_guess)\b", text, re.IGNORECASE))


def _dr_build_hidden_state_table() -> List[Tuple[str, ...]]:
    _, id_to_hid = build_hidden_state_tables()
    return id_to_hid


def _dr_player_evil_probs(
    belief: List[float],
    id_to_hid: List[Tuple[str, ...]],
) -> List[float]:
    """Marginalise the 60-dim belief vector to P(player_i is Evil) for i in 0..4."""
    probs = [0.0] * _NUM_PLAYERS
    for idx, prob in enumerate(belief):
        if prob <= 0.0:
            continue
        for player, role in enumerate(id_to_hid[idx]):
            if role in _DEEPROLE_EVIL:
                probs[player] += prob
    return probs


def _dr_strategy_summary(
    node: Dict[str, Any],
    player: int,
    perspective: int,
) -> Dict[str, Any]:
    """Return {phase, options:[{label, prob}]} for the active CFR node."""
    summary: Dict[str, Any] = {"phase": node.get("type", "unknown"), "options": []}
    if "propose_strat" in node and "propose_options" in node:
        for sp, bits in zip(node["propose_strat"][perspective], node["propose_options"]):
            team = [i for i in range(_NUM_PLAYERS) if (1 << i) & bits]
            summary["options"].append({"label": f"propose{team}", "prob": round(float(sp), 4)})
        summary["phase"] = "propose"
    elif "vote_strat" in node:
        row = node["vote_strat"]
        if isinstance(row, list) and player < len(row) and row[player] is not None:
            for prob, label in zip(row[player][perspective], ("reject", "approve")):
                summary["options"].append({"label": label, "prob": round(float(prob), 4)})
        summary["phase"] = "vote"
    elif "mission_strat" in node:
        ms = node.get("mission_strat")
        if ms and player < len(ms) and ms[player] is not None:
            for prob, label in zip(ms[player][perspective], ("success", "fail")):
                summary["options"].append({"label": label, "prob": round(float(prob), 4)})
        summary["phase"] = "mission"
    return summary


def _dr_format_strategy(summary: Dict[str, Any]) -> str:
    phase = summary.get("phase", "unknown")
    opts  = summary.get("options", [])
    if not opts:
        return f"  phase={phase}, no strategy data available."
    lines = [f"  phase={phase}"]
    for o in sorted(opts, key=lambda x: -x["prob"])[:6]:
        lines.append(f"    {o['label']}: {o['prob']*100:.1f}%")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Minimal prompt construction
# ---------------------------------------------------------------------------

def _dr_build_llm_prompt(
    *,
    player_id: int,
    role: str,
    phase: str,
    game_state: Dict[str, Any],
    player_evil_probs: List[float],
    dr_action: Optional[str],
    observation_text: str,         # kept in signature for API compat, not used in prompt
) -> Tuple[str, str]:
    """
    Build the minimal (system_prompt, user_prompt) pair.

    Design principles
    -----------------
    * Only raw game facts go in — no DeepRole strategy text, no observation
      dump, no action recommendation. This forces the LLM to reason from the
      game state rather than parroting CFR outputs.
    * Evil-probability numbers are included as a *soft background hint*
      (labelled as "prior estimates") but the system prompt explicitly tells
      the model to form its own assessment.
    * Output is constrained to a small JSON object: {belief, message}.
      belief is the LLM's own probability that the current team contains Evil.
    """
    proposal   = game_state.get("team_proposal") or []
    votes_raw  = game_state.get("votes") or {}
    mission_s  = game_state.get("mission_successes", 0)
    mission_f  = game_state.get("mission_failures",  0)
    proposer   = game_state.get("leader_pid", "?")
    team_text  = str(sorted(proposal)) if proposal else "—"
    votes_text = (
        "  ".join(f"P{k}:{v}" for k, v in sorted(votes_raw.items()))
        if votes_raw else "—"
    )
    # Evil probs as a compact background hint only — not a directive.
    evil_hint = "  ".join(f"P{i}:{v:.2f}" for i, v in enumerate(player_evil_probs))

    system_prompt = (
        f"You are playing Avalon as player P{player_id} (role: {role.capitalize()}).\n"
        "Your goal: estimate whether the proposed mission team contains Evil, "
        "and share a brief in-character thought.\n\n"
        "Rules:\n"
        "  - Reason from the game facts below. Do NOT just repeat the prior estimates.\n"
        "  - `belief` is YOUR probability (0–1) that the team contains at least one Evil player.\n"
        "  - `message` is 1–2 sentences, in character, referencing players by number.\n\n"
        "Respond with VALID JSON only, no markdown:\n"
        '  {"belief": <float 0-1>, "message": "<string>"}'
    )

    user_prompt = (
        f"Phase: {phase}  |  Missions: {mission_s}✓ {mission_f}✗  |  Proposer: P{proposer}\n"
        f"Team proposed: {team_text}\n"
        f"Votes:         {votes_text}\n"
        f"Prior P(Evil): {evil_hint}  [background only — form your own view]\n"
    )

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _dr_parse_llm_result(result: LLMResult) -> Tuple[float, str]:
    """
    Parse an LLMResult into (belief, message).
    Falls back gracefully on malformed JSON; returns (0.5, "") as last resort.
    """
    raw     = result.text
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        data    = json.loads(cleaned)
        belief  = max(0.0, min(1.0, float(data.get("belief", 0.5))))
        message = str(data.get("message", "")).strip()
        return belief, message
    except (json.JSONDecodeError, ValueError, TypeError):
        m  = re.search(r'"belief"\s*:\s*([0-9.]+)', raw)
        m2 = re.search(r'"message"\s*:\s*"([^"]*)"', raw)
        belief  = max(0.0, min(1.0, float(m.group(1)))) if m else 0.5
        message = m2.group(1) if m2 else raw[:200]
        return belief, message

"""
deeprole_llm.py — support layer for DeepRoleLLMAgent.

LLM backend
-----------
Uses a locally-loaded HuggingFace / TRL-trained model for inference.
TRL produces standard AutoModelForCausalLM checkpoints (full fine-tune or
PEFT/LoRA adapters); this backend loads either form and runs generation via
transformers.generate() with output_scores=True, giving native per-token
logprobs without any external API.

Logprobs
--------
generate() returns a tuple `scores` of length T (one tensor per generated
token, shape [batch, vocab]).  For each position we:
  1. log_softmax the raw logits → log-probabilities over the vocab
  2. take the argmax (= the chosen token) and record its logprob
  3. take the top-K alternatives via torch.topk

The result is stored as List[TokenLogprob] in LLMResult.logprobs and
exposed as agent.last_logprobs after every call.

Prompt format
-------------
Minimal — only raw game facts, no DeepRole strategy dump, no observation
excerpt.  Evil-probability hint is included as a soft background label with
an explicit instruction to form an independent view.

Public surface used by basic_agents.py
---------------------------------------
  _InstrumentedDeepRoleIntegrator
  _TRLLLMBackend
  _dr_make_llm_backend(provider, model_name_or_path, max_new_tokens,
                        temperature, *, adapter_path, device, load_in_8bit,
                        load_in_4bit, top_logprobs)
  _dr_build_hidden_state_table()
  _dr_player_evil_probs(belief, id_to_hid)
  _dr_strategy_summary(node, player, perspective)
  _dr_format_strategy(summary)
  _dr_build_llm_prompt(*, player_id, role, phase, game_state,
                         player_evil_probs, dr_action, observation_text)
  dr_parse_llm_result(result)   -> (belief, message)
  _dr_is_game_action(text)
  LLMResult
  TokenLogprob
"""

from __future__ import annotations

import json
import math
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
_NUM_HIDDEN_STATES = 60   # 5 × 4 × 3 ordered (merlin, assassin, minion)
_DEFAULT_TOP_K     = 5    # top-K alternative tokens to record per position


# ---------------------------------------------------------------------------
# Logprob / result data types
# ---------------------------------------------------------------------------

@dataclass
class TokenLogprob:
    """Logprob data for a single generated token."""
    token:        str
    logprob:      float                          # log-probability of chosen token
    top_logprobs: List[Tuple[str, float]] = field(default_factory=list)
    """Top-K (token, logprob) alternatives at this position."""


@dataclass
class LLMResult:
    """Return value from every backend .call()."""
    text:     str
    logprobs: List[TokenLogprob] = field(default_factory=list)
    """Per-token logprob data; empty when the model does not provide scores."""


# ---------------------------------------------------------------------------
# Instrumented integrator
# ---------------------------------------------------------------------------

class _InstrumentedDeepRoleIntegrator(DeepRoleIntegrator):
    """
    Thin subclass that mirrors DeepRoleIntegrator's private state into
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
        self.exposed_belief:      List[float]    = [1.0 / _NUM_HIDDEN_STATES] * _NUM_HIDDEN_STATES
        self.exposed_perspective: int            = 0
        self.exposed_node:        Dict[str, Any] = {}
        self.exposed_player:      int            = 0
        self.exposed_role:        str            = "servant"
        self.exposed_dr_action:   Optional[str]  = None

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
# TRL / transformers local inference backend
# ---------------------------------------------------------------------------

class _TRLLLMBackend:
    """
    Local inference backend for TRL-trained (or any HuggingFace) models.

    Loads the model once at construction time using AutoModelForCausalLM
    (full fine-tune) or PeftModel (LoRA/adapter checkpoints produced by TRL's
    SFTTrainer / GRPOTrainer / etc.).  Generation uses transformers.generate()
    with output_scores=True so native per-token logprobs are available.

    Parameters
    ----------
    model_name_or_path : str
        HuggingFace Hub name (e.g. "Qwen/Qwen3-0.6B") or local directory
        path to the fine-tuned / TRL-trained model checkpoint.
    max_new_tokens : int
        Maximum tokens to generate (default 128).
    temperature : float
        Sampling temperature (default 0.7).  Set to 0.0 for greedy decoding.
    adapter_path : str | None
        Path to a PEFT/LoRA adapter directory produced by TRL.  When set, the
        base model at model_name_or_path is loaded first, then the adapter is
        applied on top via PeftModel.from_pretrained().
    device : str
        "cuda", "cpu", or "auto" (default "auto" — uses GPU if available).
    load_in_8bit : bool
        Load the base model in 8-bit via bitsandbytes (reduces VRAM).
    load_in_4bit : bool
        Load in 4-bit (QLoRA style).  Takes priority over load_in_8bit.
    top_logprobs : int
        Number of top alternative tokens to record per position (default 5).
    """

    def __init__(
        self,
        model_name_or_path: str,
        max_new_tokens: int  = 128,
        temperature: float   = 0.7,
        adapter_path: Optional[str] = None,
        device: str          = "auto",
        load_in_8bit: bool   = False,
        load_in_4bit: bool   = False,
        top_logprobs: int    = _DEFAULT_TOP_K,
    ):
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        except ImportError:
            raise ImportError(
                "transformers and torch are required for _TRLLLMBackend.\n"
                "Install with: pip install transformers torch"
            )

        self.max_new_tokens = max_new_tokens
        self.temperature    = temperature
        self.top_logprobs   = top_logprobs
        self._torch         = torch

        # --- resolve device ------------------------------------------------
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # --- quantisation config -------------------------------------------
        bnb_config = None
        if load_in_4bit or load_in_8bit:
            try:
                from transformers import BitsAndBytesConfig as BnB
                if load_in_4bit:
                    bnb_config = BnB(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
                else:
                    bnb_config = BnB(load_in_8bit=True)
            except Exception as e:
                raise ImportError(
                    f"bitsandbytes is required for quantisation. "
                    f"Install with: pip install bitsandbytes\nOriginal error: {e}"
                )

        # --- load tokenizer ------------------------------------------------
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name_or_path, padding_side="left"
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # --- load base model -----------------------------------------------
        model_kwargs: Dict[str, Any] = {"quantization_config": bnb_config} if bnb_config else {}
        if bnb_config:
            # BnB handles placement; don't also set device_map to a plain string
            model_kwargs["device_map"] = "auto"
        else:
            model_kwargs["device_map"] = self.device

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name_or_path, **model_kwargs
        )

        # --- optionally apply PEFT/LoRA adapter ----------------------------
        if adapter_path:
            try:
                from peft import PeftModel
            except ImportError:
                raise ImportError(
                    "peft is required to load LoRA adapters.\n"
                    "Install with: pip install peft"
                )
            self.model = PeftModel.from_pretrained(self.model, adapter_path)

        self.model.eval()

    # ------------------------------------------------------------------
    # Chat template helpers
    # ------------------------------------------------------------------

    def _build_input_ids(self, system: str, user: str):
        """
        Apply the model's chat template (if available) or fall back to a
        simple system + user concatenation.
        Returns (input_ids tensor on self.device, attention_mask tensor).
        """
        messages = [
            {"role": "system",  "content": system},
            {"role": "user",    "content": user},
        ]
        if getattr(self.tokenizer, "chat_template", None):
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            text = f"{system}\n\nUser: {user}\nAssistant:"

        enc = self.tokenizer(text, return_tensors="pt", padding=True)
        input_ids      = enc["input_ids"].to(self.device)
        attention_mask = enc["attention_mask"].to(self.device)
        return input_ids, attention_mask

    # ------------------------------------------------------------------
    # Core call
    # ------------------------------------------------------------------

    def call(self, system: str, user: str) -> LLMResult:
        import torch
        import torch.nn.functional as F

        input_ids, attention_mask = self._build_input_ids(system, user)
        prompt_len = input_ids.shape[1]

        gen_kwargs: Dict[str, Any] = dict(
            attention_mask      = attention_mask,
            max_new_tokens      = self.max_new_tokens,
            do_sample           = self.temperature > 0.0,
            output_scores       = True,
            return_dict_in_generate = True,
            pad_token_id        = self.tokenizer.pad_token_id,
        )
        if self.temperature > 0.0:
            gen_kwargs["temperature"] = self.temperature

        with torch.no_grad():
            outputs = self.model.generate(input_ids, **gen_kwargs)

        # Decode only the newly generated tokens
        generated_ids = outputs.sequences[0][prompt_len:]
        text = self.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

        # Build logprob list from outputs.scores
        # scores: tuple of T tensors, each shape [1, vocab_size] (raw logits)
        logprobs: List[TokenLogprob] = []
        for step_idx, (token_id, score_tensor) in enumerate(
            zip(generated_ids.tolist(), outputs.scores)
        ):
            log_probs = F.log_softmax(score_tensor[0], dim=-1)   # [vocab]

            chosen_lp = float(log_probs[token_id].item())
            chosen_tok = self.tokenizer.decode([token_id])

            # top-K alternatives
            topk_lp, topk_ids = torch.topk(log_probs, k=min(self.top_logprobs, log_probs.shape[0]))
            tops = [
                (self.tokenizer.decode([tid.item()]), float(lp.item()))
                for tid, lp in zip(topk_ids, topk_lp)
            ]

            logprobs.append(TokenLogprob(
                token        = chosen_tok,
                logprob      = chosen_lp,
                top_logprobs = tops,
            ))

        return LLMResult(text=text, logprobs=logprobs)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _dr_make_llm_backend(
    model_name_or_path: str,
    max_new_tokens: int  = 128,
    temperature: float   = 0.7,
    adapter_path: Optional[str] = None,
    device: str          = "auto",
    load_in_8bit: bool   = False,
    load_in_4bit: bool   = False,
    top_logprobs: int    = _DEFAULT_TOP_K,
) -> _TRLLLMBackend:
    """
    Construct and return a _TRLLLMBackend.

    Parameters
    ----------
    model_name_or_path : str
        HuggingFace Hub name or local path to any TRL-trained (or base) model.
    max_new_tokens : int    Max tokens to generate (default 128).
    temperature : float     Sampling temperature (default 0.7; 0 = greedy).
    adapter_path : str|None Path to a PEFT/LoRA adapter directory (optional).
    device : str            "cuda" | "cpu" | "auto" (default).
    load_in_8bit : bool     8-bit BnB quantisation.
    load_in_4bit : bool     4-bit QLoRA quantisation (takes priority).
    top_logprobs : int      Top-K alternatives to record per token (default 5).
    """
    return _TRLLLMBackend(
        model_name_or_path = model_name_or_path,
        max_new_tokens     = max_new_tokens,
        temperature        = temperature,
        adapter_path       = adapter_path,
        device             = device,
        load_in_8bit       = load_in_8bit,
        load_in_4bit       = load_in_4bit,
        top_logprobs       = top_logprobs,
    )


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
    """Marginalise the 60-dim belief → P(player_i is Evil) for i in 0..4."""
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
# Minimal prompt
# ---------------------------------------------------------------------------

def _dr_build_llm_prompt(
    *,
    player_id: int,
    role: str,
    phase: str,
    game_state: Dict[str, Any],
    player_evil_probs: List[float],
    dr_action: Optional[str],
    observation_text: str,       # kept in signature for API compat, not injected
) -> Tuple[str, str]:
    """
    Build a minimal (system_prompt, user_prompt) pair.

    Only raw game facts are included.  The evil-probability vector is provided
    as a labelled background hint but the system prompt instructs the model not
    to echo it — forcing independent reasoning.
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
    evil_hint  = "  ".join(f"P{i}:{v:.2f}" for i, v in enumerate(player_evil_probs))

    system_prompt = (
        f"You are playing Avalon as player P{player_id} (role: {role.capitalize()}).\n"
        "Estimate whether the proposed team contains Evil and share a brief in-character thought.\n\n"
        "Rules:\n"
        "  - Reason from the facts below. Do NOT simply echo the prior estimates.\n"
        "  - `belief` is YOUR probability (0–1) that the team contains at least one Evil player.\n"
        "  - `message` is 1–2 sentences in character, referencing players by number.\n\n"
        "Respond with valid JSON only, no markdown:\n"
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

def dr_parse_llm_result(result: LLMResult) -> Tuple[float, str]:
    """Parse LLMResult → (belief, message).  Graceful fallback on bad JSON."""
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
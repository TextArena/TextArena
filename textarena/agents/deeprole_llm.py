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

Guess-Merlin additions
----------------------
  _dr_is_guess_merlin_phase(game_state, observation_text)
  _dr_player_merlin_probs(belief, id_to_hid)
  _dr_get_evil_teammate(belief, id_to_hid, self_pid)
  _dr_build_merlin_guess_prompt(...)
  dr_parse_merlin_guess(raw, num_players, exclude)
  _dr_heuristic_merlin_guess(merlin_probs, exclude)
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
        "Vote on the proposed team and share a brief in-character thought.\n\n"
        "Rules:\n"
        "  - `vote` is exactly one of: \"approve\" or \"reject\". No other values.\n"
        "  - `belief` is YOUR probability (0–1) that the team contains at least one Evil player.\n"
        "  - `message` is 1–2 sentences in character, referencing players by number.\n"
        "  - Reason from the facts below. Do NOT simply echo the prior estimates.\n\n"
        "Respond with valid JSON only, no markdown.  Use this key order:\n"
        '  {"vote": "approve" | "reject", "belief": <float 0-1>, "message": "<string>"}'
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


# ---------------------------------------------------------------------------
# Merlin-guess phase: detection, marginalisation, prompt, lenient parser,
# heuristic fallback. All scoped to keep the generic belief+message path
# above untouched.
# ---------------------------------------------------------------------------

def _dr_is_guess_merlin_phase(
    game_state: Dict[str, Any],
    observation_text: str = "",
) -> bool:
    """True if the turn is the Guess-Merlin end-game.

    Priority: trust the parsed game_state signal when we have it. Fall back
    to the observation text ONLY by matching the exact phase-label line
    emitted by the engine ('Phase: Guess-Merlin') — an earlier, looser
    check for the substring 'guess merlin' matched the rules-header text
    ('5. Guess Merlin Phase (end condition):') that is present on every
    turn, which caused this function to return True everywhere and broke
    voting, proposal, and mission phases.
    """
    if game_state.get("guess_merlin_phase") is True:
        return True
    phase = (game_state.get("phase") or "").lower()
    if "guess" in phase and "merlin" in phase:
        return True
    # Engine-emitted phase line, lower-cased. Uses a regex anchor so it
    # cannot match inside prose (e.g. the rules header).
    return bool(
        re.search(r"(?im)^\s*phase\s*:\s*guess-merlin\s*$", observation_text or "")
    )


def _dr_player_merlin_probs(
    belief: List[float],
    id_to_hid: List[Tuple[str, ...]],
) -> List[float]:
    """Marginalise the 60-dim belief → P(player_i is Merlin)."""
    probs = [0.0] * _NUM_PLAYERS
    for idx, prob in enumerate(belief):
        if prob <= 0.0:
            continue
        hs = id_to_hid[idx]
        for pid, role in enumerate(hs):
            if role == "merlin":
                probs[pid] += prob
                break
    return probs


def _dr_get_evil_teammate(
    belief: List[float],
    id_to_hid: List[Tuple[str, ...]],
    self_pid: int,
) -> Optional[int]:
    """From Evil's filtered belief, return the teammate pid (or None).

    DeepRole filters an Evil player's belief to hidden states consistent with
    their own knowledge, so every nonzero state agrees on who the teammate is.
    """
    for idx, prob in enumerate(belief):
        if prob <= 0.0:
            continue
        for pid, role in enumerate(id_to_hid[idx]):
            if pid != self_pid and role in _DEEPROLE_EVIL:
                return pid
        break
    return None


_MERLIN_GUESS_PATTERNS: List[str] = [
    r"<merlin[_\s-]?guess>\s*(\d+)\s*</merlin[_\s-]?guess>",   # spec
    r"<guess>\s*(\d+)\s*</guess>",                              # wrong tag
    r"merlin[_\s-]?guess[:\s=]+(\d+)",                          # "merlin_guess: 3"
    r"merlin\s+is\s+(?:player|p)?\s*#?\s*(\d+)",                # "Merlin is P3"
    r"(?:player|p)\s*#?\s*(\d+)\s*(?:is|=|:)\s*merlin",         # "P3 is Merlin"
    r"(?:my\s+)?(?:final\s+)?(?:guess|answer)[:\s=]+(?:player|p)?\s*#?\s*(\d+)",
    r"\bp(?:layer)?\s*#?\s*(\d+)\b",                            # "Player 3"
    r"^\s*(\d+)\s*$",                                           # bare "3"
]


def dr_parse_merlin_guess(
    raw: str,
    num_players: int = _NUM_PLAYERS,
    exclude: Optional[set] = None,
) -> Optional[int]:
    """Extract a valid player id from raw LLM text. Returns None if none found.

    Patterns are tried in order of specificity so the canonical
    <merlin_guess> tag wins when present, and looser phrasings act as
    fallbacks for a 4-bit model that drops structure.
    """
    if not raw:
        return None
    exclude = exclude or set()
    for pat in _MERLIN_GUESS_PATTERNS:
        for m in re.finditer(pat, raw, re.IGNORECASE | re.MULTILINE):
            try:
                pid = int(m.group(1))
            except (ValueError, IndexError):
                continue
            if 0 <= pid < num_players and pid not in exclude:
                return pid
    return None


def _dr_heuristic_merlin_guess(
    merlin_probs: List[float],
    exclude: Optional[set] = None,
) -> int:
    """Argmax of P(Merlin) over non-excluded players; uniform tiebreak."""
    exclude = exclude or set()
    best_pid, best_prob = -1, -1.0
    for pid, prob in enumerate(merlin_probs):
        if pid in exclude:
            continue
        if prob > best_prob:
            best_prob, best_pid = prob, pid
    if best_pid == -1:
        for pid in range(len(merlin_probs)):
            if pid not in exclude:
                return pid
    return best_pid


def _dr_build_merlin_guess_prompt(
    *,
    player_id: int,
    role: str,
    teammate_id: Optional[int],
    candidates: List[int],
    merlin_probs: List[float],
    game_state: Dict[str, Any],
    observation_text: str = "",
) -> Tuple[str, str]:
    """Dedicated system/user prompt for the Guess-Merlin turn.

    The system prompt enumerates valid candidates so the model can only pick
    Good players that are not itself and not its teammate; it also shows the
    required output format with a concrete example. When ``observation_text``
    is supplied, a trimmed game-history summary is included so the model has
    something concrete to reason about — without it the LLM falls back on
    the (often uniform) CFR prior and the answer is effectively random.
    """
    mission_s = game_state.get("mission_successes", 3)
    mission_f = game_state.get("mission_failures",  0)

    team_line = f"You are P{player_id} (Evil, role: {role.capitalize()})."
    if teammate_id is not None:
        team_line += f" Your Evil teammate is P{teammate_id}."
    else:
        team_line += " You could not identify your teammate from game state."

    prior_line = "  ".join(f"P{pid}:{merlin_probs[pid]:.2f}" for pid in candidates)
    history = _dr_extract_history_for_merlin(observation_text)

    system_prompt = (
        f"{team_line}\n"
        f"Good succeeded {mission_s} missions ({mission_f} failed). "
        f"Evil gets ONE guess at Merlin.\n"
        f"Valid candidates: {candidates}.\n\n"
        "Merlin knows who Evil is and tends to: reject teams that include "
        "Evil players, approve clean teams, and avoid being too obvious. "
        "Look for the Good player whose votes best fit that pattern.\n\n"
        "Respond with EXACTLY this format and nothing else:\n"
        "<merlin_guess>N</merlin_guess>\n"
        f"where N is one of {candidates}.\n\n"
        f"Example: <merlin_guess>{candidates[0] if candidates else 0}</merlin_guess>"
    )
    user_prompt = (
        f"Prior P(Merlin) from CFR: {prior_line}\n\n"
        f"Game history:\n{history}\n\n"
        f"Pick from {candidates}. Output ONLY the <merlin_guess> tag."
    )
    return system_prompt, user_prompt


def _dr_is_belief_informative(
    belief: List[float],
    tolerance: float = 1e-3,
) -> bool:
    """True if the belief is meaningfully non-uniform.

    DeepRole's initial prior is 1/60 spread across 60 hidden states. When
    the integrator has not successfully updated the belief (binary missing,
    skipped phases, etc.), it stays uniform and any quantity derived from
    it — teammate inference, P(Merlin) argmax — just picks whichever
    permutation happens to come first. Treat those as noise and route
    around them.
    """
    if not belief:
        return False
    n = len(belief)
    if n == 0:
        return False
    uniform = 1.0 / n
    return max(abs(float(b) - uniform) for b in belief) > tolerance


def _dr_parse_teammate_from_obs(
    obs_text: str,
    self_pid: int,
) -> Optional[int]:
    """Best-effort teammate extraction from the observation string.

    Tries, in order:
      1. Multiple ``<player_state>`` tags — if the observation contains
         another tag for a player with an Evil role, that's the teammate.
      2. Prose mentions ('Your teammate is Player N', 'Minion is P3', ...).
      3. Bracketed lists ('Other Evil players: [3]', 'Evil team: [1,3]').

    Returns None if no signal is found. A None return is treated by the
    caller as 'teammate unknown — only exclude self,' which is strictly
    safer than excluding a wrongly-guessed teammate (since that could
    remove the real Merlin from the candidate set).
    """
    if not obs_text:
        return None
    evil_roles = {"morgana", "mordred", "minion", "assassin", "oberon"}

    # (1) Additional <player_state> tags with an Evil role.
    for m in re.finditer(
        r"<player_state>\s*(\{.*?\})\s*</player_state>",
        obs_text, re.IGNORECASE | re.DOTALL
    ):
        try:
            data = json.loads(m.group(1))
            pid = int(data.get("pid", -1))
            rname = str(data.get("role", "")).lower()
            if pid != self_pid and rname in evil_roles:
                return pid
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    # (2) Prose mentions.
    for pat in (
        r"teammates?[^\n]*?(?:player\s+|p\s*#?\s*)(\d+)",
        r"(?:fellow|other)\s+evil[^\n]*?(?:player\s+|p\s*#?\s*)(\d+)",
        r"(?:morgana|minion|mordred|assassin)\s+is\s+(?:player\s+|p\s*#?\s*)(\d+)",
    ):
        for m in re.finditer(pat, obs_text, re.IGNORECASE):
            try:
                pid = int(m.group(1))
                if 0 <= pid < 10 and pid != self_pid:
                    return pid
            except ValueError:
                continue

    # (3) Bracketed lists.
    m = re.search(
        r"(?:other\s+evil|evil\s+(?:players?|team)|fellow\s+minions?)"
        r"[^\[\]]*\[([\d,\s]+)\]",
        obs_text, re.IGNORECASE
    )
    if m:
        for num_str in m.group(1).split(","):
            try:
                pid = int(num_str.strip())
                if pid != self_pid:
                    return pid
            except ValueError:
                continue

    return None


def _dr_extract_history_for_merlin(
    obs_text: str,
    max_len: int = 2000,
) -> str:
    """Produce a trimmed, LLM-readable game-history summary from the obs.

    Keeps lines that mention team proposals, votes, and mission outcomes;
    drops the rules boilerplate and large JSON state blobs. Tail-trimmed
    to ``max_len`` chars so the most recent events survive when the obs
    exceeds the budget.
    """
    if not obs_text:
        return "(no history available)"

    keep: List[str] = []
    for ln in obs_text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("<game_state>") or ln.startswith("<player_state>"):
            continue
        if "Gameplay Rules" in ln or "Guess Merlin Phase (end condition)" in ln:
            continue
        lo = ln.lower()
        if any(kw in lo for kw in (
            "team", "vote", "mission", "proposal", "approve", "reject",
            "success", "fail", "leader", "player"
        )):
            keep.append(ln)

    summary = "\n".join(keep)
    if len(summary) > max_len:
        summary = summary[-max_len:]
    return summary or "(no relevant history)"
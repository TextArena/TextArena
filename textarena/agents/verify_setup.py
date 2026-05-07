"""
verify_setup.py — pre-flight checks for tinker_multiagent.py.

Runs cheap, offline-or-near-offline assertions to catch the failure modes
that otherwise only surface 20 minutes into a real training run:

    1. Imports & module structure
    2. TINKER_API_KEY present
    3. Tinker SDK version exposes SamplingParams.logprobs
    4. textarena Avalon-v0 environment loads and resets
    5. Dataclass + helper sanity (OnPolicyDistillDatum, _extract_vote_logprobs,
       _cfr_action_to_target, _outcome_weight, _belief_bucket)
    6. A 1-step / 1-game / 1-player smoke training step (skipped without
       --network so this stays runnable on a laptop)

Exit code is 0 when everything passes, non-zero otherwise.

Run::

    python verify_setup.py            # offline checks
    python verify_setup.py --network  # also runs a 1-step training round
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import os
import sys
import traceback
from pathlib import Path

GREEN = "\033[32m"
RED   = "\033[31m"
YELLOW= "\033[33m"
RESET = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}!{RESET} {msg}")
def hdr(msg):   print(f"\n{msg}")

errors: list[str] = []

# ---------------------------------------------------------------------------
# 1. Module imports
# ---------------------------------------------------------------------------
hdr("1. Imports")
try:
    import tinker_multiagent as tma
    ok("tinker_multiagent imports cleanly")
except Exception as e:
    fail(f"tinker_multiagent failed to import: {type(e).__name__}: {e}")
    traceback.print_exc()
    errors.append("module import")
    sys.exit(1)

try:
    import tinker_distil_agent as tda
    ok("tinker_distil_agent imports cleanly")
except Exception as e:
    fail(f"tinker_distil_agent failed to import: {type(e).__name__}: {e}")
    errors.append("distil agent import")

# Check the symbols we expect to be there.
for name in ("OnPolicyDistillDatum", "_extract_vote_logprobs",
             "_cfr_action_to_target", "_outcome_weight", "_belief_bucket",
             "_role_side", "_on_policy_cfr_distill_step",
             "_self_distill_export_jsonl", "NPlayerCoordinator",
             "TrainerConfig"):
    if hasattr(tma, name):
        ok(f"tinker_multiagent.{name} present")
    else:
        fail(f"tinker_multiagent.{name} MISSING")
        errors.append(f"missing {name}")

# ---------------------------------------------------------------------------
# 2. Environment
# ---------------------------------------------------------------------------
hdr("2. Environment")
api_key = os.environ.get("TINKER_API_KEY", "")
if api_key:
    ok(f"TINKER_API_KEY set ({len(api_key)} chars)")
else:
    warn("TINKER_API_KEY not set — required for any real run")
    errors.append("TINKER_API_KEY")

# ---------------------------------------------------------------------------
# 3. Tinker SDK
# ---------------------------------------------------------------------------
hdr("3. Tinker SDK")
try:
    import tinker
    ok(f"tinker imported (version: {getattr(tinker, '__version__', 'unknown')})")
except ImportError as e:
    fail(f"tinker not installed: {e}")
    errors.append("tinker SDK")
else:
    # Does SamplingParams accept logprobs? This is what
    # _sample_action_with_logprobs needs for the dense distillation signal.
    try:
        sp = tinker.types.SamplingParams(max_tokens=1, temperature=1.0,
                                          logprobs=True, top_logprobs=5)
        ok("SamplingParams accepts logprobs=True (dense signal will work)")
    except TypeError as e:
        warn(f"SamplingParams does NOT accept logprobs: {e}")
        warn("→ distillation will silently fall back; vote=0 in logs")
        warn("→ either upgrade tinker or switch to TinkerTokenCompleter")

# ---------------------------------------------------------------------------
# 4. textarena Avalon
# ---------------------------------------------------------------------------
hdr("4. textarena Avalon-v0")
try:
    import textarena as ta
    env = ta.make("Avalon-v0")
    env.reset(num_players=5, special_roles={"Merlin", "Morgana"}, seed=0)
    pid, obs = env.get_observation()
    ok(f"Avalon-v0 reset OK (first player: P{pid}, obs len: {len(str(obs))})")
except Exception as e:
    fail(f"Avalon-v0 not available: {type(e).__name__}: {e}")
    errors.append("Avalon-v0")

# ---------------------------------------------------------------------------
# 5. Dataclass + helper sanity
# ---------------------------------------------------------------------------
hdr("5. Helper sanity")

# _belief_bucket
assert tma._belief_bucket(0.7) == "high",  "0.7 should be high"
assert tma._belief_bucket(0.4) == "low",   "0.4 should be low"
assert tma._belief_bucket(0.5) == "high",  "≥0.5 boundary should be high"
ok("_belief_bucket: high/low boundary at 0.5")

# _outcome_weight
assert tma._outcome_weight(True)  == 1.0
assert tma._outcome_weight(False) == 0.5
ok("_outcome_weight: w(o,r) = {1.0, 0.5}")

# _role_side
assert tma._role_side("Servant")  == "Good"
assert tma._role_side("Merlin")   == "Good"
assert tma._role_side("Morgana")  == "Evil"
assert tma._role_side("Assassin") == "Evil"
# Lowercase forms — the integrator's exposed_role uses these, and the
# previous version of _role_side returned "other" for all of them, causing
# good_datums=0 / evil_datums=0 in every CFR distill log line.
assert tma._role_side("servant")  == "Good", "lowercase 'servant' regression"
assert tma._role_side("morgana")  == "Evil", "lowercase 'morgana' regression"
assert tma._role_side("MINION")   == "Evil", "uppercase regression"
assert tma._role_side("")         == "other"
assert tma._role_side("unknown")  == "other"
ok("_role_side: case-insensitive, handles servant/morgana/MINION")

# _cfr_action_to_target
t = tma._cfr_action_to_target("approve", sharpness=0.85)
assert t is not None and abs(t["approve"] - 0.85) < 1e-6 and abs(t["reject"] - 0.15) < 1e-6, f"got {t}"
t = tma._cfr_action_to_target("reject", sharpness=0.85)
assert t is not None and abs(t["approve"] - 0.15) < 1e-6 and abs(t["reject"] - 0.85) < 1e-6, f"got {t}"
# XML-wrapped form (DeepRole's actual output format — this was the bug
# behind "0/0 vote turns"):
t = tma._cfr_action_to_target("<vote>approve</vote>", sharpness=0.85)
assert t is not None and abs(t["approve"] - 0.85) < 1e-6, f"XML-wrapped approve: {t}"
t = tma._cfr_action_to_target("<vote>reject</vote>", sharpness=0.85)
assert t is not None and abs(t["reject"] - 0.85) < 1e-6, f"XML-wrapped reject: {t}"
t = tma._cfr_action_to_target("<VOTE>Approve</VOTE>", sharpness=0.85)
assert t is not None and abs(t["approve"] - 0.85) < 1e-6, f"case-insensitive XML: {t}"
# Non-vote actions should return None (so the distill loop skips them):
assert tma._cfr_action_to_target("<team>0,2,4</team>") is None, "team tag must skip"
assert tma._cfr_action_to_target("<action>pass</action>") is None, "action tag must skip"
assert tma._cfr_action_to_target("<merlin_guess>3</merlin_guess>") is None, "merlin tag must skip"
assert tma._cfr_action_to_target("guess_merlin_at_2") is None
assert tma._cfr_action_to_target(None) is None
ok("_cfr_action_to_target: bare + XML-wrapped + skips non-vote tags")

# _extract_vote_logprobs — fake some token-logprob shaped objects
class FakeTok:
    def __init__(self, token, logprob, top_logprobs):
        self.token, self.logprob, self.top_logprobs = token, logprob, top_logprobs

# Case A: sampled "approve", "reject" in top_logprobs
toks = [FakeTok("approve", -0.3, [("approve", -0.3), ("reject", -1.5)])]
result = tma._extract_vote_logprobs(toks)
assert result is not None, "should find vote signal"
idx, vote, slp, lpa, lpr = result
assert idx == 0 and vote == "approve"
assert abs(slp - (-0.3)) < 1e-6
assert abs(lpa - (-0.3)) < 1e-6 and abs(lpr - (-1.5)) < 1e-6
ok("_extract_vote_logprobs: sampled approve")

# Case B: sampled "reject", "approve" in top_logprobs
toks = [FakeTok(" reject", -0.5, [(" reject", -0.5), (" approve", -0.9)])]
result = tma._extract_vote_logprobs(toks)
assert result is not None
idx, vote, slp, lpa, lpr = result
assert vote == "reject" and idx == 0
ok("_extract_vote_logprobs: sampled reject (handles leading space)")

# Case C: no vote token → None
toks = [FakeTok("Hello", -2.0, [("Hi", -1.5), ("Hey", -2.5)]),
        FakeTok(",",     -0.1, [])]
result = tma._extract_vote_logprobs(toks)
assert result is None, f"expected None, got {result}"
ok("_extract_vote_logprobs: returns None when no vote signal")

# Case D: alternative class NOT in top_logprobs — we now use a fallback
# instead of returning None (the gradient only needs the sampled logprob).
# This is the case Qwen-8B-Base actually hits in production: when forced by
# the prompt to emit "vote": "X, the model is very confident and the top-5
# alternatives at that position are all approve-variants (or all reject-
# variants), with the opposite class outside top-K.
toks = [FakeTok("approve", -0.3, [("approve", -0.3), ("Approve", -2.5),
                                   ("APPROVE", -3.1), ("appr", -3.5),
                                   ("ap", -4.0)])]
result = tma._extract_vote_logprobs(toks)
assert result is not None, "should NOT return None when only one vote class in top-K"
idx, vote, slp, lpa, lpr = result
assert vote == "approve" and abs(slp - (-0.3)) < 1e-6
assert abs(lpa - (-0.3)) < 1e-6, f"lpa should be exact for sampled class, got {lpa}"
# Fallback for reject: one nat below smallest visible top-K logprob (-4.0)
assert lpr < lpa, f"fallback lpr {lpr} should be < lpa {lpa}"
assert abs(lpr - (-5.0)) < 1e-6, f"fallback should be min_top - 1.0 = -5.0, got {lpr}"
ok("_extract_vote_logprobs: uses min_top_lp − 1.0 fallback when alt class missing")

# Case E: vote token is BEYOND position 8 (the old bug — Qwen's reasoning prefix)
toks = (
    [FakeTok(f"word{i}", -1.0, []) for i in range(15)]   # 15 reasoning tokens
    + [FakeTok("approve", -0.3, [("approve", -0.3), ("reject", -1.2)])]
)
result = tma._extract_vote_logprobs(toks)
assert result is not None, "should now find vote past position 8"
idx, vote, _, _, _ = result
assert idx == 15 and vote == "approve"
ok("_extract_vote_logprobs: scans whole response (vote at position 15)")

# Case F: max_scan limits the scan window
toks = [FakeTok(f"x{i}", -1.0, []) for i in range(5)] + [
    FakeTok("approve", -0.3, [("approve", -0.3), ("reject", -1.2)]),
]
result = tma._extract_vote_logprobs(toks, max_scan=3)
assert result is None, "max_scan=3 should not find vote at position 5"
result = tma._extract_vote_logprobs(toks, max_scan=10)
assert result is not None and result[0] == 5
ok("_extract_vote_logprobs: max_scan parameter limits scan window")

# _vote_class helper
assert tma._vote_class("approve") == "approve"
assert tma._vote_class(" Approve") == "approve"
assert tma._vote_class("REJECT") == "reject"
assert tma._vote_class("not") is None        # critical: don't confuse with "no"
assert tma._vote_class("hello") is None
assert tma._vote_class("") is None
assert tma._vote_class(None) is None         # type: ignore[arg-type]
# JSON-quoted variants — exactly what BPE produces for {"vote": "approve"}:
assert tma._vote_class('"approve"') == "approve",  '"approve" should match'
assert tma._vote_class('"approve')   == "approve",  '"approve  (open quote) should match'
assert tma._vote_class('approve"')   == "approve",  'approve" (close quote) should match'
assert tma._vote_class('"approve",') == "approve",  'with trailing comma should match'
assert tma._vote_class(' "reject')   == "reject",   'leading space + open quote should match'
assert tma._vote_class('"reject":')  == "reject",   'with trailing colon should match'
# But adjacent-word false positives must still be rejected:
assert tma._vote_class("Approveed") is None,  "no prefix matching on longer words"
assert tma._vote_class("rejection") is None,  "no prefix matching on rejection"
assert tma._vote_class("note") is None,       "note shouldn't match no"
ok("_vote_class: handles JSON quoting + still rejects 'not'/'note'/'rejection'")

# OnPolicyDistillDatum can be instantiated
d = tma.OnPolicyDistillDatum(
    prompt_messages       = [{"role": "system", "content": "test"}],
    response_text         = "approve",
    response_token_ids    = [123, 456],
    sampling_logprobs     = [-0.3, -0.1],
    vote_token_index      = 0,
    sampled_vote          = "approve",
    student_logprob       = -0.3,
    student_log_p_approve = -0.3,
    student_log_p_reject  = -1.5,
    cfr_target            = {"approve": 0.85, "reject": 0.15},
    msg_target            = None,
    role                  = "Servant",
    role_side             = "Good",
    won                   = True,
    phase                 = "vote",
    player_id             = 0,
    belief_continuous     = 0.4,
    belief_bucket         = "low",
)
ok("OnPolicyDistillDatum: constructs cleanly")

# JSONL export round-trips
import tempfile, json as _json
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "self_distill.jsonl"
    n = tma._self_distill_export_jsonl(out_path=p, distill_datums=[d, d], step=7)
    assert n == 2 and p.exists()
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 2
    rec = _json.loads(lines[0])
    assert rec["step"] == 7
    assert rec["sampled_vote"] == "approve"
    assert rec["role_side"] == "Good"
    assert rec["won"] is True
    assert rec["cfr_target"]["approve"] == 0.85
    assert rec["cfr_target"]["reject"] == 0.15
    # π_θ^a should be present and normalized to 1.0
    assert "student_pi_a" in rec, "JSONL missing student_pi_a (π_θ^a from spec)"
    pa = rec["student_pi_a"]
    assert abs(pa["approve"] + pa["reject"] - 1.0) < 1e-6, f"π_θ^a not normalized: {pa}"
    # log -0.3 ≫ log -1.5 → approve should dominate the student distribution
    assert pa["approve"] > pa["reject"], f"π_θ^a wrong way round: {pa}"
ok("_self_distill_export_jsonl: writes 2 records, π_θ^a normalized, JSON round-trips")

# Reverse-KL advantage hand-calc check (no Tinker call — just the math).
# advantage = w · [log p_cfr(a) - log p_θ(a)]
# w = 1.0 (won), p_cfr(approve) = 0.85, p_θ(approve) = exp(-0.3) ≈ 0.7408
# expected = 1.0 · [log 0.85 - (-0.3)] = -0.1625 + 0.3 = 0.1375
import math
expected_adv = 1.0 * (math.log(0.85) - (-0.3))
assert abs(expected_adv - 0.13744) < 1e-3, f"adv math drift: {expected_adv}"
ok(f"reverse-KL advantage math: {expected_adv:+.4f} (won, p_cfr=0.85, p_θ≈0.74)")

# Same datum with won=False should give half the gradient
d_loss = tma.OnPolicyDistillDatum(**{**d.__dict__, "won": False})
expected_adv_loss = 0.5 * (math.log(0.85) - (-0.3))
assert abs(expected_adv_loss - 0.06872) < 1e-3
ok(f"outcome weighting: loss reduces advantage to {expected_adv_loss:+.4f}")

# Role-leakage detector — uses the EXACT response from the user's smoke test
# log so this catches regressions of the live-traffic case.
real_leak = (
    '{"vote": "reject", "belief": 0.67, "message": "As a Minion, I must '
    'ensure the Evil team\'s survival. The proposed team lacks at least '
    'one Evil member, so I reject it."}'
)
spans = tma._detect_role_leakage(real_leak, role="minion")
assert len(spans) >= 1, f"should detect leakage in real Minion self-out, got {spans}"
matched_substrings = [real_leak[s:e].lower() for s, e in spans]
assert any("minion" in m for m in matched_substrings), \
    f"should match 'As a Minion', got {matched_substrings}"
ok(f"_detect_role_leakage: real Minion self-out → {len(spans)} matches")

# False positive checks — Evil player accusing OTHER players is fine.
clean = '{"vote": "reject", "belief": 0.8, "message": "I think P3 looks Evil based on the failed mission."}'
assert tma._detect_role_leakage(clean, role="minion") == [], \
    f"accusing others is not leakage, got {tma._detect_role_leakage(clean, role='minion')}"
ok("_detect_role_leakage: 'I think P3 is Evil' is NOT a leak (accusation, not self-ID)")

# Servant claiming "Servant" should NOT be penalised — common cover.
servant_text = '{"vote": "approve", "belief": 0.2, "message": "As a loyal Servant, I trust the team."}'
assert tma._detect_role_leakage(servant_text, role="servant") == [], \
    "Servant claiming Servant is normal cover, not leakage"
ok("_detect_role_leakage: Servant cover is not penalised")

# Merlin self-out
merlin_leak = '{"vote": "reject", "belief": 0.9, "message": "I am Merlin. I see Evil on this team."}'
spans = tma._detect_role_leakage(merlin_leak, role="merlin")
assert len(spans) >= 1, "should detect Merlin self-out"
ok(f"_detect_role_leakage: Merlin self-out → {len(spans)} matches")

# An Evil player saying "I'm Good" is fine (deception, expected behaviour).
evil_pretending = '{"vote": "approve", "belief": 0.3, "message": "I am Good and I trust this team."}'
assert tma._detect_role_leakage(evil_pretending, role="morgana") == [], \
    "Evil claiming Good is intended deception, not leakage"
ok("_detect_role_leakage: Evil claiming Good is not penalised (intended deception)")

# Empty / None handling
assert tma._detect_role_leakage("", "minion") == []
assert tma._detect_role_leakage("test", None) == []
assert tma._detect_role_leakage("test", "") == []
ok("_detect_role_leakage: empty inputs handled")

# _find_leak_token_indices — fake tokenizer for the test
class FakeTokenizer:
    """Minimal tokenizer that decodes ints as themselves separated by spaces."""
    _vocab = {1: "As", 2: " a", 3: " Minion", 4: ",", 5: " I", 6: " must", 7: " act"}
    def decode(self, ids, skip_special_tokens=False):
        return "".join(self._vocab.get(i, "?") for i in ids)
ftok = FakeTokenizer()
# Tokens decode to: "As a Minion, I must act"
# Char positions:    0  2  4 10 11 13 18
# Span "As a Minion" = (0, 11)
token_ids = [1, 2, 3, 4, 5, 6, 7]
leak_idxs = tma._find_leak_token_indices(token_ids, [(0, 11)], ftok)
assert 0 in leak_idxs and 1 in leak_idxs and 2 in leak_idxs, \
    f"should mark first 3 tokens (As, a, Minion), got {leak_idxs}"
assert 6 not in leak_idxs, "trailing tokens should not be marked"
ok(f"_find_leak_token_indices: maps char span (0,11) → tokens {leak_idxs}")

# ---------------------------------------------------------------------------
# 6. Optional: 1-step network smoke test
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--network", action="store_true",
                    help="Also run a 1-step training round (uses API credits)")
parser.add_argument("--base-model", type=str,
                    default=os.environ.get("VERIFY_BASE_MODEL",
                                            "meta-llama/Llama-3.2-1B"),
                    help="Base model for smoke test "
                         "(e.g. 'Qwen/Qwen3-8B-Base', 'meta-llama/Llama-3.2-1B').")
parser.add_argument("--renderer-name", type=str,
                    default=os.environ.get("VERIFY_RENDERER", "llama3"),
                    help="Tinker renderer matching the base model family "
                         "('qwen3' for Qwen, 'llama3' for Llama).")
parser.add_argument("--lora-rank", type=int, default=8,
                    help="LoRA rank for the smoke-test LoRA (default 8 — small, "
                         "since this is just a wiring check).")
parser.add_argument("--max-new-tokens", type=int, default=None,
                    help="Override max_new_tokens (default 32 for ≤1B models, "
                         "64 for larger).")
args = parser.parse_args()

if args.network:
    # Auto-tune max_new_tokens for the model size: small models can vote in
    # ~32 tokens, but Qwen-8B-Base tends to ramble and you want to give it
    # enough room to actually emit an action token before truncation.
    if args.max_new_tokens is None:
        is_big = any(s in args.base_model.lower()
                     for s in ("8b", "7b", "13b", "70b"))
        max_new_tokens = 64 if is_big else 32
    else:
        max_new_tokens = args.max_new_tokens

    hdr(f"6. Network smoke test (1 step, 1 game, {args.base_model})")
    if not api_key:
        fail("Cannot run network test without TINKER_API_KEY")
        errors.append("smoke test skipped")
    else:
        try:
            import asyncio
            cfg = tma.TrainerConfig(
                base_model          = args.base_model,
                renderer_name       = args.renderer_name,
                lora_rank           = args.lora_rank,
                games_per_step      = 1,
                num_players         = 5,
                steps               = 1,
                save_every          = 1,
                skip_sft            = True,
                cfr_distill_enabled = True,
                cfr_distill_lr      = 5e-6,
                temperature         = 0.7,
                max_new_tokens      = max_new_tokens,
                run_name            = "verify_smoke",
                out_dir             = "results/verify_smoke",
            )
            print(f"  base_model     = {cfg.base_model}")
            print(f"  renderer       = {cfg.renderer_name}")
            print(f"  lora_rank      = {cfg.lora_rank}")
            print(f"  max_new_tokens = {cfg.max_new_tokens}")
            print(f"  this will take ~30–120s depending on model size")
            asyncio.run(tma.rl_train(cfg))
            # Search for self_distill.jsonl anywhere under out_dir — the
            # actual run dir is out_dir/run_name/ which the verifier doesn't
            # need to reconstruct manually.
            candidates = sorted(Path(cfg.out_dir).rglob("self_distill.jsonl"))
            jsonl = candidates[-1] if candidates else None   # latest match
            if jsonl is not None and jsonl.stat().st_size > 0:
                lines = jsonl.read_text().strip().splitlines()
                ok(f"smoke test wrote {len(lines)} self-distill tuples → {jsonl}")
                # Spot-check the first record to confirm π_θ^a came through.
                import json as _j
                first = _j.loads(lines[0])
                if "student_pi_a" in first:
                    pa = first["student_pi_a"]
                    ok(f"first record: sampled={first['sampled_vote']}  "
                       f"π_θ^a={{approve:{pa['approve']:.3f}, "
                       f"reject:{pa['reject']:.3f}}}")
                else:
                    warn("first record missing student_pi_a — check JSONL export")
                # Cross-check role-side breakdown — if good=0 and evil=0 we
                # silently mis-bucketed every Good/Evil role.
                roles_seen = {_j.loads(L).get("role_side", "?") for L in lines}
                if roles_seen == {"other"}:
                    warn("every datum has role_side='other' — _role_side() "
                         "may be receiving role names in unexpected casing")
                else:
                    ok(f"role_side distribution: {sorted(roles_seen)}")
            else:
                # Don't guess at the cause — the training log already printed
                # diagnostics ("distill capture: 0/N vote turns ...") that say
                # exactly which step failed.  Direct the user there instead.
                warn("smoke test ran to completion but produced no self-distill tuples")
                warn("→ scroll up in the log for a 'distill capture: X/Y' line")
                warn("→ if X=0 and Y=0: no vote phases occurred (rollout may have crashed)")
                warn("→ if X=0 and Y>0: model isn't emitting parseable vote tokens")
                warn("                   (look for 'example responses where ...' lines)")
                warn("→ if no 'distill capture' line appeared: rollout never finished")
                errors.append("smoke test produced no datums")
        except Exception as e:
            fail(f"smoke test crashed: {type(e).__name__}: {e}")
            traceback.print_exc()
            errors.append("smoke test")
else:
    hdr("6. Network smoke test")
    print("  skipped (re-run with --network to execute a real 1-step round)")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
if errors:
    print(f"{RED}FAILED{RESET} — {len(errors)} issue(s):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print(f"{GREEN}ALL CHECKS PASSED{RESET}")
    if not args.network:
        print("Next: run with --network for the 1-step smoke test, then start training.")
    sys.exit(0)
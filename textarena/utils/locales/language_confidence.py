"""Track B — low-resource language confidence surface.

The low-resource UI localizations under this directory are produced by open
machine-translation models and certified by an automatic, reader-free verifier
(forward MT -> two independent back-translations -> LLM faithfulness adjudication).
That process is strong but not a human native reviewer, so each such language
carries a confidence tier and a list of games where a residual divergence was
found. This module surfaces that information to callers and UIs.

Source of truth: ``_trackb_confidence.json`` next to this file.

Tiers
-----
CERTIFIED          - verifier-clean; ship as-is.
CERTIFIED_FLAGGED  - a handful of confirmed divergences; every confirmed leaf has
                     been reverted to English, and the affected games are listed so
                     a UI can show a caveat. Safe to use; imperfect prose possible.
EXPERIMENTAL       - many divergences; structurally valid and playable but meaning
                     is not certified. Not shipped in the low-resource PR; available
                     for research use only.

Typical use::

    from textarena.utils.locales import language_confidence as lc
    lc.warn_if_flagged("kn")          # emits a one-time UserWarning if not CERTIFIED
    info = lc.confidence("kn")         # -> dict or None
    if lc.is_shippable("kn"): ...
"""
import json
import os
import warnings

_MANIFEST = os.path.join(os.path.dirname(__file__), "_trackb_confidence.json")
_CACHE = None
_WARNED = set()

SHIPPABLE_TIERS = ("CERTIFIED", "CERTIFIED_FLAGGED")


def _load():
    global _CACHE
    if _CACHE is None:
        try:
            with open(_MANIFEST, encoding="utf-8") as f:
                _CACHE = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
        except (OSError, ValueError):
            _CACHE = {}
    return _CACHE


def confidence(lang):
    """Return the confidence record for ``lang`` (dict), or ``None`` if the language
    is not a Track B open-MT localization (e.g. English or a human-reviewed language)."""
    return _load().get(lang)


def tier(lang):
    """Confidence tier string, or ``None`` if ``lang`` is not tracked here."""
    rec = confidence(lang)
    return rec.get("tier") if rec else None


def is_tracked(lang):
    return lang in _load()


def is_shippable(lang):
    """True for CERTIFIED / CERTIFIED_FLAGGED (the tiers included in the PR)."""
    return tier(lang) in SHIPPABLE_TIERS


def flagged_games(lang):
    rec = confidence(lang)
    return list(rec.get("flagged_games", [])) if rec else []


def disclaimer(lang):
    """Human-readable one-liner suitable for a UI tooltip / log, or ``None``."""
    rec = confidence(lang)
    if not rec:
        return None
    t = rec.get("tier")
    name = rec.get("name", lang)
    n = len(rec.get("flagged_games", []))
    if t == "CERTIFIED":
        return f"{name}: machine-translated, automatically verified."
    if t == "CERTIFIED_FLAGGED":
        return (f"{name}: machine-translated and automatically verified; a few phrases "
                f"may be imperfect and {n} game(s) are flagged for review.")
    return (f"{name}: EXPERIMENTAL machine translation — structurally valid and playable "
            f"but meaning is not certified; use with caution.")


def warn_if_flagged(lang, once=True):
    """Emit a ``UserWarning`` if ``lang`` is a non-CERTIFIED Track B localization.
    Deduplicated per language when ``once`` is True. No-op for untracked/CERTIFIED
    languages, so it is safe to call unconditionally on locale load."""
    t = tier(lang)
    if t is None or t == "CERTIFIED":
        return
    if once and lang in _WARNED:
        return
    _WARNED.add(lang)
    warnings.warn(disclaimer(lang), UserWarning, stacklevel=2)


def summary():
    """{tier: [langs]} — for building README tables / CI reports."""
    out = {}
    for lang, rec in _load().items():
        out.setdefault(rec.get("tier", "UNKNOWN"), []).append(lang)
    return {k: sorted(v) for k, v in out.items()}

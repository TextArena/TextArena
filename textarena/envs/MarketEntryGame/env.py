import math
import re
from decimal import Decimal, localcontext
from fractions import Fraction
from numbers import Rational, Real
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.MarketEntryGame.renderer import create_board_str


def _is_renderable(value: Any) -> bool:
    try:
        str(value)
    except (OverflowError, ValueError):
        return False
    return True


def _is_finite_real(value: Any) -> bool:
    if not isinstance(value, Real) or isinstance(value, bool):
        return False
    if isinstance(value, Rational):
        return True
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _is_payoff(value: Any) -> bool:
    return _is_finite_real(value) and _is_renderable(value)


def _exact_number(value: Real) -> Union[int, Fraction]:
    fraction = Fraction(value) if isinstance(value, Rational) else Fraction.from_float(float(value))
    return fraction.numerator if fraction.denominator == 1 else fraction


def _format_number(value: Real) -> str:
    try:
        numeric = float(value)
    except (OverflowError, TypeError, ValueError):
        numeric = None
    if numeric is not None and math.isfinite(numeric):
        return f"{numeric:g}" if abs(numeric) < 1e12 else f"{numeric:.3e}"
    if isinstance(value, Rational):
        with localcontext() as context:
            context.prec = 8
            decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        return f"{decimal_value:.3E}"
    return str(value)


class MarketEntryGameEnv(ta.GameEnv):
    min_players = 2
    max_players = 15
    mdp_includes_actions = False
    broadcast_actions = False  # raw actions stay private; the game reveals messages/decisions simultaneously

    num_rounds = ta.Param(5, "The number of rounds.", min=1, check=_is_renderable, rule="a positive integer")
    communication_turns = ta.Param(
        3, "The simultaneous message turns before each decision. With 0, communication is skipped.",
        min=0, check=_is_renderable, rule="a non-negative integer",
    )
    market_capacity = ta.Param(
        2, "The largest number of entrants for which entering is profitable.",
        min=0, check=_is_renderable, rule="a non-negative integer",
    )
    entry_profit = ta.Param(
        15, "The payoff for entering a market that is not overcrowded.",
        type=Real, check=_is_payoff, rule="a finite number",
    )
    overcrowding_penalty = ta.Param(
        -5, "The payoff for entering an overcrowded market.", type=Real, check=_is_payoff, rule="a finite number",
    )
    safe_payoff = ta.Param(5, "The payoff for staying out.", type=Real, check=_is_payoff, rule="a finite number")
    default_num_players = ta.Param(
        4, "The number of players used when `reset()` is called without `num_players`.", min=2, max=15,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Decision regex - bare E/S.
        self.decision_pattern = re.compile(r"^\s*(E|S)\s*$", re.IGNORECASE)
        # Public message regex - matches messages in curly braces like {Hello everyone!}
        self.public_message_pattern = re.compile(r"\{([^}]*)\}", re.DOTALL)

    def get_board_str(self):
        return create_board_str(self.state.game_state)

    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players
        return {
            "round": 1,
            "num_rounds": self.num_rounds,
            "phase": "decision" if self.communication_turns == 0 else "conversation",
            "conversation_round": 0,
            "total_conversation_rounds": self.communication_turns,
            "decisions": {i: None for i in range(num_players)},  # 'E' for enter, 'S' for stay out
            "total_scores": {i: 0 for i in range(num_players)},
            "round_scores": {i: 0 for i in range(num_players)},
            "market_capacity": self.market_capacity,
            "entry_profit": self.entry_profit,
            "overcrowding_penalty": self.overcrowding_penalty,
            "safe_payoff": self.safe_payoff,
            "history": [],
            "eliminations": [],  # Track eliminated players
            "pending_messages": {},  # Store messages until all players have acted
            "pending_decisions": {},  # Store decisions until all players have acted
        }

    def on_start(self):
        instruction = (
            "Decision phase: Submit 'E' to enter or 'S' to stay out."
            if self.game_state["phase"] == "decision"
            else "Communication phase: Submit your message using {message} format for public communication."
        )
        self.broadcast(
            f"--- Starting Round {self.game_state['round']} ---\n{instruction}",
            ta.ObservationType.GAME_MESSAGE,
        )

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        all_enter_overcrowded = self.state.num_players > game_state["market_capacity"]
        all_enter_status = "overcrowded" if all_enter_overcrowded else "not overcrowded"
        all_enter_payoff = (
            game_state["overcrowding_penalty"]
            if all_enter_overcrowded
            else game_state["entry_profit"]
        )
        return (
            f"You are Player {player_id} in a Market Entry Game spanning "
            f"{game_state['num_rounds']} rounds.\n\n"
            f"Game Structure:\n"
            f"- Each round, you must decide whether to ENTER the market or STAY OUT.\n"
            f"- Market capacity: {game_state['market_capacity']} players can profitably enter.\n"
            f"- Before each decision you have {game_state['total_conversation_rounds']} "
            f"turns to communicate with other players.\n"
            f"- Communication is SIMULTANEOUS: Messages from a turn are revealed only after all players submit.\n"
            f"- After communication, all players SIMULTANEOUSLY choose to Enter (E) or Stay Out (S).\n"
            f"- Decisions are revealed only after all players have decided.\n\n"
            f"Payoff Structure:\n"
            f"- If you STAY OUT: guaranteed {game_state['safe_payoff']} points\n"
            f"- If you ENTER:\n"
            f"  • When ≤{game_state['market_capacity']} players enter: {game_state['entry_profit']} points\n"
            f"  • When >{game_state['market_capacity']} players enter: {game_state['overcrowding_penalty']} points (loss!)\n\n"
            f"Example Scenarios (with {self.state.num_players} players):\n"
            f"- If at most {game_state['market_capacity']} player(s) enter: entrants get {game_state['entry_profit']}, others get {game_state['safe_payoff']}\n"
            f"- If more than {game_state['market_capacity']} player(s) enter: entrants get {game_state['overcrowding_penalty']}, others get {game_state['safe_payoff']}\n"
            f"- If all {self.state.num_players} enter: the market is {all_enter_status}, and everyone gets {all_enter_payoff}\n"
            f"- If none enter: everyone gets {game_state['safe_payoff']}\n\n"
            f"How to Play:\n"
            f"- You can think internally and reason about your strategy (this won't be shared).\n"
            f"- Your goal is to maximize your total score across all rounds.\n"
            f"- During conversation: send public messages using {{message}} format.\n"
            f"  Example: 'I'm considering entering. {{I think only 2 of us should enter this round}}'\n"
            f"  Only the text in curly braces will be visible to other players.\n"
            f"- During decision phase: reply with 'E' to enter or 'S' to stay out.\n"
            f"- An invalid move (wrong format) gets a warning; a second one in a row eliminates you.\n"
            f"- If you don't send any public message during conversation (no {{}} format), others will see that you remained silent.\n\n"
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if (
            not isinstance(player_id, int)
            or isinstance(player_id, bool)
            or not 0 <= player_id < self.state.num_players
            or not self.state.is_player_alive(player_id)
            or player_id != self.current_player_id
        ):
            return self.invalid("Action submitted by an unauthorized player.")
        if self.game_state["phase"] == "conversation":
            return self._handle_conversation_phase(player_id, action)
        return self._handle_decision_phase(player_id, action)

    def _extract_public_message(self, action: str) -> Optional[str]:
        """Extract and validate public message from action using {message} format."""
        matches = self.public_message_pattern.findall(action)
        if matches:
            valid_messages = [match.strip() for match in matches if match.strip()]
            if valid_messages:
                return self.strip_role_tags(" ".join(valid_messages)).strip() or None
        return None

    def _handle_conversation_phase(self, player_id: int, action: str) -> Union[ta.Invalid, None]:
        gs = self.game_state
        if player_id in gs["pending_messages"]:
            return self.invalid("You have already submitted a message for this communication turn.")
        gs["pending_messages"][player_id] = self._extract_public_message(action)  # None => remained silent

        alive_players = self.state.alive_players
        if all(p in gs["pending_messages"] for p in alive_players):
            # All alive players have submitted - reveal all public messages simultaneously
            messages_to_broadcast = []
            for sender_id in alive_players:
                public_msg = gs["pending_messages"][sender_id]
                messages_to_broadcast.append(f"Player {sender_id}: {public_msg}" if public_msg else f"Player {sender_id}: [remained silent]")
            if messages_to_broadcast:
                full_message = "Messages from this turn:\n" + "\n".join(messages_to_broadcast)
                for receiver_id in alive_players:
                    self.message(receiver_id, full_message, ta.ObservationType.GAME_MESSAGE)

            gs["pending_messages"] = {}
            gs["conversation_round"] += 1
            if gs["conversation_round"] >= gs["total_conversation_rounds"]:
                gs["phase"] = "decision"
                self.broadcast(
                    f"Conversation finished for round {gs['round']}.\n"
                    f"Decision phase: Reply with 'E' to enter the market or 'S' to stay out.\n"
                    f"Decisions will be revealed after all players decide.",
                    ta.ObservationType.GAME_MESSAGE,
                )
        return None

    def _handle_decision_phase(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if player_id in self.game_state["pending_decisions"]:
            return self.invalid("You have already submitted a decision for this round.")
        match = self.decision_pattern.search(action)
        if not match:
            return self.invalid("No valid decision found. Please reply with 'E' to enter or 'S' to stay out.")
        self.game_state["pending_decisions"][player_id] = match.group(1).upper()
        return self._maybe_resolve_decisions()

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        # Repeated invalid decisions: eliminate the player, default their decision to stay out.
        self.eliminate(player_id)
        self.game_state["pending_decisions"][player_id] = 'S'
        self.game_state["eliminations"].append(player_id)
        self.broadcast(f"Player {player_id} eliminated for too many invalid moves.", ta.ObservationType.GAME_MESSAGE)
        outcome = self._maybe_resolve_decisions()
        if outcome is not None:
            return outcome
        if not self.state.alive_players:
            return self.draw(reason="All players eliminated!")
        return None

    def _maybe_resolve_decisions(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        alive_players = self.state.alive_players
        if not all(p in gs["pending_decisions"] for p in alive_players):
            return None

        # All players have decided - reveal all decisions
        gs["decisions"] = gs["pending_decisions"].copy()
        gs["pending_decisions"] = {}
        entries = sum(1 for p in alive_players if gs["decisions"].get(p) == 'E')

        decision_msg = "All players have made their decisions:\n"
        for pid in sorted(alive_players):
            decision_text = "ENTERED" if gs["decisions"][pid] == 'E' else "STAYED OUT"
            decision_msg += f"Player {pid}: {decision_text}\n"
        decision_msg += f"\nMarket Status: {entries} player(s) entered"
        if entries > gs["market_capacity"]:
            decision_msg += f" (OVERCROWDED! Capacity is {gs['market_capacity']})"
        elif entries > 0:
            decision_msg += f" (Not overcrowded, capacity is {gs['market_capacity']})"
        self.broadcast(decision_msg, ta.ObservationType.GAME_MESSAGE)

        self._resolve_round()

        if gs["round"] >= gs["num_rounds"]:
            gs["phase"] = "complete"
            return self._determine_winner()

        # Reset for next round
        gs["round"] += 1
        gs["decisions"] = {i: None for i in range(self.state.num_players)}
        gs["round_scores"] = {i: 0 for i in range(self.state.num_players)}
        gs["pending_messages"] = {}
        gs["pending_decisions"] = {}
        gs["phase"] = "decision" if gs["total_conversation_rounds"] == 0 else "conversation"
        gs["conversation_round"] = 0
        instruction = (
            "Decision phase: Submit 'E' to enter or 'S' to stay out."
            if gs["phase"] == "decision"
            else "Communication phase: Submit your message using {message} format for public communication."
        )
        self.broadcast(
            f"--- Starting Round {gs['round']} ---\n{instruction}",
            ta.ObservationType.GAME_MESSAGE,
        )
        return None

    def _resolve_round(self):
        gs = self.game_state
        decisions = gs["decisions"]
        alive_players = self.state.alive_players
        entrants = [p for p in alive_players if decisions.get(p) == 'E']
        num_entrants = len(entrants)
        is_overcrowded = num_entrants > gs["market_capacity"]

        round_info = {
            "round": gs["round"],
            "decisions": {p: decisions.get(p) for p in alive_players},
            "num_entrants": num_entrants,
            "is_overcrowded": is_overcrowded,
            "payoffs": {},
        }

        result_message = f"Round {gs['round']} results:\n"
        result_message += f"Market capacity: {gs['market_capacity']}\n"
        result_message += f"Players who entered: {num_entrants}\n"
        result_message += f"Market status: {'OVERCROWDED' if is_overcrowded else 'Not overcrowded'}\n\n"

        for player_id in range(self.state.num_players):
            if self.state.is_player_alive(player_id):
                if decisions.get(player_id) == 'E':
                    payoff = gs["overcrowding_penalty"] if is_overcrowded else gs["entry_profit"]
                    result_message += f"Player {player_id}: ENTERED ({'overcrowded' if is_overcrowded else 'profitable'}) = {payoff} points\n"
                else:
                    payoff = gs["safe_payoff"]
                    result_message += f"Player {player_id}: STAYED OUT = {payoff} points\n"
                round_info["payoffs"][player_id] = payoff
                gs["round_scores"][player_id] = payoff
                gs["total_scores"][player_id] = _exact_number(
                    gs["total_scores"][player_id] + _exact_number(payoff)
                )
                result_message += f"  Total score: {_format_number(gs['total_scores'][player_id])}\n"
            else:
                result_message += f"Player {player_id}: ELIMINATED\n"

        gs["history"].append(round_info)
        self.broadcast(result_message, ta.ObservationType.GAME_MESSAGE)

    def _determine_winner(self) -> ta.Outcome:
        gs = self.game_state
        alive_players = self.state.alive_players
        scores = {p: gs["total_scores"][p] for p in alive_players}
        if not scores:
            return self.draw(reason="All players eliminated!")

        max_score = max(scores.values())
        winners = [p for p, s in scores.items() if s == max_score]

        final_message = "Game Over! Final scores:\n"
        for player_id in range(self.state.num_players):
            score = gs["total_scores"][player_id]
            status = " (eliminated)" if not self.state.is_player_alive(player_id) else ""
            final_message += f"Player {player_id}: {_format_number(score)}{status}\n"

        if len(winners) == 1:
            return self.winner(
                winners[0],
                reason=f"{final_message}\nPlayer {winners[0]} wins with {_format_number(max_score)} points!",
            )
        if len(winners) == self.state.num_players:
            return self.draw(
                reason=f"{final_message}\nAll players tied with {_format_number(max_score)} points. It's a draw!"
            )
        return self.winner(
            winners,
            reason=(
                f"{final_message}\nPlayers {', '.join(map(str, winners))} tied for first "
                f"with {_format_number(max_score)} points."
            ),
        )

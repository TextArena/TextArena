import math
import re
from decimal import Decimal, localcontext
from fractions import Fraction
from numbers import Rational, Real
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.PublicGoodsGame.renderer import create_board_str


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


def _exact_number(value: Real) -> Union[int, Fraction]:
    fraction = Fraction(value) if isinstance(value, Rational) else Fraction.from_float(float(value))
    return fraction.numerator if fraction.denominator == 1 else fraction


def _format_number(value: Real) -> str:
    try:
        numeric = float(value)
    except (OverflowError, TypeError, ValueError):
        numeric = None
    if numeric is not None and math.isfinite(numeric):
        return f"{numeric:.1f}" if abs(numeric) < 1e12 else f"{numeric:.3e}"
    if isinstance(value, Rational):
        with localcontext() as context:
            context.prec = 8
            decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        return f"{decimal_value:.3E}"
    return str(value)


class PublicGoodsGameEnv(ta.GameEnv):
    min_players = 2
    max_players = 15
    broadcast_actions = False  # raw actions stay private; messages/contributions are revealed simultaneously
    error_allowance = 2  # allow 2 errors before elimination

    def __init__(self,
                 num_rounds: int = 5,
                 communication_turns: int = 3,
                 endowment: int = 20,
                 multiplication_factor: float = 1.5,
                 num_players: int = 4):
        """
        Initialize the Public Goods Game environment.

        Args:
            num_rounds: Number of rounds to play
            communication_turns: Number of communication turns before each decision
            endowment: Number of tokens each player starts with each round
            multiplication_factor: Factor by which total contributions are multiplied
            num_players: Number of players in the game (default 4)
        """
        if (
            not isinstance(num_rounds, int)
            or isinstance(num_rounds, bool)
            or num_rounds <= 0
            or not _is_renderable(num_rounds)
        ):
            raise ValueError("num_rounds must be a positive integer")
        if (
            not isinstance(communication_turns, int)
            or isinstance(communication_turns, bool)
            or communication_turns < 0
            or not _is_renderable(communication_turns)
        ):
            raise ValueError("communication_turns must be a non-negative integer")
        if (
            not isinstance(endowment, int)
            or isinstance(endowment, bool)
            or endowment < 0
            or not _is_renderable(endowment)
        ):
            raise ValueError("endowment must be a non-negative integer")
        if (
            not _is_finite_real(multiplication_factor)
            or multiplication_factor < 0
            or not _is_renderable(multiplication_factor)
        ):
            raise ValueError("multiplication_factor must be a finite non-negative number")
        if (
            not isinstance(num_players, int)
            or isinstance(num_players, bool)
            or not self.min_players <= num_players <= self.max_players
        ):
            raise ValueError(f"num_players must be between {self.min_players} and {self.max_players}")

        self.num_rounds = num_rounds
        self.communication_turns = communication_turns
        self.endowment = endowment
        self.multiplication_factor = multiplication_factor
        self.default_num_players = num_players

        # Contribution regex - bare number, with optional stray brackets for robustness.
        self.contribution_pattern = re.compile(r"^\s*\[?\s*(\d+)\s*\]?\s*$", re.IGNORECASE)
        # Public message regex - matches messages in curly braces like {Hello everyone!}
        self.public_message_pattern = re.compile(r"\{([^}]*)\}", re.DOTALL)

    def get_board_str(self):
        return create_board_str(self.state.game_state)

    def reset(self, num_players: Optional[int] = None, seed: Optional[int] = None):
        if num_players is None:
            num_players = self.default_num_players
        super().reset(num_players=num_players, seed=seed)

    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players
        return {
            "round": 1,
            "num_rounds": self.num_rounds,
            "phase": "decision" if self.communication_turns == 0 else "conversation",
            "conversation_round": 0,
            "total_conversation_rounds": self.communication_turns,
            "contributions": {i: None for i in range(num_players)},
            "total_scores": {i: 0 for i in range(num_players)},
            "round_scores": {i: 0 for i in range(num_players)},
            "endowment": self.endowment,
            "multiplication_factor": self.multiplication_factor,
            "history": [],
            "eliminations": [],  # Track eliminated players
            "pending_messages": {},  # Store messages until all players have acted
            "pending_contributions": {},  # Store contributions until all players have acted
        }

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        sample_contribution = min(10, game_state["endowment"])
        sample_total = sample_contribution * self.state.num_players
        sample_public_good = _exact_number(sample_total) * _exact_number(
            game_state["multiplication_factor"]
        )
        sample_public_good = _exact_number(sample_public_good)
        sample_share = _exact_number(
            Fraction(sample_public_good, self.state.num_players)
        )
        sample_kept = game_state["endowment"] - sample_contribution
        sample_payoff = _exact_number(_exact_number(sample_kept) + sample_share)
        if game_state.get("phase") == "conversation":
            phase_round_description = (
                f"Round {game_state['round']} - Communication Round {game_state['conversation_round'] + 1} "
                f"of {game_state['total_conversation_rounds']}\n"
            )
        else:
            phase_round_description = f"Round {game_state['round']} - Decision Phase"

        return (
            f"You are Player {player_id} in a Public Goods Game spanning "
            f"{game_state['num_rounds']} rounds.\n\n"
            f"Game Structure:\n"
            f"- Each round, you receive {game_state['endowment']} tokens.\n"
            f"- Before each decision you have {game_state['total_conversation_rounds']} "
            f"turns to communicate with other players.\n"
            f"- Communication is SIMULTANEOUS: Messages from a turn are revealed only after all players submit.\n"
            f"- After communication, all players SIMULTANEOUSLY choose how many tokens to contribute "
            f"to the public pot (0 to {game_state['endowment']}).\n"
            f"- Contributions are revealed only after all players have decided.\n\n"
            f"Payoff Calculation:\n"
            f"- Your payoff = (tokens kept) + (your share of public good)\n"
            f"- Public good = (sum of all contributions) × {game_state['multiplication_factor']}\n"
            f"- The public good is divided equally among all {self.state.num_players} players\n\n"
            f"Example:\n"
            f"If everyone contributes {sample_contribution} tokens:\n"
            f"- Total contributions: {sample_total}\n"
            f"- Public good: {sample_total} × {game_state['multiplication_factor']} = {_format_number(sample_public_good)}\n"
            f"- Each player gets: {_format_number(sample_share)} from public good\n"
            f"- Plus {sample_kept} tokens kept = {_format_number(sample_payoff)} total\n\n"
            f"How to Play:\n"
            f"- You can think internally and reason about your strategy (this won't be shared).\n"
            f"- Your goal is to maximize your total score across all rounds.\n"
            f"- During conversation: send public messages using {{message}} format.\n"
            f"  Example: 'I think we should cooperate. {{Let me propose we all contribute 15 tokens}}'\n"
            f"  Only the text in curly braces will be visible to other players.\n"
            f"- During decision phase: reply with the number of tokens you will contribute (0-{game_state['endowment']}).\n"
            f"  Example: '15'\n"
            f"- Invalid moves (wrong format or out of range) will result in warnings, then elimination.\n"
            f"- If you don't send any public message during conversation (no {{}} format), others will see that you remained silent.\n\n"
            f"Game Status: \n"
            f"{phase_round_description}\n"
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
                return " ".join(valid_messages)
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
                    f"Decision phase: Reply with your contribution as a number from 0 to {gs['endowment']}.\n"
                    f"Contributions will be revealed after all players decide.",
                    ta.ObservationType.GAME_BOARD,
                )
        return None

    def _handle_decision_phase(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if player_id in gs["pending_contributions"]:
            return self.invalid("You have already submitted a contribution for this round.")
        match = self.contribution_pattern.search(action)
        if not match:
            return self.invalid(f"No valid contribution found. Please reply with a number from 0 to {gs['endowment']}.")
        contribution = int(match.group(1))
        if not (0 <= contribution <= gs["endowment"]):
            return self.invalid(f"Invalid contribution {contribution}. Must be between 0 and {gs['endowment']}.")
        gs["pending_contributions"][player_id] = contribution
        return self._maybe_resolve_contributions()

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        # Repeated invalid contributions: eliminate the player, default their contribution to 0.
        self.eliminate(player_id)
        self.game_state["pending_contributions"][player_id] = 0
        self.game_state["eliminations"].append(player_id)
        self.broadcast(f"Player {player_id} eliminated for too many invalid moves.", ta.ObservationType.GAME_MESSAGE)
        outcome = self._maybe_resolve_contributions()
        if outcome is not None:
            return outcome
        if not self.state.alive_players:
            return self.draw(reason="All players eliminated!")
        return None

    def _maybe_resolve_contributions(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        alive_players = self.state.alive_players
        if not all(p in gs["pending_contributions"] for p in alive_players):
            return None

        # All players have decided - reveal all contributions
        gs["contributions"] = gs["pending_contributions"].copy()
        gs["pending_contributions"] = {}

        contrib_msg = "All players have made their decisions:\n"
        for pid in sorted(alive_players):
            contrib_msg += f"Player {pid}: {gs['contributions'][pid]} tokens\n"
        self.broadcast(contrib_msg, ta.ObservationType.GAME_MESSAGE)

        self._resolve_round()

        if gs["round"] >= gs["num_rounds"]:
            gs["phase"] = "complete"
            return self._determine_winner()

        # Reset for next round - clear both contributions and pending data
        gs["round"] += 1
        gs["contributions"] = {i: None for i in range(self.state.num_players)}
        gs["round_scores"] = {i: 0 for i in range(self.state.num_players)}
        gs["pending_messages"] = {}
        gs["pending_contributions"] = {}
        gs["phase"] = "decision" if gs["total_conversation_rounds"] == 0 else "conversation"
        gs["conversation_round"] = 0
        instruction = (
            "Decision phase: Submit a contribution from "
            f"0 to {gs['endowment']}."
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
        contributions = gs["contributions"]
        alive_players = self.state.alive_players

        total_contribution = sum(contributions.get(p, 0) for p in alive_players)
        public_good = _exact_number(total_contribution) * _exact_number(gs["multiplication_factor"])
        public_good = _exact_number(public_good)
        share_per_player = (
            _exact_number(Fraction(public_good, len(alive_players)))
            if alive_players
            else 0
        )

        round_info = {
            "round": gs["round"],
            "contributions": {p: contributions.get(p, 0) for p in alive_players},
            "total_contribution": total_contribution,
            "public_good": public_good,
            "payoffs": {},
        }

        result_message = f"Round {gs['round']} results:\n"
        result_message += f"Alive players: {len(alive_players)}\n"
        result_message += f"Contributions: {', '.join([f'P{i}: {contributions.get(i, 0)}' for i in alive_players])}\n"
        result_message += f"Total contribution: {total_contribution}\n"
        result_message += f"Public good: {total_contribution} × {gs['multiplication_factor']} = {_format_number(public_good)}\n"
        result_message += f"Share per alive player: {_format_number(share_per_player)}\n\n"

        for player_id in range(self.state.num_players):
            if self.state.is_player_alive(player_id):
                tokens_kept = gs["endowment"] - contributions.get(player_id, 0)
                payoff = _exact_number(_exact_number(tokens_kept) + share_per_player)
                round_info["payoffs"][player_id] = payoff
                gs["round_scores"][player_id] = payoff
                gs["total_scores"][player_id] = _exact_number(gs["total_scores"][player_id] + payoff)
                result_message += (
                    f"Player {player_id}: kept {tokens_kept} + share {_format_number(share_per_player)} "
                    f"= {_format_number(payoff)} (total: {_format_number(gs['total_scores'][player_id])})\n"
                )
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
        return self.winner(
            winners,
            reason=(
                f"{final_message}\nPlayers {', '.join(map(str, winners))} tied for first "
                f"with {_format_number(max_score)} points."
            ),
        )

"""Play agents against each other on TextArena games and summarize the results."""
import itertools
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from statistics import fmean
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from textarena.core import Wrapper

__all__ = ["evaluate", "Evaluation", "GameResult"]


@dataclass
class GameResult:
    """One evaluated game. `seats[player_id]` names the agent that played that seat."""
    env_id: str
    seed: int
    seats: Tuple[str, ...]
    rewards: Dict[int, float]
    invalid_moves: Dict[int, bool]
    turns: int
    error: Optional[str] = None
    record: Optional[Dict[str, Any]] = None

    def won(self, player_id: int) -> Optional[bool]:
        """Whether the seat scored strictly more than every other seat; None for single-player or failed games."""
        if self.error is not None or len(self.seats) < 2:
            return None
        return all(self.rewards[player_id] > reward for pid, reward in self.rewards.items() if pid != player_id)


@dataclass
class Evaluation:
    games: List[GameResult]

    def to_rows(self) -> List[Dict[str, Any]]:
        """One row per seat per game, e.g. for `pandas.DataFrame(evaluation.to_rows())`."""
        return [
            {
                "env_id": game.env_id, "seed": game.seed, "agent": agent, "player_id": pid,
                "reward": game.rewards.get(pid), "won": game.won(pid), "invalid_move": game.invalid_moves.get(pid),
                "turns": game.turns, "error": game.error,
            }
            for game in self.games
            for pid, agent in enumerate(game.seats)
        ]

    def summary(self) -> List[Dict[str, Any]]:
        """Per agent and environment: seats played, mean reward, win rate (games with two or more seats only),
        invalid-move rate, mean turns, and games that failed with an error."""
        groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for row in self.to_rows():
            groups.setdefault((row["agent"], row["env_id"]), []).append(row)
        summary = []
        for (agent, env_id), rows in groups.items():
            played = [row for row in rows if row["error"] is None]
            outcomes = [row["won"] for row in played if row["won"] is not None]
            summary.append({
                "agent": agent,
                "env_id": env_id,
                "games": len(played),
                "mean_reward": fmean(row["reward"] for row in played) if played else None,
                "win_rate": fmean(outcomes) if outcomes else None,
                "invalid_move_rate": fmean(row["invalid_move"] for row in played) if played else None,
                "mean_turns": fmean(row["turns"] for row in played) if played else None,
                "errors": len(rows) - len(played),
            })
        return summary


def _seatings(names: Sequence[str], seats: int) -> List[Tuple[str, ...]]:
    """Every agent plays every seat equally often: all orderings of distinct agents when there are enough of
    them, otherwise every rotation of the agent list around the table."""
    if len(names) >= seats:
        return list(itertools.permutations(names, seats))
    return [tuple(names[(start + offset) % len(names)] for offset in range(seats)) for start in range(len(names))]


def _default_seats(env_id: str) -> int:
    from textarena.envs.registration import make

    env = make(env_id)
    while isinstance(env, Wrapper):
        env = env.env
    return env.default_num_players or env.min_players


def _play(env_id: str, seed: int, seats: Tuple[str, ...], agents: Dict[str, Callable[[str], str]]) -> GameResult:
    from textarena.envs.registration import make

    try:
        env = make(env_id)
        env.reset(num_players=len(seats), seed=seed)
        done = False
        while not done:
            player_id, observation = env.get_observation()
            done = env.step(agents[seats[player_id]](observation))
        rewards, game_info = env.close()
        invalid = {pid: bool(info.get("invalid_move")) for pid, info in game_info.items()}
        return GameResult(env_id, seed, seats, dict(rewards), invalid, env.state.turn, record=env.record())
    except Exception as error:  # one failing game (e.g. an unreachable model) must not end the evaluation
        return GameResult(env_id, seed, seats, {}, {}, 0, error=f"{type(error).__name__}: {error}")


def evaluate(
    agents: Dict[str, Callable[[str], str]],
    env_ids: Union[str, Sequence[str]],
    episodes: int = 10,
    seed: int = 0,
    workers: int = 1,
    num_players: Optional[int] = None,
) -> Evaluation:
    """Play `agents` (a name -> agent mapping) against each other on every environment in `env_ids`.

    Each environment is played `episodes` times with seeds `seed`, `seed + 1`, ..., and each seed is played once per
    seating, so every agent plays every seat equally often on the same deals. Games use the environment's default
    player count (or `num_players`); with fewer agents than seats, agents fill several seats. `workers > 1` plays
    games in parallel threads, so the agents must be safe to call concurrently (the built-in model agents are).
    A game that raises is recorded with its error instead of stopping the evaluation.
    """
    if isinstance(env_ids, str):
        env_ids = [env_ids]
    names = list(agents)
    if not names:
        raise ValueError("evaluate needs at least one agent")
    jobs = []
    for env_id in env_ids:
        seatings = _seatings(names, num_players or _default_seats(env_id))
        jobs += [(env_id, seed + episode, seating) for episode in range(episodes) for seating in seatings]

    def run(job):
        return _play(*job, agents)

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            games = list(pool.map(run, jobs))
    else:
        games = [run(job) for job in jobs]
    return Evaluation(games)

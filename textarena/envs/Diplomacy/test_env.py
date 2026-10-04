"""Deterministic, fully offline gameplay tests for the Diplomacy environment.

No network / LLM use: only the negotiation-message parsing and order-submission
paths are exercised, with programmatically generated hold orders.
"""
import random

import pytest

import textarena as ta
from textarena.envs.Diplomacy.env import DiplomacyEnv
from textarena.envs.Diplomacy.game_engine import (
    DiplomacyGameEngine,
    Order,
    PhaseType,
    Season,
    Unit,
    UnitType,
)


ALL_POWERS = {
    "FRANCE",
    "ENGLAND",
    "GERMANY",
    "ITALY",
    "AUSTRIA",
    "RUSSIA",
    "TURKEY",
}


def _clear_units(engine: DiplomacyGameEngine) -> None:
    for region in engine.map.regions.values():
        region.unit = None
        region.dislodged_unit = None
    for power in engine.powers.values():
        power.units.clear()
        power.clear_orders()
        power.is_defeated = False


def _place_unit(
    engine: DiplomacyGameEngine,
    power_name: str,
    unit_type: UnitType,
    location: str,
) -> Unit:
    unit = Unit(unit_type, power_name)
    assert unit.place_in_region(engine.map.get_region(location))
    engine.powers[power_name].add_unit(unit)
    return unit


def _assert_unit_map_consistency(engine: DiplomacyGameEngine) -> None:
    for power_name, power in engine.powers.items():
        for unit in power.units:
            assert unit.power == power_name
            assert unit.region is not None
            if unit.dislodged:
                assert unit.region.dislodged_unit is unit
                assert unit.region.unit is not unit
            else:
                assert unit.region.unit is unit

    for region in engine.map.regions.values():
        if region.unit:
            assert not region.unit.dislodged
            assert region.unit.region is region
            assert region.unit in engine.powers[region.unit.power].units
        if region.dislodged_unit:
            assert region.dislodged_unit.dislodged
            assert region.dislodged_unit.region is region
            assert region.dislodged_unit in engine.powers[
                region.dislodged_unit.power
            ].units


def _hold_orders_action(env: DiplomacyEnv, player_id: int) -> str:
    """Build a 'Submit Orders:' action holding every unit of the player's power."""
    power_name = env.player_power_map[player_id]
    units = env.engine.powers[power_name].units
    orders = "\n".join(f"{unit} H" for unit in units)
    return f"Submit Orders:\n{orders}\n"


def _submit_orders_for_all(env: DiplomacyEnv, order_action_fn) -> bool:
    """Have every remaining player submit orders once; return the last `done` flag."""
    done = False
    for _ in range(len([pid for pid in env.player_power_map if env.state.is_player_alive(pid)])):
        pid = env.state.current_player_id
        done, _info = env.step(order_action_fn(env, pid))
    return done


def test_env_constructs():
    env = DiplomacyEnv()
    assert env is not None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_turns": 0},
        {"negotiations_per_phase": 0},
    ],
)
def test_constructor_rejects_nonpositive_limits(kwargs):
    with pytest.raises(ValueError):
        DiplomacyEnv(**kwargs)


@pytest.mark.parametrize("num_players", [3, 7])
def test_reset_succeeds(num_players):
    env = DiplomacyEnv()
    env.reset(num_players=num_players, seed=42)

    assert isinstance(env.state, ta.GameState)
    assert env.state.num_players == num_players
    assert len(env.player_power_map) == num_players
    assert env.state.done is False

    # Initial engine/game state: Spring 1901 Movement
    assert env.state.game_state["year"] == 1901
    assert env.state.game_state["season"] == "Spring"
    assert env.state.game_state["phase"] == "Movement"

    # Role mapping holds the power names (plus the GAME entry)
    for pid, power in env.player_power_map.items():
        assert env.state.role_mapping[pid] == power
    assert ta.GAME_ID in env.state.role_mapping


@pytest.mark.parametrize("num_players", [2, 8])
def test_reset_rejects_invalid_player_counts(num_players):
    env = DiplomacyEnv()
    with pytest.raises(AssertionError):
        env.reset(num_players=num_players, seed=42)


def test_initial_observations_contain_prompts():
    env = DiplomacyEnv()
    env.reset(num_players=3, seed=42)

    for pid, power in env.player_power_map.items():
        prompts = [msg for (_from, msg, obs_type) in env.state.observations[pid]
                   if obs_type == ta.ObservationType.PROMPT]
        assert len(prompts) == 1
        assert f"YOU ARE {power} (PLAYER {pid})" in prompts[0]

    current_pid, observation = env.get_observation()
    assert current_pid == 0
    assert len(observation) > 0


def test_negotiation_round_advances_after_full_rotation():
    env = DiplomacyEnv(negotiations_per_phase=2)
    env.reset(num_players=3, seed=42)
    assert env.current_negotiation_round == 0

    for pid in range(3):
        assert env.state.current_player_id == pid
        done, _info = env.step("Broadcast: Hello everyone, let us keep the peace.")
        assert done is False

    # After all three players acted, the (final) negotiation round begins
    assert env.current_negotiation_round == 1
    assert env.state.game_state["current_negotiation_round"] == 1


def test_hold_orders_execute_and_phase_transitions():
    # negotiations_per_phase=1 -> every round is the order-submission round
    env = DiplomacyEnv(negotiations_per_phase=1)
    env.reset(num_players=3, seed=42)

    # Spring 1901 Movement: everyone holds
    done = _submit_orders_for_all(env, _hold_orders_action)
    assert done is False
    assert env.state.game_state["season"] == "Spring"
    assert env.state.game_state["phase"] == "Retreats"

    # Spring 1901 Retreats: an explicit empty order set omits all retreats.
    done = _submit_orders_for_all(
        env, lambda e, pid: "Submit Orders:\n# no retreat orders\n"
    )
    assert done is False
    assert env.state.game_state["season"] == "Fall"
    assert env.state.game_state["phase"] == "Movement"
    assert env.state.game_state["year"] == 1901

    # Fall 1901 Movement: everyone holds again
    done = _submit_orders_for_all(env, _hold_orders_action)
    assert done is False
    assert env.state.game_state["season"] == "Fall"
    assert env.state.game_state["phase"] == "Retreats"


def test_invalid_action_is_rejected_without_ending_game():
    env = DiplomacyEnv(negotiations_per_phase=1)
    env.reset(num_players=3, seed=42)

    # Final negotiation round requires order submission; garbage is invalid
    done, _info = env.step("I refuse to cooperate with this game.")
    assert done is False
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0  # no rotation, player retries
    assert env.state.is_player_alive(0)

    # A valid submission afterwards is accepted and play moves on
    done, _info = env.step(_hold_orders_action(env, 0))
    assert done is False
    assert env.state.current_player_id == 1


def test_repeated_invalid_moves_eliminate_player():
    env = DiplomacyEnv(negotiations_per_phase=1)
    env.reset(num_players=3, seed=42)

    done, _info = env.step("gibberish")
    assert done is False
    assert env.state.is_player_alive(0)

    done, _info = env.step("more gibberish")
    assert done is False
    assert not env.state.is_player_alive(0)
    assert env.state.eliminated == [0]
    assert env.state.game_info[0]["invalid_move"] is True
    assert env.state.current_player_id == 1

    # The remaining players can still play out the phase
    for pid in (1, 2):
        assert env.state.current_player_id == pid
        done, _info = env.step(_hold_orders_action(env, pid))
    assert done is False
    assert env.state.game_state["phase"] == "Retreats"


def test_supported_head_to_head_keeps_active_and_dislodged_units_synchronized():
    engine = DiplomacyGameEngine()
    _clear_units(engine)
    attacker = _place_unit(engine, "FRANCE", UnitType.ARMY, "PAR")
    _place_unit(engine, "FRANCE", UnitType.ARMY, "GAS")
    defender = _place_unit(engine, "GERMANY", UnitType.ARMY, "BUR")

    engine.resolve_orders({
        "FRANCE": ["A PAR - BUR", "A GAS S A PAR - BUR"],
        "GERMANY": ["A BUR - PAR"],
    })

    bur = engine.map.get_region("BUR")
    assert bur.unit is attacker
    assert attacker.region is bur
    assert bur.dislodged_unit is defender
    assert defender.dislodged
    assert defender.region is bur
    assert engine.map.get_region("PAR").unit is None
    _assert_unit_map_consistency(engine)


@pytest.mark.parametrize("num_players", [3, 4, 5, 6])
def test_inactive_powers_leave_no_units_or_owned_centers(num_players):
    engine = DiplomacyGameEngine()
    player_power_map = engine.setup_game(
        num_players, rng=random.Random(100 + num_players)
    )
    active_powers = set(player_power_map.values())
    inactive_powers = ALL_POWERS - active_powers

    assert set(engine.powers) == active_powers
    for region in engine.map.regions.values():
        assert region.unit is None or region.unit.power in active_powers
        assert region.dislodged_unit is None
        assert region.owner is None or region.owner in active_powers

    # A stale former owner must also be harmless when that center is captured.
    inactive_power = next(iter(inactive_powers))
    former_center = engine.map.get_home_centers(inactive_power)[0]
    center_region = engine.map.get_region(former_center)
    active_power = next(iter(active_powers))
    active_unit = engine.powers[active_power].units[0]
    active_unit.region.unit = None
    active_unit.region = center_region
    center_region.unit = active_unit
    center_region.owner = inactive_power
    engine.season = Season.FALL

    engine._update_supply_centers()

    assert center_region.owner == active_power
    assert former_center in engine.powers[active_power].controlled_centers


@pytest.mark.parametrize(
    "malformed_order",
    [
        "A PAR S",
        "A PAR S A",
        "X PAR H",
        "A PAR TELEPORT BUR",
        "A PAR H trailing",
    ],
)
def test_malformed_orders_are_atomic_and_do_not_count_as_submitted(
    malformed_order,
):
    env = DiplomacyEnv(negotiations_per_phase=1)
    env.reset(num_players=3, seed=42)
    marker = "THIS-MESSAGE-MUST-NOT-LEAK"
    chat_before = list(env.chat_history)

    done, _ = env.step(
        f"Broadcast: {marker}\n"
        f"Whisper to 1: {marker}\n"
        f"Submit Orders:\n{malformed_order}\n"
    )

    assert done is False
    assert env.state.current_player_id == 0
    assert env.state.error_count == 1
    assert env.orders_submitted == set()
    assert env.pending_orders == {}
    assert env.chat_history == chat_before
    assert all(
        marker not in message
        for observations in env.state.observations.values()
        for _from_id, message, _observation_type in observations
    )


def test_parser_failures_are_recorded_as_invalid_orders():
    engine = DiplomacyGameEngine()
    parsed, invalid = engine.parse_orders(
        "FRANCE", ["A PAR S", "A PAR TELEPORT BUR"]
    )

    assert parsed == []
    assert len(invalid) == 2


def test_omitted_retreat_disbands_unit_and_clears_both_region_pointers():
    engine = DiplomacyGameEngine()
    _clear_units(engine)
    dislodged = _place_unit(engine, "FRANCE", UnitType.ARMY, "BUR")
    bur = engine.map.get_region("BUR")
    bur.unit = None
    bur.dislodged_unit = dislodged
    dislodged.dislodged = True
    dislodged.retreat_options = ["PAR"]
    engine.phase = PhaseType.RETREATS

    engine.resolve_orders({"FRANCE": []})

    assert dislodged not in engine.powers["FRANCE"].units
    assert dislodged.region is None
    assert bur.unit is None
    assert bur.dislodged_unit is None
    _assert_unit_map_consistency(engine)


def test_support_move_uses_supported_and_supporting_destination_rules():
    engine = DiplomacyGameEngine()
    _clear_units(engine)
    _place_unit(engine, "FRANCE", UnitType.ARMY, "PAR")
    _place_unit(engine, "GERMANY", UnitType.ARMY, "RUH")

    legal = Order.parse("A RUH S A PAR - BUR", "GERMANY")
    illegal = Order.parse("A RUH S A PAR - MUN", "GERMANY")

    assert engine.validate_order(legal) == (True, None)
    valid, reason = engine.validate_order(illegal)
    assert not valid
    assert "cannot move to MUN" in reason


def test_convoy_path_reaches_occupied_sea_chain_and_coastal_destination():
    engine = DiplomacyGameEngine()
    _clear_units(engine)
    _place_unit(engine, "ENGLAND", UnitType.ARMY, "LON")
    _place_unit(engine, "FRANCE", UnitType.FLEET, "ENG")

    assert engine._has_possible_convoy_path("LON", "BEL")
    assert engine.validate_order(
        Order.parse("A LON - BEL", "ENGLAND")
    ) == (True, None)
    assert engine.validate_order(
        Order.parse("F ENG C A LON - BEL", "FRANCE")
    ) == (True, None)


@pytest.mark.parametrize("max_game_years", [1, 2])
def test_max_game_years_ends_after_complete_years(max_game_years):
    engine = DiplomacyGameEngine(max_turns=max_game_years)
    phases_per_year = 5

    for _ in range(phases_per_year * max_game_years - 1):
        engine.resolve_orders({})
        assert engine.game_over is False

    engine.resolve_orders({})

    assert engine.game_over is True
    assert engine.year == 1901 + max_game_years


def test_public_game_state_schema_survives_resolution():
    env = DiplomacyEnv(negotiations_per_phase=1)
    env.reset(num_players=3, seed=42)
    public_keys = {
        "player_power_map",
        "powers_info",
        "current_negotiation_round",
        "total_negotiation_rounds",
    }
    assert public_keys <= env.state.game_state.keys()

    _submit_orders_for_all(env, _hold_orders_action)

    assert public_keys <= env.state.game_state.keys()
    assert env.state.game_state["player_power_map"] == env.player_power_map
    assert env.state.game_state["total_negotiation_rounds"] == 1
    assert env.state.game_state["current_negotiation_round"] == 0
    assert set(env.state.game_state["powers_info"]) == set(
        env.player_power_map.values()
    )


def test_prompt_resource_lookup_is_independent_of_working_directory(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    env = DiplomacyEnv()
    env.reset(num_players=3, seed=42)

    prompt = env.get_prompt(0, history_text="")

    assert "DIPLOMACY GAME" in prompt
    assert "POSSIBLE ORDERS" in prompt


def test_dislodged_support_does_not_decide_competing_attack():
    engine = DiplomacyGameEngine()
    _clear_units(engine)
    france_attacker = _place_unit(engine, "FRANCE", UnitType.ARMY, "PAR")
    france_supporter = _place_unit(engine, "FRANCE", UnitType.ARMY, "GAS")
    italy_attacker = _place_unit(engine, "ITALY", UnitType.ARMY, "MUN")
    _place_unit(engine, "ITALY", UnitType.ARMY, "RUH")
    _place_unit(engine, "GERMANY", UnitType.ARMY, "BUR")
    _place_unit(engine, "GERMANY", UnitType.ARMY, "MAR")

    engine.resolve_orders(
        {
            "FRANCE": ["A PAR - BUR", "A GAS S A PAR - BUR"],
            "ITALY": ["A MUN - BUR", "A RUH S A MUN - BUR"],
            "GERMANY": ["A BUR - GAS", "A MAR S A BUR - GAS"],
        }
    )

    assert engine.map.get_region("BUR").unit is italy_attacker
    assert engine.map.get_region("PAR").unit is france_attacker
    assert france_supporter.dislodged
    _assert_unit_map_consistency(engine)


def test_failed_convoy_attack_does_not_cut_support():
    engine = DiplomacyGameEngine()
    _clear_units(engine)
    france_attacker = _place_unit(engine, "FRANCE", UnitType.ARMY, "PIC")
    _place_unit(engine, "FRANCE", UnitType.ARMY, "BEL")
    _place_unit(engine, "FRANCE", UnitType.FLEET, "ENG")
    _place_unit(engine, "FRANCE", UnitType.FLEET, "HEL")
    germany_attacker = _place_unit(engine, "GERMANY", UnitType.ARMY, "MUN")
    _place_unit(engine, "GERMANY", UnitType.ARMY, "RUH")
    england_army = _place_unit(engine, "ENGLAND", UnitType.ARMY, "LON")
    convoy_fleet = _place_unit(engine, "ENGLAND", UnitType.FLEET, "NTH")

    engine.resolve_orders(
        {
            "FRANCE": [
                "A PIC - BUR",
                "A BEL S A PIC - BUR",
                "F ENG - NTH",
                "F HEL S F ENG - NTH",
            ],
            "GERMANY": ["A MUN - BUR", "A RUH S A MUN - BUR"],
            "ENGLAND": ["A LON - BEL", "F NTH C A LON - BEL"],
        }
    )

    # NTH is dislodged, so LON-BEL never attacks and cannot cut BEL's support.
    # The two strength-two attacks on BUR therefore bounce.
    assert convoy_fleet.dislodged
    assert engine.map.get_region("BUR").unit is None
    assert engine.map.get_region("PIC").unit is france_attacker
    assert engine.map.get_region("MUN").unit is germany_attacker
    assert engine.map.get_region("LON").unit is england_army
    _assert_unit_map_consistency(engine)


def test_standoff_province_is_not_a_retreat_option():
    engine = DiplomacyGameEngine()
    _clear_units(engine)
    _place_unit(engine, "FRANCE", UnitType.ARMY, "PAR")
    _place_unit(engine, "GERMANY", UnitType.ARMY, "MUN")
    dislodged = _place_unit(engine, "ITALY", UnitType.ARMY, "GAS")
    _place_unit(engine, "ENGLAND", UnitType.ARMY, "MAR")
    _place_unit(engine, "ENGLAND", UnitType.ARMY, "SPA")

    engine.resolve_orders(
        {
            "FRANCE": ["A PAR - BUR"],
            "GERMANY": ["A MUN - BUR"],
            "ENGLAND": ["A MAR - GAS", "A SPA S A MAR - GAS"],
            "ITALY": ["A GAS H"],
        }
    )

    assert dislodged.dislodged
    assert "BUR" not in dislodged.retreat_options
    _assert_unit_map_consistency(engine)


def test_omitted_adjustment_orders_auto_disband_and_detach_units():
    engine = DiplomacyGameEngine()
    _clear_units(engine)
    power = engine.powers["FRANCE"]
    first = _place_unit(engine, "FRANCE", UnitType.ARMY, "PAR")
    second = _place_unit(engine, "FRANCE", UnitType.ARMY, "MAR")
    power.controlled_centers = []
    engine.phase = PhaseType.ADJUSTMENTS
    engine.season = Season.WINTER

    engine.resolve_orders({})

    assert power.units == []
    assert first.region is None
    assert second.region is None
    assert engine.map.get_region("PAR").unit is None
    assert engine.map.get_region("MAR").unit is None
    _assert_unit_map_consistency(engine)


def test_invalid_whisper_target_is_atomic():
    env = DiplomacyEnv(negotiations_per_phase=2)
    env.reset(num_players=3, seed=42)
    events_before = list(env.state.events)
    history_before = list(env.chat_history)

    done, _ = env.step("Whisper to 99: secret")

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.state.events[:-1] == events_before
    assert env.chat_history == history_before


def test_whisper_is_visible_only_to_sender_and_recipient():
    env = DiplomacyEnv(negotiations_per_phase=2)
    env.reset(num_players=3, seed=42)
    secret = "private-passphrase"

    env.step(f"Whisper to 1: {secret}")

    matching_events = [event for event in env.state.events if secret in event[1]]
    assert len(matching_events) == 2
    assert {event[3] for event in matching_events} == {0, 1}
    assert all(event[3] != -1 for event in matching_events)


def test_defeated_power_is_removed_from_future_turn_rotation():
    env = DiplomacyEnv(negotiations_per_phase=1)
    env.reset(num_players=3, seed=42)
    defeated_pid = 1
    defeated_power = env.player_power_map[defeated_pid]
    power = env.engine.powers[defeated_power]
    for unit in list(power.units):
        if unit.region and unit.region.unit is unit:
            unit.region.unit = None
        unit.region = None
    power.units.clear()
    for center in list(power.controlled_centers):
        env.engine.map.get_region(center).owner = None
    power.controlled_centers.clear()

    _submit_orders_for_all(env, _hold_orders_action)

    assert not env.state.is_player_alive(defeated_pid)
    assert defeated_pid not in {
        env.state.current_player_id,
        env.state.next_alive_player(),
    }


def test_seed_and_snapshot_restore_replay_identically():
    first = DiplomacyEnv(negotiations_per_phase=2)
    second = DiplomacyEnv(negotiations_per_phase=2)
    first.reset(num_players=5, seed=2026)
    second.reset(num_players=5, seed=2026)
    assert first.player_power_map == second.player_power_map

    snapshot = first.snapshot()
    action = "Broadcast: deterministic replay"
    first.step(action)
    state_after = (
        first.state.current_player_id,
        first.current_negotiation_round,
        list(first.state.events),
        list(first.chat_history),
    )
    first.restore(snapshot)
    first.step(action)

    assert (
        first.state.current_player_id,
        first.current_negotiation_round,
        first.state.events,
        first.chat_history,
    ) == state_after


def test_terminal_outcome_reason_contains_final_center_counts():
    env = DiplomacyEnv()
    env.reset(num_players=3, seed=42)
    winning_power = env.player_power_map[0]
    env.engine.winners = [winning_power]

    outcome = env._announce_game_result()

    assert "Final supply center counts:" in outcome.reason
    for power_name, player_id in env.power_player_map.items():
        count = len(env.engine.powers[power_name].controlled_centers)
        assert (
            f"Player {player_id} ({power_name}): {count} centers"
            in outcome.reason
        )

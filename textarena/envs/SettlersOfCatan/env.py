import re
from collections import Counter
from typing import Optional, Dict, Any, Tuple, Union

import textarena as ta 
from textarena.envs.SettlersOfCatan.game_engine import Board, render_board, Terrain


# Canonical bare, line-anchored negotiation commands, matched against each
# stripped line. Accept/Deny/Done must be a line of their own (optional trailing
# punctuation) so incidental prose is not misparsed; any line starting with the
# word "offer" is an offer attempt and must be well formed.
_NEGO_DECISION_RE = re.compile(r'(accept|deny|done)[ \t]*[.!]?', re.I)
_NEGO_OFFER_WORD_RE = re.compile(r'offer\b', re.I)
_NEGO_OFFER_RE = re.compile(r'offer[ \t]*:(?P<body>.*)', re.I)
_MAX_COMMAND_CHARS = 500
_RESOURCE_PAIR_RE = re.compile(r'(\d+)\s+([A-Za-z]+)', re.I)
_RESOURCE_ORDER = (Terrain.BRICK, Terrain.WOOD, Terrain.WHEAT, Terrain.ORE, Terrain.SHEEP)

"""
- TODO add Thief logic
- TODO add development cards
- TODO add mini version maybe (i.e. smaller top score requirement)
"""

_RESOURCE_CANON = {"sheeps": "sheep", "woods": "wood"}

def _to_terrain(name: str) -> Terrain:
    base = _RESOURCE_CANON.get(name.lower(), name.lower())  # e.g., "woods"->"wood"
    return Terrain[base.upper()]  # "wood" -> Terrain.WOOD

def _parse_resource_list(text: str) -> Optional[Dict[Terrain, int]]:
    parts = [part.strip() for part in text.split(",")]
    if not parts or any(not part for part in parts):
        return None
    out: Dict[Terrain, int] = {}
    for part in parts:
        match = _RESOURCE_PAIR_RE.fullmatch(part)
        if match is None:
            return None
        qty_s, raw = match.groups()
        if len(qty_s) > 9: return None
        qty = int(qty_s)
        if qty <= 0: return None
        try: terr = _to_terrain(raw)
        except KeyError: return None  # unknown resource name
        if terr is Terrain.DESERT:
            return None
        out[terr] = out.get(terr, 0) + qty
    return out

def _parse_offer_body(body: str) -> Optional[Dict[str, Dict[Terrain, int]]]:
    body = ' '.join(body.split())
    body = body.rstrip('.,!?')
    body = re.sub(r'^(i\s+(?:give|offer)\s+)', '', body, flags=re.I)
    parts = re.split(r'\s*->\s*', body)
    if len(parts) != 2: return None
    offered   = _parse_resource_list(parts[0])
    requested = _parse_resource_list(parts[1])
    if not offered or not requested: return None
    return {"offered_resources": offered, "requested_resources": requested}

def _has_resources(player_inv: Counter, costs: Dict[Terrain, int]) -> bool:
    return all(player_inv.get(res, 0) >= qty for res, qty in costs.items())

def _format_resources(resources: Dict[Terrain, int]) -> str:
    return ", ".join(f"{qty} {terrain.name.title()}" for terrain, qty in resources.items())

def _format_offer(offer: Dict[str, Dict[Terrain, int]]) -> str:
    return f"{_format_resources(offer['offered_resources'])} -> {_format_resources(offer['requested_resources'])}"


def _parse_negotiation_command(
    action: str,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """Parse at most one negotiation control command from an action."""
    commands = []
    for line in action.splitlines():
        text = line.strip()
        decision = _NEGO_DECISION_RE.fullmatch(text)
        if decision:
            commands.append((decision.group(1).lower(), None))
            continue
        if _NEGO_OFFER_WORD_RE.match(text):
            match = _NEGO_OFFER_RE.fullmatch(text) if len(text) <= _MAX_COMMAND_CHARS else None
            parsed = _parse_offer_body(match.group("body")) if match else None
            if parsed is None:
                return None, None, (
                    "Malformed offer command. Put 'Offer: <resources you give> -> <resources you want>' on its own "
                    "line, e.g. 'Offer: 2 Wood, 1 Brick -> 1 Wheat'."
                )
            commands.append(("offer", {"body": _format_offer(parsed), **parsed}))
    if len(commands) > 1:
        return None, None, "Submit at most one negotiation command per action."
    if not commands:
        return None, None, None
    command, data = commands[0]
    return command, data, None


class SettlersOfCatanEnv(ta.GameEnv):
    min_players = 3
    max_players = 4
    broadcast_actions = False  # the raw action is echoed only to its author

    role_colors = {0: "Red", 1: "White", 2: "Blue", 3: "Orange"}
    pids_from_roles = {"red": 0, "white": 1, "blue": 2, "orange": 3}

    player_move_allowance = ta.Param(10, "The number of actions per turn.", min=1)
    max_turns = ta.Param(200, "The number of moves in the whole game, counting every valid reply from any player.", min=1)
    # Every player starts with two settlements (2 VP), so a lower target would end the game on the first move.
    winning_score = ta.Param(10, "The victory points needed to win; everyone starts with 2.", min=3)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.game_moves = None

    def roles(self) -> Dict[int, str]:
        return {
            pid: self.role_colors[pid]
            for pid in range(self.state.num_players)
        }

    def get_board_str(self):
        colour = self.board.str_to_enum(color_str=self.role_colors[self.state.current_player_id])
        scores = self.board.get_scores()
        score_lines = [f"{str(c):6} {rec['total']:>2} VP   (S:{rec['settlements']}  C:{rec['cities']}  R:{rec['roads']}) {'(eliminated)' if self.pids_from_roles[str(c)] in self.state.game_state['eliminated_players'] else ''}" for c, rec in scores.items()]
        hand_cards = ", ".join(
            f"{terrain.name.lower()}: {quantity}"
            for terrain, quantity in self.board.players[colour].hand.items()
        )
        return "\n".join([
            f"{'='*24} {colour.name} ({self.state.game_state['turn_phase']} - {self.state.game_state['move_count']} -- {self.state.turn}) {'='*24}",
            "Scores\n───────",
            "\n".join(score_lines),
            "",
            "Board\n──────",
            render_board(self.board),
            f"\nCurrent player's hand: {hand_cards}",
        ])

    def setup(self) -> Dict[str, Any]:
        self.board = Board.build_standard()
        active_colors = {
            self.board.str_to_enum(self.role_colors[pid])
            for pid in range(self.state.num_players)
        }
        for corner in self.board.corners.values():
            if corner.owner not in active_colors:
                corner.piece = None
                corner.owner = None
        for edge in self.board.edges.values():
            if edge.owner not in active_colors:
                edge.owner = None
        for color in list(self.board.players):
            if color not in active_colors:
                self.board.players.pop(color)
        return {
            "eliminated_players": set(), "move_allowance": self.player_move_allowance, "move_count": 0, "turn_done": False, "turn_phase": "action",
            "negotiation_partner": None, "main_negotiator": None,
            "current_offer": None
        }

    def on_start(self):
        self._roll_dice(self.state.current_player_id)

    def prompt(self, player_id: int) -> str:
        """Instruction prompt shown to each agent at game start and after resets."""
        color = self.role_colors[player_id]
        allowance = self.player_move_allowance

        return f"""
    You are playing Settlers of Catan as {color}.

    OBJECTIVE
    - Maximize Victory Points (VP).
    - The first player to reach {self.winning_score} VP wins.
    - VP sources implemented: Settlement = 1 VP, City = 2 VP.
    - Not implemented in this environment: Largest Road, Largest Army, Development cards / VP cards, and trading with the bank or harbors (you can only trade with other players).
    - The game also ends after {self.max_turns} moves in total, counting every valid reply from any player (including negotiation messages); players are then ranked by VP.

    TURN FLOW (what you can do)
    1) Dice are rolled automatically at the start of a turn and resources are distributed to any settlements/cities on tiles matching the roll (desert produces nothing).
    – Note: The robber and special 7-roll behavior are not implemented.
    2) During your action phase you may take up to {allowance} actions. Each of the following counts as 1 action:
    – Build ROAD
    – Build SETTLEMENT
    – Upgrade CITY
    – Start a NEGOTIATION (trading with a single opponent)
    – Do NOTHING (end your turn early)

    HOW TO SELECT ACTIONS
    - You will receive a "Viable moves" list. To pick one, reply with its index, e.g. "3".
    - If you pick "Negotiate.", you must then select the partner by replying with exactly one id:
    "0" or "Red" or "1" or "White" etc. (ids or color names both work).
    - To end your turn early choose the "Nothing." option.

    BUILD COSTS (must have enough resources in hand)
    - ROAD:    1 Brick, 1 Wood
    - SETTLEMENT: 1 Brick, 1 Wood, 1 Wheat, 1 Sheep
    - CITY:    3 Ore, 2 Wheat
    - Piece limits: 15 Roads, 5 Settlements, 4 Cities

    TRADING / NEGOTIATION (one counterparty at a time)
    - Make an offer by putting this command on its own line (exact format):
    Offer: 2 Wood, 1 Brick -> 1 Wheat
    (Use singular resource names: Wheat, Wood, Sheep, Brick, Ore. Case-insensitive; plurals like "woods" and "sheeps" are also accepted.)
    - The other player can respond with a line containing exactly:
    Accept   — trade executes if both sides have the resources
    Deny     — trade is declined
    - Only one offer can be open at a time; it stays open until its recipient accepts or denies it.
    - Either negotiator ends the negotiation with a line containing exactly: Done
    - Starting the negotiation consumes 1 action. Messages and "Done" do not consume additional actions.
    - While negotiating, you can also send normal chat text on other lines alongside these commands; it is shown only to your negotiation partner. Any line that starts with "Offer" is read as an offer and must use the exact format.

    BOARD LEGEND (text board you will see)
    - Settlements appear as 'V' with the owner initial near them; Cities as 'C'.
    - Roads draw across edges. Empty horizontal edges show "______"; owned horizontal edges show the owner's letter repeated.
    - Tile labels show terrain and number tokens; desert produces nothing.

    GUIDELINES
    - Always pick a legal move from the provided list using its index.
    - If you cannot build, consider negotiating for needed resources; otherwise choose "Nothing." to end your turn.
    - Be concise but explicit: show your choice and any required follow-up in the correct format.

    Now wait for the "Board" and "Viable moves" list, then respond with your action index, e.g. "1".
    """.strip()

    def _roll_dice(self, player_id: int):
        roll_str, added_clean = self.board.roll_dice(self.rng)
        if any([len(qty_dict)!=0 for color, qty_dict in added_clean.items()]):
            message = f"Player {player_id} ({self.role_colors[player_id]}) rolled: {roll_str}. Items received:"
            for color, qty_dict in added_clean.items():
                if len(qty_dict) == 0: continue
                message += f"\n\t {color}: " + ', '.join([f"{terrain}: +{qty}" for terrain, qty in qty_dict.items()])
        else: message = f"Player {player_id} ({self.role_colors[player_id]}) rolled: {roll_str}. Nobody received anything."
        self.broadcast(message, ta.ObservationType.GAME_MESSAGE)

    def render(self, player_id: int) -> Optional[str]:
        """Board + viable-move list in the action phase; hand + open offer while negotiating."""
        phase = self.state.game_state["turn_phase"]
        if phase == "negotiation":
            return self._render_negotiation(player_id)
        if phase != "action":
            return None
        colour = self.board.str_to_enum(color_str=self.role_colors[player_id])
        player = self.board.players[colour]
        scores = self.board.get_scores()
        score_lines = [f"{str(c):6} {rec['total']:>2} VP   (S:{rec['settlements']}  C:{rec['cities']}  R:{rec['roads']}) {'(eliminated)' if self.pids_from_roles[str(c)] in self.state.game_state['eliminated_players'] else ''}" for c, rec in scores.items()]
        self.game_moves = self.board._viable_moves(player)
        len_game_moves = len(self.game_moves)
        self.game_moves += [(len_game_moves+1, f"Negotiate.", None), (len_game_moves+2, f"Nothing.", None)]
        move_block = "\n".join(f"'{idx}'\t-  {desc}" for idx, desc, _ in self.game_moves)
        hand_cards = '\n\t'.join(f'{k.name.lower()}: {v}' for k,v in player.hand.items())
        remaining_turn_moves = self.state.game_state["move_allowance"] - self.state.game_state["move_count"]
        return "\n".join([
            f"{'='*24}  {colour.name}  {'='*24}", "Scores\n───────", "\n".join(score_lines), "", "Board\n──────", render_board(self.board),
            "", f"Your hand cards are:\n\t{hand_cards}", "", "Viable moves\n────────────", move_block, "Please select one of the viable actions by replying with the move index, e.g. '3'.",
            f"You have {remaining_turn_moves} moves left in your turn."
        ])

    def _render_negotiation(self, player_id: int) -> str:
        gs = self.state.game_state
        partner = gs["negotiation_partner"] if player_id == gs["main_negotiator"] else gs["main_negotiator"]
        hand = self.board.players[self.board.str_to_enum(self.role_colors[player_id])].hand
        lines = [
            f"NEGOTIATION between Player {gs['main_negotiator']} ({self.role_colors[gs['main_negotiator']]}) "
            f"and Player {gs['negotiation_partner']} ({self.role_colors[gs['negotiation_partner']]})",
            "Your hand: " + ", ".join(f"{terrain.name.lower()}: {hand.get(terrain, 0)}" for terrain in _RESOURCE_ORDER),
        ]
        offer = gs["current_offer"]
        if offer is None:
            lines.append("No open offer. Put 'Offer: <give> -> <get>' on its own line to propose a trade.")
        else:
            lines.append(
                f"Open offer from Player {offer['from_player']} to Player {offer['to_player']}: "
                f"{_format_offer(offer)} (the proposer gives the resources before '->')"
            )
            if offer["to_player"] == player_id:
                lines.append("Reply with a line containing exactly 'Accept' or 'Deny'.")
        lines.append(f"Chat with Player {partner} ({self.role_colors[partner]}) freely; a line containing exactly 'Done' ends the negotiation.")
        return "\n".join(lines)

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        """A player who exceeds the error allowance is eliminated from play; the turn moves on."""
        gs = self.game_state
        phase = gs["turn_phase"]
        turn_owner = (
            gs.get("main_negotiator")
            if phase == "negotiation"
            else player_id
        )
        self.eliminate(player_id)
        gs["eliminated_players"].add(player_id)
        self.broadcast(f"Player {player_id} ({self.role_colors[player_id]}) has been eliminated because of repeated invalid moves.", ta.ObservationType.GAME_ADMIN)
        active_players = [
            pid for pid in range(self.state.num_players)
            if pid not in gs["eliminated_players"]
        ]
        if len(active_players) <= 1:
            if active_players:
                return self.winner(
                    active_players[0],
                    reason=f"Player {active_players[0]} is the last remaining player.",
                )
            return self.draw(reason="All players were eliminated.")

        # If a counterparty is eliminated during somebody else's negotiation,
        # cancel the negotiation and return the still-valid turn to its owner.
        if (
            phase == "negotiation"
            and turn_owner is not None
            and player_id != turn_owner
            and self.state.is_player_alive(turn_owner)
        ):
            gs["turn_done"] = False
            gs["turn_phase"] = "action"
            gs["negotiation_partner"] = None
            gs["main_negotiator"] = None
            gs["current_offer"] = None
            if gs["move_count"] < gs["move_allowance"]:
                self.set_next_player(turn_owner)
                return None
            next_pid = self._next_active_player(turn_owner)
        else:
            next_pid = self._next_active_player(
                turn_owner if turn_owner is not None else player_id
            )

        gs["turn_done"] = False
        gs["move_count"] = 0
        gs["turn_phase"] = "action"
        gs["negotiation_partner"] = None
        gs["main_negotiator"] = None
        gs["current_offer"] = None
        self.set_next_player(next_pid)
        self._roll_dice(next_pid)
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self._determine_winner()

    def _next_active_player(self, from_pid: int) -> Optional[int]:
        """Next clockwise player who has not been eliminated; None if nobody else remains."""
        _next = lambda x: (x+1)%self.state.num_players
        next_pid = _next(from_pid)
        while next_pid != from_pid:
            if next_pid not in self.state.game_state["eliminated_players"]:
                return next_pid
            next_pid = _next(next_pid)
        return None

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        colour = self.board.str_to_enum(color_str=self.role_colors[player_id])
        next_holder = player_id  # who holds the turn after this action (never auto-rotated)
        match gs["turn_phase"]:
            case "action":
                m = re.fullmatch(r'\s*(\d+)\s*', action.strip())
                if m is None: return self.invalid("No action found. Please reply with the index of a viable move, e.g. '3'.")
                act = int(m.group(1)) if len(m.group(1)) <= 6 else 0
                if act > len(self.game_moves) or act <=0: 
                    return self.invalid("Selected action index is out of bounds. Please select from the list.")

                elif act == len(self.game_moves): # skip turn selected
                    self.broadcast(f"Player {player_id} ({self.role_colors[player_id]}) ends his turn.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    gs["turn_done"] = True

                elif act == len(self.game_moves)-1: # player selectes negotiation
                    gs["move_count"] += 1
                    gs["turn_phase"] = "negotiation_start"
                    pid_options = ", ".join([f"'{pid}'/'{self.role_colors[pid]}'" for pid in range(self.state.num_players) if (pid not in gs["eliminated_players"] and pid != player_id)])
                    self.message(player_id, f"You selected action {len(self.game_moves)-1} (Negotiation). Please select a player you would like to negotiation with. The options are: {pid_options}. Please select exactly one.", ta.ObservationType.GAME_MESSAGE)
                    self.set_next_player(player_id)
                    return None

                else: # player selected a game action
                    selected = next(m for m in self.game_moves if m[0] == act)
                    player = self.board.players[colour]
                    ok, err = self.board.execute_action(player, selected[2])
                    if not ok:
                        return self.invalid(err or "The selected build is no longer legal.")
                    gs["move_count"] += 1
                    self.broadcast(f"Player {player_id} ({self.role_colors[player_id]}): {' '.join(selected[1].split())}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

            case "negotiation_start":
                successful = self._negotiation_partner_selection(player_id, action=action)
                if not successful: # invalid move 
                    options = ", ".join(f"'{pid}'/'{self.role_colors[pid]}'" for pid in range(self.state.num_players) if pid != player_id and pid not in gs["eliminated_players"])
                    return self.invalid(f"Invalid negotiation partner selection. Reply with exactly one of: {options}.")

            case "negotiation":
                result = self._negotiation_message(player_id, action=action)
                if isinstance(result, ta.Invalid):
                    return result
                next_holder = result

        # check for win
        scores = self.board.get_scores()
        if any(
            scores[self.board.str_to_enum(self.role_colors[pid])]["total"]
            >= self.winning_score
            for pid in range(self.state.num_players)
            if pid not in gs["eliminated_players"]
        ):
            return self._determine_winner()
        # check for turn over
        if (
            gs["turn_phase"] == "action"
            and (
                gs["turn_done"]
                or gs["move_count"] >= gs["move_allowance"]
            )
        ):
            next_pid = self._next_active_player(next_holder)
            if next_pid is None:
                return self._determine_winner()
            gs["turn_done"] = False; gs["move_count"] = 0
            gs["turn_phase"] = "action"
            gs["negotiation_partner"] = None
            gs["main_negotiator"] = None
            gs["current_offer"] = None
            self.set_next_player(next_pid)
            self._roll_dice(next_pid)
        else:
            self.set_next_player(next_holder)
        return None

    def _negotiation_partner_selection(self, player_id: int, action: str):
        gs = self.game_state
        pid_options = [pid for pid in range(self.state.num_players) if (pid not in gs["eliminated_players"] and pid != player_id)]
        m = re.fullmatch(r'(?i)\s*([0123]|red|white|blue|orange)\s*', action.strip())
        if m is None: return False
        choice = m.group(1).lower()
        choice = self.pids_from_roles[choice] if choice in self.pids_from_roles else int(choice)
        if choice not in pid_options: return False
        gs["negotiation_partner"] = choice
        gs["main_negotiator"] = player_id
        negotiation_explanation = "You can converse freely and make trade offers by putting the command on its own line, e.g. 'Offer: 3 Sheep, 2 Ore -> 5 Brick, 2 Sheep' (format: Offer: Offered Resources -> Requested Resources). When you receive a trade offer, reply with a line containing exactly 'Accept' or 'Deny'"
        self.message(player_id, f"You have selected Player {choice} ({self.role_colors[choice]}) to negotiation with. {negotiation_explanation}. When you are done negotiating, reply with a line containing exactly 'Done'. You may now send your first message.", ta.ObservationType.GAME_MESSAGE)
        self.message(choice, f"Player {player_id} ({self.role_colors[player_id]}) selected you to negotiate with. {negotiation_explanation}.", ta.ObservationType.GAME_MESSAGE)
        gs["turn_phase"] = "negotiation"
        return True

    def _negotiation_message(self, player_id: int, action: str) -> Union[ta.Invalid, int]:
        """Handle one negotiation message; returns the pid holding the turn next, or Invalid."""
        gs = self.game_state
        me = player_id
        owner = gs["main_negotiator"]
        opp = gs["negotiation_partner"] if me == owner else owner
        action = self.strip_role_tags(action).strip()  # commands are read from exactly the text the partner sees
        command, offer_data, error = _parse_negotiation_command(action)
        if error:
            return self.invalid(error)
        # 1) A 'Done' line ends negotiation immediately for BOTH players; the turn returns to its owner
        if command == "done":
            self._share_negotiation_message(me, opp, action)
            gs["turn_phase"] = "action"
            gs["negotiation_partner"] = None
            gs["main_negotiator"] = None
            gs["current_offer"] = None
            self.broadcast("Negotiation finished.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return owner
        # 2) Accept / Deny an existing offer (if I'm the receiver)
        if command in {"accept", "deny"}:
            if (
                not gs.get("current_offer")
                or gs["current_offer"]["to_player"] != me
            ):
                return self.invalid("There is no offer for you to resolve.")
            if command == "accept":
                result = self._execute_trade_accept()
                if isinstance(result, ta.Invalid):
                    return result
            else:
                self._notify_negotiators(
                    f"Player {me} denied the trade offer."
                )
                gs["current_offer"] = None
        # 3) Look for a NEW offer (only one active at a time)
        if command == "offer":
            if gs.get("current_offer"):
                return self.invalid(
                    "Resolve the current offer before making another."
                )
            player = self.board.players[
                self.board.str_to_enum(self.role_colors[me])
            ]
            if not _has_resources(
                player.hand, offer_data["offered_resources"]
            ):
                return self.invalid(
                    f"Unaffordable offer: you do not hold {_format_resources(offer_data['offered_resources'])}."
                )
            body = offer_data.pop("body")
            gs["current_offer"] = {
                "from_player": me,
                "to_player": opp,
                **offer_data,
            }
            self._notify_negotiators(
                f"Player {me} offered to Player {opp}: {body}"
            )
        self._share_negotiation_message(me, opp, action)
        return opp

    def _share_negotiation_message(self, sender: int, recipient: int, action: str):
        # The engine already echoes the raw action to its author.
        self.message(recipient, action, ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=sender)

    def _notify_negotiators(self, message: str) -> None:
        participants = {
            self.game_state.get("main_negotiator"),
            self.game_state.get("negotiation_partner"),
        }
        for player_id in participants:
            if player_id is not None:
                self.message(
                    player_id,
                    message,
                    ta.ObservationType.GAME_ACTION_DESCRIPTION,
                )

    def _execute_trade_accept(self) -> Optional[ta.Invalid]:
        gs = self.game_state
        offer = gs["current_offer"]
        giver_pid = offer["from_player"]
        taker_pid = offer["to_player"]
        giver_c = self.board.str_to_enum(self.role_colors[giver_pid])
        taker_c = self.board.str_to_enum(self.role_colors[taker_pid])
        giver_pl = self.board.players[giver_c]
        taker_pl = self.board.players[taker_c]
        if not (_has_resources(taker_pl.hand, offer["requested_resources"]) and _has_resources(giver_pl.hand, offer["offered_resources"])):
            return self.invalid("Trade failed: resources missing.")

        for terr, qty in offer["offered_resources"].items():    giver_pl.hand[terr] -= qty; taker_pl.hand[terr] += qty
        for terr, qty in offer["requested_resources"].items():  taker_pl.hand[terr] -= qty; giver_pl.hand[terr] += qty
        fmt = lambda d: {t.name.title(): n for t, n in d.items()}
        self._notify_negotiators(
            f"Trade executed: Player {giver_pid} → {taker_pid} "
            f"(offered {fmt(offer['offered_resources'])} / "
            f"requested {fmt(offer['requested_resources'])})."
        )
        gs["current_offer"] = None

    def _determine_winner(self) -> ta.Outcome:
        scores = self.board.get_scores()  # {Color: {"total": vp, ...}}
        eliminated = set(self.game_state["eliminated_players"])
        active = [pid for pid in range(self.state.num_players) if pid not in eliminated]
        if not active:
            return self.draw(reason=f"All players were eliminated. Final scores: {scores}")

        # 1) collect VP per active pid
        pid_vp: dict[int, int] = {}
        for pid in active:
            color = self.board.str_to_enum(self.role_colors[pid])
            pid_vp[pid] = scores[color]["total"]
        # 2) worst→best order by VP
        ranked = sorted(active, key=lambda p: pid_vp[p])
        # 3) dense tie-groups by equal VP (still worst→best)
        groups: list[list[int]] = []
        for pid in ranked:
            if not groups or pid_vp[groups[-1][0]] != pid_vp[pid]: groups.append([pid])
            else: groups[-1].append(pid)
        # 4) map groups to rewards in [-1, +1]
        G = len(groups)
        reward_dict = {pid: -1.0 for pid in eliminated}
        if G == 1:
            tied_reward = 1.0 if eliminated else 0.0
            reward_dict.update({pid: tied_reward for pid in groups[0]})
        else:
            for g_idx, g in enumerate(groups):            # g_idx: 0..G-1 (worst..best)
                r = -1.0 + 2.0 * (g_idx / (G - 1))        # linear scale
                for pid in g: reward_dict[pid] = r
        # 5) end game with summary
        score_summary = "; ".join(
            (
                f"Player {pid} ({self.role_colors[pid]}): "
                f"{scores[self.board.str_to_enum(self.role_colors[pid])]['total']} VP"
                f"{' (eliminated)' if pid in eliminated else ''}"
            )
            for pid in range(self.state.num_players)
        )
        return self.outcome(
            reward_dict,
            reason=f"Final ranking by victory points: {score_summary}",
        )

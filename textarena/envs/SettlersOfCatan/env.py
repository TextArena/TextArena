import re
from collections import Counter
from typing import Optional, Dict, Any, Tuple, Union

import textarena as ta 
from textarena.envs.SettlersOfCatan.game_engine import Board, render_board, Terrain


# Canonical bare, line-anchored negotiation commands. Accept/Deny/Done must be
# a line of their own (optional trailing punctuation) so incidental prose is
# not misparsed; Offer takes the rest of its line. Stray square brackets from
# the legacy format are tolerated.
_NEGO_ACCEPT_RE = re.compile(r'^[ \t]*\[?accept\]?[ \t]*[.!]?[ \t]*$', re.I | re.M)
_NEGO_DENY_RE   = re.compile(r'^[ \t]*\[?deny\]?[ \t]*[.!]?[ \t]*$',   re.I | re.M)
_NEGO_DONE_RE   = re.compile(r'^[ \t]*\[?done\]?[ \t]*[.!]?[ \t]*$',   re.I | re.M)
_NEGO_OFFER_RE  = re.compile(r'^[ \t]*\[?offer[ \t]*:[ \t]*(?:i[ \t]+(?:give|offer)[ \t]+)?([^\[\]\n]+?)[ \t]*\]?[ \t]*$', re.I | re.M)
_NEGO_OFFER_PREFIX_RE = re.compile(r'^[ \t]*\[?offer\b[^\n]*$', re.I | re.M)
_RESOURCE_PAIR_RE = re.compile(r'(\d+)\s+([A-Za-z]+)', re.I)

"""
- TODO show hand cards at start of negotiation (to nego opponents)
- TODO show num remaining moves for player

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
    body = re.sub(r'[.,!?]+$', '', body)
    body = re.sub(r'^(i\s+(?:give|offer)\s+)', '', body, flags=re.I)
    parts = re.split(r'\s*->\s*', body)
    if len(parts) != 2: return None
    offered   = _parse_resource_list(parts[0])
    requested = _parse_resource_list(parts[1])
    if not offered or not requested: return None
    return {"offered_resources": offered, "requested_resources": requested}

def _has_resources(player_inv: Counter, costs: Dict[Terrain, int]) -> bool:
    return all(player_inv.get(res, 0) >= qty for res, qty in costs.items())


def _parse_negotiation_command(
    action: str,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """Parse at most one negotiation control command from an action."""
    accept_count = len(list(_NEGO_ACCEPT_RE.finditer(action)))
    deny_count = len(list(_NEGO_DENY_RE.finditer(action)))
    done_count = len(list(_NEGO_DONE_RE.finditer(action)))
    offer_prefixes = list(_NEGO_OFFER_PREFIX_RE.finditer(action))
    offer_matches = list(_NEGO_OFFER_RE.finditer(action))

    if len(offer_prefixes) != len(offer_matches):
        return None, None, "Malformed offer command."
    command_count = (
        accept_count + deny_count + done_count + len(offer_prefixes)
    )
    if command_count > 1:
        return None, None, "Submit at most one negotiation command per action."
    if done_count:
        return "done", None, None
    if accept_count:
        return "accept", None, None
    if deny_count:
        return "deny", None, None
    if offer_matches:
        body = offer_matches[0].group(1)
        parsed = _parse_offer_body(body)
        if parsed is None:
            return None, None, "Malformed offer command."
        return "offer", {"body": body, **parsed}, None
    return None, None, None


class SettlersOfCatanEnv(ta.GameEnv):
    min_players = 3
    max_players = 4
    broadcast_actions = False  # the raw action is echoed only to its author

    role_colors = {0: "Red", 1: "White", 2: "Blue", 3: "Orange"}
    pids_from_roles = {"red": 0, "white": 1, "blue": 2, "orange": 3}

    def __init__(self, player_move_allowance: int = 10, max_turns: int = 200, winning_score: int = 10):
        if player_move_allowance < 1:
            raise ValueError("player_move_allowance must be at least one")
        if max_turns < 1:
            raise ValueError("max_turns must be at least one")
        if winning_score < 1:
            raise ValueError("winning_score must be at least one")
        self.game_moves = None
        self.player_move_allowance = player_move_allowance
        self.max_turns = max_turns
        self.winning_score = winning_score

    def roles(self) -> Dict[int, str]:
        return {
            pid: self.role_colors[pid]
            for pid in range(self.state.num_players)
        }

    def get_board_str(self):
        cpid = self.state.current_player_id
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
    - Not implemented in this environment: Largest Road, Largest Army, Development cards / VP cards.

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
    - Starting the negotiation consumes 1 action. Messages and "Done" do not consume additional actions.
    - While negotiating, you can also send normal chat text on other lines alongside these commands.

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
        """Board + viable-move list shown to the player about to act (action phase only)."""
        if self.state.game_state["turn_phase"] != "action":
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
                m = re.search(r'^\s*\[?\s*(\d+)\s*\]?\s*$', action)
                if m is None: return self.invalid("No action found. Please reply with the index of a viable move, e.g. '3'.")
                act = int(m.group(1))
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

            case "negotiation_start":
                successful = self._negotiation_partner_selection(player_id, action=action)
                if not successful: # invalid move 
                    return self.invalid(f"Invalid negotiation partner selection. Received: {action}")

            case "negotiation":
                if player_id == gs["main_negotiator"]: result = self._negotiation_step(player_id, action=action)
                else: result = self._negotiation_response_step(player_id, action=action)
                if isinstance(result, ta.Invalid):
                    return result
                if result is not None:
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
        m_list = list(re.compile(r'(?i)^\s*\[?\s*([0123]|red|white|blue|orange)\s*\]?\s*$').finditer(action))
        if not m_list: return False
        m = m_list[-1]
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

    def _negotiation_step(self, player_id: int, action: str) -> Union[ta.Invalid, int, None]:
        """Returns the pid holding the turn next, or Invalid."""
        gs = self.game_state
        me = player_id
        opp = gs["negotiation_partner"]
        command, offer_data, error = _parse_negotiation_command(action)
        if error:
            return self.invalid(error)
        # 1) A 'Done' line ends negotiation immediately for BOTH players
        if command == "done":
            self._share_negotiation_message(me, opp, action)
            gs["turn_phase"] = "action"
            gs["negotiation_partner"] = None
            gs["main_negotiator"] = None
            gs["current_offer"] = None
            self.broadcast("Negotiation finished.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return me
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
                    f"Malformed or unaffordable offer. Submitted action: {action}"
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

    def _negotiation_response_step(self, player_id: int, action: str) -> Union[ta.Invalid, int, None]:
        """Returns the pid holding the turn next, or Invalid."""
        gs = self.game_state
        me = player_id
        opp = gs["main_negotiator"]
        command, offer_data, error = _parse_negotiation_command(action)
        if error:
            return self.invalid(error)
        if command == "done":
            self._share_negotiation_message(me, opp, action)
            gs["turn_phase"] = "action"
            gs["negotiation_partner"] = None
            gs["main_negotiator"] = None
            gs["current_offer"] = None
            self.broadcast("Negotiation finished.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return opp
        # 1) Accept / Deny an existing offer (if I'm the receiver)
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
        # 2) Look for a NEW offer (only one active at a time)
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
                    f"Malformed or unaffordable offer. Submitted action: {action}"
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
        self.message(recipient, action, ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=sender)
        self.message(sender, action, ta.ObservationType.GAME_ACTION_DESCRIPTION, from_id=sender)

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

import re
from collections import Counter
from typing import Optional, Dict, Any, Tuple

import textarena as ta 
from textarena.envs.SettlersOfCatan.game_engine import Board, render_board, Terrain
from textarena.envs.SettlersOfCatan.renderer import render_hand_cards_table


_NEGO_ACCEPT_RE = re.compile(r'\[accept\]', re.I)
_NEGO_DENY_RE   = re.compile(r'\[deny\]',   re.I)
_NEGO_DONE_RE   = re.compile(r'\[done\]',   re.I)
_NEGO_OFFER_RE  = re.compile(r'\[offer:?\s*(?:i\s+(?:give|offer)\s+)?([^\[\]]+?)\s*\]', re.I | re.S)
_RESOURCE_PAIR_RE = re.compile(r'(\d+)\s+([A-Za-z]+)', re.I)
_RESOURCE_CANON = {"Sheeps": "Sheep", "Woods": "Wood"}
_C2_RES_NAMES = ["Wheat", "Wood", "Sheep", "Brick", "Ore"]

"""
- TODO show hand cards at start of negotiation (to nego opponents)
- TODO show num remaining moves for player

- TODO add Thief logic
- TODO add development cards
- TODO add mini version maybe (i.e. smaller top score requirement)
"""

_RESOURCE_CANON = {"sheeps": "sheep", "woods": "wood"}  # extend if you like

def _to_terrain(name: str) -> Terrain:
    base = _RESOURCE_CANON.get(name.lower(), name.lower())  # e.g., "woods"->"wood"
    return Terrain[base.upper()]  # "wood" -> Terrain.WOOD

def _parse_resource_list(text: str) -> Optional[Dict[Terrain, int]]:
    pairs = _RESOURCE_PAIR_RE.findall(text)
    if not pairs: return None
    out: Dict[Terrain, int] = {}
    for qty_s, raw in pairs:
        qty = int(qty_s)
        if qty <= 0: return None
        try: terr = _to_terrain(raw)
        except KeyError: return None  # unknown resource name
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

def _has_resources(player_inv: Counter[Terrain], costs: Dict[Terrain, int]) -> bool:
    return all(player_inv.get(res, 0) >= qty for res, qty in costs.items())

class SettlersOfCatanEnv(ta.Env):
    roles = {0: "Red", 1: "White", 2: "Blue", 3: "Orange"}
    pids_from_roles = {"red": 0, "white": 1, "blue": 2, "orange": 3}
    def __init__(self, player_move_allowance: int=10, max_turns: int=200):
        self.game_moves = None
        self.player_move_allowance = player_move_allowance
        self.max_turns = max_turns

    def get_board_str(self):
        cpid = self.state.current_player_id
        colour = self.board.str_to_enum(color_str=self.roles[self.state.current_player_id])
        scores = self.board.get_scores()
        score_lines = [f"{str(c):6} {rec['total']:>2} VP   (S:{rec['settlements']}  C:{rec['cities']}  R:{rec['roads']}) {'(eliminated)' if self.pids_from_roles[str(c)] in self.state.game_state['eliminated_players'] else ''}" for c, rec in scores.items()]
        hand_cards = render_hand_cards_table(board=self.board, eliminated_pids=self.state.game_state["eliminated_players"], pids_from_roles=self.pids_from_roles)
        return "\n".join([f"{'='*24} {colour.name} ({self.state.game_state['turn_phase']} - {self.state.game_state['move_count']} -- {self.state.turn}) {'='*24}", "Scores\n───────", "\n".join(score_lines), "", "Board\n──────", render_board(self.board), hand_cards])


    def reset(self, num_players: int, seed: Optional[int]=None):
        assert num_players == 4, f"Environment is hard-coded for exactly four players. Received {num_players} players on reset."
        self.state = ta.MinimalMultiPlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        self.board = Board.build_standard()
        game_state = {
            "eliminated_players": set(), "move_allowance": self.player_move_allowance, "move_count": 0, "turn_done": False, "turn_phase": "action",
            "negotiation_partner": None, "trade_offer": None
        }
        self.state.reset(game_state=game_state, role_mapping=self.roles, player_prompt_function=self._prompt)
        # for _ in range(20): self._roll_dice() # for testing
        self._roll_dice()
        self._render_board_state()
    
    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        """Instruction prompt shown to each agent at game start and after resets."""
        color = self.roles[player_id]
        allowance = self.player_move_allowance

        return f"""
    You are playing Settlers of Catan as {color}.

    OBJECTIVE
    - Maximize Victory Points (VP).
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
    - You will receive a "Viable moves" list. To pick one, reply with its index in square brackets, e.g. "[3]".
    - If you pick "Negotiate.", you must then select the partner by sending exactly one bracketed id:
    "[0]" or "[Red]" or "[1]" or "[White]" etc. (ids or color names both work).
    - To end your turn early choose the "Nothing." option.

    BUILD COSTS (must have enough resources in hand)
    - ROAD:    1 Brick, 1 Wood
    - SETTLEMENT: 1 Brick, 1 Wood, 1 Wheat, 1 Sheep
    - CITY:    3 Ore, 2 Wheat

    TRADING / NEGOTIATION (one counterparty at a time)
    - Make an offer with the exact format:
    [Offer: 2 Wood, 1 Brick -> 1 Wheat]
    (Use singular resource names: Wheat, Wood, Sheep, Brick, Ore. Case-insensitive; plurals like "woods" and "sheeps" are also accepted.)
    - The other player can respond with:
    [accept]   — trade executes if both sides have the resources
    [deny]     — trade is declined
    - Either side may type [done] to leave negotiation (consumes 1 action for the player who initiated negotiation).
    - While negotiating, you can also send normal chat text along with these tags.

    BOARD LEGEND (text board you will see)
    - Settlements appear as 'V' with the owner initial near them; Cities as 'C'.
    - Roads draw across edges. Empty horizontal edges show "______"; owned horizontal edges show the owner's letter repeated.
    - Tile labels show terrain and number tokens; desert produces nothing.

    GUIDELINES
    - Always pick a legal move from the provided list using the bracketed index.
    - If you cannot build, consider negotiating for needed resources; otherwise choose "Nothing." to end your turn.
    - Be concise but explicit: show the bracketed choice and any required follow-up in the correct format.

    Now wait for the "Board" and "Viable moves" list, then respond with your action index, e.g. "[1]".
    """.strip()

    def _roll_dice(self):
        roll_str, added_clean = self.board.roll_dice()
        if any([len(qty_dict)!=0 for color, qty_dict in added_clean.items()]):
            message = f"Player {self.state.current_player_id} ({self.roles[self.state.current_player_id]}) rolled: {roll_str}. Items received:"
            for color, qty_dict in added_clean.items():
                if len(qty_dict) == 0: continue
                message += f"\n\t {color}: " + ', '.join([f"{terrain}: +{qty}" for terrain, qty in qty_dict.items()])
        else: message = f"Player {self.state.current_player_id} ({self.roles[self.state.current_player_id]}) rolled: {roll_str}. Nobody received anything."
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_MESSAGE)

    def _render_board_state(self):
        cpid = self.state.current_player_id
        colour = self.board.str_to_enum(color_str=self.roles[self.state.current_player_id])
        player = self.board.players[colour]
        scores = self.board.get_scores()
        score_lines = [f"{str(c):6} {rec['total']:>2} VP   (S:{rec['settlements']}  C:{rec['cities']}  R:{rec['roads']}) {'(eliminated)' if self.pids_from_roles[str(c)] in self.state.game_state['eliminated_players'] else ''}" for c, rec in scores.items()]
        self.game_moves = self.board._viable_moves(player)
        len_game_moves = len(self.game_moves)
        self.game_moves += [(len_game_moves+1, f"Negotiate.", None), (len_game_moves+2, f"Nothing.", None)]
        move_block = "\n".join(f"'[{idx}]'\t-  {desc}" for idx, desc, _ in self.game_moves) 
        hand_cards = '\n\t'.join(f'{k.name.lower()}: {v}' for k,v in player.hand.items())
        remaining_turn_moves = self.state.game_state["move_allowance"] - self.state.game_state["move_count"]
        message = "\n".join([
            f"{'='*24}  {colour.name}  {'='*24}", "Scores\n───────", "\n".join(score_lines), "", "Board\n──────", render_board(self.board),
            "", f"Your hand cards are:\n\t{hand_cards}", "", "Viable moves\n────────────", move_block, "Please select on of the viable actions by returning '[idx]' as part of your action."
            f"You have {remaining_turn_moves} moves left in your turn."
        ])
        self.state.add_observation(to_id=cpid, message=message, observation_type=ta.ObservationType.GAME_BOARD)

    def _handle_invalid(self, reason):
        player_terminated = self.state.set_invalid_move(reason=reason)
        if player_terminated:
            pid = self.state.current_player_id
            self.state.game_state["eliminated_players"].add(pid)
            self.state.add_observation(message=f"Player {pid} ({self.roles[pid]}) has been eliminated because of repeated invalid moves.", observation_type=ta.ObservationType.GAME_ADMIN)
            return True
        return False

    def _rotate_players(self, force: bool):
        # check for the next non eliminated player
        _next = lambda x: (x+1)%self.state.num_players
        next_pid = _next(self.state.current_player_id)
        while next_pid != self.state.current_player_id:
            if next_pid not in self.state.game_state["eliminated_players"]:
                self.state.manually_set_current_player_id(new_player_id=next_pid, force=force) # set next player
                self.state.game_state["turn_done"] = False; self.state.game_state["move_count"] = 1
                self.state.game_state["turn_phase"] = "action"
                return
            else: next_pid = _next(next_pid)
        self._determine_winner() # if we reach here, no more alive players. End game 
        return

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, to_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        # Safeguard the game always terminates. The only "natural" endings are a
        # player reaching the VP target or every player being eliminated; without
        # this, a table that never reaches the target (e.g. everyone repeatedly
        # choosing "Nothing.") would run forever. On reaching the turn cap we
        # resolve on points, ranked by VP (the same ranking used on elimination).
        if self.state.turn >= self.state.max_turns and not self.state.done:
            self.state.add_observation(message=f"The turn limit ({self.state.max_turns}) was reached without a player hitting the victory-point target. Resolving on victory points.", observation_type=ta.ObservationType.GAME_MESSAGE)
            self._determine_winner()
            return self.state.step(rotate_player=False)
        colour = self.board.str_to_enum(color_str=self.roles[self.state.current_player_id])
        match self.state.game_state["turn_phase"]: 
            case "action":
                m = re.search(r'\[(\d+)\]', action)
                if m is None: self.state.set_invalid_move(reason=f"No action found."); return self.state.step()
                act = int(m.group(1))
                if act > len(self.game_moves) or act <=0: 
                    if self._handle_invalid(reason="Selected action index is out of bounds. Please select from the list."):
                        self._rotate_players(force=True)
                        self._roll_dice()
                        self._render_board_state()
                        return self.state.step(rotate_player=False) 
                    
                elif act == len(self.game_moves): # skip turn selected
                    self.state.add_observation(message=f"Player {self.state.current_player_id} ({self.roles[self.state.current_player_id]}) ends his turn.", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    self.state.game_state["turn_done"] = True

                elif act == len(self.game_moves)-1: # player selectes negotiation
                    self.state.game_state["move_count"] += 1
                    self.state.game_state["turn_phase"] = "negotiation_start"
                    pid_options = ", ".join([f"'[{pid}]'/'[{self.roles[pid]}]'" for pid in range(self.state.num_players) if (pid not in self.state.game_state["eliminated_players"] and pid != self.state.current_player_id)])
                    # print("OPTIONS", pid_options)
                    self.state.add_observation(to_id=self.state.current_player_id, message=f"You selected action [{len(self.game_moves)-1}] (Negotiation). Please select a player you would like to negotiation with. The options are: {pid_options}. Please select exactly one.", observation_type=ta.ObservationType.GAME_MESSAGE)
                    return self.state.step(rotate_player=False)
                
                else: # player selected a game action
                    selected = next(m for m in self.game_moves if m[0] == act)
                    player = self.board.players[colour]
                    ok, err = self.board.execute_action(player, selected[2])
                    # TODO addd observation of what the player did
                    self._render_board_state()
                    self.state.game_state["move_count"] += 1

            case "negotiation_start":
                successful = self._negotiation_partner_selection(action=action)
                if not successful: # invalid move 
                    if self._handle_invalid(f"Invalid negotiation partner selection. Received: {action}"):
                        self._rotate_players(force=True)
                        self._roll_dice()
                        self._render_board_state()
                        return self.state.step(rotate_player=False) 

            case "negotiation":
                if self.state.current_player_id == self.state.game_state["main_negotiator"]: self._negotiation_step(action=action)
                else: self._negotiation_response_step(action=action)

        # check for win
        if any(rec["total"] >= 11 for rec in self.board.get_scores().values()): self._determine_winner()
        # check for turn over
        if self.state.game_state["turn_done"] or self.state.game_state["move_allowance"] < self.state.game_state["move_count"]:
            self._rotate_players(force=True); self._roll_dice(); self._render_board_state()
        return self.state.step(rotate_player=False)


    def _negotiation_partner_selection(self, action: str):
        pid_options = [pid for pid in range(self.state.num_players) if (pid not in self.state.game_state["eliminated_players"] and pid != self.state.current_player_id)]
        m_list = list(re.compile(r'(?i)\[\s*([0123]|red|white|blue|orange)\s*\]').finditer(action))
        if not m_list: return False
        m = m_list[-1]
        choice = m.group(1).lower()
        if choice in self.pids_from_roles.keys(): choice = self.pids_from_roles[choice]
        # `choice` is now either a pid int (mapped from a colour name above) or a
        # digit string from the [0-3] regex branch, so int() cannot fail here; the
        # previous try/except only swallowed an exception that could never occur.
        choice = int(choice)
        colors = [self.roles[pid] for pid in pid_options]
        if choice not in pid_options+colors: pass ; return False # not a valid selection # TODO
        # convert to pid choice 
        if choice in colors: choice = self.pids_from_roles[choice]
        self.state.game_state["negotiation_partner"] = choice
        self.state.game_state["main_negotiator"] = self.state.current_player_id
        negotiation_explanation = "You can converse freely and make trade offers in the following format: '[Offer: 3 Sheep, 2 Ore -> 5 Brick, 2 Sheep]': [Offer: Offered Resources -> Requested Resources]. When you receive a trade offer you can '[accept]' or '[deny]' it"
        self.state.add_observation(to_id=self.state.current_player_id, message=f"You have selected Player {choice} ({self.roles[choice]}) to negotiation with. {negotiation_explanation}. When you are done negotiating, please include '[done]' your response. You may now send your first message.", observation_type=ta.ObservationType.GAME_MESSAGE)
        self.state.add_observation(to_id=choice, message=f"Player {self.state.current_player_id} ({self.roles[self.state.current_player_id]}) selected you to negotiate with. {negotiation_explanation}.", observation_type=ta.ObservationType.GAME_MESSAGE)
        self.state.game_state["turn_phase"] = "negotiation"
        return True

    def _negotiation_step(self, action: str):
        gs = self.state.game_state
        me = self.state.current_player_id
        opp = gs["negotiation_partner"]
        self.state.add_observation(from_id=me, to_id=opp, message=action, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.state.add_observation(from_id=me, to_id=me, message=action, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        # 1) [Done] ends negotiation immediately for BOTH players
        if _NEGO_DONE_RE.search(action):
            gs["turn_phase"] = "action"
            gs["move_count"] += 1
            gs["negotiation_partner"] = None
            gs["current_offer"] = None
            gs["game_phase"] = "action"
            self.state.add_observation(message="Negotiation finished.", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
            self._render_board_state()
            return # TODO rotate to correct player and phase
        # 2) Accept / Deny an existing offer (if I'm the receiver)
        if gs.get("current_offer") and gs["current_offer"]["to_player"] == me:
            if _NEGO_ACCEPT_RE.search(action):
                self._execute_trade_accept()
                # return TODO prob not good to return here
            elif _NEGO_DENY_RE.search(action):
                self.state.add_observation(message=f"Player {me} denied the trade offer.", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                gs["current_offer"] = None
        # 3) Look for a NEW offer (only one active at a time)
        if not gs.get("current_offer"):
            offer_m = _NEGO_OFFER_RE.search(action)
            if offer_m:
                body = offer_m.group(1)
                parsed = _parse_offer_body(body)
                if parsed and _has_resources(self.board.players[self.board.str_to_enum(self.roles[me])].hand, parsed["offered_resources"]):
                    gs["current_offer"] = {"from_player": me, "to_player": opp, **parsed}
                    self.state.add_observation(message=f"Player {me} offered to Player {opp}: {body}", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                else:
                    if self._handle_invalid(f"Malformed or unaffordable offer. Submitted action: {action}"):
                        pass # handle player termination TODO
                    return
        self.state.manually_set_current_player_id(new_player_id=opp, force=True)
        gs["move_count"] += 1

    def _negotiation_response_step(self, action: str):
        gs = self.state.game_state 
        me = self.state.current_player_id
        opp = gs["main_negotiator"]
        self.state.add_observation(from_id=me, to_id=opp, message=action, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.state.add_observation(from_id=me, to_id=me, message=action, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        # 1) Accept / Deny an existing offer (if I'm the receiver)
        if gs.get("current_offer") and gs["current_offer"]["to_player"] == me:
            if _NEGO_ACCEPT_RE.search(action): self._execute_trade_accept()
            else: # else always deny
                self.state.add_observation(message=f"Player {me} denied the trade offer.", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                gs["current_offer"] = None
        # 2) Look for a NEW offer (only one active at a time)
        if not gs.get("current_offer"): # technically not necessary
            offer_m = _NEGO_OFFER_RE.search(action)
            # print("OFFER M")
            if offer_m:
                body = offer_m.group(1)
                parsed = _parse_offer_body(body)
                if parsed and _has_resources(self.board.players[self.board.str_to_enum(self.roles[me])].hand, parsed["offered_resources"]):
                    gs["current_offer"] = {"from_player": me, "to_player": opp, **parsed}
                    self.state.add_observation(message=f"Player {me} offered to Player {opp}: {body}", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                else:
                    if self._handle_invalid(f"Malformed or unaffordable offer. Submitted action: {action}"): pass # handle player termination
                    return
        self.state.manually_set_current_player_id(new_player_id=opp, force=True)

    def _execute_trade_accept(self):
        gs = self.state.game_state
        offer = gs["current_offer"]
        giver_pid = offer["from_player"]
        taker_pid = offer["to_player"]
        giver_c = self.board.str_to_enum(self.roles[giver_pid])
        taker_c = self.board.str_to_enum(self.roles[taker_pid])
        giver_pl = self.board.players[giver_c]
        taker_pl = self.board.players[taker_c]
        if not (_has_resources(taker_pl.hand, offer["requested_resources"]) and _has_resources(giver_pl.hand, offer["offered_resources"])):
            self._handle_invalid("Trade failed: resources missing.")
            gs["current_offer"] = None
            return

        for terr, qty in offer["offered_resources"].items():    giver_pl.hand[terr] -= qty; taker_pl.hand[terr] += qty
        for terr, qty in offer["requested_resources"].items():  taker_pl.hand[terr] -= qty; giver_pl.hand[terr] += qty
        fmt = lambda d: {t.name.title(): n for t, n in d.items()}
        self.state.add_observation(message=(f"Trade executed: Player {giver_pid} → {taker_pid} (offered {fmt(offer['offered_resources'])} / requested {fmt(offer['requested_resources'])})."), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        gs["current_offer"] = None

    def _determine_winner(self):
        scores = self.board.get_scores()  # {Color: {"total": vp, ...}}
        # 1) collect VP per pid
        pid_vp: dict[int, int] = {}
        for pid in range(self.state.num_players):
            color = self.board.str_to_enum(self.roles[pid])
            pid_vp[pid] = scores[color]["total"]
        # 2) worst→best order by VP
        ranked = sorted(range(self.state.num_players), key=lambda p: pid_vp[p])
        # 3) dense tie-groups by equal VP (still worst→best)
        groups: list[list[int]] = []
        for pid in ranked:
            if not groups or pid_vp[groups[-1][0]] != pid_vp[pid]: groups.append([pid])
            else: groups[-1].append(pid)
        # 4) map groups to rewards in [-1, +1]
        G = len(groups)
        if G == 1: reward_dict = {pid: 0.0 for pid in groups[0]}
        else:
            reward_dict: dict[int, float] = {}
            for g_idx, g in enumerate(groups):            # g_idx: 0..G-1 (worst..best)
                r = -1.0 + 2.0 * (g_idx / (G - 1))        # linear scale
                for pid in g: reward_dict[pid] = r
        # 5) end game with summary
        self.state.set_game_outcome(reward_dict=reward_dict, reason=f"Final scores: {scores}")

import re, random, string
from math import sqrt
from enum import Enum, auto
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set


HexCoord = Tuple[int, int] # (q, r)   axial
CornerID = Tuple[HexCoord, HexCoord, HexCoord]  # sorted triple of tiles
EdgeID = Tuple[CornerID, CornerID] # canonical edge key
InterCoord = Tuple[int, int, int] # cube coords, uniquely identifies a corner
EdgeCoord = Tuple[InterCoord, InterCoord]

AXIAL_DIRS: list[HexCoord] = [(+1,  0), (+1, -1), ( 0, -1), (-1,  0), (-1, +1), ( 0, +1)]
CORNER_DIR_PAIRS = [(2, 3), (1, 2), (0, 1), (5, 0), (4, 5), (3, 4)]

class Terrain(Enum):
    BRICK = "brick"; WOOD = "wood"; ORE = "ore"; WHEAT = "wheat"; SHEEP = "sheep"; DESERT = "desert" # produces nothing
    def __str__(self): return self.value

class Piece(Enum):
    ROAD = auto(); SETTLEMENT = auto(); CITY = auto()

class Color(Enum):
    BLUE = 0; ORANGE = 1; WHITE = 2; RED = 3
    def __str__(self): return self.name.lower()

class _SafeDict(dict):
    def __missing__(self, k): return "" # format_map replacement-dict that returns '' for unknown keys.

@dataclass
class Hex:
    coord: HexCoord
    terrain: Terrain
    token: Optional[int] # None for desert
    has_robber: bool = False
    def produces(self) -> Optional[str]: return None if self.terrain is Terrain.DESERT else self.terrain.value

@dataclass
class Corner:
    tiles: Set[HexCoord] = field(default_factory=set)
    piece: Optional[Piece] = None
    owner: Optional[Color] = None

@dataclass
class Edge:
    ends: EdgeID # (cornerA, cornerB) - sorted CornerIDs
    adjacent_hexes: Set[HexCoord]
    owner: Optional[Color] = None
    orient: Optional[str] = None  # 'H' (horizontal), 'F' (forward slash ╱), 'B' (backslash ╲)
    i: Optional[int] = None

@dataclass
class Player:
    color: Color
    settlements: list[CornerID] = field(default_factory=list)
    roads: list[EdgeID] = field(default_factory=list)
    hand: Counter = field(default_factory=Counter)
    def add_cards(self, terrain: Terrain, qty: int = 1) -> None:
        if terrain is Terrain.DESERT: return
        self.hand[terrain] += qty
    def can_pay(self, cost: Counter) -> bool:
        return all(self.hand[res] >= qty for res, qty in cost.items())
    def pay(self, cost: Counter) -> None:
        for res, qty in cost.items():
            self.hand[res] -= qty
            
# game vars
COST_ROAD = Counter({Terrain.BRICK: 1, Terrain.WOOD: 1})
COST_SETTLEMENT = Counter({Terrain.BRICK: 1, Terrain.WOOD: 1, Terrain.WHEAT: 1, Terrain.SHEEP: 1})
COST_CITY = Counter({Terrain.ORE: 3, Terrain.WHEAT: 2})

# regex helpers
_desc_re = re.compile(r"\s*(\d+)?\s*([a-zA-Z]+)\s*", re.I)

def corner_ids_of_tile(q: int, r: int) -> List[CornerID]:
    """ Return the six CornerIDs (triples of axial coords) for tile (q,r) """
    corners: list[CornerID] = []
    for d1, d2 in CORNER_DIR_PAIRS:
        t1 = (q + AXIAL_DIRS[d1][0], r + AXIAL_DIRS[d1][1])
        t2 = (q + AXIAL_DIRS[d2][0], r + AXIAL_DIRS[d2][1])
        triple = tuple(sorted(((q, r), t1, t2)))   # canonical ordering
        corners.append(triple)
    return corners

def _parse_hex_descriptor(text: str) -> tuple[Terrain, Optional[int]] | None:
    """ Accepts strings like '8 wood', 'wood 8', 'desert'. Returns (Terrain, token)  where token is int or None. """
    text = text.lower()
    if text.strip() == "desert": return Terrain.DESERT, None
    m = _desc_re.fullmatch(text)
    if not m: return None
    a, b = m.group(1), m.group(2)
    if a and b:                      # '8 wood' or 'wood 8'
        token = int(a) if a.isdigit() else int(b)
        word  = b if a.isdigit() else a
    else: return None # just 'wood' or just '8'  (disallow)
    try:                return Terrain[word.upper()], token
    except KeyError:    return None

def _corner_descr(cid: CornerID, board: "Board") -> str:
    parts = []
    for q, r in cid:
        hex_ = board.hexes.get((q, r))          # ← no KeyError anymore
        if hex_ is None: continue # sea / harbour
        tok = "/" if hex_.terrain is Terrain.DESERT else hex_.token
        parts.append(f"{tok} {hex_.terrain.value}")
    return "{" + ", ".join(parts) + "}" if parts else "{edge}"

def _encode(n: int) -> str:
    return str(n) if n >= 0 else f"_{-n}"

def _corner_key_core(triple: CornerID) -> str:
    # CornerID -> "__" joined "q_r" triplets, sorted for canonicalization
    sorted_triple = sorted(triple)
    return "__".join(f"{_encode(q)}_{_encode(r)}" for q, r in sorted_triple)

def edge_key(eid: EdgeID, suffix: str) -> str:
    # E + cornerA + "__" + cornerB + orientation suffix
    a, b = sorted(eid)
    return "E" + _corner_key_core(a) + "__" + _corner_key_core(b) + suffix

Move   = Tuple[int, str, Tuple[str, object]]   # (index, text, action_spec)
Action = Tuple[str, object]                    # ("build_road", EdgeID) …

def _mk_action(kind: str, payload) -> Action: return (kind, payload)

class Board:
    def __init__(self):
        self.hexes: Dict[HexCoord, Hex] = {}
        self.corners: Dict[CornerID, Corner] = {}
        self.edges: Dict[EdgeID, Edge] = {}
        self.players: Dict[Color, Player]    = {}

    def build_settlement(self, cid: CornerID, player: Player):
        corner = self.corners[cid]
        assert corner.piece is None, "intersection already taken"
        corner.piece  = Piece.SETTLEMENT
        corner.owner  = player.color
        player.settlements.append(cid)

    def build_road(self, eid: EdgeID, player: Player):
        edge = self.edges[eid]
        assert edge.owner is None, "edge already taken"
        edge.owner = player.color
        player.roads.append(eid)

    def _adjacent_edges(self, cid: CornerID) -> list[EdgeID]:
        return [eid for eid in self.edges if cid in eid]

    def _adjacent_corners(self, cid: CornerID) -> list[CornerID]:
        neigh = []
        for eid in self._adjacent_edges(cid):
            a, b = eid
            neigh.append(b if a == cid else a)
        return neigh

    def _corner_from_triplet(self, descriptors: list[str]) -> tuple[CornerID | None, str | None]:
        """Return CornerID matching the three token/terrain descriptors."""
        if len(descriptors) != 3:
            return None, "Need exactly three hex descriptors"
        parsed = []
        for txt in descriptors:
            pair = _parse_hex_descriptor(txt)
            if pair is None:
                return None, f"Cannot parse descriptor '{txt}'"
            parsed.append(pair)
        key = frozenset(parsed)
        cid = self._corner_lookup.get(key)
        if cid is None:
            return None, "No corner matches those three hexes"
        return cid, None

    @classmethod
    def build_standard(cls) -> "Board":
        board = cls()
        board.hexes = {
            (-2, 2): Hex(coord=(-2, 2), terrain=Terrain.ORE, token=10), (-1, 2): Hex(coord=(-1, 2), terrain=Terrain.SHEEP, token=2), (0, 2): Hex(coord=(0, 2), terrain=Terrain.WOOD, token=9), # r = +2  (top row)
            (-2, 1): Hex(coord=(-2, 1), terrain=Terrain.WHEAT, token=12), (-1, 1): Hex(coord=(-1, 1), terrain=Terrain.BRICK, token=6), (0, 1): Hex(coord=(0, 1), terrain=Terrain.SHEEP, token=4), (1, 1): Hex(coord=(1, 1), terrain=Terrain.BRICK, token=10), # r = +1
            (-2, 0): Hex(coord=(-2, 0), terrain=Terrain.WHEAT, token=9), (-1, 0): Hex(coord=(-1, 0), terrain=Terrain.WOOD, token=11), (0, 0): Hex(coord=(0, 0), terrain=Terrain.DESERT,token=None, has_robber=True), (1, 0): Hex(coord=(1, 0), terrain=Terrain.WOOD, token=3), (2, 0): Hex(coord=(2, 0), terrain=Terrain.ORE, token=8), # r = 0  (centre row)
            (-1, -1): Hex(coord=(-1, -1), terrain=Terrain.WOOD, token=8), (0, -1): Hex(coord=(0, -1), terrain=Terrain.ORE, token=3), (1, -1): Hex(coord=(1, -1), terrain=Terrain.WHEAT, token=4), (2, -1): Hex(coord=(2, -1), terrain=Terrain.SHEEP, token=5), # r = –1
            (0, -2): Hex(coord=(0, -2), terrain=Terrain.BRICK, token=5), (1, -2): Hex(coord=(1, -2), terrain=Terrain.WHEAT, token=6), (2, -2): Hex(coord=(2, -2), terrain=Terrain.SHEEP, token=11), # r = –2  (bottom row)
        }

        # 2) build corners by walking each tile
        for q, r in board.hexes.keys():
            for cid in corner_ids_of_tile(q, r):
                corner = board.corners.setdefault(cid, Corner())
                corner.tiles.add((q, r))

        # 3) build edges (72 in total)
        for (q, r) in board.hexes:
            tile_corners = corner_ids_of_tile(q, r) # 6 corners around (q,r)

            # adjacent pairs around the hex form its six edges
            for i in range(6):
                cid_a = tile_corners[i]
                cid_b = tile_corners[(i + 1) % 6]
                edge_key_id: EdgeID = tuple(sorted((cid_a, cid_b)))
                # edge = board.edges.setdefault(edge_key, Edge(ends=edge_key, adjacent_hexes=set()))
                edge = board.edges.setdefault(edge_key_id, Edge(ends=edge_key_id, adjacent_hexes=set()))
                if edge.orient is None:
                    if i in (0, 3):   edge.orient = 'H'
                    elif i in (1, 4): edge.orient = 'F' #'F'  # ╱
                    else:             edge.orient = 'B' #'B'  # ╲
                    edge.i = i


        board._corner_lookup = {}
        for cid in board.corners:
            triple = []
            for coord in cid:
                if coord not in board.hexes: # sea edge → skip
                    break
                terr, tok = board.hexes[coord].terrain, board.hexes[coord].token
                triple.append((terr, tok))
            else: # only if all 3 on-board
                key = frozenset(triple)
                # duplicates should not occur; assert for safety
                assert key not in board._corner_lookup, "non-unique triplet!"
                board._corner_lookup[key] = cid

        # 4) players
        for col in Color:                       # BLUE, ORANGE, WHITE, RED
            board.players[col] = Player(color=col)

        # 5) beginner setup  (intersection triples & edge pairs)
        BEGINNER: dict[Color, list[tuple[CornerID, EdgeID]]] = {
            Color.RED: [(tuple(sorted([(-2, 2), (-1, 2), (-1, 1)])), tuple(sorted([tuple(sorted([(-2, 2), (-1, 2), (-1, 1)])), tuple(sorted([(-1, 2), (-1, 1), (0, 1)]))]))), (tuple(sorted([(-2, 0), (-1, 0), (-1, -1)])), tuple(sorted([tuple(sorted([(-2, 0), (-1, 0), (-1, -1)])), tuple(sorted([(-1, 0), (-1, -1), (0, -1)]))])))],
            Color.WHITE: [(tuple(sorted([(-2, 1), (-1, 1), (-1, 0)])), tuple(sorted([tuple(sorted([(-2, 1), (-1, 1), (-1, 0)])), tuple(sorted([(-2, 1), (-2, 0), (-1, 0)]))]))), (tuple(sorted([(2, -1), (1, 0), (2, 0)])), tuple(sorted([tuple(sorted([(1, 1), (1, 0), (2, 0)])), tuple(sorted([(1, 0), (2, 0), (2, -1)]))])))],
            Color.BLUE: [(tuple(sorted([(-1, -1), (0, -1), (0, -2)])), tuple(sorted([tuple(sorted([(-1, -1), (0, -1), (0, -2)])), tuple(sorted([(0, -1), (0, -2), (1, -2)]))]))), (tuple(sorted([(1, -1), (2, -1), (2, -2)])), tuple(sorted([tuple(sorted([(1, -1), (2, -1), (2, -2)])), tuple(sorted([(1, -1), (2, -1), (1, 0)]))])))],
            Color.ORANGE: [(tuple(sorted([(0, 2), (1, 1), (0, 1)])), tuple(sorted([tuple(sorted([(0, 2), (-1, 2), (0, 1)])), tuple(sorted([(0, 2), (1, 1), (0, 1)]))]))), (tuple(sorted([(0, -1), (1, -1), (1, -2)])), tuple(sorted([tuple(sorted([(0, -1), (1, -1), (1, -2)])), tuple(sorted([(2, -2), (1, -1), (1, -2)]))])))],
        }

        for colour, builds in BEGINNER.items():
            pl = board.players[colour]
            for cid, eid in builds:
                board.build_settlement(cid, pl)
                board.build_road(eid, pl)

        for colour, builds in BEGINNER.items():
            second_settlement_cid = builds[1][0] # index 1 == “second”
            player = board.players[colour]
            corner = board.corners[second_settlement_cid]
            for q, r in corner.tiles:
                terrain = board.hexes[(q, r)].terrain
                player.add_cards(terrain)                    # +1 card

        assert len(board.hexes)   == 19, "should have 19 tiles"
        assert len(board.corners) == 54, "should have 54 corners"
        assert len(board.edges)   == 72, "should have 72 edges"
        return board
    

    def roll_dice(self) -> tuple[str, dict[Color, dict[Terrain, int]]]: # TODO add 7 roll
        """Roll 2 d6, distribute resources, return roll-string & payout map."""
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total  = d1 + d2
        roll_str = f"{d1} + {d2} = {total}"

        # track what everyone just gained
        added: dict[Color, Counter] = {c: Counter() for c in self.players}

        # for every producing hex with matching token
        for (q, r), hex_ in self.hexes.items():
            if hex_.token != total or hex_.has_robber or hex_.terrain is Terrain.DESERT: continue

            # pay adjacent corners
            for cid in corner_ids_of_tile(q, r):
                corner = self.corners[cid]
                if corner.owner is None:
                    continue
                qty = 2 if corner.piece is Piece.CITY else 1
                player = self.players[corner.owner]
                player.add_cards(hex_.terrain, qty)
                added[player.color][hex_.terrain] += qty
        # convert Counter → plain dict for a clean, JSON-ish return
        added_clean = {col: dict(cnt) for col, cnt in added.items()}
        return roll_str, added_clean
    

    def player_build_road(self, player: Player, eid: EdgeID):
        edge = self.edges.get(eid)
        if edge is None:                    return False, "Edge does not exist"
        if edge.owner is not None:          return False, "Edge already occupied"
        if not player.can_pay(COST_ROAD):   return False, "Insufficient resources"
        # connectivity – must touch player road or settlement
        if not any((cid in player.settlements or eid2 in player.roads) for cid in eid for eid2 in self._adjacent_edges(cid)):
            return False, "Road not connected to your network"
        player.pay(COST_ROAD)
        edge.owner = player.color
        player.roads.append(eid)
        return True, None

    def player_build_settlement(self, player: Player, cid: CornerID):
        corner = self.corners.get(cid)
        if corner is None:                                                                  return False, "Corner does not exist"
        if corner.piece is not None:                                                        return False, "Corner already occupied"
        if not player.can_pay(COST_SETTLEMENT):                                             return False, "Insufficient resources"
        if any(self.corners[n].piece is not None for n in self._adjacent_corners(cid)):     return False, "Too close to another settlement/city" # 2-space rule – no adjacent occupied intersections
        if not any(self.edges[e].owner == player.color for e in self._adjacent_edges(cid)): return False, "Must connect to one of your roads" # connectivity – must touch player road
        player.pay(COST_SETTLEMENT)
        corner.piece, corner.owner = Piece.SETTLEMENT, player.color
        player.settlements.append(cid)
        return True, None

    def player_build_city(self, player: Player, cid: CornerID):
        corner = self.corners.get(cid)
        if corner is None:                                                      return False, "Corner does not exist"
        if corner.piece != Piece.SETTLEMENT or corner.owner != player.color:    return False, "Must upgrade your own settlement"
        if not player.can_pay(COST_CITY):                                       return False, "Insufficient resources"
        player.pay(COST_CITY)
        corner.piece = Piece.CITY
        return True, None

    def player_build_settlement_by_triplet(self, player: Player, triplet: list[str]) -> tuple[bool, str | None]:
        cid, err = self._corner_from_triplet(triplet)
        if cid is None: return False, err
        return self.player_build_settlement(player, cid)

    def player_build_city_by_triplet(self, player: Player, triplet: list[str]) -> tuple[bool, str | None]:
        cid, err = self._corner_from_triplet(triplet)
        if cid is None: return False, err
        return self.player_build_city(player, cid)
    

    def get_scores(self) -> dict[Color, dict[str, int]]:
        results: dict[Color, dict[str, int]] = {col: {"total": 0, "cities": 0, "settlements": 0, "roads": 0} for col in self.players}
        # count buildings directly from the board so we can't go out of sync
        for corner in self.corners.values():
            if corner.owner is None: continue
            record = results[corner.owner]
            if corner.piece is Piece.CITY:
                record["cities"] += 1
                record["total"] += 2 # each city = 2 VP
            elif corner.piece is Piece.SETTLEMENT:
                record["settlements"] += 1
                record["total"] += 1  # each settlement = 1 VP
        # roads are easy – just trust the player list
        for col, p in self.players.items():
            results[col]["roads"] = len(p.roads)
        return results

    def _viable_moves(self, player: Player) -> list[Move]:
        moves: list[Move] = []
        idx = 1

        # roads 
        if player.can_pay(COST_ROAD):
            for eid, edge in self.edges.items():
                if edge.owner is not None: continue
                if not any((cid in player.settlements or eid2 in player.roads) for cid in eid for eid2 in self._adjacent_edges(cid)): continue
                desc = f"Build ROAD  between {_corner_descr(eid[0], self)} ↔ {_corner_descr(eid[1], self)}"
                action = _mk_action("build_road", eid)
                moves.append((idx, desc, action))
                idx += 1

        # settlements
        if player.can_pay(COST_SETTLEMENT):
            for cid, corner in self.corners.items():
                if corner.piece is not None: continue
                if any(self.corners[n].piece is not None for n in self._adjacent_corners(cid)): continue # 2-space rule
                if not any(self.edges[e].owner == player.color for e in self._adjacent_edges(cid)): continue # road adjacency
                desc = f"Build SETTLEMENT at {_corner_descr(cid, self)}"
                action = _mk_action("build_settlement", cid)
                moves.append((idx, desc, action))
                idx += 1

        # cities
        if player.can_pay(COST_CITY):
            for cid in player.settlements:
                corner = self.corners[cid]
                if corner.piece is Piece.SETTLEMENT:
                    desc = f"Upgrade CITY at {_corner_descr(cid, self)}"
                    action = _mk_action("build_city", cid)
                    moves.append((idx, desc, action))
                    idx += 1
        return moves

    def render_player_view(self, colour: Color) -> str:
        player = self.players[colour]
        scores = self.get_scores()
        score_lines = [f"{str(c):6} {rec['total']:>2} Victory Points   (Settlements:{rec['settlements']}  Cities:{rec['cities']}  Roads:{rec['roads']})" for c, rec in scores.items()]
        moves = self._viable_moves(player)
        move_block = "\n".join(f"{idx}. {desc}" for idx, desc, _ in moves) or "No legal moves."
        parts = [
            f"{'='*24}  {colour.name}  {'='*24}", f"Hand:  {{{', '.join(f'{k.name}:{v}' for k,v in player.hand.items())}}}", "", "Scores\n───────", 
            "\n".join(score_lines), "", "Board \n──────", render_board(self), "", "Viable moves\n────────────", move_block,
        ]
        return "\n".join(parts)


    def execute_action(self, player: Player, action: Action) -> Tuple[bool, str | None]:
        kind, data = action
        if   kind == "build_road":        return self.player_build_road(player, data)
        elif kind == "build_settlement":  return self.player_build_settlement(player, data)
        elif kind == "build_city":        return self.player_build_city(player, data)
        else:                             return False, f"Unknown action type: {kind}"

    def str_to_enum(self, color_str: str) -> Color:
        match color_str:
            case "Red":     return Color.RED
            case "White":   return Color.WHITE
            case "Blue":    return Color.BLUE
            case "Orange":  return Color.ORANGE
            case _: raise Exception(f"Received unexpected color: {color_str}")

_TEMPLATE = """
                                   _        _
                                  ╱{C_1_3__0_2__0_3O}╲{E_1_3__0_2__0_3__0_2__0_3__1_2H}╱{C0_2__0_3__1_2O}╲        
                                  ╲{C_1_3__0_2__0_3C}╱      ╲{C0_2__0_3__1_2C}╱   
                        _        _{E_1_2___1_3__0_2___1_3__0_2__0_3F}▔        ▔{E0_2__0_3__1_2__0_2__1_1__1_2B}_        _
                       ╱{C_2_3___1_2___1_3O}╲{E_2_3___1_2___1_3___1_2___1_3__0_2H}╱{C_1_2___1_3__0_2O}╲  {C02T:^5}   ╱{C0_2__1_1__1_2O}╲{E0_2__1_1__1_2__1_1__1_2__2_1H}╱{C1_1__1_2__2_1O}╲
                       ╲{C_2_3___1_2___1_3C}╱      ╲{C_1_2___1_3__0_2C}╱   [{C02N:^2}]   ╲{C0_2__1_1__1_2C}╱      ╲{C1_1__1_2__2_1C}╱
             _        _{E_2_2___2_3___1_2___2_3___1_2___1_3F}▔        ▔{E_1_2___1_3__0_2___1_2__0_1__0_2B}_        _{E0_1__0_2__1_1__0_2__1_1__1_2F}▔        ▔{E1_1__1_2__2_1__1_1__2_0__2_1B}_        _ 
            ╱{C_3_3___2_2___2_3O}╲{E_3_3___2_2___2_3___2_2___2_3___1_2H}╱{C_2_2___2_3___1_2O}╲   {C_12T:^5}  ╱{C_1_2__0_1__0_2O}╲{E_1_2__0_1__0_2__0_1__0_2__1_1H}╱{C0_1__0_2__1_1O}╲   {C11T:^5}  ╱{C1_1__2_0__2_1O}╲{E1_1__2_0__2_1__2_0__2_1__3_0H}╱{C2_0__2_1__3_0O}╲
            ╲{C_3_3___2_2___2_3C}╱      ╲{C_2_2___2_3___1_2C}╱   [{C_12N:^2}]   ╲{C_1_2__0_1__0_2C}╱      ╲{C0_1__0_2__1_1C}╱    [{C11N:^2}]  ╲{C1_1__2_0__2_1C}╱      ╲{C2_0__2_1__3_0C}╱ 
           _{E_3_2___3_3___2_2___3_3___2_2___2_3F}▔        ▔{E_2_2___2_3___1_2___2_2___1_1___1_2B}_        _{E_1_1___1_2__0_1___1_2__0_1__0_2F}▔        ▔{E0_1__0_2__1_1__0_1__1_0__1_1B}_        _{E1_0__1_1__2_0__1_1__2_0__2_1F}▔        ▔{E2_0__2_1__3_0__2_0__3__1__3_0B}_   
          ╱{C_3_2___3_3___2_2O}╲  {C_22T:^5}   ╱{C_2_2___1_1___1_2O}╲{E_2_2___1_1___1_2___1_1___1_2__0_1H}╱{C_1_1___1_2__0_1O}╲  {C01T:^5}   ╱{C0_1__1_0__1_1O}╲{E0_1__1_0__1_1__1_0__1_1__2_0H}╱{C1_0__1_1__2_0O}╲  {C20T:^5}   ╱{C2_0__3__1__3_0O}╲
          ╲{C_3_2___3_3___2_2C}╱   [{C_22N:^2}]   ╲{C_2_2___1_1___1_2C}╱      ╲{C_1_1___1_2__0_1C}╱   [{C01N:^2}]   ╲{C0_1__1_0__1_1C}╱      ╲{C1_0__1_1__2_0C}╱   [{C20N:^2}]   ╲{C2_0__3__1__3_0C}╱
           ▔{E_3_2___3_3___2_2___3_2___2_1___2_2B}_        _{E_2_1___2_2___1_1___2_2___1_1___1_2F}▔        ▔{E_1_1___1_2__0_1___1_1__0_0__0_1B}_        _{E0_0__0_1__1_0__0_1__1_0__1_1F}▔        ▔{E1_0__1_1__2_0__1_0__2__1__2_0B}_        _{E2__1__2_0__3__1__2_0__3__1__3_0F}▔ 
            ╱{C_3_2___2_1___2_2O}╲{E_3_2___2_1___2_2___2_1___2_2___1_1H}╱{C_2_1___2_2___1_1O}╲   {C_11T:^5}  ╱{C_1_1__0_0__0_1O}╲{E_1_1__0_0__0_1__0_0__0_1__1_0H}╱{C0_0__0_1__1_0O}╲   {C10T:^5}  ╱{C1_0__2__1__2_0O}╲{E1_0__2__1__2_0__2__1__2_0__3__1H}╱{C2__1__2_0__3__1O}╲
            ╲{C_3_2___2_1___2_2C}╱      ╲{C_2_1___2_2___1_1C}╱   [{C_11N:^2}]   ╲{C_1_1__0_0__0_1C}╱      ╲{C0_0__0_1__1_0C}╱    [{C10N:^2}]  ╲{C1_0__2__1__2_0C}╱      ╲{C2__1__2_0__3__1C}╱
           _{E_3_1___3_2___2_1___3_2___2_1___2_2F}▔        ▔{E_2_1___2_2___1_1___2_1___1_0___1_1B}_        _{E_1_0___1_1__0_0___1_1__0_0__0_1F}▔        ▔{E0_0__0_1__1_0__0_0__1__1__1_0B}_        _{E1__1__1_0__2__1__1_0__2__1__2_0F}▔        ▔{E2__1__2_0__3__1__2__1__3__2__3__1B}_ 
          ╱{C_3_1___3_2___2_1O}╲   {C_21T:^5}  ╱{C_2_1___1_0___1_1O}╲{E_2_1___1_0___1_1___1_0___1_1__0_0H}╱{C_1_0___1_1__0_0O}╲  {C00T:^6}  ╱{C0_0__1__1__1_0O}╲{E0_0__1__1__1_0__1__1__1_0__2__1H}╱{C1__1__1_0__2__1O}╲  {C2_1T:^5}   ╱{C2__1__3__2__3__1O}╲
          ╲{C_3_1___3_2___2_1C}╱   [{C_21N:^2}]   ╲{C_2_1___1_0___1_1C}╱      ╲{C_1_0___1_1__0_0C}╱   [{C00N:^2}]   ╲{C0_0__1__1__1_0C}╱      ╲{C1__1__1_0__2__1C}╱   [{C2_1N:^2}]   ╲{C2__1__3__2__3__1C}╱
           ▔{E_3_1___3_2___2_1___3_1___2_0___2_1B}_        _{E_2_0___2_1___1_0___2_1___1_0___1_1F}▔        ▔{E_1_0___1_1__0_0___1_0__0__1__0_0B}_        _{E0__1__0_0__1__1__0_0__1__1__1_0F}▔        ▔{E1__1__1_0__2__1__1__1__2__2__2__1B}_        _{E2__2__2__1__3__2__2__1__3__2__3__1F}▔ 
            ╱{C_3_1___2_0___2_1O}╲{E_3_1___2_0___2_1___2_0___2_1___1_0H}╱{C_2_0___2_1___1_0O}╲  {C_10T:^5}   ╱{C_1_0__0__1__0_0O}╲{E_1_0__0__1__0_0__0__1__0_0__1__1H}╱{C0__1__0_0__1__1O}╲  {C1_1T:^5}   ╱{C1__1__2__2__2__1O}╲{E1__1__2__2__2__1__2__2__2__1__3__2H}╱{C2__2__2__1__3__2O}╲
            ╲{C_3_1___2_0___2_1C}╱      ╲{C_2_0___2_1___1_0C}╱   [{C_10N:^2}]   ╲{C_1_0__0__1__0_0C}╱      ╲{C0__1__0_0__1__1C}╱   [{C1_1N:^2}]   ╲{C1__1__2__2__2__1C}╱      ╲{C2__2__2__1__3__2C}╱            
           _{E_3_0___3_1___2_0___3_1___2_0___2_1F}▔        ▔{E_2_0___2_1___1_0___2_0___1__1___1_0B}_        _{E_1__1___1_0__0__1___1_0__0__1__0_0F}▔        ▔{E0__1__0_0__1__1__0__1__1__2__1__1B}_        _{E1__2__1__1__2__2__1__1__2__2__2__1F}▔        ▔{E2__2__2__1__3__2__2__2__3__3__3__2B}_              
          ╱{C_3_0___3_1___2_0O}╲  {C_20T:^5}   ╱{C_2_0___1__1___1_0O}╲{E_2_0___1__1___1_0___1__1___1_0__0__1H}╱{C_1__1___1_0__0__1O}╲   {C0_1T:^5}  ╱{C0__1__1__2__1__1O}╲{E0__1__1__2__1__1__1__2__1__1__2__2H}╱{C1__2__1__1__2__2O}╲  {C2_2T:^5}   ╱{C2__2__3__3__3__2O}╲               
          ╲{C_3_0___3_1___2_0C}╱   [{C_20N:^2}]   ╲{C_2_0___1__1___1_0C}╱      ╲{C_1__1___1_0__0__1C}╱   [{C0_1N:^2}]   ╲{C0__1__1__2__1__1C}╱      ╲{C1__2__1__1__2__2C}╱   [{C2_2N:^2}]   ╲{C2__2__3__3__3__2C}╱              
           ▔{E_3_0___3_1___2_0___3_0___2__1___2_0B}_        _{E_2__1___2_0___1__1___2_0___1__1___1_0F}▔        ▔{E_1__1___1_0__0__1___1__1__0__2__0__1B}_        _{E0__2__0__1__1__2__0__1__1__2__1__1F}▔        ▔{E1__2__1__1__2__2__1__2__2__3__2__2B}_        _{E2__3__2__2__3__3__2__2__3__3__3__2F}▔             
            ╱{C_3_0___2__1___2_0O}╲{E_3_0___2__1___2_0___2__1___2_0___1__1H}╱{C_2__1___2_0___1__1O}╲  {C_1_1T:^5}   ╱{C_1__1__0__2__0__1O}╲{E_1__1__0__2__0__1__0__2__0__1__1__2H}╱{C0__2__0__1__1__2O}╲   {C1_2T:^5}  ╱{C1__2__2__3__2__2O}╲{E1__2__2__3__2__2__2__3__2__2__3__3H}╱{C2__3__2__2__3__3O}╲            
            ╲{C_3_0___2__1___2_0C}╱      ╲{C_2__1___2_0___1__1C}╱   [{C_1_1N:^2}]   ╲{C_1__1__0__2__0__1C}╱      ╲{C0__2__0__1__1__2C}╱   [{C1_2N:^2}]   ╲{C1__2__2__3__2__2C}╱      ╲{C2__3__2__2__3__3C}╱       
             ▔        ▔{E_2__1___2_0___1__1___2__1___1__2___1__1B}_        _{E_1__2___1__1__0__2___1__1__0__2__0__1F}▔        ▔{E0__2__0__1__1__2__0__2__1__3__1__2B}_        _{E1__3__1__2__2__3__1__2__2__3__2__2F}▔        ▔         
                       ╱{C_2__1___1__2___1__1O}╲{E_2__1___1__2___1__1___1__2___1__1__0__2H}╱{C_1__2___1__1__0__2O}╲   {C0_2T:^5}  ╱{C0__2__1__3__1__2O}╲{E0__2__1__3__1__2__1__3__1__2__2__3H}╱{C1__3__1__2__2__3O}╲                     
                       ╲{C_2__1___1__2___1__1C}╱      ╲{C_1__2___1__1__0__2C}╱   [{C0_2N:^2}]   ╲{C0__2__1__3__1__2C}╱      ╲{C1__3__1__2__2__3C}╱                
                        ▔        ▔{E_1__2___1__1__0__2___1__2__0__3__0__2B}_        _{E0__3__0__2__1__3__0__2__1__3__1__2F}▔        ▔               
                                  ╱{C_1__2__0__3__0__2O}╲{E_1__2__0__3__0__2__0__3__0__2__1__3H}╱{C0__3__0__2__1__3O}╲                                  
                                  ╲{C_1__2__0__3__0__2C}╱      ╲{C0__3__0__2__1__3C}╱                                                                 
                                   ▔        ▔                         
"""

def _encode(n: int) -> str:             return str(n) if n >= 0 else f"_{-n}"
def coord_key(q: int, r: int) -> str:   return f"{_encode(q)}{_encode(r)}"
def corner_key(triple: CornerID, suffix: str) -> str:
    def part(n: int) -> str: return f"{n}" if n >= 0 else f"_{-n}"
    sorted_triple = sorted(triple)
    return "C" + "__".join(f"{part(q)}_{part(r)}" for q, r in sorted_triple) + suffix

def render_board(board: 'Board') -> str:
    mapping: Dict[str, str] = {}

    for (q, r), hex_ in board.hexes.items():
        root = "C" + coord_key(q, r)
        name = hex_.terrain.name.title()
        mapping[root + "T"] = name[:5] if (len(name) > 5 and name!="Desert") else name
        mapping[root + "N"] = "/" if hex_.terrain is Terrain.DESERT else hex_.token

    for cid, corner in board.corners.items():
        mapping[corner_key(cid, "O")] = " "
        mapping[corner_key(cid, "C")] = " "
        if corner.piece:
            mapping[corner_key(cid, "O")] = "V" if corner.piece == Piece.SETTLEMENT else "C"
            mapping[corner_key(cid, "C")] = corner.owner.name[0].upper() if corner.owner else "?"

    # Roads
    H_LEN = 6
    for eid, e in board.edges.items():
        suffix = e.orient or 'H'
        owner = e.owner
        char = ' ' if owner is None else owner.name[0]  # B, O, W, R
        if suffix == 'H': fill = ('_' * H_LEN) if owner is None else (char * H_LEN) # For unowned, keep the original look (underscores)
        elif suffix == 'F': fill = "╱" if owner is None else owner.name[0]
        elif suffix == 'B': fill = "╲" if owner is None else owner.name[0]
        mapping[edge_key(eid, suffix)] = fill

    required = {fn.split(':')[0] for _, fn, *_ in string.Formatter().parse(_TEMPLATE) if fn}
    missing  = required - mapping.keys()
    assert not missing, f"still missing: {missing}"
    return _TEMPLATE.format_map(_SafeDict(mapping))


if __name__ == "__main__":
    board = Board.build_standard()

    # give Blue some resources to make options interesting
    blue = board.players[Color.BLUE]
    blue.hand.update({Terrain.BRICK: 2, Terrain.WOOD: 2, Terrain.SHEEP: 1, Terrain.WHEAT: 1, Terrain.ORE: 3})

    print(board.render_player_view(Color.BLUE))

    moves = board._viable_moves(blue)  # list[Move]
    choice = int(input("Pick a move number: "))
    selected = next(m for m in moves if m[0] == choice)   # (idx, desc, action_spec)

    ok, err = board.execute_action(blue, selected[2])
    print("Success!" if ok else f"Failed: {err}")
    print(board.render_player_view(Color.BLUE))
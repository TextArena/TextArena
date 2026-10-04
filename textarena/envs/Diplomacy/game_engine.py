# good explanation of the game: https://www.youtube.com/watch?v=l53oL0ptt7k
import random
import re
from enum import Enum
from typing import List, Optional, Dict, Set, Tuple, Any
from collections import defaultdict

from textarena.envs.Diplomacy.map_fstring import DIPLOMACY_MAP_TEMPLATE

class Season(Enum):
    SPRING = "Spring"
    FALL = "Fall"
    WINTER = "Winter"

class PhaseType(Enum):
    MOVEMENT = "Movement"
    RETREATS = "Retreats"
    ADJUSTMENTS = "Adjustments"

class UnitType(Enum):
    ARMY = "A"
    FLEET = "F"

class TerrainType(Enum):
    LAND = "land"
    SEA = "sea"
    COAST = "coast"

class OrderType(Enum):
    HOLD = "H"
    MOVE = "-"
    SUPPORT = "S"
    CONVOY = "C"
    RETREAT = "R"
    BUILD = "B"
    DISBAND = "D"
    WAIVE = "WAIVE"


MULTI_COASTS: Dict[str, Dict[str, Set[str]]] = {
    "SPA": {
        "NC": {"GAS", "MAO", "POR"},
        "SC": {"LYO", "MAO", "MAR", "WES"},
    },
    "STP": {
        "NC": {"BAR", "NWY"},
        "SC": {"BOT", "FIN", "LVN"},
    },
    "BUL": {
        "EC": {"BLA", "CON", "RUM"},
        "SC": {"AEG", "CON", "GRE"},
    },
}
_LOCATION_RE = re.compile(
    r"^([A-Z]{3})(?:\((NC|SC|EC)\)|/(NC|SC|EC))?$"
)


def _parse_location(token: str) -> Tuple[str, Optional[str]]:
    """Parse a province token and normalize optional split-coast notation."""
    match = _LOCATION_RE.fullmatch(token.upper())
    if not match:
        raise ValueError(f"Invalid province: {token}")
    province = match.group(1)
    coast = match.group(2) or match.group(3)
    if coast and coast not in MULTI_COASTS.get(province, {}):
        raise ValueError(f"{province} has no {coast} coast")
    return province, coast


def _format_location(province: str, coast: Optional[str]) -> str:
    return f"{province}({coast})" if coast else province


class Region:
    """ Represents a region on the Diplomacy map """
    def __init__(self, name: str, terrain_type: TerrainType, is_supply_center: bool = False):
        self.name: str = name 
        self.terrain_type: TerrainType = terrain_type
        self.is_supply_center: bool = is_supply_center
        self.owner: Optional[str] = None 
        self.unit: Optional[Unit] = None 
        self.dislodged_unit: Optional[Unit] = None 
        self.adjacent_regions: Dict[str, Set[str]] = {"A": set(), "F": set()}
        self.home_for: Optional[str] = None

    def add_adjacency(self, other_region: str, unit_types: List[str]):
        """ Add adjacency to another region for specific unit types """
        for unit_type in unit_types:
            self.adjacent_regions[unit_type].add(other_region)

    def is_adjacent(self, unit_type: UnitType, other_region: str) -> bool:
        """ Check if this region is adjacent to another for a given unit type """
        return other_region in self.adjacent_regions[unit_type.value]

    def place_unit(self, unit) -> bool:
        """ Place a unit in this region """
        if self.unit is not None:
            return False 
        self.unit = unit 
        return True 

    def remove_unit(self) -> Optional['Unit']:
        """ Remove and return the unit from this region """
        unit = self.unit 
        self.unit = None 
        return unit 

    def dislodge_unit(self) -> Optional['Unit']:
        """ Remove any disloged unit """
        unit = self.dislodged_unit
        self.dislodged_unit = None 
        return unit 

    def set_owner(self, power) -> None:
        """ Set the owner of this supply center """
        if not self.is_supply_center:
            return 
        self.owner = power

    def __str__(self) -> str:
        return self.name 



class Unit:
    """ Represents a military unit on the map """
    def __init__(self, unit_type: UnitType, power: str):
        self.type: UnitType = unit_type
        self.power: str = power
        self.region: Optional[Region] = None # will be set when placed on map
        self.dislodged: bool = False 
        self.retreat_options: List[str] = [] 
        self.dislodged_from: Optional[str] = None
        self.coast: Optional[str] = None

    def place_in_region(self, region: Region) -> bool:
        """ Place this unit in a region """
        if region.place_unit(self):
            self.region = region 
            return True 
        return False 

    def move_to_region(self, region: Region) -> bool:
        """ Move this unit to a new region """
        if not self.region:
            return False 
        
        old_region = self.region 
        if region.place_unit(self):
            old_region.remove_unit()
            self.region = region 
            return True 
        return False 

    def dislodge(self) -> None:
        """ Mark this unit as dislodged """
        self.dislodged = True 
        if self.region and self.region.unit is self:
            self.region.unit = None 

    def retreat(self, region: Region, coast: Optional[str] = None) -> bool:
        """ Retreat this unit to a new region """
        destination = _format_location(region.name, coast)
        if not self.dislodged or destination not in self.retreat_options:
            return False 

        if region.place_unit(self):
            old_region = self.region
            if old_region and old_region.dislodged_unit is self:
                old_region.dislodged_unit = None
            self.dislodged = False 
            self.region = region 
            self.coast = coast
            self.retreat_options = []
            self.dislodged_from = None
            return True 
        return False

    def __str__(self) -> str:
        prefix = "*" if self.dislodged else ""
        location = (
            _format_location(self.region.name, self.coast)
            if self.region
            else "NOWHERE"
        )
        return f"{prefix}{self.type.value} {location}"



class Order:
    """ Represents an order in the game """
    def __init__(self, power: str, unit_type: UnitType, location: str, 
                 order_type: OrderType, target: str = None,
                 secondary_target: str = None, location_coast: str = None,
                 target_coast: str = None, secondary_target_coast: str = None,
                 via_convoy: bool = False):
        self.power: str = power
        self.unit_type: UnitType = unit_type 
        self.location: str = location 
        self.order_type: OrderType = order_type 
        self.target: Optional[str] = target 
        self.secondary_target: Optional[str] = secondary_target
        self.result: Optional[str] = None # For storing resolution results
        self.strength: int = 1 # Base strength of the order 
        self.location_coast: Optional[str] = location_coast
        self.target_coast: Optional[str] = target_coast
        self.secondary_target_coast: Optional[str] = secondary_target_coast
        self.via_convoy: bool = via_convoy

    def __str__(self) -> str:
        location = _format_location(self.location, self.location_coast)
        if self.order_type == OrderType.HOLD:
            return f"{self.unit_type.value} {location} {self.order_type.value}"
        elif self.order_type == OrderType.MOVE:
            target = _format_location(self.target, self.target_coast)
            suffix = " VIA" if self.via_convoy else ""
            return (
                f"{self.unit_type.value} {location} "
                f"{self.order_type.value} {target}{suffix}"
            )
        elif self.order_type == OrderType.SUPPORT:
            supported = _format_location(
                self.target.split()[1], self.target_coast
            )
            if self.secondary_target:
                # Support move
                destination = _format_location(
                    self.secondary_target, self.secondary_target_coast
                )
                return (
                    f"{self.unit_type.value} {location} "
                    f"{self.order_type.value} {self.target.split()[0]} "
                    f"{supported} {OrderType.MOVE.value} {destination}"
                )
            else:
                # Support hold
                return (
                    f"{self.unit_type.value} {location} "
                    f"{self.order_type.value} {self.target.split()[0]} "
                    f"{supported}"
                )
        elif self.order_type == OrderType.CONVOY:
            supported = _format_location(
                self.target.split()[1], self.target_coast
            )
            destination = _format_location(
                self.secondary_target, self.secondary_target_coast
            )
            return (
                f"{self.unit_type.value} {location} "
                f"{self.order_type.value} {self.target.split()[0]} "
                f"{supported} {OrderType.MOVE.value} {destination}"
            )
        elif self.order_type == OrderType.RETREAT:
            target = _format_location(self.target, self.target_coast)
            return f"{self.unit_type.value} {location} R {target}"
        elif self.order_type == OrderType.BUILD:
            return f"{self.unit_type.value} {location} B"
        elif self.order_type == OrderType.DISBAND:
            return f"{self.unit_type.value} {location} D"
        elif self.order_type == OrderType.WAIVE:
            return "WAIVE"
        return "Invalid Order"

    @classmethod
    def parse(cls, order_str: str, power: str) -> 'Order':
        """Parse an order string into an Order object"""
        if not isinstance(order_str, str):
            raise ValueError("Order must be a string")

        normalized = order_str.strip().upper()
        if normalized == "WAIVE":
            return cls(power, None, None, OrderType.WAIVE)
            
        parts = normalized.split()
        if len(parts) < 3:
            raise ValueError(f"Invalid order format: {order_str}")

        if parts[0] not in {"A", "F"}:
            raise ValueError(f"Unknown unit type {parts[0]!r}: {order_str}")
        unit_type = UnitType(parts[0])
        location, location_coast = _parse_location(parts[1])
        
        if parts[2] == 'H':
            if len(parts) != 3:
                raise ValueError(f"Hold order invalid: {order_str}")
            return cls(
                power, unit_type, location, OrderType.HOLD,
                location_coast=location_coast,
            )
        elif parts[2] == '-':
            if len(parts) not in {4, 5} or (
                len(parts) == 5 and parts[4] != "VIA"
            ):
                raise ValueError(f"Move order missing destination: {order_str}")
            target, target_coast = _parse_location(parts[3])
            return cls(
                power, unit_type, location, OrderType.MOVE, target,
                location_coast=location_coast,
                target_coast=target_coast,
                via_convoy=len(parts) == 5,
            )
        elif parts[2] == 'S':
            if len(parts) == 6 and parts[5] == "H":
                parts = parts[:5]
            if len(parts) not in {5, 7}:
                raise ValueError(f"Support order invalid: {order_str}")
            if parts[3] not in {"A", "F"}:
                raise ValueError(f"Unknown supported unit type {parts[3]!r}: {order_str}")
            supported_unit_type = UnitType(parts[3])
            supported_location, supported_coast = _parse_location(parts[4])
            
            if len(parts) == 7:
                if parts[5] != '-':
                    raise ValueError(f"Support move order invalid: {order_str}")
                # Support move
                destination, destination_coast = _parse_location(parts[6])
                return cls(
                    power, unit_type, location, OrderType.SUPPORT,
                    f"{supported_unit_type.value} {supported_location}",
                    destination, location_coast, supported_coast,
                    destination_coast,
                )
            else:
                # Support hold
                return cls(
                    power, unit_type, location, OrderType.SUPPORT,
                    f"{supported_unit_type.value} {supported_location}",
                    location_coast=location_coast,
                    target_coast=supported_coast,
                )
        elif parts[2] == 'C':
            if len(parts) != 7 or parts[5] != '-':
                raise ValueError(f"Convoy order invalid: {order_str}")
            if parts[3] not in {"A", "F"}:
                raise ValueError(f"Unknown convoyed unit type {parts[3]!r}: {order_str}")
            convoyed_unit_type = UnitType(parts[3])
            convoyed_location, convoyed_coast = _parse_location(parts[4])
            destination, destination_coast = _parse_location(parts[6])
            return cls(
                power, unit_type, location, OrderType.CONVOY,
                f"{convoyed_unit_type.value} {convoyed_location}",
                destination, location_coast, convoyed_coast,
                destination_coast,
            )
        elif parts[2] == 'R':
            if len(parts) != 4:
                raise ValueError(f"Retreat order missing destination: {order_str}")
            target, target_coast = _parse_location(parts[3])
            return cls(
                power, unit_type, location, OrderType.RETREAT, target,
                location_coast=location_coast,
                target_coast=target_coast,
            )
        elif parts[2] == 'B':
            if len(parts) != 3:
                raise ValueError(f"Build order invalid: {order_str}")
            return cls(
                power, unit_type, location, OrderType.BUILD,
                location_coast=location_coast,
            )
        elif parts[2] == 'D':
            if len(parts) != 3:
                raise ValueError(f"Disband order invalid: {order_str}")
            return cls(
                power, unit_type, location, OrderType.DISBAND,
                location_coast=location_coast,
            )
            
        raise ValueError(f"Unknown order type: {parts[2]}")



class Power:
    """ Represents a power in the game """
    def __init__(self, name: str):
        self.name: str = name 
        self.units: List[Unit] = [] 
        self.orders: List[Order] = []
        self.home_centers: List[str] = [] # List of home supply center names
        self.controlled_centers: List[str] = [] # List of currently controlled supply centers
        self.is_waiting: bool = True
        self.is_defeated: bool = False

    def __str__(self) -> str:
        return self.name
    
    def add_unit(self, unit: Unit) -> None:
        """ Add a unit to this power """
        unit.power = self.name
        self.units.append(unit)

    def remove_unit(self, unit: Unit) -> None:
        """ Remove a unit from this power """
        if unit in self.units:
            self.units.remove(unit)

    def add_center(self, center: str) -> None:
        """ Add a supply center to this power """
        if center not in self.controlled_centers:
            self.controlled_centers.append(center)
    
    def remove_center(self, center: str) -> None:
        """ Remove a supply center from this power """
        if center in self.controlled_centers:
            self.controlled_centers.remove(center)

    def clear_orders(self) -> None:
        """ Clear all orders """
        self.orders = [] 

    def set_orders(self, orders: List[Order]) -> None:
        """ Set orders for this power """
        self.orders = orders 
        self.is_waiting = False 

    def check_elimination(self) -> bool:
        """ Check if this power is eliminated """
        if not self.units and not self.controlled_centers:
            self.is_defeated = True 
        return self.is_defeated

    def get_buildable_locations(self, game_map: 'Map') -> List[str]:
        """ Get locations where this power can build new units """
        buildable = []
        for center_name in self.home_centers:
            if (center_name in self.controlled_centers and 
                game_map.regions[center_name].unit is None and 
                game_map.regions[center_name].dislodged_unit is None):
                buildable.append(center_name)
        return buildable

    def count_needed_builds(self) -> int:
        """ Calculate needed builds (positive) or needed disbands (negative) """
        return len(self.controlled_centers) - len(self.units)


class Map:
    """ Represents the Diplomacy map """
    def __init__(self):
        self.regions: Dict[str, Region] = {} # Dict mapping region names to Region objects

    def add_region(self, name: str, terrain_type: TerrainType, is_supply_center: bool = False, home_for: str = None) -> None:
        """ Add a region to the map """
        region: Region = Region(name, terrain_type, is_supply_center)
        region.home_for = home_for 
        self.regions[name] = region 

    def add_adjacency(self, region1: str, region2: str, unit_types: List[str]) -> None:
        """ Add bidirectional adjacency between regions """
        if region1 in self.regions and region2 in self.regions:
            self.regions[region1].add_adjacency(region2, unit_types)
            self.regions[region2].add_adjacency(region1, unit_types)

    def get_region(self, name: str) -> Optional[Region]:
        """ Get a region by name """
        return self.regions.get(name)

    def get_all_regions(self) -> List[Region]:
        """ Get all regions on the map """
        return list(self.regions.values())

    def get_supply_centers(self) -> List[str]:
        """ Get all dupply center names """
        return [name for name, region in self.regions.items() if region.is_supply_center]

    def get_home_centers(self, power: str) -> List[str]:
        """ Get home supply centers for a power """
        return [name for name, region in self.regions.items()
                    if region.is_supply_center and region.home_for == power]

    @classmethod
    def create_standard_map(cls) -> 'Map':
        """ Create the standard Diplomacy map """
        game_map = cls()

        # Define regions
        regions_data = [
            # Format: (name, terrain_type, is_supply_center, home_power)
            # Home Supply Centers
            ('BRE', TerrainType.COAST, True, 'FRANCE'),
            ('PAR', TerrainType.LAND, True, 'FRANCE'),
            ('MAR', TerrainType.COAST, True, 'FRANCE'),
            ('LON', TerrainType.COAST, True, 'ENGLAND'),
            ('EDI', TerrainType.COAST, True, 'ENGLAND'),
            ('LVP', TerrainType.COAST, True, 'ENGLAND'),
            ('BER', TerrainType.COAST, True, 'GERMANY'),
            ('MUN', TerrainType.LAND, True, 'GERMANY'),
            ('KIE', TerrainType.COAST, True, 'GERMANY'),
            ('VEN', TerrainType.COAST, True, 'ITALY'),
            ('ROM', TerrainType.COAST, True, 'ITALY'),
            ('NAP', TerrainType.COAST, True, 'ITALY'),
            ('VIE', TerrainType.LAND, True, 'AUSTRIA'),
            ('TRI', TerrainType.COAST, True, 'AUSTRIA'),
            ('BUD', TerrainType.LAND, True, 'AUSTRIA'),
            ('CON', TerrainType.COAST, True, 'TURKEY'),
            ('ANK', TerrainType.COAST, True, 'TURKEY'),
            ('SMY', TerrainType.COAST, True, 'TURKEY'),
            ('WAR', TerrainType.LAND, True, 'RUSSIA'),
            ('MOS', TerrainType.LAND, True, 'RUSSIA'),
            ('SEV', TerrainType.COAST, True, 'RUSSIA'),
            ('STP', TerrainType.COAST, True, 'RUSSIA'),
            # Neutral Supply Centers
            ('NWY', TerrainType.COAST, True, None),
            ('SWE', TerrainType.COAST, True, None),
            ('DEN', TerrainType.COAST, True, None),
            ('HOL', TerrainType.COAST, True, None),
            ('BEL', TerrainType.COAST, True, None),
            ('SPA', TerrainType.COAST, True, None),
            ('POR', TerrainType.COAST, True, None),
            ('TUN', TerrainType.COAST, True, None),
            ('SER', TerrainType.LAND, True, None),
            ('RUM', TerrainType.COAST, True, None),
            ('BUL', TerrainType.COAST, True, None),
            ('GRE', TerrainType.COAST, True, None),
            # Non-supply centers
            ('PIC', TerrainType.COAST, False, None),
            ('BUR', TerrainType.LAND, False, None),
            ('GAS', TerrainType.COAST, False, None),
            ('YOR', TerrainType.COAST, False, None),
            ('WAL', TerrainType.COAST, False, None),
            ('CLY', TerrainType.COAST, False, None),
            ('RUH', TerrainType.LAND, False, None),
            ('PIE', TerrainType.COAST, False, None),
            ('TUS', TerrainType.COAST, False, None),
            ('APU', TerrainType.COAST, False, None),
            ('TYR', TerrainType.LAND, False, None),
            ('BOH', TerrainType.LAND, False, None),
            ('GAL', TerrainType.LAND, False, None),
            ('SIL', TerrainType.LAND, False, None),
            ('PRU', TerrainType.COAST, False, None),
            ('FIN', TerrainType.COAST, False, None),
            ('LVN', TerrainType.COAST, False, None),
            ('UKR', TerrainType.LAND, False, None),
            ('ALB', TerrainType.COAST, False, None),
            ('ARM', TerrainType.COAST, False, None),
            ('SYR', TerrainType.COAST, False, None),
            # Seas
            ('MAO', TerrainType.SEA, False, None),
            ('NAO', TerrainType.SEA, False, None),
            ('IRI', TerrainType.SEA, False, None),
            ('ENG', TerrainType.SEA, False, None),
            ('NTH', TerrainType.SEA, False, None),
            ('SKA', TerrainType.SEA, False, None),
            ('HEL', TerrainType.SEA, False, None),
            ('BAL', TerrainType.SEA, False, None),
            ('BOT', TerrainType.SEA, False, None),
            ('BAR', TerrainType.SEA, False, None),
            ('NWG', TerrainType.SEA, False, None),
            ('WES', TerrainType.SEA, False, None),
            ('LYO', TerrainType.SEA, False, None),
            ('TYS', TerrainType.SEA, False, None),
            ('ADR', TerrainType.SEA, False, None),
            ('ION', TerrainType.SEA, False, None),
            ('AEG', TerrainType.SEA, False, None),
            ('EAS', TerrainType.SEA, False, None),
            ('BLA', TerrainType.SEA, False, None),
        ]

        # Add regions to the map 
        for name, terrain, is_sc, home_for in regions_data:
            game_map.add_region(name, terrain, is_sc, home_for)

        # Add adjacencies - grouped by region for readability
        adjacencies = [
            # Western Europe
            ('BRE', 'ENG', ['F']),
            ('BRE', 'MAO', ['F']),
            ('BRE', 'PAR', ['A']),
            ('BRE', 'PIC', ['A', 'F']),
            ('BRE', 'GAS', ['A', 'F']),
            ('PAR', 'PIC', ['A']),
            ('PAR', 'BUR', ['A']),
            ('PAR', 'GAS', ['A']),
            ('MAR', 'PIE', ['A']),
            ('MAR', 'BUR', ['A']),
            ('MAR', 'GAS', ['A']),
            ('MAR', 'LYO', ['F']),
            ('MAR', 'SPA', ['A', 'F']),
            ('GAS', 'SPA', ['A', 'F']),
            ('GAS', 'BUR', ['A']),
            ('GAS', 'MAO', ['F']),
            ('PIC', 'BUR', ['A']),
            ('PIC', 'BEL', ['A', 'F']),
            ('PIC', 'ENG', ['F']),
            ('BUR', 'RUH', ['A']),
            ('BUR', 'BEL', ['A']),
            ('BUR', 'MUN', ['A']),
            
            # British Isles
            ('EDI', 'CLY', ['A', 'F']),
            ('EDI', 'YOR', ['A', 'F']),
            ('EDI', 'LVP', ['A']),
            ('EDI', 'NTH', ['F']),
            ('EDI', 'NWG', ['F']),
            ('CLY', 'NAO', ['F']),
            ('CLY', 'NWG', ['F']),
            ('CLY', 'LVP', ['A', 'F']),
            ('LVP', 'YOR', ['A']),
            ('LVP', 'WAL', ['A', 'F']),
            ('LVP', 'IRI', ['F']),
            ('LVP', 'NAO', ['F']),
            ('YOR', 'WAL', ['A']),
            ('YOR', 'LON', ['A', 'F']),
            ('YOR', 'NTH', ['F']),
            ('WAL', 'LON', ['A', 'F']),
            ('WAL', 'ENG', ['F']),
            ('WAL', 'IRI', ['F']),
            ('LON', 'NTH', ['F']),
            ('LON', 'ENG', ['F']),
            
            # Seas around Britain
            ('IRI', 'NAO', ['F']),
            ('IRI', 'MAO', ['F']),
            ('IRI', 'ENG', ['F']),
            ('NAO', 'NWG', ['F']),
            ('NAO', 'MAO', ['F']),
            ('ENG', 'NTH', ['F']),
            ('ENG', 'MAO', ['F']),
            ('ENG', 'BEL', ['F']),
            ('MAO', 'WES', ['F']),
            ('NTH', 'NWG', ['F']),
            ('NTH', 'NWY', ['F']),
            ('NTH', 'SKA', ['F']),
            ('NTH', 'DEN', ['F']),
            ('NTH', 'HEL', ['F']),
            ('NTH', 'HOL', ['F']),
            ('NTH', 'BEL', ['F']),
            ('NWG', 'BAR', ['F']),
            ('NWG', 'NWY', ['F']),
            ('BAR', 'STP', ['F']),
            ('BAR', 'NWY', ['F']),
            
            # Central Europe
            ('HOL', 'BEL', ['A', 'F']),
            ('HOL', 'KIE', ['A', 'F']),
            ('HOL', 'RUH', ['A']),
            ('HOL', 'HEL', ['F']),
            ('BEL', 'RUH', ['A']),
            ('RUH', 'KIE', ['A']),
            ('RUH', 'MUN', ['A']),
            ('KIE', 'BER', ['A', 'F']),
            ('KIE', 'MUN', ['A']),
            ('KIE', 'DEN', ['A', 'F']),
            ('KIE', 'HEL', ['F']),
            ('KIE', 'BAL', ['F']),
            ('BER', 'PRU', ['A', 'F']),
            ('BER', 'SIL', ['A']),
            ('BER', 'MUN', ['A']),
            ('BER', 'BAL', ['F']),
            ('MUN', 'BOH', ['A']),
            ('MUN', 'TYR', ['A']),
            ('MUN', 'SIL', ['A']),
            ('MUN', 'BUR', ['A']),
            
            # Scandinavia
            ('DEN', 'SKA', ['F']),
            ('DEN', 'BAL', ['F']),
            ('DEN', 'SWE', ['A', 'F']),
            ('DEN', 'HEL', ['F']),
            ('NWY', 'SWE', ['A', 'F']),
            ('NWY', 'FIN', ['A']),
            ('NWY', 'STP', ['A', 'F']),
            ('NWY', 'SKA', ['F']),
            ('SWE', 'FIN', ['A', 'F']),
            ('SWE', 'SKA', ['F']),
            ('SWE', 'BAL', ['F']),
            ('SWE', 'BOT', ['F']),
            ('FIN', 'STP', ['A', 'F']),
            ('FIN', 'BOT', ['F']),
            
            # Baltic Region
            ('BAL', 'PRU', ['F']),
            ('BAL', 'LVN', ['F']),
            ('BAL', 'BOT', ['F']),
            ('BOT', 'STP', ['F']),
            ('BOT', 'LVN', ['F']),
            ('PRU', 'SIL', ['A']),
            ('PRU', 'WAR', ['A']),
            ('PRU', 'LVN', ['A', 'F']),
            ('SIL', 'BOH', ['A']),
            ('SIL', 'GAL', ['A']),
            ('SIL', 'WAR', ['A']),
            
            # Eastern Europe
            ('STP', 'MOS', ['A']),
            ('STP', 'LVN', ['A']),
            ('LVN', 'MOS', ['A']),
            ('LVN', 'WAR', ['A']),
            ('MOS', 'UKR', ['A']),
            ('MOS', 'SEV', ['A']),
            ('MOS', 'WAR', ['A']),
            ('WAR', 'UKR', ['A']),
            ('WAR', 'GAL', ['A']),
            ('UKR', 'SEV', ['A']),
            ('UKR', 'RUM', ['A']),
            ('UKR', 'GAL', ['A']),
            ('SEV', 'RUM', ['A', 'F']),
            ('SEV', 'ARM', ['A', 'F']),
            ('SEV', 'BLA', ['F']),
            
            # Italy and Adriatic
            ('PIE', 'TYR', ['A']),
            ('PIE', 'VEN', ['A']),
            ('PIE', 'TUS', ['A', 'F']),
            ('PIE', 'MAR', ['F']),
            ('PIE', 'LYO', ['F']),
            ('VEN', 'TYR', ['A']),
            ('VEN', 'TRI', ['A', 'F']),
            ('VEN', 'APU', ['A', 'F']),
            ('VEN', 'ROM', ['A']),
            ('VEN', 'TUS', ['A']),
            ('VEN', 'ADR', ['F']),
            ('TYR', 'BOH', ['A']),
            ('TYR', 'VIE', ['A']),
            ('TYR', 'TRI', ['A']),
            ('TYR', 'MUN', ['A']),
            ('TUS', 'ROM', ['A', 'F']),
            ('TUS', 'LYO', ['F']),
            ('TUS', 'TYS', ['F']),
            ('ROM', 'NAP', ['A', 'F']),
            ('ROM', 'APU', ['A']),
            ('ROM', 'TYS', ['F']),
            ('NAP', 'APU', ['A', 'F']),
            ('NAP', 'ION', ['F']),
            ('NAP', 'TYS', ['F']),
            ('APU', 'ADR', ['F']),
            ('APU', 'ION', ['F']),
            
            # Mediterranean Seas
            ('LYO', 'TYS', ['F']),
            ('LYO', 'WES', ['F']),
            ('LYO', 'SPA', ['F']),
            ('WES', 'TYS', ['F']),
            ('WES', 'TUN', ['F']),
            ('WES', 'NAF', ['F']),
            ('WES', 'SPA', ['F']),
            ('TYS', 'ION', ['F']),
            ('TYS', 'TUN', ['F']),
            ('ION', 'ADR', ['F']),
            ('ION', 'ALB', ['F']),
            ('ION', 'GRE', ['F']),
            ('ION', 'TUN', ['F']),
            ('ION', 'EAS', ['F']),
            ('ION', 'AEG', ['F']),
            ('ADR', 'TRI', ['F']),
            ('ADR', 'ALB', ['F']),
            ('AEG', 'EAS', ['F']),
            ('AEG', 'GRE', ['F']),
            ('AEG', 'BUL', ['F']),
            ('AEG', 'CON', ['F']),
            ('AEG', 'SMY', ['F']),
            ('EAS', 'SMY', ['F']),
            ('EAS', 'SYR', ['F']),
            
            # Iberian Peninsula
            ('SPA', 'POR', ['A', 'F']),
            ('SPA', 'GAS', ['A']),
            ('SPA', 'MAO', ['F']),
            ('SPA', 'MAR', ['A', 'F']),
            ('POR', 'MAO', ['F']),
            ('MAO', 'NAF', ['F']),
            
            # North Africa
            ('NAF', 'TUN', ['A', 'F']),
            ('NAF', 'MAO', ['F']),
            ('TUN', 'NAF', ['A', 'F']),
            
            # Balkans
            ('BOH', 'VIE', ['A']),
            ('BOH', 'GAL', ['A']),
            ('VIE', 'GAL', ['A']),
            ('VIE', 'BUD', ['A']),
            ('VIE', 'TRI', ['A']),
            ('GAL', 'BUD', ['A']),
            ('GAL', 'RUM', ['A']),
            ('BUD', 'TRI', ['A']),
            ('BUD', 'SER', ['A']),
            ('BUD', 'RUM', ['A']),
            ('TRI', 'ALB', ['A', 'F']),
            ('TRI', 'SER', ['A']),
            ('SER', 'ALB', ['A']),
            ('SER', 'GRE', ['A']),
            ('SER', 'BUL', ['A']),
            ('SER', 'RUM', ['A']),
            ('RUM', 'BUL', ['A', 'F']),
            ('RUM', 'BLA', ['F']),
            ('BUL', 'GRE', ['A', 'F']),
            ('BUL', 'CON', ['A']),
            ('BUL', 'BLA', ['F']),
            ('BUL', 'AEG', ['F']),
            ('GRE', 'ALB', ['A', 'F']),
            ('ALB', 'ADR', ['F']),
            ('ALB', 'ION', ['F']),
            
            # Black Sea and Turkey
            ('BLA', 'ANK', ['F']),
            ('BLA', 'ARM', ['F']),
            ('BLA', 'CON', ['F']),
            ('CON', 'ANK', ['A', 'F']),
            ('CON', 'SMY', ['A', 'F']),
            ('ANK', 'ARM', ['A', 'F']),
            ('ANK', 'SMY', ['A']),
            ('ARM', 'SYR', ['A']),
            ('ARM', 'SMY', ['A']),
            ('SMY', 'SYR', ['A', 'F']),
            ('SMY', 'EAS', ['F'])
        ]
        
        for r1, r2, types in adjacencies:
            game_map.add_adjacency(r1, r2, types)

        return game_map



class DiplomacyGameEngine:
    """ The core game engine for Diplomacy """
    
    def __init__(self, rules=None, max_turns: int = 100):
        if max_turns < 1:
            raise ValueError("max_turns must be at least one game year")
        self.map: Map = Map.create_standard_map()
        self.powers: Dict[str, Power] = {} # Dict mapping power names to Power objects
        self.start_year: int = 1901
        self.year: int = self.start_year
        self.season: Season = Season.SPRING
        self.phase: PhaseType = PhaseType.MOVEMENT 
        self.turn_number: int = 1 
        self.max_game_years: int = max_turns
        # Backward-compatible name retained for callers that still pass/read max_turns.
        self.max_turns: int = max_turns
        self.winners: List[str] = []
        self.game_over: bool = False
        self.ascii_map_version: int = 5
        self.order_history: List[Dict[str, Any]] = [] # Track order history
        self.game_state_history: List[Dict[str, Any]] = []  # Store game state history
        self._standoff_regions: Set[str] = set()

        # Initialize powers
        self._initialize_powers()

    @property
    def completed_game_years(self) -> int:
        return self.year - self.start_year

    def _initialize_powers(self):
        """ Initialize powers with starting units and centers """
        # Define standard powers
        standard_powers = {
            'FRANCE': [
                (UnitType.ARMY, 'PAR'),
                (UnitType.ARMY, 'MAR'),
                (UnitType.FLEET, 'BRE')
            ],
            'ENGLAND': [
                (UnitType.FLEET, 'LON'),
                (UnitType.FLEET, 'EDI'),
                (UnitType.ARMY, 'LVP')
            ],
            'GERMANY': [
                (UnitType.ARMY, 'BER'),
                (UnitType.ARMY, 'MUN'),
                (UnitType.FLEET, 'KIE')
            ],
            'ITALY': [
                (UnitType.ARMY, 'ROM'),
                (UnitType.ARMY, 'VEN'),
                (UnitType.FLEET, 'NAP')
            ],
            'AUSTRIA': [
                (UnitType.ARMY, 'VIE'),
                (UnitType.ARMY, 'BUD'),
                (UnitType.FLEET, 'TRI')
            ],
            'RUSSIA': [
                (UnitType.ARMY, 'MOS'),
                (UnitType.ARMY, 'WAR'),
                (UnitType.FLEET, 'SEV'),
                (UnitType.FLEET, 'STP')
            ],
            'TURKEY': [
                (UnitType.ARMY, 'CON'),
                (UnitType.ARMY, 'SMY'),
                (UnitType.FLEET, 'ANK')
            ]
        }

        # Create powers with their units
        for power_name, starting_units in standard_powers.items():
            power = Power(power_name)
            self.powers[power_name] = power

            # Set home centers
            power.home_centers = self.map.get_home_centers(power_name)

            # Add initial units
            for unit_type, location in starting_units:
                unit: Unit = Unit(unit_type, power_name)
                if power_name == "RUSSIA" and location == "STP":
                    unit.coast = "SC"
                region: Optional[Region] = self.map.get_region(location)
                if region and unit.place_in_region(region):
                    power.add_unit(unit)
                
            # Set initial controlled centers
            for center in power.home_centers:
                power.add_center(center)
                region: Optional[Region] = self.map.get_region(center)
                if region:
                    region.set_owner(power_name)

    def setup_game(self, num_players, rng=None) -> Dict[int, str]:
        """ Set up the game with the specified number of players """
        # assert correct player number once more
        if num_players < 3 or num_players > 7:
            raise ValueError(f"Number of players must be between 3 and 7, got {num_players}")
            

        # Select powers for the game 
        all_powers = list(self.powers.keys()) # ["AUS", "ENG", "FR", "GER", "ITA", "RUS", "TUR"]
        active_powers = (rng or random).sample(all_powers, num_players)

        # Remove unused powers
        for power_name in all_powers:
            if power_name not in active_powers:
                inactive_power = self.powers[power_name]
                for unit in list(inactive_power.units):
                    if unit.region:
                        if unit.region.unit is unit:
                            unit.region.unit = None
                        if unit.region.dislodged_unit is unit:
                            unit.region.dislodged_unit = None
                    unit.region = None
                    unit.dislodged = False
                    unit.retreat_options = []
                inactive_power.units.clear()
                inactive_power.controlled_centers.clear()

                for region in self.map.regions.values():
                    if region.owner == power_name:
                        region.set_owner(None)
                self.powers.pop(power_name)

        return {i: power for i, power in enumerate(active_powers)}

    def get_state(self):
        """ Get the current game state """
        units = {}
        centers = {}

        for power_name, power in self.powers.items():
            units[power_name] = [str(unit) for unit in power.units]
            centers[power_name] = power.controlled_centers.copy()

        return {
            'year': self.year,
            'season': self.season.value,
            'phase': self.phase.value,
            'turn': self.turn_number,
            'units': units,
            'centers': centers,
            'game_over': self.game_over,
            'winners': self.winners.copy() if self.winners else []
        }

    def get_orderable_locations(self, power_name: str) -> List[str]:
        """ Get locations where orders can be issued for a power """
        if power_name not in self.powers:
            return []

        power: Power = self.powers[power_name]
        orderable_locations: List[str] = []

        if self.phase == PhaseType.MOVEMENT:
            # IN movement phase, all units can be ordered
            for unit in power.units:
                if not unit.dislodged:
                    orderable_locations.append(unit.region.name)

        elif self.phase == PhaseType.RETREATS:
            # In retreat phase, only dislodged units can be ordered
            for unit in power.units:
                if unit.dislodged and unit.region:
                    orderable_locations.append(unit.region.name)

        elif self.phase == PhaseType.ADJUSTMENTS:
            # Calculate build/disband count 
            build_count = power.count_needed_builds()

            if build_count > 0:
                # Can build in unoccupied home centers
                orderable_locations = power.get_buildable_locations(self.map)
            elif build_count < 0:
                # Must move units
                for unit in power.units:
                    if not unit.dislodged:
                        orderable_locations.append(unit.region.name)
        
        return orderable_locations

    def get_possible_orders(self, power_name: str) -> Dict[str, List[str]]:
        """ Get all possible orders for a power in the current phase """
        if power_name not in self.powers:
            return {}
            
        power = self.powers[power_name]
        possible_orders = {}
        
        # Get orderable locations for this power
        orderable_locations = self.get_orderable_locations(power_name)
        
        if self.phase == PhaseType.MOVEMENT:
            # For each unit, determine possible orders
            for unit in power.units:
                if unit.dislodged:
                    continue
                    
                location = unit.region.name
                if location not in orderable_locations:
                    continue
                    
                orders = []
                
                # Hold order is always possible
                orders.append(f"{unit.type.value} {location} H")
                
                # Move orders, preserving split-coast destinations for fleets.
                for destination, coast in self._adjacent_destinations(unit):
                    orders.append(
                        f"{unit.type.value} {location} - "
                        f"{_format_location(destination, coast)}"
                    )
                
                # Support orders
                for supported_power in self.powers.values():
                    for supported_unit in supported_power.units:
                        if (
                            supported_unit.dislodged
                            or supported_unit is unit
                            or not self._can_unit_move_to(
                                unit,
                                supported_unit.region.name,
                                supported_unit.coast,
                                require_explicit_coast=False,
                            )
                        ):
                            continue
                        # Support hold
                        orders.append(
                            f"{unit.type.value} {location} S "
                            f"{supported_unit.type.value} "
                            f"{_format_location(supported_unit.region.name, supported_unit.coast)}"
                        )

                # A unit may support a move by a non-adjacent unit as long as
                # both the supported unit and supporter can reach the destination.
                for supported_power in self.powers.values():
                    for supported_unit in supported_power.units:
                        if supported_unit.dislodged or supported_unit is unit:
                            continue
                        supported_location = supported_unit.region.name
                        supported_destinations = self._adjacent_destinations(
                            supported_unit
                        )
                        if supported_unit.type == UnitType.ARMY:
                            supported_destinations.extend(
                                (destination, None)
                                for destination, region in self.map.regions.items()
                                if (
                                    destination != supported_location
                                    and region.terrain_type == TerrainType.COAST
                                    and self._has_possible_convoy_path(
                                        supported_location, destination
                                    )
                                )
                            )
                        for destination, coast in supported_destinations:
                            if self._can_unit_move_to(
                                unit,
                                destination,
                                coast,
                                require_explicit_coast=False,
                            ):
                                orders.append(
                                    f"{unit.type.value} {location} S "
                                    f"{supported_unit.type.value} {supported_location} "
                                    f"- {_format_location(destination, coast)}"
                                )
                
                # Convoy orders (only for fleets in sea regions)
                if unit.type == UnitType.FLEET and unit.region.terrain_type == TerrainType.SEA:
                    for army_power in self.powers.values():
                        for army in army_power.units:
                            if (
                                army.dislodged
                                or army.type != UnitType.ARMY
                                or army.region.terrain_type != TerrainType.COAST
                            ):
                                continue
                            army_location = army.region.name
                            for dest_region_name, dest_region in self.map.regions.items():
                                if (
                                    dest_region.terrain_type == TerrainType.COAST
                                    and dest_region_name != army_location
                                    and self._fleet_can_participate_in_convoy(
                                        unit, army_location, dest_region_name
                                    )
                                ):
                                    orders.append(
                                        f"F {location} C A {army_location} - "
                                        f"{dest_region_name}"
                                    )
                
                possible_orders[location] = orders
                
        elif self.phase == PhaseType.RETREATS:
            # For each dislodged unit, determine retreat options
            for unit in power.units:
                if not unit.dislodged:
                    continue
                    
                location = unit.region.name
                orders = []
                
                # Disband is always an option
                orders.append(f"{unit.type.value} {location} D")
                
                # Retreat to valid locations
                for retreat_loc in unit.retreat_options:
                    orders.append(f"{unit.type.value} {location} R {retreat_loc}")
                
                possible_orders[location] = orders
                
        elif self.phase == PhaseType.ADJUSTMENTS:
            build_count = power.count_needed_builds()
            
            if build_count > 0:
                # Can build in unoccupied home centers
                buildable_locations = power.get_buildable_locations(self.map)
                
                for location in buildable_locations:
                    orders = []
                    region = self.map.get_region(location)
                    
                    # Can build army in any buildable location
                    orders.append(f"A {location} B")
                    
                    # Can build fleet only in coastal regions
                    if region.terrain_type == TerrainType.COAST:
                        if location in MULTI_COASTS:
                            orders.extend(
                                f"F {_format_location(location, coast)} B"
                                for coast in MULTI_COASTS[location]
                            )
                        else:
                            orders.append(f"F {location} B")
                    
                    # Can also waive a build
                    orders.append("WAIVE")
                    
                    possible_orders[location] = orders
                    
            elif build_count < 0:
                # Must disband units
                for unit in power.units:
                    if not unit.dislodged:
                        location = unit.region.name
                        possible_orders[location] = [f"{unit.type.value} {location} D"]
        
        return possible_orders

    def validate_order(self, order: Order) -> Tuple[bool, Optional[str]]:
        """ Validate if an order is legal and return reason if invalid """
        if order.power not in self.powers:
            return False, f"Power {order.power} does not exist"

        if order.order_type == OrderType.WAIVE:
            # WAIVE is only valid in adjustment phase when building 
            if self.phase != PhaseType.ADJUSTMENTS:
                return False, "WAIVE orders only valid in adjustment phase"
            if order.power not in self.powers or self.powers[order.power].count_needed_builds() <= 0:
                return False, "WAIVE orders only valid when builds are available"
            return True, None

        movement_orders = {
            OrderType.HOLD,
            OrderType.MOVE,
            OrderType.SUPPORT,
            OrderType.CONVOY,
        }
        if order.order_type in movement_orders and self.phase != PhaseType.MOVEMENT:
            return False, f"{order.order_type.value} orders are only valid in movement phases"
        if order.order_type == OrderType.RETREAT and self.phase != PhaseType.RETREATS:
            return False, "Retreat orders are only valid in retreat phases"
        if order.order_type == OrderType.BUILD and self.phase != PhaseType.ADJUSTMENTS:
            return False, "Build orders are only valid in adjustment phases"
        if order.order_type == OrderType.DISBAND and self.phase not in {
            PhaseType.RETREATS,
            PhaseType.ADJUSTMENTS,
        }:
            return False, "Disband orders are only valid in retreat or adjustment phases"

        # Builds create a new unit; every other non-waive order acts on an existing one.
        unit: Optional[Unit] = None
        if order.order_type != OrderType.BUILD:
            unit = self._find_unit(order.power, order.unit_type, order.location)
            if not unit:
                return False, f"No {order.unit_type.value} unit found at {order.location} for {order.power}"
            if order.location_coast and order.location_coast != unit.coast:
                return False, (
                    f"Unit at {order.location} is not on the "
                    f"{order.location_coast} coast"
                )
            if self.phase == PhaseType.MOVEMENT and unit.dislodged:
                return False, f"Unit at {order.location} is dislodged and cannot receive movement orders"

        # Validate based on order type 
        if order.order_type == OrderType.HOLD:
            # Hold is always valid for a unit
            return True, None

        elif order.order_type == OrderType.MOVE:
            # Check if destination exists
            dest_region = self.map.get_region(order.target)
            if not dest_region:
                return False, f"Destination region {order.target} does not exist"

            if order.via_convoy:
                if unit.type != UnitType.ARMY:
                    return False, "Only armies can move VIA convoy"
                if order.target_coast:
                    return False, "Convoyed armies do not specify a destination coast"
                if self._has_possible_convoy_path(unit.region.name, order.target):
                    return True, None
                return False, (
                    f"No possible convoy path from {order.location} "
                    f"to {order.target}"
                )

            # Check if the move is adjacent (or can be convoyed for armies)
            if self._can_unit_move_to(
                unit, order.target, order.target_coast
            ):
                return True, None

            # Check if army can be convoyed
            if (
                unit.type == UnitType.ARMY
                and order.target_coast is None
                and self._has_possible_convoy_path(unit.region.name, order.target)
            ):
                return True, None

            return False, f"Unit at {order.location} cannot move to {order.target} (not adjacent or no convoy path)"

        elif order.order_type == OrderType.SUPPORT:
            # Check if the supported unit exists
            target_parts = order.target.split()
            if len(target_parts) != 2 or target_parts[0] not in {"A", "F"}:
                return False, f"Invalid supported unit: {order.target}"
            supported_type = UnitType(target_parts[0])
            supported_loc = target_parts[1]
            supported_unit = self._find_unit(None, supported_type, supported_loc)

            if not supported_unit:
                return False, f"No {supported_type.value} unit found at {supported_loc} to support"

            if order.secondary_target:
                destination = self.map.get_region(order.secondary_target)
                if not destination:
                    return False, f"Destination region {order.secondary_target} does not exist"

                # Support move - check if the destination is reachable by the
                # supported unit. A fleet move into a split coast must name it.
                if not self._can_unit_move_to(
                    supported_unit,
                    order.secondary_target,
                    order.secondary_target_coast,
                ):
                    # Check if it could be a convoyed move
                    if not (
                        supported_unit.type == UnitType.ARMY
                        and order.secondary_target_coast is None
                        and self._has_possible_convoy_path(supported_loc, order.secondary_target)
                    ):
                        return False, f"Unit at {supported_loc} cannot move to {order.secondary_target}"

                # A supporter must be able to move to the supported destination.
                if not self._can_unit_move_to(
                    unit,
                    order.secondary_target,
                    order.secondary_target_coast,
                    require_explicit_coast=False,
                ):
                    return False, f"Cannot support move to {order.secondary_target} (not adjacent to supporting unit)"
            elif not self._can_unit_move_to(
                unit,
                supported_loc,
                supported_unit.coast,
                require_explicit_coast=False,
            ):
                # Support-to-hold is given into the supported unit's province.
                return False, f"Cannot support unit at {supported_loc} (not adjacent)"

            return True, None

        elif order.order_type == OrderType.CONVOY:
            # Only fleets in water regions can convoy
            if unit.type != UnitType.FLEET:
                return False, "Only fleets can convoy"
            if unit.region.terrain_type != TerrainType.SEA:
                return False, "Convoying fleet must be in a sea region"

            # Check if the convoyed unit exists and is an army
            convoyed_type = UnitType.ARMY if order.target.startswith("A ") else UnitType.FLEET
            convoyed_loc = order.target.split()[1]
            convoyed_unit = self._find_unit(None, convoyed_type, convoyed_loc)

            if not convoyed_unit:
                return False, f"No {convoyed_type.value} unit found at {convoyed_loc} to convoy"
            if convoyed_unit.type != UnitType.ARMY:
                return False, "Only armies can be convoyed"
            if order.target_coast or order.secondary_target_coast:
                return False, "Convoyed armies do not specify coast qualifiers"

            # Check if the destination is a coastal region
            dest_region = self.map.get_region(order.secondary_target)
            if not dest_region:
                return False, f"Destination region {order.secondary_target} does not exist"
            if dest_region.terrain_type != TerrainType.COAST:
                return False, f"Convoy destination {order.secondary_target} must be a coastal region"
            if not self._fleet_can_participate_in_convoy(
                unit, convoyed_loc, order.secondary_target
            ):
                return False, (
                    f"Fleet at {unit.region.name} is not on a convoy path from "
                    f"{convoyed_loc} to {order.secondary_target}"
                )
            
            return True, None

        elif order.order_type == OrderType.RETREAT:
            # Unit must be dislodged
            if not unit.dislodged:
                return False, f"Unit at {order.location} is not dislodged and cannot retreat"

            # Check if retreat location is valid
            retreat_destination = _format_location(
                order.target, order.target_coast
            )
            if retreat_destination not in unit.retreat_options:
                return False, f"Cannot retreat to {order.target} (not a valid retreat option)"
            
            return True, None

        elif order.order_type == OrderType.BUILD:
            # Must be adjustment phase 
            if self.phase != PhaseType.ADJUSTMENTS:
                return False, "Build orders only valid in adjustment phase"

            power = self.powers[order.power]

            # Must have builds available
            if power.count_needed_builds() <= 0:
                return False, f"{order.power} has no builds available"

            # Location must be buildable home center
            buildable_locs = power.get_buildable_locations(self.map)
            if order.location not in buildable_locs:
                return False, f"Cannot build at {order.location} (not a vacant home supply center)"

            # Unit type must be valid for the terrain
            region = self.map.get_region(order.location)
            if order.unit_type == UnitType.FLEET and region.terrain_type != TerrainType.COAST:
                return False, f"Cannot build fleet at {order.location} (not a coastal region)"
            if order.unit_type == UnitType.ARMY and order.location_coast:
                return False, "Army builds do not specify a coast"
            if order.unit_type == UnitType.FLEET:
                if (
                    order.location in MULTI_COASTS
                    and order.location_coast not in MULTI_COASTS[order.location]
                ):
                    return False, (
                        f"Fleet build at {order.location} must specify a coast"
                    )
                if (
                    order.location not in MULTI_COASTS
                    and order.location_coast
                ):
                    return False, f"{order.location} does not have split coasts"

            return True, None

        elif order.order_type == OrderType.DISBAND:
            # Must be adjustment phase OR retreat phase 
            if self.phase not in [PhaseType.ADJUSTMENTS, PhaseType.RETREATS]:
                return False, "Disband orders only valid in adjustment or retreat phase"

            power = self.powers[order.power]

            if self.phase == PhaseType.ADJUSTMENTS:
                # Must need to remove units
                if power.count_needed_builds() >= 0:
                    return False, f"{order.power} does not need to remove units"
            else: # RETREATS phase
                # Unit must be dislodged
                if not unit.dislodged:
                    return False, f"Unit at {order.location} is not dislodged and cannot be disbanded in retreat phase"
            
            return True, None

        return False, f"Unknown or unsupported order type: {order.order_type}"

    def _find_unit(self, power_name: Optional[str], unit_type: UnitType, location: str) -> Optional[Unit]:
        """ Find a unit by type and location, optionally filtering by power """
        region: Region = self.map.get_region(location)
        if not region:
            return None

        for unit in (region.unit, region.dislodged_unit):
            if (
                unit
                and unit.type == unit_type
                and (power_name is None or unit.power == power_name)
            ):
                return unit
        
        return None

    def _adjacent_destinations(
        self, unit: Unit
    ) -> List[Tuple[str, Optional[str]]]:
        """Enumerate direct destinations with explicit split coasts."""
        destinations: List[Tuple[str, Optional[str]]] = []
        for destination in self.map.regions:
            if unit.type == UnitType.FLEET and destination in MULTI_COASTS:
                for coast in MULTI_COASTS[destination]:
                    if self._can_unit_move_to(unit, destination, coast):
                        destinations.append((destination, coast))
            elif self._can_unit_move_to(unit, destination):
                destinations.append((destination, None))
        return destinations

    @staticmethod
    def _fleet_destination_coasts(source: str, destination: str) -> Set[str]:
        """Return destination coasts reachable from the source province."""
        return {
            coast
            for coast, neighbors in MULTI_COASTS.get(destination, {}).items()
            if source in neighbors
        }

    def _can_unit_move_to(
        self,
        unit: Unit,
        destination: str,
        destination_coast: Optional[str] = None,
        *,
        require_explicit_coast: bool = True,
    ) -> bool:
        """Check adjacency while preserving the standard map's split coasts."""
        destination_region = self.map.get_region(destination)
        if not unit.region or not destination_region:
            return False

        if unit.type == UnitType.ARMY:
            return (
                destination_coast is None
                and unit.region.is_adjacent(UnitType.ARMY, destination)
            )

        source = unit.region.name
        if source in MULTI_COASTS:
            if unit.coast not in MULTI_COASTS[source]:
                return False
            if destination not in MULTI_COASTS[source][unit.coast]:
                return False
        elif not unit.region.is_adjacent(UnitType.FLEET, destination):
            return False

        if destination in MULTI_COASTS:
            reachable_coasts = self._fleet_destination_coasts(
                source, destination
            )
            if destination_coast:
                return destination_coast in reachable_coasts
            return bool(reachable_coasts) and not require_explicit_coast

        return destination_coast is None

    def _has_possible_convoy_path(self, start, end):
        """ Check if there's a possible convoy path between locations """
        start_region = self.map.get_region(start)
        end_region = self.map.get_region(end)
        if (
            not start_region
            or not end_region
            or start_region.terrain_type != TerrainType.COAST
            or end_region.terrain_type != TerrainType.COAST
        ):
            return False

        fleets = [
            region.unit
            for region in self.map.regions.values()
            if (
                region.terrain_type == TerrainType.SEA
                and region.unit
                and region.unit.type == UnitType.FLEET
                and not region.unit.dislodged
            )
        ]
        return self._convoy_fleets_connect(start, end, fleets)

    def _convoy_fleets_connect(self, start: str, end: str, fleets: List[Unit]) -> bool:
        """Return whether the supplied fleets form a sea chain between two coasts."""
        fleet_regions = {fleet.region.name for fleet in fleets if fleet.region}
        start_region = self.map.get_region(start)
        if not start_region:
            return False

        queue = [
            location
            for location in start_region.adjacent_regions["F"]
            if location in fleet_regions
        ]
        visited: Set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            current_region = self.map.get_region(current)
            if end in current_region.adjacent_regions["F"]:
                return True
            queue.extend(
                adjacent
                for adjacent in current_region.adjacent_regions["F"]
                if adjacent in fleet_regions and adjacent not in visited
            )
        return False

    def _fleet_can_participate_in_convoy(
        self, fleet: Unit, start: str, end: str
    ) -> bool:
        """Return whether a fleet belongs to an occupied chain joining both coasts."""
        if not fleet.region or fleet.region.terrain_type != TerrainType.SEA:
            return False
        all_fleets = [
            region.unit
            for region in self.map.regions.values()
            if (
                region.terrain_type == TerrainType.SEA
                and region.unit
                and region.unit.type == UnitType.FLEET
                and not region.unit.dislodged
            )
        ]
        fleet_regions = {candidate.region.name for candidate in all_fleets}
        start_region = self.map.get_region(start)
        if not start_region:
            return False
        queue = [
            location
            for location in start_region.adjacent_regions["F"]
            if location in fleet_regions
        ]
        component: Set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in component:
                continue
            component.add(current)
            current_region = self.map.get_region(current)
            queue.extend(
                adjacent
                for adjacent in current_region.adjacent_regions["F"]
                if adjacent in fleet_regions and adjacent not in component
            )
        return (
            fleet.region.name in component
            and any(
                end in self.map.get_region(location).adjacent_regions["F"]
                for location in component
            )
        )

    # TODO maybe keep track of completed and failed orders to add as observations?
    def parse_orders(
        self, power_name: str, order_strings: List[str]
    ) -> Tuple[List[Order], List[Dict[str, Any]]]:
        """Parse and validate an order set without mutating engine state."""
        if power_name not in self.powers:
            return [], [{"reason": "Power not found", "orders": list(order_strings)}]

        parsed_orders: List[Order] = []
        invalid_orders: List[Dict[str, Any]] = []
        ordered_locations: Set[str] = set()
        for order_str in order_strings:
            try:
                if isinstance(order_str, str) and order_str.strip() == "```":
                    continue
                order = Order.parse(order_str, power_name)
                is_valid, reason = self.validate_order(order)
                if not is_valid:
                    invalid_orders.append({"reason": reason, "orders": [order_str]})
                    continue
                if order.location and order.location in ordered_locations:
                    invalid_orders.append({
                        "reason": f"Multiple orders submitted for unit at {order.location}",
                        "orders": [order_str],
                    })
                    continue
                if order.location:
                    ordered_locations.add(order.location)
                parsed_orders.append(order)
            except (ValueError, IndexError, TypeError, AttributeError) as exc:
                invalid_orders.append({"reason": str(exc), "orders": [order_str]})
        return parsed_orders, invalid_orders

    def resolve_orders(self, orders_by_power: Dict[str, List[str]]) -> Tuple[bool, Dict[str, Any]]:
        """ Process and resolve orders for all powers """
        # Reset waiting status
        for power in self.powers.values():
            power.is_waiting = True

        # Process submitted orders
        valid_orders: Dict[str, List[Order]] = {}
        invalid_orders: Dict[str, List[Dict[str, Any]]] = {}
        for power_name, orders_list in orders_by_power.items():
            invalid_orders[power_name] = []
            if power_name not in self.powers:
                invalid_orders[power_name].append({"reason": "Power not found", "orders": orders_list})
                continue

            power = self.powers[power_name]
            parsed_orders, parse_errors = self.parse_orders(power_name, orders_list)
            invalid_orders[power_name].extend(parse_errors)

            power.set_orders(parsed_orders)
            valid_orders[power_name] = parsed_orders 
        
        # Save order history
        order_record = {
            "turn": self.turn_number,
            "year": self.year,
            "season": self.season.value,
            "phase": self.phase.value,
            "valid_orders": {power: [str(order) for order in orders] for power, orders in valid_orders.items()},
            "invalid_orders": invalid_orders
        }
        self.order_history.append(order_record)

        if self.phase == PhaseType.MOVEMENT:
            self._resolve_movement(valid_orders)
        elif self.phase == PhaseType.RETREATS:
            self._resolve_retreats(valid_orders)
        elif self.phase == PhaseType.ADJUSTMENTS:
            self._resolve_adjustments(valid_orders)

        # Advance phase 
        self._advance_phase()

        # Check for game end conditinos
        self._check_victory()

        return True, self.get_state()

    def _record_game_state(self):
        """Record the current game state to history"""
        state = {
            "turn": self.turn_number,
            "season": self.season.value,
            "year": self.year,
            "phase": self.phase.value,
            "sc_counts": {power.name: len(power.controlled_centers) for power in self.powers.values()},
            "unit_counts": {power.name: len(power.units) for power in self.powers.values()},
            "territories": {
                region.name: {
                    "owner": region.unit.power if region.unit else None,
                    "unit_type": region.unit.type.value if region.unit else None,
                    "is_supply_center": region.is_supply_center,
                }
                for region in self.map.regions.values()
            }
        }
        self.game_state_history.append(state)

    def _resolve_movement(self, valid_orders: Dict[str, List[Order]]):
        """ Resolve the movement orders """
        move_orders: Dict[Unit, str] = {}
        move_target_coasts: Dict[Unit, Optional[str]] = {}
        via_convoy_units: Set[Unit] = set()
        support_orders: Dict[
            Unit, Tuple[Unit, Optional[str], Optional[str]]
        ] = {}
        convoys: Dict[Tuple[str, str], List[Unit]] = defaultdict(list)

        # Identify all moves, supports, and convoy orders.
        for power_name, orders in valid_orders.items():
            for order in orders:
                unit: Optional[Unit] = self._find_unit(power_name, order.unit_type, order.location)
                if not unit or unit.dislodged:
                    continue

                if order.order_type == OrderType.MOVE:
                    move_orders[unit] = order.target
                    move_target_coasts[unit] = order.target_coast
                    if order.via_convoy:
                        via_convoy_units.add(unit)
                elif order.order_type == OrderType.SUPPORT:
                    supported_type = UnitType(order.target.split()[0])
                    supported_loc = order.target.split()[1]
                    supported_unit = self._find_unit(None, supported_type, supported_loc)
                    if supported_unit and not supported_unit.dislodged:
                        support_orders[unit] = (
                            supported_unit,
                            order.secondary_target,
                            order.secondary_target_coast,
                        )
                elif order.order_type == OrderType.CONVOY:
                    convoyed_type = UnitType(order.target.split()[0])
                    convoyed_loc = order.target.split()[1]
                    convoyed_unit = self._find_unit(None, convoyed_type, convoyed_loc)
                    if convoyed_unit and convoyed_unit.type == UnitType.ARMY:
                        convoys[(convoyed_loc, order.secondary_target)].append(unit)

        # Convoy validity, support cutting, and dislodgement depend on one
        # another. Re-adjudicate after removing dislodged supporters and convoy
        # fleets until no additional dependency can be invalidated.
        disabled_supporters: Set[Unit] = set()
        unavailable_convoy_fleets: Set[Unit] = set()
        convoy_fleets = {
            fleet for fleet_list in convoys.values() for fleet in fleet_list
        }
        successful_moves: Dict[Unit, str] = {}
        dislodged_units: Dict[Unit, str] = {}
        standoff_regions: Set[str] = set()

        dependency_count = len(support_orders) + len(convoy_fleets) + 1
        for _ in range(dependency_count):
            active_convoys = {
                route
                for route, fleets in convoys.items()
                if self._convoy_fleets_connect(
                    route[0],
                    route[1],
                    [
                        fleet
                        for fleet in fleets
                        if fleet not in unavailable_convoy_fleets
                    ],
                )
            }

            supports: Dict[Unit, List[Unit]] = defaultdict(list)
            for supporting_unit, (
                supported_unit,
                destination,
                destination_coast,
            ) in support_orders.items():
                if supporting_unit in disabled_supporters:
                    continue
                supported_move = move_orders.get(supported_unit)
                support_matches = (
                    (destination is None and supported_move is None)
                    or (
                        destination is not None
                        and supported_move == destination
                        and move_target_coasts.get(supported_unit)
                        == destination_coast
                    )
                )
                support_target = destination or supported_unit.region.name
                if (
                    support_matches
                    and self._is_valid_support(
                        supporting_unit,
                        supported_unit,
                        support_target,
                        valid_orders,
                        active_convoys,
                    )
                ):
                    supports[supported_unit].append(supporting_unit)

            disrupted_convoys = {
                (unit.region.name, destination)
                for unit, destination in move_orders.items()
                if (
                    (
                        unit in via_convoy_units
                        or not self._can_unit_move_to(
                            unit,
                            destination,
                            move_target_coasts.get(unit),
                        )
                    )
                    and (unit.region.name, destination) not in active_convoys
                )
            }
            (
                successful_moves,
                dislodged_units,
                standoff_regions,
            ) = self._calculate_movements(
                move_orders,
                supports,
                disrupted_convoys,
                via_convoy_units,
                move_target_coasts,
            )

            newly_disabled_supporters = (
                set(dislodged_units) & set(support_orders)
            ) - disabled_supporters
            newly_unavailable_fleets = (
                set(dislodged_units) & convoy_fleets
            ) - unavailable_convoy_fleets
            if not newly_disabled_supporters and not newly_unavailable_fleets:
                break
            disabled_supporters.update(newly_disabled_supporters)
            unavailable_convoy_fleets.update(newly_unavailable_fleets)

        self._standoff_regions = standoff_regions
        self._apply_movements(
            successful_moves,
            dislodged_units,
            move_target_coasts,
        )

        # Update supply center ownership and prepare retreats.
        self._update_supply_centers()
        self._prepare_retreats()

    def _is_valid_support(
        self,
        supporting_unit: Unit,
        supported_unit: Unit,
        target: str,
        valid_orders: Dict[str, List[Order]],
        active_convoys: Optional[Set[Tuple[str, str]]] = None,
    ) -> bool:
        """ Check if a support is valid (not cut) """
        supporting_region: Region = supporting_unit.region
        active_convoys = active_convoys or set()

        for power_name, orders in valid_orders.items():
            for order in orders:
                if (
                    order.order_type == OrderType.MOVE
                    and order.target == supporting_region.name
                    and power_name != supporting_unit.power
                ):
                    attacking_unit = self._find_unit(
                        power_name, order.unit_type, order.location
                    )
                    if not attacking_unit or attacking_unit.dislodged:
                        continue
                    if (
                        (
                            order.via_convoy
                            or not self._can_unit_move_to(
                                attacking_unit,
                                supporting_region.name,
                                order.target_coast,
                            )
                        )
                        and (
                            attacking_unit.region.name,
                            supporting_region.name,
                        )
                        not in active_convoys
                    ):
                        # A convoyed move whose convoy failed never attacks the
                        # supporter's province and therefore cannot cut support.
                        continue
                    # An attack from the province against which support is given
                    # does not cut that support; every other enemy attack does.
                    if order.location != target:
                        return False 

        return True 

    def _resolve_convoy_disruptions(
        self,
        convoys: Dict[Tuple[str, str], List[Unit]],
        move_orders: Dict[Unit, str],
        supports: Dict[Unit, List[Unit]],
    ) -> Set[Tuple[str, str]]:
        """ Determine which convoys are disrupted """
        disrupted_convoys: Set[Tuple[str, str]] = set()
        attackers_by_target: Dict[str, List[Unit]] = defaultdict(list)
        for attacker, target in move_orders.items():
            attackers_by_target[target].append(attacker)

        for (start, end), fleet_list in convoys.items():
            for fleet in fleet_list:
                attackers = [
                    attacker
                    for attacker in attackers_by_target.get(fleet.region.name, [])
                    if attacker.power != fleet.power
                ]
                if not attackers:
                    continue
                strengths = {
                    attacker: 1 + len(supports.get(attacker, []))
                    for attacker in attackers
                }
                highest = max(strengths.values())
                strongest = [
                    attacker for attacker, strength in strengths.items()
                    if strength == highest
                ]
                fleet_strength = 1 + len(supports.get(fleet, []))
                if len(strongest) == 1 and highest > fleet_strength:
                    disrupted_convoys.add((start, end))
                    break
        return disrupted_convoys

    def _resolve_movements(
        self,
        move_orders: Dict[Unit, str],
        supports: Dict[Unit, List[Unit]],
        disrupted_convoys: Set[Tuple[str, str]],
    ) -> None:
        """Resolve and apply one movement adjudication."""
        successful_moves, dislodged_units, standoffs = self._calculate_movements(
            move_orders, supports, disrupted_convoys
        )
        self._standoff_regions = standoffs
        self._apply_movements(successful_moves, dislodged_units)

    def _calculate_movements(
        self,
        move_orders: Dict[Unit, str],
        supports: Dict[Unit, List[Unit]],
        disrupted_convoys: Set[Tuple[str, str]],
        via_convoy_units: Optional[Set[Unit]] = None,
        move_target_coasts: Optional[Dict[Unit, Optional[str]]] = None,
    ) -> Tuple[Dict[Unit, str], Dict[Unit, str], Set[str]]:
        """Adjudicate movement without mutating units or map occupancy."""
        via_convoy_units = via_convoy_units or set()
        move_target_coasts = move_target_coasts or {}
        original_regions = {unit: unit.region for unit in move_orders}
        original_occupants = {
            name: region.unit for name, region in self.map.regions.items()
        }

        blocked_moves: Set[Unit] = set()
        direct_moves: Dict[Unit, bool] = {}
        for unit, destination in move_orders.items():
            source = original_regions[unit].name
            direct_moves[unit] = (
                unit not in via_convoy_units
                and self._can_unit_move_to(
                    unit, destination, move_target_coasts.get(unit)
                )
            )
            if not direct_moves[unit] and (source, destination) in disrupted_convoys:
                blocked_moves.add(unit)

        attackers_by_target: Dict[str, List[Unit]] = defaultdict(list)
        attack_strength: Dict[Unit, int] = {}
        for unit, destination in move_orders.items():
            if unit in blocked_moves:
                continue
            attackers_by_target[destination].append(unit)
            attack_strength[unit] = 1 + len(supports.get(unit, []))

        winner_by_target: Dict[str, Unit] = {}
        standoff_regions: Set[str] = set()
        for destination, attackers in attackers_by_target.items():
            highest = max(attack_strength[attacker] for attacker in attackers)
            strongest = [
                attacker for attacker in attackers
                if attack_strength[attacker] == highest
            ]
            if len(strongest) == 1:
                winner_by_target[destination] = strongest[0]
            elif len(strongest) > 1:
                standoff_regions.add(destination)

        status: Dict[Unit, bool] = {}
        resolving: Set[Unit] = set()

        def dislodging_strength(attacker: Unit, defender: Unit) -> int:
            # Support supplied by the defender's own power cannot dislodge it,
            # though it still counts when determining standoffs.
            return 1 + sum(
                supporter.power != defender.power
                for supporter in supports.get(attacker, [])
            )

        def succeeds(unit: Unit) -> bool:
            if unit in status:
                return status[unit]
            destination = move_orders[unit]
            if unit in blocked_moves or winner_by_target.get(destination) is not unit:
                status[unit] = False
                return False

            defender = original_occupants[destination]
            if defender is None:
                status[unit] = True
                return True

            source = original_regions[unit].name
            defender_destination = move_orders.get(defender)
            is_head_to_head = (
                defender_destination == source
                and direct_moves.get(unit, False)
                and direct_moves.get(defender, False)
                and defender not in blocked_moves
            )
            if is_head_to_head:
                status[unit] = (
                    unit.power != defender.power
                    and dislodging_strength(unit, defender)
                    > attack_strength.get(defender, 1)
                )
                return status[unit]

            if defender in move_orders:
                if defender in resolving:
                    # A cycle of three or more moves vacates all its provinces.
                    status[unit] = True
                    return True
                resolving.add(unit)
                defender_succeeds = succeeds(defender)
                resolving.discard(unit)
                if defender_succeeds:
                    status[unit] = True
                    return True

            # The province remains occupied. A power may not dislodge its own unit.
            if unit.power == defender.power:
                status[unit] = False
                return False
            defense_strength = 1
            if defender not in move_orders:
                defense_strength += len(supports.get(defender, []))
            status[unit] = (
                dislodging_strength(unit, defender) > defense_strength
            )
            return status[unit]

        successful_moves = {
            unit: destination
            for unit, destination in move_orders.items()
            if succeeds(unit)
        }
        successful_units = set(successful_moves)

        dislodged_units: Dict[Unit, str] = {}
        for attacker, destination in successful_moves.items():
            defender = original_occupants[destination]
            if defender and defender not in successful_units:
                dislodged_units[defender] = original_regions[attacker].name

        return successful_moves, dislodged_units, standoff_regions

    def _apply_movements(
        self,
        successful_moves: Dict[Unit, str],
        dislodged_units: Dict[Unit, str],
        move_target_coasts: Optional[Dict[Unit, Optional[str]]] = None,
    ) -> None:
        """Apply a completed movement adjudication atomically."""
        move_target_coasts = move_target_coasts or {}
        original_regions = {unit: unit.region for unit in successful_moves}
        successful_units = set(successful_moves)

        # Clear every source and dislodged defender before placing any attacker.
        for unit in successful_units:
            source_region = original_regions[unit]
            if source_region.unit is unit:
                source_region.unit = None
        for unit, attacker_origin in dislodged_units.items():
            region = unit.region
            if region and region.unit is unit:
                region.unit = None
            unit.dislodged = True
            unit.dislodged_from = attacker_origin
            unit.retreat_options = []
            if region:
                region.dislodged_unit = unit

        for unit, destination in successful_moves.items():
            destination_region = self.map.get_region(destination)
            unit.region = destination_region
            unit.coast = move_target_coasts.get(unit)
            unit.dislodged = False
            unit.dislodged_from = None
            destination_region.unit = unit

    def _update_supply_centers(self):
        """ Update supply center ownership after Fall movement """
        if self.season != Season.FALL:
            return 

        # Only update in Fall
        for region_name in self.map.get_supply_centers():
            region = self.map.get_region(region_name)
            occupying_unit: Optional[Unit] = region.unit 

            if occupying_unit:
                old_owner: Optional[str] = region.owner 
                new_owner: str = occupying_unit.power

                # Transfer ownership if changed
                if old_owner != new_owner:
                    if old_owner in self.powers:
                        self.powers[old_owner].remove_center(region_name)

                    if new_owner in self.powers:
                        self.powers[new_owner].add_center(region_name)
                    region.set_owner(new_owner)

    def _prepare_retreats(self):
        """ Determine valid retreat locations for all dislodged units """
        # For each dislodged unit, find valid retreat locations
        for power_name, power in self.powers.items():
            for unit in power.units:
                if unit.dislodged:
                    retreat_options = [] 

                    # Check all adjacent locations, keeping split coasts distinct.
                    for adjacent, coast in self._adjacent_destinations(unit):
                        adjacent_region = self.map.get_region(adjacent)

                        # Location must be empty and not be a bounce location
                        if (adjacent_region and 
                            not adjacent_region.unit and
                            not adjacent_region.dislodged_unit and
                            adjacent != unit.dislodged_from and
                            adjacent not in self._standoff_regions):
                            retreat_options.append(
                                _format_location(adjacent, coast)
                            )

                    unit.retreat_options = retreat_options

    def _resolve_retreats(self, valid_orders: Dict[str, List[Order]]):
        """ Resolve retreat phase orders """
        retreat_targets: Dict[
            str, List[Tuple[Unit, Optional[str]]]
        ] = {}  # {province: [(retreating unit, coast)]}
        disband_units: Set[Unit] = {
            unit
            for power in self.powers.values()
            for unit in power.units
            if unit.dislodged
        }

        # Collect all retreat orders
        for power_name, orders in valid_orders.items():
            for order in orders:
                unit: Optional[Unit] = self._find_unit(power_name, order.unit_type, order.location)
                if not unit or not unit.dislodged:
                    continue 

                if order.order_type == OrderType.RETREAT:
                    retreat_targets.setdefault(order.target, []).append(
                        (unit, order.target_coast)
                    )
                elif order.order_type == OrderType.DISBAND:
                    disband_units.add(unit)

        # Resolve retreats - units bounce if multiple units retreat to same location
        successful_retreats: Dict[
            Unit, Tuple[str, Optional[str]]
        ] = {}
        for location, unit_coasts in retreat_targets.items():
            if len(unit_coasts) == 1:
                unit, coast = unit_coasts[0]
                successful_retreats[unit] = (location, coast)
                disband_units.discard(unit)
            else:
                # All bounced units are disbanded
                disband_units.update(unit for unit, _coast in unit_coasts)

        # Execute successful retreats
        for unit, (destination, coast) in successful_retreats.items():
            region: Optional[Region] = self.map.get_region(destination)
            if not region or not unit.retreat(region, coast):
                disband_units.add(unit)

        # Disband explicit, failed, and omitted retreats.
        for unit in disband_units:
            power: Power = self.powers[unit.power]
            power.remove_unit(unit)
            if unit.region:
                if unit.region.dislodged_unit is unit:
                    unit.region.dislodged_unit = None
                if unit.region.unit is unit:
                    unit.region.unit = None
            unit.region = None
            unit.coast = None
            unit.dislodged = False
            unit.dislodged_from = None
            unit.retreat_options = []


    def _resolve_adjustments(self, valid_orders: Dict[str, List[Order]]):
        """ Resolve adjustment phase orders """
        for power_name, power in self.powers.items():
            orders = valid_orders.get(power_name, [])
            build_count: int = power.count_needed_builds()

            # Process builds if needed
            if build_count > 0:
                builds_executed = 0 
                waives = 0

                for order in orders:
                    if order.order_type == OrderType.BUILD and builds_executed < build_count:
                        # Create and place the new unit
                        unit: Unit = Unit(order.unit_type, power_name)
                        unit.coast = order.location_coast
                        region: Optional[Region] = self.map.get_region(order.location)

                        if unit.place_in_region(region):
                            power.add_unit(unit)
                            builds_executed += 1
                    elif order.order_type == OrderType.WAIVE:
                        waives += 1

                # Waive any remaining builds
                builds_executed += waives 

            # Process disbands if needed
            elif build_count < 0:
                disbands_needed: int = abs(build_count)
                disbands_executed: int = 0

                for order in orders:
                    if order.order_type == OrderType.DISBAND and disbands_executed < disbands_needed:
                        unit: Optional[Unit] = self._find_unit(power_name, order.unit_type, order.location)
                        if unit:
                            self._remove_unit_from_map(power, unit)
                            disbands_executed += 1


                # If not enough disbands were ordered, auto-disband furthest units from home
                if disbands_executed < disbands_needed:
                    units_to_disband = self._select_units_to_disband(
                        power, disbands_needed - disbands_executed
                    )

                    for unit in units_to_disband:
                        self._remove_unit_from_map(power, unit)

    @staticmethod
    def _remove_unit_from_map(power: Power, unit: Unit) -> None:
        """Remove a unit while keeping power, unit, and region pointers aligned."""
        region = unit.region
        power.remove_unit(unit)
        if region:
            if region.unit is unit:
                region.unit = None
            if region.dislodged_unit is unit:
                region.dislodged_unit = None
        unit.region = None
        unit.coast = None
        unit.dislodged = False
        unit.dislodged_from = None
        unit.retreat_options = []

    def _select_units_to_disband(self, power: Power, count: int) -> List[Unit]:
        """ Select units to automatically disband on distance from home centers """
        if count <= 0:
            return []


        # Calculate distance from each unit to nearest home center 
        unit_distances = []
        for unit in power.units:
            if unit.dislodged:
                continue 

            min_distance = float('inf')
            for home in power.home_centers:
                distance = self._calculate_distance(unit.region.name, home)
                min_distance = min(min_distance, distance)

            unit_distances.append((unit, min_distance))

        # Sort by distance (descending) then by unit type (fleets first)
        unit_distances.sort(key=lambda x: (-x[1], 0 if x[0].type == UnitType.FLEET else 1))
        
        return [unit for unit, _ in unit_distances[:count]]

    def _calculate_distance(self, start, end):
        """ Calculate approximate distance between two regions """
        # Simple BFS
        visited = set()
        queue = [(start, 0)] # (location, distance)

        while queue:
            current, distance = queue.pop(0)

            if current == end:
                return distance 

            if current in visited:
                continue 

            visited.add(current)
            current_region = self.map.get_region(current)

            # Add all adjacent regions 
            adjacencies = set()
            for unit_type in ["A", "F"]:
                adjacencies.update(current_region.adjacent_regions[unit_type])

            for adj in adjacencies:
                if adj not in visited:
                    queue.append((adj, distance + 1))

        return float('inf') # No path found 

    def _advance_phase(self):
        """ Advance to the next game phase """
        if self.phase == PhaseType.MOVEMENT:
            self.phase = PhaseType.RETREATS
            
        elif self.phase == PhaseType.RETREATS:
            if self.season == Season.FALL:
                self.season = Season.WINTER
                self.phase = PhaseType.ADJUSTMENTS
            else:
                self.season = Season.FALL
                self.phase = PhaseType.MOVEMENT
                
        elif self.phase == PhaseType.ADJUSTMENTS:
            self.year += 1
            self.season = Season.SPRING
            self.phase = PhaseType.MOVEMENT
            self.turn_number += 1 
            
        # Reset all waiting flags
        for power in self.powers.values():
            power.is_waiting = True
            power.clear_orders()

        # After advancing phase, record the new game state
        self._record_game_state()

    def _check_victory(self):
        """ Check if any power has achieved victory """
        # Count supply centers for each power
        for power_name, power in self.powers.items():
            # Check for elimination
            power.check_elimination()
            if power.is_defeated:
                continue

            # Check for victory
            center_count = len(power.controlled_centers)
            total_centers = len(self.map.get_supply_centers())
            victory_threshold = (total_centers // 2) + 1 

            if center_count >= victory_threshold:
                self.winners = [power_name]
                self.game_over = True 
                return 

        # A game year is complete only after its Winter adjustment advances the
        # engine to the next Spring. Do not treat movement/retreat phases as years.
        active_powers = [p for p in self.powers.values() if not p.is_defeated]
        if (
            len(active_powers) <= 1
            or self.completed_game_years >= self.max_game_years
        ):
            # Game ends in draw or with one winner
            if len(active_powers) == 1:
                self.winners = [active_powers[0].name]
            self.game_over = True

    def get_ascii_map(self) -> str:
        versions = {
            1: self.get_ascii_map_v1,
            2: self.get_ascii_map_v2,
            3: self.get_ascii_map_v3,
            4: self.get_ascii_map_v4,
            5: self.get_ascii_map_v5,
        }
        return versions[self.ascii_map_version]()

    def get_ascii_map_v1(self) -> str:
        """Generate a tile-based ASCII map with clear terrain and border indicators"""
        # Define power abbreviations and colors
        power_abbr = {
            'AUSTRIA': 'AUS',
            'ENGLAND': 'ENG',
            'FRANCE': 'FRA',
            'GERMANY': 'GER',
            'ITALY': 'ITA',
            'RUSSIA': 'RUS',
            'TURKEY': 'TUR',
            None: '   '
        }
        
        # Create territory ownership mapping
        territory_owners = {}
        for power_name, power in self.powers.items():
            for center in power.controlled_centers:
                territory_owners[center] = power_name
        
        # Create unit location mapping
        units_by_location = {}
        for power_name, power in self.powers.items():
            for unit in power.units:
                if unit.region:
                    units_by_location[unit.region.name] = {
                        'type': unit.type.value,
                        'power': power_name,
                        'dislodged': unit.dislodged
                    }
        
        # Create a tile for each territory with appropriate borders
        def create_territory_box(name):
            """Create a text box representing a territory"""
            if not name or name not in self.map.regions:
                return ["          ", "          ", "          ", "          ", "          ", "          "]
                
            region = self.map.regions[name]
            is_sc = region.is_supply_center
            owner = territory_owners.get(name, None)
            owner_abbr = power_abbr.get(owner, '   ')
            
            # Determine border style based on terrain
            terrain = region.terrain_type
            
            # Unit information
            unit_info = units_by_location.get(name, None)
            if unit_info:
                unit_display = f"{unit_info['type']}-{power_abbr[unit_info['power']][:3]}"
                if unit_info['dislodged']:
                    unit_display = f"*{unit_display}"
                else:
                    unit_display = f" {unit_display}"
            else:
                unit_display = "      "
            
            sc_marker = "SC" if is_sc else "  "
            
            # Create box with appropriate borders based on terrain
            if terrain == TerrainType.SEA:
                line1 = f"~~~~~~~~"
                line2 = f"~ {name:^4} ~"
                line3 = f"~      ~"
                line4 = f"~{unit_display:^6}~"
                line5 = f"~      ~"
                line6 = f"~~~~~~~~"
            elif terrain == TerrainType.COAST:
                line1 = f"+~~~~~~+"
                line2 = f"| {name:^4} |"
                line3 = f"| {sc_marker:^4} |"
                line4 = f"|{unit_display:^6}|"
                line5 = f"| {owner_abbr:^4} |"
                line6 = f"+~~~~~~+"
            else:  # LAND
                line1 = f"+------+"
                line2 = f"| {name:^4} |"
                line3 = f"| {sc_marker:^4} |"
                line4 = f"|{unit_display:^6}|"
                line5 = f"| {owner_abbr:^4} |"
                line6 = f"+------+"
            
            return [line1, line2, line3, line4, line5, line6]
        
        # Define regions by geographic area for layout
        map_layout = [
            # North
            [None, "BAR", "STP", None, None, "FIN", None],
            ["NAO", "NWG", "NTH", "SKA", "BOT", "SWE", None],
            ["IRI", "CLY", "EDI", "DEN", "BAL", "LVN", "MOS"],
            [None, "LVP", "YOR", "HEL", "BER", "PRU", "WAR"],
            
            # Central Europe
            ["MAO", "WAL", "LON", "HOL", "KIE", "SIL", "GAL", "UKR"],
            ["BRE", "ENG", "BEL", "RUH", "MUN", "BOH", "VIE", "RUM"],
            ["GAS", "PAR", "BUR", "TYR", "TRI", "BUD", "SER", "SEV"],
            ["SPA", "MAR", "PIE", "VEN", "ADR", "ALB", "BUL", "BLA"],
            
            # Mediterranean
            ["POR", "WES", "LYO", "TUS", "ROM", "ION", "GRE", "AEG"],
            ["NAF", "TYS", "APU", "NAP", "EAS", "CON", "ANK", "ARM"],
            ["TUN", None, None, None, "SYR", "SMY", None, None],
        ]
        
        # Generate the map tiles
        tile_grid = []
        for row in map_layout:
            row_tiles = []
            for region in row:
                row_tiles.append(create_territory_box(region))
            tile_grid.append(row_tiles)
        
        # Combine tiles into a map
        map_lines = []
        for row_idx, row in enumerate(tile_grid):
            # Each tile has 6 lines
            for line_idx in range(6):
                line = ""
                for tile in row:
                    if line_idx < len(tile):
                        line += tile[line_idx] + "  "
                    else:
                        line += "          "
                map_lines.append(line)
            # Add space between rows
            map_lines.append("")
        
        # Create legend with improved formatting
        legend = [
            "+----------------------------------------------------------+",
            "|                   MAP LEGEND                             |",
            "+----------------------------------------------------------+",
            "| TERRAIN TYPES:                                           |",
            "| +------+  Land region (solid border)                     |",
            "| +~~~~~~+  Coastal region (mixed border)                  |",
            "| ~~~~~~~~  Sea region (wavy border)                       |",
            "|                                                          |",
            "| TERRITORY FORMAT:                                        |",
            "| | NAME |  <- Territory name (3-letter code)              |",
            "| |  SC  |  <- Supply center (if present)                  |",
            "| |A-PWR |  <- Unit type and power (A=Army, F=Fleet)       |",
            "| | PWR  |  <- Controlling power                           |",
            "|                                                          |",
            "| UNIT FORMAT:                                             |",
            "| A-FRA = Army France                                      |",
            "| F-ENG = Fleet England                                    |",
            "| *F-TUR = Dislodged Fleet Turkey                          |",
            "+----------------------------------------------------------+",
            "|                CURRENT GAME STATE                        |",
            "+----------------------------------------------------------+",
            f"| PHASE: {self.season.value} {self.year} {self.phase.value}",
            f"| TURN: {self.turn_number}/{self.max_turns}",
            "+----------------------------------------------------------+",
            "| POWER       SUPPLY CENTERS       UNITS                   |",
        ]
        
        # Add power statistics with better spacing
        for power_name, power in self.powers.items():
            centers = len(power.controlled_centers)
            units = len(power.units)
            legend.append(f"| {power_name:<12} {centers:^18} {units:^18} |")
        
        legend.append("+----------------------------------------------------------+")
        
        # Add key connection information with improved organization
        connections_info = [
            "LAND BORDERS BETWEEN POWERS:",
            "• France/Germany: Burgundy connects Paris and Munich",
            "• Germany/Russia: Prussia connects Berlin and Warsaw",
            "• Austria/Italy: Tyrolia and Venezia connect Vienna and Rome",
            "• Austria/Russia: Galicia connects Vienna and Warsaw",
            "• Turkey/Russia: Armenia connects Constantinople and Sevastopol",
            "",
            "SEA BORDERS:",
            "• England/France: English Channel connects London and Brest",
            "• Italy/Austria: Adriatic Sea connects Venice and Trieste",
            "• Turkey/Russia: Black Sea connects Constantinople and Sevastopol",
            "",
            "STRATEGIC STRAITS:",
            "• Denmark connects North Sea and Baltic Sea",
            "• Constantinople connects Black Sea and Aegean Sea",
            "• Gibraltar (between Spain and North Africa) connects Atlantic and Mediterranean",
            "",
            "COASTAL REGIONS WITH MULTIPLE COASTS:",
            "• Spain has North (Atlantic) and South (Mediterranean) coasts",
            "• St. Petersburg has North (Barents Sea) and South (Gulf of Bothnia) coasts",
            "• Bulgaria has East (Black Sea) and South (Aegean Sea) coasts"
        ]
        
        # Combine everything
        return "\n".join(map_lines) + "\n\n" + "\n".join(legend) + "\n\n" + "\n".join(connections_info)

    def get_ascii_map_v2(self) -> str:
        """
        Generate a classic-style ASCII map using a single pre-drawn template.
        Territory names, supply centers, and unit info are overlaid at
        specific coordinates.
        """
        # -------------------------------------------------------------
        # 1) The big ASCII map template: paste the 1989 text here
        # -------------------------------------------------------------
        ASCII_MAP_TEMPLATE = r"""
+-------------+-------------------------+-----------------------------------+
|.............|.........................|...................................|
|.........+---+...........+-------------+...............BAR.................|
|.........|   |...........|             |...................................|
|...NAO...| C |...........|             +-----------------------------------+
|.........| L |...........|             |                      nc           |
|.....+---+ Y |....NWG....|             +-----------------+                 |
|.....|   |   |...........|    =NWY=    |       FIN       |                 |
|.....|   +---+...........|             +---------+-------+                 |
|.....|   |   |...........|             |         |.......|                 |
|.....| L | E |...........|             +-----+   |.......|                 |
|.....|=V=|=D=|...........|             |.....|   |.......|      =STP=      |
|.....| P | I +-----------+-------------+.SKA.|   |.......|                 |
|.....|   |   |.........................|.....| S |.......|                 |
|.+---+   +---+..........NTH............+-----+=W=|..GOB..|sc               |
|.|...|   | Y |.........................|     | E |.......|                 |
|.|...+---+ O |.....+---+-------+-------+     |   |.......|                 |
|.|...|   | R |.....|   | =HOL= |..HEL..|=DEN=|   |.......|                 |
|.|...| W +---+.....|   | +-----+-------+     |   |.......|                 |
|.|...| A | L |.....|   | |             |     |   |.......|                 |
|.|...| L |=O=|.....|   | |             +-----+---+---+---+-----------+     |
|.|.I.|   | N |.....|   | |    =KIE=    |.....BAL.....|      LVN      |     |
|.|.R.+---+---+.....|   | |             +-----+-------+---+---+-------+-----+
|.|.I.|.......|.....|   | |             |     |           |   |             |
|.|...|.......+-----+   +-+-+-----------+=BER=|    PRU    | W |    =MOS=    |
|.|...|.......|         |   |           |     |           |=A=|             |
|.|...|..ENG..|   =BEL= | R |           +-----+-----------+ R +-+-----------+
|.|...|.......|         | U |  =MUN=    |       SIL       |   | |           |
|.|...|.......+-------+ | H |           +-------------+---+---+ |           |
|.|...|.......|  PIC  | |   |           |             |       |U|           |
+-+---+---+---+-+---+-+-+---+-+-+-------+     BOH     |       |K|   =SEV=   |
|.........|     |   |         | |       |             |  GAL  |R|           |
|.........|     | P |         | |       +-------------+       | |           |
|.........|=BRE=|=A=|  BUR    | |  TYR  |    =VIE=    |       | |           |
|.........|     | R |       +-+ |       +-----------+-+---+---+-+-+-------+-+
|.........|     |   |       |SWZ|       |           |     |       |.......| |
|.........+-----+---+-+-----+-+-+-+-----+    =TRI=  |=BUD=|       |.......| |
|.........|           |       |   |     |           |     | =RUM= |.......| |
|.........|           |       | P |     +-------+-+-+-----+       |..BLA..| |
|.........|    GAS    | =MAR= | I |=VEN=|...ADR.| |       |       |.......| |
|...MAO...|           |       | E |     +-----+.| | =SER= +-------+.......|A|
|.........|           |       |   |     |     |.| |       |     ec|.......|R|
|.........+-----------+---+---+-+-+-+---+ APU |.|A+-------+ =BUL= +---+---+M|
|.........|nc             |.....| T | R |     |.|L|       |   sc  | C | A | |
|.........+-----+         |.....| U |=O=+---+ |.|B|       +-------+=O=|=N=| |
|.........|=POR=|   =SPA= |.GOL.| S | M | N | |.| | =GRE= |.......| N | K | |
|.........+-----+         |.....+-+-+---+=A=| |.| |       |.......+---+---+ |
|.........|sc           sc|.......|.....| P | |.| |       |..AEG..|       | |
|.........+---------------+-------+.TYS.+---+-+-+-+-------+.......| =SMY= +-+
|.........|...........WMD.........|.....|.................|.......|       |S|
|.........+-----------------+-----+-----+.......ION.......+-------+-------+Y|
|.........|         NAF     |  =TUN=    |.................|......EMD......|R|
+---------+-----------------+-----------+-----------------+---------------+-+
    """.strip('\n')

        # -------------------------------------------------------------
        # 2) Define row/column positions for each region label
        #    (You must figure these out by trial/error or counting lines)
        # -------------------------------------------------------------
        region_positions = {
            "STP": (2, 20),  # Example: row=2, col=20
            "NWG": (3, 5),
            "FIN": (2, 40),
            "SWE": (3, 50),
            # ... add all other territories
        }

        # -------------------------------------------------------------
        # 3) Create a mutable structure from the template
        #    (so we can overwrite certain positions)
        # -------------------------------------------------------------
        map_lines = [list(line) for line in ASCII_MAP_TEMPLATE.split('\n')]


        # -------------------------------------------------------------
        # 4) Prepare data: territory owners, units, etc.
        # -------------------------------------------------------------
        power_abbr = {
            'AUSTRIA': 'AUS',
            'ENGLAND': 'ENG',
            'FRANCE':  'FRA',
            'GERMANY': 'GER',
            'ITALY':   'ITA',
            'RUSSIA':  'RUS',
            'TURKEY':  'TUR',
            None:      '   '
        }

        # Who owns each supply center?
        territory_owners = {}
        for power_name, power in self.powers.items():
            for center in power.controlled_centers:
                territory_owners[center] = power_name

        # Which units are in which regions?
        units_by_location = {}
        for power_name, power in self.powers.items():
            for unit in power.units:
                if unit.region:
                    units_by_location[unit.region.name] = {
                        'type': unit.type.value,    # 'A' or 'F'
                        'power': power_name,
                        'dislodged': unit.dislodged
                    }

        # -------------------------------------------------------------
        # 5) Overlay territory labels, supply centers, and units
        # -------------------------------------------------------------
        def place_text(r, c, text):
            """Helper to place text at map_lines[r][c..] (if in range)."""
            if 0 <= r < len(map_lines):
                line = map_lines[r]
                for i, ch in enumerate(text):
                    if 0 <= c + i < len(line):
                        line[c + i] = ch

        for region_name, (row, col) in region_positions.items():
            region_label = region_name.upper()[:3]

            # (a) Place the region label
            place_text(row, col, region_label)

            # (b) If it's a supply center, add a marker after the label
            region_obj = self.map.regions.get(region_name)
            if region_obj and region_obj.is_supply_center:
                place_text(row, col + len(region_label), "*")

            # (c) If there's a unit, place it on the next line (row+1)
            unit_info = units_by_location.get(region_name)
            if unit_info:
                # Example format: "A-FRA" or "*F-TUR" if dislodged
                unit_str = f"{unit_info['type']}-{power_abbr[unit_info['power']]}"
                if unit_info['dislodged']:
                    unit_str = "*" + unit_str
                place_text(row + 1, col, unit_str)

        # -------------------------------------------------------------
        # 6) Convert the map back to a single string
        # -------------------------------------------------------------
        final_map_lines = ["".join(chars) for chars in map_lines]
        final_map = "\n".join(final_map_lines)

        # -------------------------------------------------------------
        # 7) (Optional) Add your legend and other info
        # -------------------------------------------------------------
        legend = [
            " +------------------------------------------------------+",
            " |                    MAP LEGEND                         |",
            " +------------------------------------------------------+",
            " |  * indicates a supply center.                         |",
            " |  A-FRA means an Army from France, etc.                |",
            " |  *A-GER means a dislodged Army from Germany.          |",
            " +------------------------------------------------------+",
            f" | PHASE: {self.season.value} {self.year} {self.phase.value}",
            f" | TURN: {self.turn_number}/{self.max_turns}",
            " +------------------------------------------------------+",
            " | POWER       SUPPLY CENTERS       UNITS               |",
        ]

        # Example: show each power's centers/units
        for power_name, power in self.powers.items():
            centers_count = len(power.controlled_centers)
            units_count   = len(power.units)
            legend.append(f" | {power_name:<12} {centers_count:^18} {units_count:^18} |")

        legend.append(" +------------------------------------------------------+")

        # -------------------------------------------------------------

        # 8) Return the combined map + legend
        # -------------------------------------------------------------
        return final_map + "\n\n" + "\n".join(legend) + "\n"
    
    def get_ascii_map_v3(self) -> str:
        """Generate a tile-based ASCII art representation of the current game state with improved spacing"""
        # Define power abbreviations
        power_abbr = {
            'AUSTRIA': 'AUS',
            'ENGLAND': 'ENG',
            'FRANCE': 'FRA',
            'GERMANY': 'GER',
            'ITALY': 'ITA',
            'RUSSIA': 'RUS',
            'TURKEY': 'TUR',
            None: '   '
        }
        
        # Create territory ownership mapping
        territory_owners = {}
        for power_name, power in self.powers.items():
            for center in power.controlled_centers:
                territory_owners[center] = power_name
        
        # Create unit location mapping
        units_by_location = {}
        for power_name, power in self.powers.items():
            for unit in power.units:
                if unit.region:
                    units_by_location[unit.region.name] = {
                        'type': unit.type.value,
                        'power': power_name,
                        'dislodged': unit.dislodged
                    }
        
        # Create a tile for each territory
        def create_territory_box(name):
            """Create a text box representing a territory"""
            if not name or name not in self.map.regions:
                return ["          ", "          ", "          ", "          ", "          ", "          ", "          "]
                
            region = self.map.regions[name]
            is_sc = region.is_supply_center
            owner = territory_owners.get(name, None)
            owner_abbr = power_abbr.get(owner, '   ')
            
            # Unit information
            unit_info = units_by_location.get(name, None)
            if unit_info:
                unit_display = f"{unit_info['type']}-{power_abbr[unit_info['power']]}"
                if unit_info['dislodged']:
                    unit_display = f"*{unit_display}"
                else:
                    unit_display = f" {unit_display}"
            else:
                unit_display = "     "
            
            # Create box
            line1 = f"+--------+"
            line2 = f"|  {name:^4}  |"
            line3 = f"|        |"
            line4 = f"|{('SC' if is_sc else '  '):^8}|"
            line5 = f"|{unit_display:^8}|"
            line6 = f"|{owner_abbr:^8}|"
            line7 = f"+--------+"
            
            return [line1, line2, line3, line4, line5, line6, line7]
        
        # Define regions by geographic area for layout
        map_layout = [
            # North
            [None, "BAR", "STP", None, None, "FIN", None],
            ["NAO", "NWG", "NTH", "SKA", "BOT", "SWE", None],
            ["IRI", "CLY", "EDI", "DEN", "BAL", "LVN", "MOS"],
            [None, "LVP", "YOR", "HEL", "BER", "PRU", "WAR"],
            
            # Central Europe
            ["MAO", "WAL", "LON", "HOL", "KIE", "SIL", "GAL", "UKR"],
            ["BRE", "ENG", "BEL", "RUH", "MUN", "BOH", "VIE", "RUM"],
            ["GAS", "PAR", "BUR", "TYR", "TRI", "BUD", "SER", "SEV"],
            ["SPA", "MAR", "PIE", "VEN", "ADR", "ALB", "BUL", "BLA"],
            
            # Mediterranean
            ["POR", "WES", "LYO", "TUS", "ROM", "ION", "GRE", "AEG"],
            ["NAF", "TYS", "APU", "NAP", "EAS", "CON", "ANK", "ARM"],
            ["TUN", None, None, None, "SYR", "SMY", None, None],
        ]
        
        # Generate the map tiles
        tile_grid = []
        for row in map_layout:
            row_tiles = []
            for region in row:
                row_tiles.append(create_territory_box(region))
            tile_grid.append(row_tiles)
        
        # Combine tiles into a map
        map_lines = []
        for row_idx, row in enumerate(tile_grid):
            # Each tile has 7 lines
            for line_idx in range(7):
                line = ""
                for tile in row:
                    if line_idx < len(tile):
                        line += tile[line_idx] + "  "
                    else:
                        line += "            "
                map_lines.append(line)
            # Add space between rows
            map_lines.append("")
        
        # Create legend with improved formatting
        legend = [
            "+-------------------------------------------------------+",
            "|                     TERRITORY FORMAT                  |",
            "+-------------------------------------------------------+",
            "| +--------+                                           |",
            "| |  NAME  |  <- Territory name (3-letter code)        |",
            "| |        |                                           |",
            "| |   SC   |  <- Supply center (if present)            |",
            "| |  X-YYY |  <- Unit type and power (X=A/F, YYY=power)|",
            "| |  ZZZ   |  <- Controlling power (ZZZ=power)         |",
            "| +--------+                                           |",
            "|                                                       |",
            "| Unit Format:   A-ENG = Army England                  |",
            "|                F-RUS = Fleet Russia                  |",
            "|                *F-TUR = Dislodged Fleet Turkey       |",
            "+-------------------------------------------------------+",
            "|           CURRENT GAME STATE                          |",
            "+-------------------------------------------------------+",
            f"| PHASE: {self.season.value} {self.year} {self.phase.value}",
            f"| TURN: {self.turn_number}/{self.max_turns}",
            "+-------------------------------------------------------+",
            "| POWER       SUPPLY CENTERS       UNITS                |",
        ]
        
        # Add power statistics with better spacing
        for power_name, power in self.powers.items():
            centers = len(power.controlled_centers)
            units = len(power.units)
            legend.append(f"| {power_name:<12} {centers:^18} {units:^18} |")
        
        legend.append("+-------------------------------------------------------+")
        
        # Add key connection information
        connections = [
            "KEY STRATEGIC REGIONS AND CONNECTIONS:",
            "",
            "STRAITS:",
            "• Denmark (DEN) - Connects North Sea (NTH) to Baltic Sea (BAL)",
            "• Constantinople (CON) - Connects Black Sea (BLA) to Aegean Sea (AEG)",
            "• Bulgaria (BUL) - Has separate coasts on Black Sea and Aegean Sea",
            "",
            "STRATEGIC WATERWAYS:",
            "• English Channel (ENG) - Key waterway between Britain and mainland Europe",
            "• Mid-Atlantic Ocean (MAO) - Critical passage to Western Mediterranean",
            "• Tyrrhenian Sea (TYS) - Controls access to Italian supply centers",
            "• Ionian Sea (ION) - Strategic Mediterranean crossroads",
            "",
            "CRITICAL LAND ROUTES:",
            "• Burgundy (BUR) - Controls movement through Western Europe",
            "• Tyrolia (TYR) - Mountain pass connecting Germany, Austria and Italy",
            "• Galicia (GAL) - Key buffer zone between Russia, Austria and Germany",
            "• Ukraine (UKR) - Controls Eastern European approaches",
            "",
            "DEFENSIBLE POSITIONS:",
            "• Munich (MUN) - Protects Southern Germany",
            "• Vienna (VIE) - Central to Austrian defense",
            "• Moscow (MOS) - Russian heartland",
            "• Constantinople (CON) - Turkish stronghold between Europe and Asia"
        ]
        
        # Combine everything
        return "\n".join(map_lines) + "\n\n" + "\n".join(legend) + "\n\n" + "\n".join(connections)            

    def get_ascii_map_v4(self) -> str:
        """Generate a tile-based ASCII map with territory connections"""
        # Define power abbreviations
        power_abbr = {
            'AUSTRIA': 'AUS',
            'ENGLAND': 'ENG',
            'FRANCE': 'FRA',
            'GERMANY': 'GER',
            'ITALY': 'ITA',
            'RUSSIA': 'RUS',
            'TURKEY': 'TUR',
            None: '   '
        }
        
        # Create territory ownership mapping
        territory_owners = {}
        for power_name, power in self.powers.items():
            for center in power.controlled_centers:
                territory_owners[center] = power_name
        
        # Create unit location mapping
        units_by_location = {}
        for power_name, power in self.powers.items():
            for unit in power.units:
                if unit.region:
                    units_by_location[unit.region.name] = {
                        'type': unit.type.value,
                        'power': power_name,
                        'dislodged': unit.dislodged
                    }
        
        # Create a tile for each territory
        def create_territory_box(name):
            """Create a text box representing a territory"""
            if not name or name not in self.map.regions:
                return ["     ", "     ", "     ", "     "]
                
            region = self.map.regions[name]
            is_sc = region.is_supply_center
            owner = territory_owners.get(name, None)
            owner_abbr = power_abbr.get(owner, '   ')
            
            # Unit information
            unit_info = units_by_location.get(name, None)
            if unit_info:
                unit_display = f"{unit_info['type']}-{power_abbr[unit_info['power']][:1]}"
                if unit_info['dislodged']:
                    unit_display = f"*{unit_display}"
                else:
                    unit_display = f" {unit_display}"
            else:
                unit_display = "    "
            
            # Create box
            line1 = f"+-----+"
            line2 = f"|{name:^5}|" 
            line3 = f"|{('SC' if is_sc else '  '):^5}|"
            line4 = f"|{unit_display:^5}|"
            line5 = f"|{owner_abbr:^5}|"
            line6 = f"+-----+"
            
            return [line1, line2, line3, line4, line5, line6]
        
        # Define regions by geographic area for layout
        map_layout = [
            # North
            [None, "BAR", "STP", None, None],
            ["NAO", "NWG", "NTH", "SKA", "BOT"],
            ["IRI", "CLY", "EDI", "DEN", "BAL"],
            [None, "LVP", "YOR", "HEL", "BER"],
            
            # Central Europe
            ["MAO", "WAL", "LON", "HOL", "KIE"],
            ["BRE", "ENG", "BEL", "RUH", "MUN"],
            ["GAS", "PAR", "BUR", "BOH", "VIE"],
            ["SPA", "MAR", "PIE", "TYR", "TRI"],
            
            # Eastern Europe
            [None, "FIN", "SWE", "LVN", "MOS"],
            [None, None, "PRU", "WAR", "UKR"],
            [None, None, "SIL", "GAL", "RUM"],
            [None, None, "SER", "BUD", "SEV"],
            
            # Mediterranean
            ["POR", "WES", "LYO", "VEN", "ADR"],
            ["NAF", "TYS", "TUS", "ROM", "ALB"],
            ["TUN", "ION", "NAP", "GRE", "AEG"],
            [None, "EAS", None, "BUL", "BLA"],
            
            # Near East
            [None, None, "SYR", "CON", "ANK"],
            [None, None, None, None, "SMY"]
        ]
        
        # Generate the map tiles
        tile_grid = []
        for row in map_layout:
            row_tiles = []
            for region in row:
                row_tiles.append(create_territory_box(region))
            tile_grid.append(row_tiles)
        
        # Combine tiles into a map
        map_lines = []
        for row_idx, row in enumerate(tile_grid):
            # Each tile has 6 lines
            for line_idx in range(6):
                line = ""
                for tile in row:
                    if line_idx < len(tile):
                        line += tile[line_idx]
                    else:
                        line += "      "
                map_lines.append(line)
        
        # Add connections between key territories
        # (This could be expanded with actual connections from the adjacency data)
        connections = [
            "KEY CONNECTIONS:",
            "Water regions connect to adjacent coastal territories",
            "Land regions connect to adjacent territories",
            "",
            "IMPORTANT STRAITS:",
            "- Denmark (DEN): Connects NTH to BAL",
            "- Constantinople (CON): Connects BLA to AEG",
            "- Bulgaria (BUL): Has separate coasts on BLA and AEG",
            "- Spain (SPA): Has separate coasts on MAO and WES",
            "- St. Petersburg (STP): Has separate coasts on BAR and BOT"
        ]
        
        # Create legend
        legend = [
            "+---------------------------------------+",
            "| TERRITORY FORMAT                      |",
            "| +-----+                              |",
            "| |NAME |  <- Territory name           |",
            "| | SC  |  <- Supply center (if shown) |",
            "| | A-P |  <- Unit type and power      |",
            "| |OWNER|  <- Controlling power        |",
            "| +-----+                              |",
            "|                                      |",
            "| Unit Format: A-P = Army/Fleet-Power  |",
            "| * = Dislodged unit                   |",
            "+---------------------------------------+",
            "| POWER       SUPPLY CENTERS    UNITS   |"
        ]
        
        # Add power statistics
        for power_name, power in self.powers.items():
            centers = len(power.controlled_centers)
            units = len(power.units)
            legend.append(f"| {power_name:<10} {centers:^15} {units:^7} |")
        
        legend.append("+---------------------------------------+")
        
        # Add game status
        status = [
            f"GAME STATUS: {self.season.value} {self.year} {self.phase.value}",
            f"TURN: {self.turn_number}/{self.max_turns}"
        ]
        
        # Combine everything
        return "\n".join(map_lines) + "\n\n" + "\n".join(legend) + "\n\n" + "\n".join(connections) + "\n\n" + "\n".join(status)

    def get_ascii_map_v5(self) -> str:
        """Render the current game state as an ASCII map"""
        values = {}
        
        def initialize_empty_values():
            # Get all placeholder patterns from map_fstring
            import re
            placeholders = re.findall(r'{([^}]+)}', DIPLOMACY_MAP_TEMPLATE)
            for p in placeholders:
                values[p] = "         "  # 9 spaces

        def pad_center(text: str, width: int = 9) -> str:
            text = text[:width]  # Truncate if too long
            padding = width - len(text)
            left_pad = padding // 2
            right_pad = padding - left_pad
            return " " * left_pad + text + " " * right_pad

        def format_region(region_code: str, region: Region) -> None:
            """Format a single region's display values"""
            # Row 1: Region abbreviation (centered)
            values[f"{region_code}_nam"] = pad_center(region_code.upper())
            
            # Row 2: Supply center info
            sc_info = ""
            if region.is_supply_center:
                if region.owner:
                    sc_info = f"SC {region.owner[:3]}"
                else:
                    sc_info = "SC"
            values[f"{region_code}_sc_"] = pad_center(sc_info)
            
            # Row 3: Unit info
            unit_info = ""
            if region.unit:
                prefix = "*" if region.unit.dislodged else ""
                unit_info = f"{prefix}{region.unit.type.value} {region.unit.power[:3]}"
            values[f"{region_code}_uni"] = pad_center(unit_info)

        # Initialize empty values
        initialize_empty_values()
        
        # Process regions
        for region_code, region in self.map.regions.items():
            region_code = region_code.lower()
            format_region(region_code, region)
        
        # Add power summary values with consistent padding
        power_codes = ['fra', 'eng', 'ger', 'aus', 'rus', 'tur']
        for power_code in power_codes:
            # Default to padded spaces
            values[f"{power_code}_scs"] = " " * 9  # 9 spaces for supply centers
            values[f"{power_code}_uns"] = " " * 9  # 9 spaces for units
            
            # If power exists, update with actual values
            power_name = {'fra': 'FRANCE', 'eng': 'ENGLAND', 'ger': 'GERMANY',
                        'aus': 'AUSTRIA', 'rus': 'RUSSIA', 'tur': 'TURKEY'}[power_code].upper()
            
            for power in self.powers.values():
                if power.name == power_name:
                    sc_count = len(power.controlled_centers)
                    unit_count = len(power.units)
                    values[f"{power_code}_scs"] = str(sc_count).center(9)
                    values[f"{power_code}_uns"] = str(unit_count).center(9)
                    break
        
        # Apply the values to the template
        return DIPLOMACY_MAP_TEMPLATE.format(**values)


    def get_ascii_map_v5(self) -> str:
        """Render the current game state as an ASCII map"""
        values = {}
        
        def initialize_empty_values():
            # Get all placeholder patterns from map_fstring
            import re
            placeholders = re.findall(r'{([^}]+)}', DIPLOMACY_MAP_TEMPLATE)
            for p in placeholders:
                values[p] = "         "  # 9 spaces

        def pad_center(text: str, width: int = 9) -> str:
            text = text[:width]  # Truncate if too long
            padding = width - len(text)
            left_pad = padding // 2
            right_pad = padding - left_pad
            return " " * left_pad + text + " " * right_pad

        def format_region(region_code: str, region: Region) -> None:
            """Format a single region's display values"""
            # Row 1: Region abbreviation (centered)
            values[f"{region_code}_nam"] = pad_center(region_code.upper())
            
            # Row 2: Supply center info
            sc_info = ""
            if region.is_supply_center:
                if region.owner:
                    sc_info = f"SC {region.owner[:3]}"
                else:
                    sc_info = "SC"
            values[f"{region_code}_sc_"] = pad_center(sc_info)
            
            # Row 3: Unit info
            unit_info = ""
            if region.unit:
                prefix = "*" if region.unit.dislodged else ""
                unit_info = f"{prefix}{region.unit.type.value} {region.unit.power[:3]}"
            values[f"{region_code}_uni"] = pad_center(unit_info)

        # Initialize empty values
        initialize_empty_values()
        
        # Process regions
        for region_code, region in self.map.regions.items():
            region_code = region_code.lower()
            format_region(region_code, region)
        
        # Add power summary values with consistent padding
        power_codes = ['fra', 'eng', 'ger', 'aus', 'rus', 'tur']
        for power_code in power_codes:
            # Default to padded spaces
            values[f"{power_code}_scs"] = " " * 9  # 9 spaces for supply centers
            values[f"{power_code}_uns"] = " " * 9  # 9 spaces for units
            
            # If power exists, update with actual values
            power_name = {'fra': 'FRANCE', 'eng': 'ENGLAND', 'ger': 'GERMANY',
                        'aus': 'AUSTRIA', 'rus': 'RUSSIA', 'tur': 'TURKEY'}[power_code].upper()
            
            for power in self.powers.values():
                if power.name == power_name:
                    sc_count = len(power.controlled_centers)
                    unit_count = len(power.units)
                    values[f"{power_code}_scs"] = str(sc_count).center(9)
                    values[f"{power_code}_uns"] = str(unit_count).center(9)
                    break
        
        # Apply the values to the template
        return DIPLOMACY_MAP_TEMPLATE.format(**values)

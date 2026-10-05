# good explanation of the game: https://www.youtube.com/watch?v=l53oL0ptt7k
import copy
import random
import re
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple
from collections import defaultdict


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
        "SC": {"LYO", "MAO", "MAR", "POR", "WES"},
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
            ('NAF', TerrainType.COAST, False, None),
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
            ('STP', 'LVN', ['A', 'F']),
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
            ('BUL', 'CON', ['A', 'F']),
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
        self.order_history: List[Dict[str, Any]] = [] # Track order history
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
                                    and not self._can_unit_move_to(supported_unit, destination)
                                    and self._has_possible_convoy_path(
                                        supported_location, destination
                                    )
                                )
                            )
                        for destination, coast in supported_destinations:
                            if self._can_unit_move_to(
                                unit,
                                destination,
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

    def get_convoy_destinations(self, location: str) -> List[str]:
        """Coastal provinces an army at `location` could currently reach by convoy."""
        return sorted(
            name
            for name, region in self.map.regions.items()
            if (
                name != location
                and region.terrain_type == TerrainType.COAST
                and self._has_possible_convoy_path(location, name)
            )
        )

    @staticmethod
    def _army_coast_error(order: Order) -> str:
        """Rejection for an order that names a coast for an army, with the order rewritten without it."""
        corrected = copy.copy(order)
        if order.unit_type == UnitType.ARMY:
            corrected.location_coast = None
            if order.order_type in {OrderType.MOVE, OrderType.RETREAT}:
                corrected.target_coast = None
        if order.order_type in {OrderType.SUPPORT, OrderType.CONVOY} and order.target.startswith("A "):
            corrected.target_coast = corrected.secondary_target_coast = None
        return f"Armies don't use coasts: write '{corrected}'"

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
            if unit.type == UnitType.ARMY and order.location_coast:
                return False, self._army_coast_error(order)
            if order.location_coast and order.location_coast != unit.coast:
                corrected = copy.copy(order)
                corrected.location_coast = unit.coast
                return False, (
                    f"The fleet at {order.location} is on the {unit.coast} coast, not "
                    f"{order.location_coast}: write '{corrected}'"
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

            if unit.type == UnitType.ARMY and order.target_coast:
                return False, self._army_coast_error(order)
            if order.via_convoy:
                if unit.type != UnitType.ARMY:
                    return False, "Only armies can move VIA convoy"
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
            if supported_type == UnitType.ARMY and (order.target_coast or order.secondary_target_coast):
                return False, self._army_coast_error(order)

            if order.secondary_target:
                destination = self.map.get_region(order.secondary_target)
                if not destination:
                    return False, f"Destination region {order.secondary_target} does not exist"

                # Support move - check if the destination is reachable by the
                # supported unit. Support is given to a province, so the coast
                # may be omitted; a coast that is named must be reachable.
                if not self._can_unit_move_to(
                    supported_unit,
                    order.secondary_target,
                    order.secondary_target_coast,
                    require_explicit_coast=False,
                ):
                    # Check if it could be a convoyed move
                    if not (
                        supported_unit.type == UnitType.ARMY
                        and order.secondary_target_coast is None
                        and self._has_possible_convoy_path(supported_loc, order.secondary_target)
                    ):
                        return False, f"Unit at {supported_loc} cannot move to {order.secondary_target}"

                # A supporter must be able to move to the supported province,
                # whichever coast the supported unit is moving to.
                if not self._can_unit_move_to(
                    unit,
                    order.secondary_target,
                    require_explicit_coast=False,
                ):
                    return False, f"Cannot support move to {order.secondary_target} (not adjacent to supporting unit)"
            elif not self._can_unit_move_to(
                unit,
                supported_loc,
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
                return False, self._army_coast_error(order)

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

            if unit.type == UnitType.ARMY and order.target_coast:
                return False, self._army_coast_error(order)

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
        if not start_region or start == end:
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
        if not start_region or start == end:
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

    def parse_orders(
        self, power_name: str, order_strings: List[str]
    ) -> Tuple[List[Order], List[Dict[str, Any]]]:
        """Parse and validate an order set without mutating engine state."""
        if power_name not in self.powers:
            return [], [{"reason": "Power not found", "orders": list(order_strings)}]

        parsed_orders: List[Order] = []
        invalid_orders: List[Dict[str, Any]] = []
        ordered_locations: Set[str] = set()
        build_count = self.powers[power_name].count_needed_builds()
        adjustments_used = 0
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
                if self.phase == PhaseType.ADJUSTMENTS and order.order_type in {
                    OrderType.BUILD, OrderType.WAIVE, OrderType.DISBAND,
                }:
                    if adjustments_used >= abs(build_count):
                        verb = "build (or waive)" if build_count > 0 else "disband"
                        invalid_orders.append({
                            "reason": (
                                f"{power_name} may {verb} only {abs(build_count)} "
                                "unit(s) this adjustment phase"
                            ),
                            "orders": [order_str],
                        })
                        continue
                    adjustments_used += 1
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
        
        # Save order history. `results` maps each power to [order, outcome]
        # pairs, including units that received no order.
        order_record = {
            "turn": self.turn_number,
            "year": self.year,
            "season": self.season.value,
            "phase": self.phase.value,
            "valid_orders": {power: [str(order) for order in orders] for power, orders in valid_orders.items()},
            "invalid_orders": invalid_orders,
            "results": {},
            "dislodged": [],
            "center_changes": [],
        }
        self.order_history.append(order_record)

        if self.phase == PhaseType.MOVEMENT:
            order_record["results"] = self._resolve_movement(valid_orders)
            order_record["dislodged"] = self._dislodged_units_summary()
        elif self.phase == PhaseType.RETREATS:
            order_record["results"] = self._resolve_retreats(valid_orders)
            # Ownership changes at the end of the Fall turn, after retreats.
            order_record["center_changes"] = self._update_supply_centers()
        elif self.phase == PhaseType.ADJUSTMENTS:
            order_record["results"] = self._resolve_adjustments(valid_orders)

        # Advance phase 
        self._advance_phase()

        # Check for game end conditinos
        self._check_victory()

        return True, self.get_state()

    def _resolve_movement(
        self, valid_orders: Dict[str, List[Order]]
    ) -> Dict[str, List[List[str]]]:
        """Resolve the movement orders and return each power's order outcomes."""
        move_orders: Dict[Unit, str] = {}
        move_target_coasts: Dict[Unit, Optional[str]] = {}
        via_convoy_units: Set[Unit] = set()
        support_orders: Dict[
            Unit, Tuple[Unit, Optional[str], Optional[str]]
        ] = {}
        convoys: Dict[Tuple[str, str], List[Unit]] = defaultdict(list)
        ordered_units: List[Tuple[str, Order, Unit]] = []

        # Identify all moves, supports, and convoy orders.
        for power_name, orders in valid_orders.items():
            for order in orders:
                unit: Optional[Unit] = self._find_unit(power_name, order.unit_type, order.location)
                if not unit or unit.dislodged:
                    continue
                ordered_units.append((power_name, order, unit))

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

        def moves_by_convoy(unit: Unit) -> bool:
            return unit in via_convoy_units or not self._can_unit_move_to(
                unit, move_orders[unit], move_target_coasts.get(unit)
            )

        convoy_routes = sorted({
            (unit.region.name, destination)
            for unit, destination in move_orders.items()
            if moves_by_convoy(unit)
            and self._convoy_fleets_connect(
                unit.region.name, destination, convoys.get((unit.region.name, destination), [])
            )
        })
        adjudications: Dict[FrozenSet[Tuple[str, str]], Tuple[Any, ...]] = {}

        def adjudicate(active_convoys: FrozenSet[Tuple[str, str]]) -> Tuple[Any, ...]:
            """Adjudicate with the given convoys assumed to work."""
            if active_convoys not in adjudications:
                adjudications[active_convoys] = self._adjudicate_with_convoys(
                    active_convoys, move_orders, move_target_coasts, via_convoy_units,
                    support_orders, valid_orders, moves_by_convoy,
                )
            return adjudications[active_convoys]

        def intact_routes(active_convoys: FrozenSet[Tuple[str, str]]) -> FrozenSet[Tuple[str, str]]:
            dislodged = adjudicate(active_convoys)[3]
            return frozenset(
                route for route in convoy_routes
                if self._convoy_fleets_connect(
                    route[0], route[1], [fleet for fleet in convoys[route] if fleet not in dislodged]
                )
            )

        active_convoys, paradox_routes = self._settle_convoys(convoy_routes, intact_routes)
        (
            support_status,
            disrupted_convoys,
            successful_moves,
            dislodged_units,
            standoff_regions,
        ) = adjudicate(active_convoys)
        convoyed_origins = {
            unit.region.name for unit in successful_moves if moves_by_convoy(unit)
        }
        dislodged_by_convoy = {
            unit for unit, origin in dislodged_units.items() if origin in convoyed_origins
        }

        results = self._movement_outcomes(
            ordered_units,
            move_orders,
            successful_moves,
            dislodged_units,
            support_status,
            disrupted_convoys,
            active_convoys,
            paradox_routes,
        )
        self._standoff_regions = standoff_regions
        self._apply_movements(
            successful_moves,
            dislodged_units,
            move_target_coasts,
        )

        # Ownership is not updated here: centers change hands after the Fall
        # retreats (see resolve_orders).
        self._prepare_retreats(dislodged_by_convoy)
        return results

    @staticmethod
    def _settle_convoys(
        routes: List[Tuple[str, str]],
        intact_routes: Callable[[FrozenSet[Tuple[str, str]]], FrozenSet[Tuple[str, str]]],
    ) -> Tuple[FrozenSet[Tuple[str, str]], Set[Tuple[str, str]]]:
        """Decide which convoys work, failing paradoxical ones (the Szykman rule).

        `intact_routes(assumed)` gives the convoys whose fleets survive when the
        `assumed` convoys work. Convoys whose outcomes depend on one another are
        settled together: a group with exactly one self-consistent outcome takes
        it, and a group with none or several is a paradox whose convoys all fail.
        Returns the working convoys and the convoys that failed by paradox.
        """
        if len(routes) > 8:
            # Too many convoys to enumerate: drop convoys that do not survive
            # until the rest are consistent.
            active = frozenset(routes)
            while intact_routes(active) & active != active:
                active = intact_routes(active) & active
            return active, set()

        assignments = [
            frozenset(route for index, route in enumerate(routes) if mask >> index & 1)
            for mask in range(2 ** len(routes))
        ]
        outcome = {assumed: intact_routes(assumed) for assumed in assignments}
        reaches: Dict[Tuple[str, str], Set[Tuple[str, str]]] = {route: set() for route in routes}
        for assumed in assignments:
            for flipped_route in routes:
                flipped = outcome[assumed ^ {flipped_route}]
                for route in routes:
                    if (route in outcome[assumed]) != (route in flipped):
                        reaches[route].add(flipped_route)
        changed = True
        while changed:
            changed = False
            for route in routes:
                expanded = reaches[route].union(*(reaches[other] for other in reaches[route]))
                if expanded != reaches[route]:
                    reaches[route], changed = expanded, True

        decided: Dict[Tuple[str, str], bool] = {}
        paradox_routes: Set[Tuple[str, str]] = set()
        while len(decided) < len(routes):
            undecided = [route for route in routes if route not in decided]
            route = next(
                candidate for candidate in undecided
                if all(
                    other in decided or candidate in reaches[other]
                    for other in reaches[candidate]
                )
            )
            group = sorted({route} | {other for other in reaches[route] if route in reaches[other]})
            settled = frozenset(other for other, works in decided.items() if works)
            solutions = []
            for mask in range(2 ** len(group)):
                chosen = frozenset(other for index, other in enumerate(group) if mask >> index & 1)
                if outcome[settled | chosen] & set(group) == chosen:
                    solutions.append(chosen)
            working = solutions[0] if len(solutions) == 1 else frozenset()
            if len(solutions) != 1:
                paradox_routes.update(group)
            for other in group:
                decided[other] = other in working
        return frozenset(route for route, works in decided.items() if works), paradox_routes

    def _adjudicate_with_convoys(
        self,
        active_convoys: FrozenSet[Tuple[str, str]],
        move_orders: Dict[Unit, str],
        move_target_coasts: Dict[Unit, Optional[str]],
        via_convoy_units: Set[Unit],
        support_orders: Dict[Unit, Tuple[Unit, Optional[str], Optional[str]]],
        valid_orders: Dict[str, List[Order]],
        moves_by_convoy: Callable[[Unit], bool],
    ) -> Tuple[Dict[Unit, str], Set[Tuple[str, str]], Dict[Unit, str], Dict[Unit, str], Set[str]]:
        """Adjudicate a turn in which exactly `active_convoys` work.

        Supporters that end up dislodged lose their support, so re-adjudicate
        until no further supporter is dislodged.
        """
        disabled_supporters: Set[Unit] = set()
        for _ in range(len(support_orders) + 1):
            supports: Dict[Unit, List[Unit]] = defaultdict(list)
            support_status: Dict[Unit, str] = {}
            for supporting_unit, (
                supported_unit,
                destination,
                destination_coast,
            ) in support_orders.items():
                if supporting_unit in disabled_supporters:
                    support_status[supporting_unit] = "cut"
                    continue
                supported_move = move_orders.get(supported_unit)
                support_matches = (
                    (destination is None and supported_move is None)
                    or (
                        destination is not None
                        and supported_move == destination
                        and destination_coast in {
                            None, move_target_coasts.get(supported_unit),
                        }
                    )
                )
                support_target = destination or supported_unit.region.name
                if not support_matches:
                    support_status[supporting_unit] = "void"
                elif self._is_valid_support(
                    supporting_unit,
                    supported_unit,
                    support_target,
                    valid_orders,
                    active_convoys,
                ):
                    supports[supported_unit].append(supporting_unit)
                    support_status[supporting_unit] = "given"
                else:
                    support_status[supporting_unit] = "cut"

            disrupted_convoys = {
                (unit.region.name, destination)
                for unit, destination in move_orders.items()
                if moves_by_convoy(unit) and (unit.region.name, destination) not in active_convoys
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
            if not newly_disabled_supporters:
                break
            disabled_supporters.update(newly_disabled_supporters)
        return support_status, disrupted_convoys, successful_moves, dislodged_units, standoff_regions

    def _movement_outcomes(
        self,
        ordered_units: List[Tuple[str, Order, Unit]],
        move_orders: Dict[Unit, str],
        successful_moves: Dict[Unit, str],
        dislodged_units: Dict[Unit, str],
        support_status: Dict[Unit, str],
        disrupted_convoys: Set[Tuple[str, str]],
        active_convoys: Set[Tuple[str, str]],
        paradox_routes: Set[Tuple[str, str]],
    ) -> Dict[str, List[List[str]]]:
        """Describe every unit's movement outcome; call before units move."""
        results: Dict[str, List[List[str]]] = {name: [] for name in self.powers}
        ordered: Set[Unit] = set()
        for power_name, order, unit in ordered_units:
            ordered.add(unit)
            if order.order_type == OrderType.MOVE:
                if unit in successful_moves:
                    outcome = "moved"
                elif (unit.region.name, order.target) in paradox_routes:
                    outcome = "failed (convoy paradox)"
                elif (unit.region.name, order.target) in disrupted_convoys:
                    outcome = "failed (no convoy)"
                else:
                    outcome = "bounced"
            elif order.order_type == OrderType.SUPPORT:
                outcome = {
                    "given": "support given",
                    "cut": "support cut",
                }.get(support_status.get(unit), "support void (no matching order)")
            elif order.order_type == OrderType.CONVOY:
                army_location = order.target.split()[1]
                army = self._find_unit(None, UnitType.ARMY, army_location)
                if army is None or move_orders.get(army) != order.secondary_target:
                    outcome = "convoy void (no matching move)"
                elif army in successful_moves:
                    outcome = "convoyed"
                elif (army_location, order.secondary_target) in paradox_routes:
                    outcome = "convoy failed (paradox)"
                elif (army_location, order.secondary_target) not in active_convoys:
                    outcome = "convoy disrupted"
                else:
                    outcome = "convoy held, but the army bounced"
            else:
                outcome = "held"
            if unit in dislodged_units:
                outcome = "dislodged" if outcome == "held" else f"{outcome}, dislodged"
            results[power_name].append([str(order), outcome])

        for power_name, power in self.powers.items():
            for unit in power.units:
                if unit in ordered or unit.dislodged or not unit.region:
                    continue
                outcome = "dislodged" if unit in dislodged_units else "held"
                results[power_name].append([f"{unit} (no order)", outcome])
        return results

    def _dislodged_units_summary(self) -> List[Dict[str, Any]]:
        """Describe every dislodged unit awaiting the retreat phase."""
        return [
            {
                "power": power_name,
                "unit": str(unit).lstrip("*"),
                "attacked_from": unit.dislodged_from,
                "retreat_options": list(unit.retreat_options),
            }
            for power_name, power in self.powers.items()
            for unit in power.units
            if unit.dislodged
        ]

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

        status: Dict[Unit, bool] = {}
        resolving: Set[Unit] = set()

        def dislodging_strength(attacker: Unit, defender: Unit) -> int:
            # Support supplied by the defender's own power cannot dislodge it,
            # though it still counts when determining standoffs.
            return 1 + sum(
                supporter.power != defender.power
                for supporter in supports.get(attacker, [])
            )

        def head_to_head_opponent(unit: Unit) -> Optional[Unit]:
            defender = original_occupants[move_orders[unit]]
            if (
                defender is not None
                and move_orders.get(defender) == original_regions[unit].name
                and direct_moves.get(unit, False)
                and direct_moves.get(defender, False)
            ):
                return defender
            return None

        def prevent_strength(unit: Unit) -> int:
            # A unit beaten in a head-to-head battle has no effect on the
            # province its opponent came from.
            opponent = head_to_head_opponent(unit)
            if opponent is not None and succeeds(opponent):
                return 0
            return attack_strength[unit]

        def succeeds(unit: Unit) -> bool:
            if unit in status:
                return status[unit]
            if unit in resolving:
                # A cycle of three or more moves vacates all its provinces.
                return True
            resolving.add(unit)
            status[unit] = move_succeeds(unit)
            resolving.discard(unit)
            return status[unit]

        def move_succeeds(unit: Unit) -> bool:
            if unit in blocked_moves:
                return False
            destination = move_orders[unit]
            rivals = [other for other in attackers_by_target[destination] if other is not unit]
            if any(attack_strength[unit] <= prevent_strength(other) for other in rivals):
                return False

            defender = original_occupants[destination]
            if defender is None:
                return True
            opponent = head_to_head_opponent(unit)
            if opponent is None and defender in move_orders and succeeds(defender):
                return True

            # The province remains occupied. A power may not dislodge its own unit,
            # and support from the occupant's power counts neither against the
            # occupant nor against rival attackers.
            if unit.power == defender.power:
                return False
            attack = dislodging_strength(unit, defender)
            if opponent is not None:
                resistance = attack_strength[opponent]
            elif defender in move_orders:
                resistance = 1
            else:
                resistance = 1 + len(supports.get(defender, []))
            return attack > resistance and all(
                attack > prevent_strength(other) for other in rivals
            )

        successful_moves = {
            unit: destination
            for unit, destination in move_orders.items()
            if succeeds(unit)
        }
        # Provinces a non-beaten unit failed to enter cannot be retreated to.
        standoff_regions = {
            move_orders[unit]
            for unit in attack_strength
            if not succeeds(unit) and prevent_strength(unit) > 0
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

    def _update_supply_centers(self) -> List[List[Optional[str]]]:
        """Give each occupied center to its occupier at the end of the Fall turn.

        Returns the ownership changes as [center, old owner, new owner].
        """
        changes: List[List[Optional[str]]] = []
        if self.season != Season.FALL:
            return changes

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
                    changes.append([region_name, old_owner, new_owner])
        return changes

    def _prepare_retreats(self, dislodged_by_convoy: Set[Unit]):
        """Determine valid retreat locations for all dislodged units.

        A unit may retreat to the province a convoyed attacker came from.
        """
        # For each dislodged unit, find valid retreat locations
        for power in self.powers.values():
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
                            (adjacent != unit.dislodged_from or unit in dislodged_by_convoy) and
                            adjacent not in self._standoff_regions):
                            retreat_options.append(
                                _format_location(adjacent, coast)
                            )

                    unit.retreat_options = sorted(retreat_options)

    def _resolve_retreats(
        self, valid_orders: Dict[str, List[Order]]
    ) -> Dict[str, List[List[str]]]:
        """Resolve retreat orders and return each power's order outcomes."""
        retreat_targets: Dict[
            str, List[Tuple[Unit, Optional[str]]]
        ] = {}  # {province: [(retreating unit, coast)]}
        disband_units: Set[Unit] = {
            unit
            for power in self.powers.values()
            for unit in power.units
            if unit.dislodged
        }
        dislodged_labels = {
            unit: str(unit).lstrip("*") for unit in disband_units
        }
        unit_orders: Dict[Unit, Order] = {}

        # Collect all retreat orders
        for power_name, orders in valid_orders.items():
            for order in orders:
                unit: Optional[Unit] = self._find_unit(power_name, order.unit_type, order.location)
                if not unit or not unit.dislodged:
                    continue 
                unit_orders[unit] = order

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
        bounced_units: Set[Unit] = set()
        for location, unit_coasts in retreat_targets.items():
            if len(unit_coasts) == 1:
                unit, coast = unit_coasts[0]
                successful_retreats[unit] = (location, coast)
                disband_units.discard(unit)
            else:
                # All bounced units are disbanded
                bounced_units.update(unit for unit, _coast in unit_coasts)
                disband_units.update(bounced_units)

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

        results: Dict[str, List[List[str]]] = {name: [] for name in self.powers}
        for unit, label in dislodged_labels.items():
            order = unit_orders.get(unit)
            if order is None:
                entry = [f"{label} (no order)", "disbanded"]
            elif order.order_type == OrderType.DISBAND:
                entry = [str(order), "disbanded"]
            elif unit in bounced_units:
                entry = [str(order), "bounced, disbanded"]
            elif unit in disband_units:
                entry = [str(order), "failed, disbanded"]
            else:
                entry = [str(order), "retreated"]
            results[unit.power].append(entry)
        return results


    def _resolve_adjustments(
        self, valid_orders: Dict[str, List[Order]]
    ) -> Dict[str, List[List[str]]]:
        """Resolve adjustment orders and return each power's order outcomes."""
        results: Dict[str, List[List[str]]] = {name: [] for name in self.powers}
        for power_name, power in self.powers.items():
            orders = valid_orders.get(power_name, [])
            build_count: int = power.count_needed_builds()
            entries = results[power_name]

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
                            entries.append([str(order), "built"])
                        else:
                            entries.append([str(order), "not built"])
                    elif order.order_type == OrderType.BUILD:
                        entries.append([str(order), "not built"])
                    elif order.order_type == OrderType.WAIVE:
                        waives += 1
                        entries.append([str(order), "build waived"])

                unused = build_count - builds_executed - waives
                if unused > 0:
                    entries.append([f"{unused} unordered build(s)", "waived"])

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
                            entries.append([str(order), "disbanded"])


                # If not enough disbands were ordered, auto-disband furthest units from home
                if disbands_executed < disbands_needed:
                    units_to_disband = self._select_units_to_disband(
                        power, disbands_needed - disbands_executed
                    )

                    for unit in units_to_disband:
                        entries.append(
                            [f"{unit} (no order)", "disbanded automatically"]
                        )
                        self._remove_unit_from_map(power, unit)
        return results

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

        # Sort by distance (descending), then fleets first, then alphabetically by province
        unit_distances.sort(
            key=lambda x: (-x[1], 0 if x[0].type == UnitType.FLEET else 1, x[0].region.name)
        )
        
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

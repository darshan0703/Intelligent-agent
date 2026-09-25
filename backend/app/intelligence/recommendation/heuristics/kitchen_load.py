"""
app/intelligence/recommendation/heuristics/kitchen_load.py
Kitchen Station Load & Operational Bottleneck Awareness (v4.0).

Dynamically balances kitchen throughput during peak rush periods.
If a station (e.g. fryer) is experiencing a bottleneck (>10 active items in prep queue),
recommendations penalize items from that station and boost idle/low-load stations (e.g. cold desserts, sodas)
to prevent kiosk conversions from escalating kitchen dispatch delays.
"""
from __future__ import annotations
from enum import Enum
from typing import Any
from app.domain.catalog.entities import MenuItem


class KitchenStation(str, Enum):
    GRILL = "grill"
    FRYER = "fryer"
    BEVERAGE = "beverage"
    DESSERT = "dessert"
    PANTRY = "pantry"


class StationLoadState(str, Enum):
    IDLE = "idle"          # 0-2 queued items (throughput boost: 1.15x)
    OPTIMAL = "optimal"    # 3-6 queued items (neutral: 1.0x)
    HEAVY = "heavy"        # 7-10 queued items (slight damping: 0.80x)
    BOTTLENECK = "bottleneck" # >10 queued items (severe damping: 0.45x)


class KitchenLoadTracker:
    """In-memory operational queue depth tracker per branch and prep station."""
    # branch_id -> {station: queue_count}
    _station_queues: dict[int, dict[KitchenStation, int]] = {}

    @classmethod
    def get_station_queue(cls, branch_id: int, station: KitchenStation) -> int:
        if branch_id not in cls._station_queues:
            cls._station_queues[branch_id] = {
                KitchenStation.GRILL: 3,
                KitchenStation.FRYER: 4,
                KitchenStation.BEVERAGE: 2,
                KitchenStation.DESSERT: 1,
                KitchenStation.PANTRY: 1,
            }
        return cls._station_queues[branch_id].get(station, 2)

    @classmethod
    def set_station_queue(cls, branch_id: int, station: KitchenStation, count: int) -> None:
        if branch_id not in cls._station_queues:
            cls.get_station_queue(branch_id, station)
        cls._station_queues[branch_id][station] = max(0, count)

    @classmethod
    def increment_queue(cls, branch_id: int, station: KitchenStation, delta: int = 1) -> None:
        current = cls.get_station_queue(branch_id, station)
        cls.set_station_queue(branch_id, station, current + delta)

    @classmethod
    def get_station_state(cls, branch_id: int, station: KitchenStation) -> StationLoadState:
        q = cls.get_station_queue(branch_id, station)
        if q <= 2:
            return StationLoadState.IDLE
        elif q <= 6:
            return StationLoadState.OPTIMAL
        elif q <= 10:
            return StationLoadState.HEAVY
        else:
            return StationLoadState.BOTTLENECK

    @classmethod
    def map_item_to_station(cls, item: MenuItem) -> KitchenStation:
        cat = str(item.category.value if hasattr(item.category, "value") else item.category).lower()
        if "drink" in cat or "beverage" in cat:
            return KitchenStation.BEVERAGE
        elif "dessert" in cat or "sweet" in cat:
            return KitchenStation.DESSERT
        elif "side" in cat or "snack" in cat:
            return KitchenStation.FRYER
        elif "burger" in cat or "main" in cat:
            return KitchenStation.GRILL
        else:
            return KitchenStation.PANTRY

    @classmethod
    def evaluate_kitchen_multiplier(cls, item: MenuItem, branch_id: int = 1) -> tuple[float, str]:
        """
        Evaluates operational kitchen load multiplier.
        Returns: (multiplier: float, explanation: str)
        """
        station = cls.map_item_to_station(item)
        state = cls.get_station_state(branch_id, station)

        if state == StationLoadState.BOTTLENECK:
            return 0.45, f"Station {station.value} at bottleneck; damped to prevent kitchen overload"
        elif state == StationLoadState.HEAVY:
            return 0.80, f"Station {station.value} load heavy; minor suppression"
        elif state == StationLoadState.IDLE:
            return 1.15, f"Station {station.value} idle; throughput boost"
        else:
            return 1.00, f"Station {station.value} operating at optimal queue depth"

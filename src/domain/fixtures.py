"""Load and validate bundled synthetic snapshots and presets."""

import json
from pathlib import Path

from src.domain import (
    Edge, EdgeDelay, NetworkRef, NetworkSnapshot, Node, NodeOutage, Scenario,
    ScenarioPreset, Shipment, validate_scenario,
)

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"


def _load_fixture(filename: str) -> tuple[NetworkSnapshot, ScenarioPreset]:
    raw = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    ref = NetworkRef(raw["network_id"], raw["version"])
    snapshot = NetworkSnapshot(
        ref, raw["display_name"], tuple(Node(**node) for node in raw["nodes"]),
        tuple(Edge(*route) for route in raw["routes"]),
    )
    preset = raw["preset"]
    shock = preset["disruption"]
    disruption = NodeOutage(**shock) if "node_id" in shock else EdgeDelay(**shock)
    shipment = Shipment(**preset["shipment"])
    scenario = Scenario(disruption, tuple(Edge(*route) for route in preset["backup_routes"]))
    validate_scenario(snapshot, shipment, scenario)
    return snapshot, ScenarioPreset(preset["preset_id"], ref, shipment, scenario)


def demo_network() -> NetworkSnapshot:
    """Return the stable demo snapshot without its preset."""
    return _load_fixture("demo.json")[0]


def bundled_fixtures() -> tuple[tuple[NetworkSnapshot, ScenarioPreset], ...]:
    return _load_fixture("demo.json"), _load_fixture("tiny.json")

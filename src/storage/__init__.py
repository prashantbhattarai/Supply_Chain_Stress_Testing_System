"""SQLite repository for immutable network versions, presets and saved comparisons."""

import json
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path

from src.domain import (
    Comparison, Criticality, Edge, EdgeDelay, NetworkRef, NetworkSnapshot, Node,
    NodeOutage, RiskMetrics, RouteClosure, RunSettings, SavedRun, Scenario,
    ScenarioPreset, Shipment, TransportSlowdown, validate_scenario,
)

APPLICATION_ID = 0x53435354
MIGRATIONS = ("001_initial.sql", "002_disruptions.sql")


def _shock_columns(shock):
    if isinstance(shock, NodeOutage):
        return "node_outage", shock.node_id, None, None, None, None
    ends = (shock.origin_id, shock.destination_id)
    if isinstance(shock, EdgeDelay):
        return "edge_delay", None, *ends, shock.added_hours, None
    if isinstance(shock, TransportSlowdown):
        return "transport_slowdown", None, *ends, None, shock.factor
    return "route_closure", None, *ends, None, None


def _shock_from_columns(kind, node, origin, destination, hours, factor):
    if kind == "node_outage":
        return NodeOutage(node)
    if kind == "edge_delay":
        return EdgeDelay(origin, destination, hours)
    if kind == "transport_slowdown":
        return TransportSlowdown(origin, destination, factor)
    if kind == "route_closure":
        return RouteClosure(origin, destination)
    raise ValueError(f"Unknown disruption kind: {kind}")


def _shock_from_json(shock):
    # The field sets distinguish each kind and preserve the schema 1 run format.
    for field, kind in (("node_id", NodeOutage), ("added_hours", EdgeDelay),
                        ("factor", TransportSlowdown)):
        if field in shock:
            return kind(**shock)
    return RouteClosure(**shock)


class SQLiteRepository:
    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def _connection(self, *, write=False, initialize=False):
        if initialize:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            database = str(self.path)
        else:
            database = self.path.resolve().as_uri() + "?mode=rw"

        with closing(sqlite3.connect(database, uri=not initialize)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                application_id = connection.execute("PRAGMA application_id").fetchone()[0]
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if initialize:
                    if (application_id, version) == (0, 0):
                        existing = connection.execute(
                            "SELECT 1 FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' LIMIT 1"
                        ).fetchone()
                        if existing:
                            raise ValueError("Refusing to initialize a nonempty foreign database")
                        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
                    elif application_id != APPLICATION_ID or not 1 <= version <= len(MIGRATIONS):
                        raise ValueError("Unsupported SQLite database or schema version")
                elif application_id != APPLICATION_ID or version != len(MIGRATIONS):
                    raise ValueError("Run initialize() with a supported foundation database")
                yield connection, version

    def initialize(self) -> None:
        """Apply missing migrations as one write transaction."""
        with self._connection(write=True, initialize=True) as (connection, version):
            for number, filename in enumerate(MIGRATIONS[version:], start=version + 1):
                script = Path(__file__).with_name(filename).read_text(encoding="utf-8")
                # Execute individual statements to keep SQLite's transaction open.
                statement = ""
                for line in script.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ""
                if statement.strip():
                    raise ValueError(f"Incomplete migration: {filename}")
                connection.execute(f"PRAGMA user_version = {number}")

    @staticmethod
    def _network_key(ref):
        return ref.network_id, ref.version

    def _get_network(self, connection, ref):
        key = self._network_key(ref)
        row = connection.execute(
            "SELECT display_name FROM networks WHERE network_id = ? AND version = ?", key
        ).fetchone()
        if row is None:
            raise KeyError(ref)
        nodes = connection.execute(
            "SELECT node_id, display_name, lead_time_days, reliability FROM nodes "
            "WHERE network_id = ? AND version = ? ORDER BY node_id", key
        )
        edges = connection.execute(
            "SELECT origin_id, destination_id, transit_hours FROM routes "
            "WHERE network_id = ? AND version = ? ORDER BY origin_id, destination_id", key
        )
        return NetworkSnapshot(ref, row[0], tuple(Node(*item) for item in nodes),
                               tuple(Edge(*item) for item in edges))

    def _save_network(self, connection, snapshot):
        try:
            existing = self._get_network(connection, snapshot.ref)
        except KeyError:
            key = self._network_key(snapshot.ref)
            connection.execute("INSERT INTO networks VALUES (?, ?, ?)", (*key, snapshot.display_name))
            connection.executemany(
                "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?)",
                ((*key, node.node_id, node.display_name, node.lead_time_days, node.reliability)
                 for node in snapshot.nodes),
            )
            connection.executemany(
                "INSERT INTO routes VALUES (?, ?, ?, ?, ?)",
                ((*key, *edge.endpoints, edge.transit_hours) for edge in snapshot.edges),
            )
        else:
            if existing != snapshot:
                raise ValueError(f"Network version is immutable: {snapshot.ref}")

    def save_network(self, snapshot: NetworkSnapshot) -> NetworkRef:
        with self._connection(write=True) as (connection, _):
            self._save_network(connection, snapshot)
        return snapshot.ref

    def get_network(self, ref: NetworkRef) -> NetworkSnapshot:
        with self._connection() as (connection, _):
            return self._get_network(connection, ref)

    def list_networks(self) -> tuple[NetworkRef, ...]:
        with self._connection() as (connection, _):
            rows = connection.execute("SELECT network_id, version FROM networks ORDER BY network_id, version")
            return tuple(NetworkRef(*row) for row in rows)

    def _get_preset(self, connection, ref, preset_id):
        key = (*self._network_key(ref), preset_id)
        row = connection.execute(
            "SELECT origin_id, destination_id, deadline_hours, disruption_kind, outage_node_id, "
            "route_origin_id, route_destination_id, added_hours, slowdown_factor FROM scenario_presets "
            "WHERE network_id = ? AND version = ? AND preset_id = ?", key
        ).fetchone()
        if row is None:
            raise KeyError((ref, preset_id))
        disruption = _shock_from_columns(*row[3:])
        edges = connection.execute(
            "SELECT origin_id, destination_id, transit_hours FROM scenario_backup_routes "
            "WHERE network_id = ? AND version = ? AND preset_id = ? ORDER BY origin_id, destination_id", key
        )
        return ScenarioPreset(preset_id, ref, Shipment(*row[:3]),
                              Scenario(disruption, tuple(Edge(*edge) for edge in edges)))

    def _save_preset(self, connection, preset):
        snapshot = self._get_network(connection, preset.network)
        validate_scenario(snapshot, preset.shipment, preset.scenario)
        try:
            existing = self._get_preset(connection, preset.network, preset.preset_id)
        except KeyError:
            key = (*self._network_key(preset.network), preset.preset_id)
            shipment = preset.shipment
            connection.execute(
                "INSERT INTO scenario_presets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*key, shipment.origin_id, shipment.destination_id, shipment.deadline_hours,
                 *_shock_columns(preset.scenario.disruption)),
            )
            connection.executemany(
                "INSERT INTO scenario_backup_routes VALUES (?, ?, ?, ?, ?, ?)",
                ((*key, *edge.endpoints, edge.transit_hours) for edge in preset.scenario.backup_edges),
            )
        else:
            if existing != preset:
                raise ValueError(f"Scenario preset is immutable: {preset.preset_id}")

    def save_preset(self, preset: ScenarioPreset) -> None:
        with self._connection(write=True) as (connection, _):
            self._save_preset(connection, preset)

    def get_preset(self, ref: NetworkRef, preset_id: str) -> ScenarioPreset:
        with self._connection() as (connection, _):
            return self._get_preset(connection, ref, preset_id)

    def seed(self, fixtures: tuple[tuple[NetworkSnapshot, ScenarioPreset], ...]) -> None:
        """Insert snapshots and matching presets together or roll back the batch."""
        with self._connection(write=True) as (connection, _):
            for snapshot, preset in fixtures:
                if snapshot.ref != preset.network:
                    raise ValueError("Fixture preset must reference its own snapshot")
                self._save_network(connection, snapshot)
                self._save_preset(connection, preset)

    def save_run(self, run: SavedRun) -> None:
        with self._connection(write=True) as (connection, _):
            snapshot = self._get_network(connection, run.network)
            validate_scenario(snapshot, run.settings.shipment, run.settings.scenario)
            shipment = run.settings.shipment
            transit_ids = {node.node_id for node in snapshot.nodes} - {shipment.origin_id, shipment.destination_id}
            if any(item.node_id not in transit_ids for item in run.result.node_criticality):
                raise ValueError("Criticality must reference transit nodes in the snapshot")
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?)",
                (run.run_id, *self._network_key(run.network), json.dumps(asdict(run.settings), allow_nan=False)),
            )
            connection.execute(
                "INSERT INTO run_results VALUES (?, ?)",
                (run.run_id, json.dumps(asdict(run.result), allow_nan=False)),
            )

    def get_run(self, run_id: str) -> SavedRun:
        with self._connection() as (connection, _):
            row = connection.execute(
                "SELECT network_id, version, settings_json, comparison_json "
                "FROM runs JOIN run_results USING (run_id) WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        settings = json.loads(row[2])
        scenario = settings["scenario"]
        shock = scenario["disruption"]
        disruption = _shock_from_json(shock)
        settings["scenario"] = Scenario(disruption, tuple(Edge(**edge) for edge in scenario["backup_edges"]))
        settings["shipment"] = Shipment(**settings["shipment"])
        result = json.loads(row[3])
        comparison = Comparison(
            RiskMetrics(**result["baseline"]), RiskMetrics(**result["stressed"]),
            RiskMetrics(**result["mitigated"]),
            tuple(Criticality(**item) for item in result["node_criticality"]),
        )
        return SavedRun(run_id, NetworkRef(*row[:2]), RunSettings(**settings), comparison)

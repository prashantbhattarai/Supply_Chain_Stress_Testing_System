ALTER TABLE scenario_presets RENAME TO scenario_presets_v1;
ALTER TABLE scenario_backup_routes RENAME TO scenario_backup_routes_v1;

CREATE TABLE scenario_presets (
    network_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    preset_id TEXT NOT NULL CHECK (length(trim(preset_id)) > 0),
    origin_id INTEGER NOT NULL,
    destination_id INTEGER NOT NULL CHECK (origin_id <> destination_id),
    deadline_hours REAL NOT NULL CHECK (deadline_hours BETWEEN 0 AND 1.7976931348623157e308),
    disruption_kind TEXT NOT NULL,
    outage_node_id INTEGER,
    route_origin_id INTEGER,
    route_destination_id INTEGER,
    added_hours REAL,
    slowdown_factor REAL,
    CHECK (
        (disruption_kind = 'node_outage' AND outage_node_id IS NOT NULL
            AND route_origin_id IS NULL AND route_destination_id IS NULL
            AND added_hours IS NULL AND slowdown_factor IS NULL)
        OR (
            outage_node_id IS NULL AND route_origin_id IS NOT NULL
            AND route_destination_id IS NOT NULL
            AND (
                (disruption_kind = 'route_closure' AND added_hours IS NULL AND slowdown_factor IS NULL)
                OR (disruption_kind = 'edge_delay' AND added_hours IS NOT NULL
                    AND added_hours > 0 AND added_hours <= 1.7976931348623157e308
                    AND slowdown_factor IS NULL)
                OR (disruption_kind = 'transport_slowdown' AND slowdown_factor IS NOT NULL
                    AND slowdown_factor BETWEEN 1 AND 1.7976931348623157e308
                    AND added_hours IS NULL)
            )
        )
    ),
    PRIMARY KEY (network_id, version, preset_id),
    FOREIGN KEY (network_id, version, origin_id) REFERENCES nodes,
    FOREIGN KEY (network_id, version, destination_id) REFERENCES nodes,
    FOREIGN KEY (network_id, version, outage_node_id) REFERENCES nodes,
    FOREIGN KEY (network_id, version, route_origin_id, route_destination_id) REFERENCES routes
);

CREATE TABLE scenario_backup_routes (
    network_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    preset_id TEXT NOT NULL,
    origin_id INTEGER NOT NULL,
    destination_id INTEGER NOT NULL CHECK (origin_id <> destination_id),
    transit_hours REAL NOT NULL CHECK (transit_hours BETWEEN 0 AND 1.7976931348623157e308),
    PRIMARY KEY (network_id, version, preset_id, origin_id, destination_id),
    FOREIGN KEY (network_id, version, preset_id) REFERENCES scenario_presets,
    FOREIGN KEY (network_id, version, origin_id) REFERENCES nodes,
    FOREIGN KEY (network_id, version, destination_id) REFERENCES nodes
);

INSERT INTO scenario_presets (
    network_id, version, preset_id, origin_id, destination_id, deadline_hours,
    disruption_kind, outage_node_id, route_origin_id, route_destination_id, added_hours
)
SELECT network_id, version, preset_id, origin_id, destination_id, deadline_hours,
       CASE WHEN outage_node_id IS NULL THEN 'edge_delay' ELSE 'node_outage' END,
       outage_node_id, delay_origin_id, delay_destination_id, added_hours
FROM scenario_presets_v1;

INSERT INTO scenario_backup_routes
SELECT network_id, version, preset_id, origin_id, destination_id, transit_hours
FROM scenario_backup_routes_v1;

DROP TABLE scenario_backup_routes_v1;
DROP TABLE scenario_presets_v1;

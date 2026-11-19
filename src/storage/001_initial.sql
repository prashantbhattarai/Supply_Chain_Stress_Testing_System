CREATE TABLE networks (
    network_id TEXT NOT NULL CHECK (length(trim(network_id)) > 0),
    version INTEGER NOT NULL CHECK (typeof(version) = 'integer' AND version > 0),
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    PRIMARY KEY (network_id, version)
);

CREATE TABLE nodes (
    network_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    node_id INTEGER NOT NULL CHECK (typeof(node_id) = 'integer'),
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    lead_time_days REAL NOT NULL CHECK (lead_time_days BETWEEN 0 AND 1.7976931348623157e308),
    reliability REAL NOT NULL CHECK (reliability BETWEEN 0 AND 1),
    PRIMARY KEY (network_id, version, node_id),
    FOREIGN KEY (network_id, version) REFERENCES networks
);

CREATE TABLE routes (
    network_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    origin_id INTEGER NOT NULL,
    destination_id INTEGER NOT NULL CHECK (origin_id <> destination_id),
    transit_hours REAL NOT NULL CHECK (transit_hours BETWEEN 0 AND 1.7976931348623157e308),
    PRIMARY KEY (network_id, version, origin_id, destination_id),
    FOREIGN KEY (network_id, version, origin_id) REFERENCES nodes,
    FOREIGN KEY (network_id, version, destination_id) REFERENCES nodes
);

CREATE TABLE scenario_presets (
    network_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    preset_id TEXT NOT NULL CHECK (length(trim(preset_id)) > 0),
    origin_id INTEGER NOT NULL,
    destination_id INTEGER NOT NULL CHECK (origin_id <> destination_id),
    deadline_hours REAL NOT NULL CHECK (deadline_hours BETWEEN 0 AND 1.7976931348623157e308),
    outage_node_id INTEGER,
    delay_origin_id INTEGER,
    delay_destination_id INTEGER,
    added_hours REAL,
    CHECK (
        (outage_node_id IS NOT NULL AND delay_origin_id IS NULL
            AND delay_destination_id IS NULL AND added_hours IS NULL)
        OR (outage_node_id IS NULL AND delay_origin_id IS NOT NULL
            AND delay_destination_id IS NOT NULL AND added_hours IS NOT NULL
            AND added_hours > 0 AND added_hours <= 1.7976931348623157e308)
    ),
    PRIMARY KEY (network_id, version, preset_id),
    FOREIGN KEY (network_id, version, origin_id) REFERENCES nodes,
    FOREIGN KEY (network_id, version, destination_id) REFERENCES nodes,
    FOREIGN KEY (network_id, version, outage_node_id) REFERENCES nodes,
    FOREIGN KEY (network_id, version, delay_origin_id, delay_destination_id) REFERENCES routes
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

CREATE TABLE runs (
    run_id TEXT NOT NULL PRIMARY KEY CHECK (length(trim(run_id)) > 0),
    network_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    settings_json TEXT NOT NULL,
    FOREIGN KEY (network_id, version) REFERENCES networks
);

CREATE TABLE run_results (
    run_id TEXT NOT NULL PRIMARY KEY,
    comparison_json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs
);

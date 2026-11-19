ALTER TABLE scenario_presets
ADD COLUMN sigma REAL NOT NULL DEFAULT 0.15 CHECK (sigma BETWEEN 0 AND 1);

CREATE TABLE run_details (
    run_id TEXT NOT NULL PRIMARY KEY,
    details_json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES run_results (run_id)
);

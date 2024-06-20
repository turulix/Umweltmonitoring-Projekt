CREATE TABLE IF NOT EXISTS boxes
(
    id       TEXT PRIMARY KEY,
    model    TEXT,
    name     TEXT,
    location geometry(POINT, 4326),
    exposure TEXT
);

CREATE TABLE IF NOT EXISTS sensors
(
    id          TEXT PRIMARY KEY,
    box_id      TEXT references boxes (id),
    icon        TEXT,
    title       TEXT,
    unit        TEXT,
    sensor_type TEXT
);

CREATE TABLE IF NOT EXISTS data
(
    box_id    TEXT,
    sensor_id TEXT references sensors (id),
    timestamp timestamptz,
    value     REAL
)

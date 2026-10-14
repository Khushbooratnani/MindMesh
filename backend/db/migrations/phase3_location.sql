CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS locations (
    location_id BIGSERIAL PRIMARY KEY,
    normalized_name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    country_code TEXT,
    admin_area TEXT,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    point GEOGRAPHY(Point, 4326) NOT NULL,
    source TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS locations_point_gist_idx
ON locations USING GIST (point);

CREATE TABLE IF NOT EXISTS memory_locations (
    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
    location_id BIGINT NOT NULL REFERENCES locations(location_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (memory_id, location_id)
);

CREATE INDEX IF NOT EXISTS memory_locations_location_idx
ON memory_locations (location_id);

CREATE INDEX IF NOT EXISTS memory_locations_memory_idx
ON memory_locations (memory_id);

-- ==============================================================================
-- MindMesh Platform Schema Migration: 005_locations_and_spatial.sql
-- Production Locations, PostGIS Spatial Geographies & Memory Geo-Referencing
-- ==============================================================================

-- 2. Table: locations
CREATE TABLE IF NOT EXISTS locations (
    location_id BIGSERIAL PRIMARY KEY,
    normalized_name VARCHAR(256) UNIQUE NOT NULL,
    display_name VARCHAR(512) NOT NULL,
    country_code VARCHAR(16),
    admin_area VARCHAR(256),
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    source VARCHAR(64) DEFAULT 'locationiq' NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_locations_lat_lon ON locations(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_locations_normalized_name ON locations(normalized_name);

-- 3. Table: memory_locations (Cross-reference linking phase1_outputs to locations)
CREATE TABLE IF NOT EXISTS memory_locations (
    memory_id VARCHAR(64) NOT NULL REFERENCES phase1_outputs(memory_id) ON DELETE CASCADE,
    location_id BIGINT NOT NULL REFERENCES locations(location_id) ON DELETE CASCADE,
    source VARCHAR(64) DEFAULT 'extraction' NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    is_primary BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (memory_id, location_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_locations_memory_id ON memory_locations(memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_locations_location_id ON memory_locations(location_id);

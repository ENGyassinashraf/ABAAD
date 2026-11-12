-- sqlite_master after `alembic upgrade head` (revision 0002), captured in the cloud workspace
-- SQLite 3.45.1

-- trigger: trg_gap_no_measurement_ins
CREATE TRIGGER trg_gap_no_measurement_ins
BEFORE INSERT ON data_gap
WHEN EXISTS (SELECT 1 FROM measurement WHERE region_id = NEW.region_id
             AND parameter_id = NEW.parameter_id AND is_current = 1)
BEGIN SELECT RAISE(ABORT, 'a current measurement already exists for this region/parameter'); END;

-- trigger: trg_gap_no_measurement_upd
CREATE TRIGGER trg_gap_no_measurement_upd
BEFORE UPDATE OF region_id, parameter_id ON data_gap
WHEN EXISTS (SELECT 1 FROM measurement WHERE region_id = NEW.region_id
             AND parameter_id = NEW.parameter_id AND is_current = 1)
BEGIN SELECT RAISE(ABORT, 'a current measurement already exists for this region/parameter'); END;

-- trigger: trg_measurement_no_gap_ins
CREATE TRIGGER trg_measurement_no_gap_ins
BEFORE INSERT ON measurement
WHEN NEW.is_current = 1 AND EXISTS (
  SELECT 1 FROM data_gap WHERE region_id = NEW.region_id AND parameter_id = NEW.parameter_id)
BEGIN SELECT RAISE(ABORT, 'a data_gap already exists for this region/parameter'); END;

-- trigger: trg_measurement_no_gap_upd
CREATE TRIGGER trg_measurement_no_gap_upd
BEFORE UPDATE OF is_current, region_id, parameter_id ON measurement
WHEN NEW.is_current = 1 AND EXISTS (
  SELECT 1 FROM data_gap WHERE region_id = NEW.region_id AND parameter_id = NEW.parameter_id)
BEGIN SELECT RAISE(ABORT, 'a data_gap already exists for this region/parameter'); END;

-- trigger: trg_measurement_reject_synthetic_ins
CREATE TRIGGER trg_measurement_reject_synthetic_ins
BEFORE INSERT ON measurement
WHEN NEW.is_synthetic = 1
BEGIN SELECT RAISE(ABORT, 'synthetic rows are not allowed in the production database'); END;

-- trigger: trg_measurement_reject_synthetic_upd
CREATE TRIGGER trg_measurement_reject_synthetic_upd
BEFORE UPDATE OF is_synthetic ON measurement
WHEN NEW.is_synthetic = 1
BEGIN SELECT RAISE(ABORT, 'synthetic rows are not allowed in the production database'); END;

-- trigger: trg_region_geometry_body_matches_region_ins
CREATE TRIGGER trg_region_geometry_body_matches_region_ins
BEFORE INSERT ON region_geometry
WHEN NEW.body_id <> (SELECT body_id FROM region WHERE id = NEW.region_id)
BEGIN SELECT RAISE(ABORT, 'region_geometry.body_id must equal the region body'); END;

-- trigger: trg_region_geometry_body_matches_region_upd
CREATE TRIGGER trg_region_geometry_body_matches_region_upd
BEFORE UPDATE OF body_id, region_id ON region_geometry
WHEN NEW.body_id <> (SELECT body_id FROM region WHERE id = NEW.region_id)
BEGIN SELECT RAISE(ABORT, 'region_geometry.body_id must equal the region body'); END;

-- trigger: trg_region_geometry_rfc7946_earth_only_ins
CREATE TRIGGER trg_region_geometry_rfc7946_earth_only_ins
BEFORE INSERT ON region_geometry
WHEN NEW.encoding = 'rfc7946_geojson'
 AND (SELECT code FROM planetary_body WHERE id = NEW.body_id) IS NOT 'earth'
BEGIN SELECT RAISE(ABORT, 'RFC 7946 GeoJSON is allowed only for Earth geometry'); END;

-- trigger: trg_region_geometry_rfc7946_earth_only_upd
CREATE TRIGGER trg_region_geometry_rfc7946_earth_only_upd
BEFORE UPDATE OF encoding, body_id ON region_geometry
WHEN NEW.encoding = 'rfc7946_geojson'
 AND (SELECT code FROM planetary_body WHERE id = NEW.body_id) IS NOT 'earth'
BEGIN SELECT RAISE(ABORT, 'RFC 7946 GeoJSON is allowed only for Earth geometry'); END;

-- table: alembic_version
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- table: data_gap
CREATE TABLE data_gap (
	id INTEGER NOT NULL, 
	region_id INTEGER NOT NULL, 
	parameter_id INTEGER NOT NULL, 
	reason TEXT NOT NULL, 
	note TEXT, 
	CONSTRAINT pk_data_gap PRIMARY KEY (id), 
	CONSTRAINT uq_data_gap_region_id_parameter_id UNIQUE (region_id, parameter_id), 
	CONSTRAINT fk_data_gap_region_id_region FOREIGN KEY(region_id) REFERENCES region (id), 
	CONSTRAINT fk_data_gap_parameter_id_parameter FOREIGN KEY(parameter_id) REFERENCES parameter (id), 
	CONSTRAINT ck_data_gap_reason_enum CHECK (reason IN ('not_measured', 'not_public', 'resolution_inadequate', 'not_applicable', 'not_yet_curated'))
)
 STRICT

;

-- table: measurement
CREATE TABLE "measurement" (
	id INTEGER NOT NULL, 
	region_id INTEGER NOT NULL, 
	parameter_id INTEGER NOT NULL, 
	value_kind TEXT NOT NULL, 
	value_num REAL, 
	interval_lower REAL, 
	interval_upper REAL, 
	value_text TEXT, 
	unit TEXT, 
	point_uncertainty_type TEXT, 
	point_uncertainty REAL, 
	evidence_grade TEXT NOT NULL, 
	source_access TEXT NOT NULL, 
	is_current INTEGER DEFAULT 1 NOT NULL, 
	is_synthetic INTEGER DEFAULT 0 NOT NULL, 
	created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')) NOT NULL, 
	observation_date TEXT, 
	resolution_adequacy TEXT, 
	CONSTRAINT pk_measurement PRIMARY KEY (id), 
	CONSTRAINT ck_measurement_category_shape CHECK (value_kind <> 'category' OR value_text IS NOT NULL), 
	CONSTRAINT ck_measurement_point_uncertainty_type_enum CHECK (point_uncertainty_type IS NULL OR point_uncertainty_type IN ('sd', 'plus_minus', 'ci95', 'none_reported')), 
	CONSTRAINT fk_measurement_region_id_region FOREIGN KEY(region_id) REFERENCES region (id), 
	CONSTRAINT ck_measurement_is_current_bool CHECK (is_current IN (0, 1)), 
	CONSTRAINT ck_measurement_source_access_enum CHECK (source_access IN ('full_text_checked', 'abstract_only', 'secondary_record', 'dataset_opened', 'raw_data_unavailable')), 
	CONSTRAINT fk_measurement_parameter_id_parameter FOREIGN KEY(parameter_id) REFERENCES parameter (id), 
	CONSTRAINT ck_measurement_is_synthetic_bool CHECK (is_synthetic IN (0, 1)), 
	CONSTRAINT ck_measurement_value_kind_enum CHECK (value_kind IN ('point', 'interval', 'category', 'distribution')), 
	CONSTRAINT ck_measurement_evidence_grade_enum CHECK (evidence_grade IN ('A', 'B', 'C', 'D')), 
	CONSTRAINT ck_measurement_point_shape CHECK (value_kind <> 'point' OR (value_num IS NOT NULL AND interval_lower IS NULL AND interval_upper IS NULL)), 
	CONSTRAINT ck_measurement_interval_shape CHECK (value_kind <> 'interval' OR (interval_lower IS NOT NULL AND interval_upper IS NOT NULL AND interval_lower <= interval_upper AND value_num IS NULL AND point_uncertainty IS NULL AND point_uncertainty_type IS NULL)), 
	CONSTRAINT ck_measurement_resolution_adequacy_enum CHECK (resolution_adequacy IS NULL OR resolution_adequacy IN ('adequate', 'marginal', 'inadequate', 'not_applicable'))
)
 STRICT

;

-- table: measurement_source
CREATE TABLE measurement_source (
	id INTEGER NOT NULL, 
	measurement_id INTEGER NOT NULL, 
	source_kind TEXT NOT NULL, 
	publication_id INTEGER, 
	role TEXT NOT NULL, 
	locator TEXT, 
	CONSTRAINT pk_measurement_source PRIMARY KEY (id), 
	CONSTRAINT fk_measurement_source_measurement_id_measurement FOREIGN KEY(measurement_id) REFERENCES measurement (id) ON DELETE CASCADE, 
	CONSTRAINT fk_measurement_source_publication_id_publication FOREIGN KEY(publication_id) REFERENCES publication (id), 
	CONSTRAINT ck_measurement_source_source_kind_enum CHECK (source_kind IN ('publication')), 
	CONSTRAINT ck_measurement_source_role_enum CHECK (role IN ('primary', 'supporting')), 
	CONSTRAINT ck_measurement_source_one_source CHECK ((source_kind = 'publication') = (publication_id IS NOT NULL))
)
 STRICT

;

-- table: parameter
CREATE TABLE parameter (
	id INTEGER NOT NULL, 
	code TEXT NOT NULL, 
	name TEXT NOT NULL, 
	canonical_unit TEXT, 
	value_type TEXT NOT NULL, 
	comparison_class TEXT NOT NULL, 
	CONSTRAINT pk_parameter PRIMARY KEY (id), 
	CONSTRAINT uq_parameter_code UNIQUE (code), 
	CONSTRAINT ck_parameter_value_type_enum CHECK (value_type IN ('scalar', 'angle_full', 'angle_axial', 'distribution', 'category')), 
	CONSTRAINT ck_parameter_comparison_class_enum CHECK (comparison_class IN ('D', 'M', 'C', 'N'))
)
 STRICT

;

-- table: planetary_body
CREATE TABLE planetary_body (
	id INTEGER NOT NULL, 
	code TEXT NOT NULL, 
	name TEXT NOT NULL, 
	default_crs_code TEXT NOT NULL, 
	mean_radius_m REAL NOT NULL, 
	CONSTRAINT pk_planetary_body PRIMARY KEY (id), 
	CONSTRAINT uq_planetary_body_code UNIQUE (code), 
	CONSTRAINT ck_planetary_body_radius_positive CHECK (mean_radius_m > 0)
)
 STRICT

;

-- table: publication
CREATE TABLE publication (
	id INTEGER NOT NULL, 
	doi TEXT, 
	title TEXT NOT NULL, 
	year INTEGER, 
	source_access TEXT NOT NULL, 
	peer_reviewed INTEGER NOT NULL, 
	CONSTRAINT pk_publication PRIMARY KEY (id), 
	CONSTRAINT uq_publication_doi UNIQUE (doi), 
	CONSTRAINT ck_publication_source_access_enum CHECK (source_access IN ('full_text_checked', 'abstract_only', 'secondary_record')), 
	CONSTRAINT ck_publication_peer_reviewed_bool CHECK (peer_reviewed IN (0, 1))
)
 STRICT

;

-- table: region
CREATE TABLE region (
	id INTEGER NOT NULL, 
	code TEXT NOT NULL, 
	body_id INTEGER NOT NULL, 
	region_role TEXT NOT NULL, 
	parent_region_id INTEGER, 
	region_level TEXT NOT NULL, 
	validation_status TEXT NOT NULL, 
	name TEXT NOT NULL, 
	description TEXT, 
	CONSTRAINT pk_region PRIMARY KEY (id), 
	CONSTRAINT uq_region_code UNIQUE (code), 
	CONSTRAINT fk_region_body_id_planetary_body FOREIGN KEY(body_id) REFERENCES planetary_body (id), 
	CONSTRAINT fk_region_parent_region_id_region FOREIGN KEY(parent_region_id) REFERENCES region (id), 
	CONSTRAINT ck_region_region_role_enum CHECK (region_role IN ('reference', 'analog')), 
	CONSTRAINT ck_region_region_level_enum CHECK (region_level IN ('region', 'subregion', 'feature')), 
	CONSTRAINT ck_region_validation_status_enum CHECK (validation_status IN ('site_confirmed', 'validation_pending', 'regional_only')), 
	CONSTRAINT ck_region_not_own_parent CHECK (parent_region_id IS NULL OR parent_region_id <> id)
)
 STRICT

;

-- table: region_geometry
CREATE TABLE region_geometry (
	id INTEGER NOT NULL, 
	region_id INTEGER NOT NULL, 
	body_id INTEGER NOT NULL, 
	geometry_role TEXT NOT NULL, 
	encoding TEXT NOT NULL, 
	geometry_text TEXT, 
	crs_code TEXT NOT NULL, 
	coordinate_units TEXT NOT NULL, 
	latitude_type TEXT NOT NULL, 
	longitude_direction TEXT NOT NULL, 
	longitude_domain TEXT NOT NULL, 
	axis_order TEXT NOT NULL, 
	min_x REAL, 
	min_y REAL, 
	max_x REAL, 
	max_y REAL, 
	geometry_status TEXT NOT NULL, 
	source_publication_id INTEGER, 
	source_locator TEXT, 
	CONSTRAINT pk_region_geometry PRIMARY KEY (id), 
	CONSTRAINT fk_region_geometry_region_id_region FOREIGN KEY(region_id) REFERENCES region (id) ON DELETE CASCADE, 
	CONSTRAINT fk_region_geometry_body_id_planetary_body FOREIGN KEY(body_id) REFERENCES planetary_body (id), 
	CONSTRAINT fk_region_geometry_source_publication_id_publication FOREIGN KEY(source_publication_id) REFERENCES publication (id), 
	CONSTRAINT ck_region_geometry_geometry_role_enum CHECK (geometry_role IN ('outline', 'point_locator', 'traverse')), 
	CONSTRAINT ck_region_geometry_encoding_enum CHECK (encoding IN ('rfc7946_geojson', 'ogc_wkt')), 
	CONSTRAINT ck_region_geometry_coordinate_units_enum CHECK (coordinate_units IN ('degree', 'metre')), 
	CONSTRAINT ck_region_geometry_latitude_type_enum CHECK (latitude_type IN ('geodetic_wgs84', 'planetocentric', 'planetographic', 'not_applicable')), 
	CONSTRAINT ck_region_geometry_longitude_direction_enum CHECK (longitude_direction IN ('east', 'west', 'not_applicable')), 
	CONSTRAINT ck_region_geometry_longitude_domain_enum CHECK (longitude_domain IN ('-180..180', '0..360', 'not_applicable')), 
	CONSTRAINT ck_region_geometry_axis_order_enum CHECK (axis_order IN ('lon_lat', 'lat_lon', 'x_y')), 
	CONSTRAINT ck_region_geometry_geometry_status_enum CHECK (geometry_status IN ('source_traced', 'approximate', 'undefined')), 
	CONSTRAINT ck_region_geometry_rfc7946_only_wgs84 CHECK (encoding <> 'rfc7946_geojson' OR (crs_code = 'OGC:CRS84' AND coordinate_units = 'degree' AND latitude_type = 'geodetic_wgs84' AND axis_order = 'lon_lat')), 
	CONSTRAINT ck_region_geometry_text_unless_undefined CHECK (geometry_status = 'undefined' OR geometry_text IS NOT NULL), 
	CONSTRAINT ck_region_geometry_traced_has_source CHECK (geometry_status <> 'source_traced' OR source_publication_id IS NOT NULL), 
	CONSTRAINT ck_region_geometry_extent_order CHECK ((min_x IS NULL AND min_y IS NULL AND max_x IS NULL AND max_y IS NULL) OR (min_x <= max_x AND min_y <= max_y))
)
 STRICT

;

-- index: ix_measurement_region_id_parameter_id
CREATE INDEX ix_measurement_region_id_parameter_id ON measurement (region_id, parameter_id);

-- index: ix_measurement_source_measurement_id
CREATE INDEX ix_measurement_source_measurement_id ON measurement_source (measurement_id);

-- index: ix_region_body_id
CREATE INDEX ix_region_body_id ON region (body_id);

-- index: ix_region_geometry_region_id
CREATE INDEX ix_region_geometry_region_id ON region_geometry (region_id);

-- index: ix_region_parent_region_id
CREATE INDEX ix_region_parent_region_id ON region (parent_region_id);

-- index: uq_measurement_current_region_parameter
CREATE UNIQUE INDEX uq_measurement_current_region_parameter ON measurement (region_id, parameter_id) WHERE is_current = 1;

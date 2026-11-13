/** Shapes returned by the Mission Lab API (/api/v1/mission/*). */

export type XY = [number, number];

export type Frame = {
  t: number; x: number; y: number; hdg: number; ex: number; ey: number; sigma: number;
  nav: string; phase: number; wp: string | null; los: string; local: boolean; earth: boolean;
  path: "direct" | "relay" | "none"; relay_ok: boolean | null; queue: number; safety: string;
  dist: number; obs: XY | null; since_contact: number | null;
};

export type MissionEvent = {
  seq: number; t: number; type: string; phase: number; x: number; y: number;
  payload: Record<string, unknown>; result: string;
};

export type Waypoint = {
  id: string; x: number; y: number; elevation_m: number; slope_deg: number;
  comm_visible: boolean; hazard_proximity: number; path_index: number;
};

export type Route = {
  distance_m: number; max_slope_deg: number; mean_slope_deg: number; estimated_duration_s: number;
  assumed_speed_mps: number; comm_visible_fraction: number; hazard_exposure_m: number;
  cost_breakdown: Record<string, number>; total_cost: number; waypoints: Waypoint[]; path: XY[];
  explanation?: string; planner_version: string; weights: Record<string, number>;
  hard_constraints: Record<string, unknown>; is_demonstration: boolean;
  meta: { status: string; reasons: string[]; alternate_note: string | null; demonstration_reason: string | null };
};

export type Phase = { phase: number; name: string; status?: string; start_s?: number; end_s?: number };

export type Summary = Record<string, unknown> & {
  status: string; science_result?: string; halt_reason?: string | null; mission_duration_s?: number;
  one_way_earth_delay_s?: number; round_trip_propagation_estimate_s?: number; reasons?: string[];
};

export type MissionConfig = {
  terrain_seed: number; seed: number; start_xy: XY; target_xy: XY; speed_profile: string;
  comm_mode: "direct" | "relay"; relay_xy: XY | null; beacons: XY[]; nav_mode: string;
  nav_event_time_s: number; autonomy: boolean; terrain_blockage: boolean;
  outages: { segment: string; start_s: number; duration_s: number }[];
  advanced: Record<string, number | Record<string, number>> & {
    max_slope_deg: number; dt_s: number; weights: Record<string, number>;
    rover_antenna_m: number; base_antenna_m: number; relay_antenna_m: number; max_link_range_m: number;
    uncertainty_threshold_m: number; science_uncertainty_m: number;
  };
};

export type Run = {
  id: number; scenario_id: number; scenario_version: number; case_label: string; comparison_group: string | null;
  seed: number; status: string; config: MissionConfig; summary: Summary; phases: Phase[]; frames?: Frame[];
  frame_count: number; routes: { recommended?: Route; alternate?: Route }; events: MissionEvent[];
  simulation_version: string; started_at: string; ended_at: string;
};

export type Scenario = {
  id: number; version: number; body_code: string; reference_region_code: string; objective_code: string;
  training_site_kind: string; training_site: TrainingSite; terrain: Record<string, unknown>; data_status: string;
  config: MissionConfig; model_version: string; created_at: string;
};

export type TrainingSite = {
  kind: string; code: string; name: string; label: string; is_validated_lunar_analog: boolean;
  why_selected: string; tasks_supported: string[]; relevant_properties: string[]; cannot_reproduce: string[];
  differences_from_moon: string[]; note: string; data_status: string;
};

export type Catalog = {
  bodies: { code: string; name: string; available: boolean; note: string }[];
  regions: { code: string; body: string; name: string; bounds: Record<string, string | number>;
    relevance: { text: string; basis: string; source?: string }[] }[];
  objectives: { code: string; name: string; region: string; primary: string; secondary: string[];
    success_criteria: string[]; abort_conditions: string[]; tasks_trained: string[] }[];
  sources: { id: string; title: string; organization: string; date: string; url: string; supports: string; access: string }[];
};

export type TerrainData = {
  metadata: Record<string, unknown>; step: number; rows: number; cols: number; spacing_m: number;
  origin_m: XY; extent_m: number; elevation_m: number[][];
  hazards: { x: number; y: number; radius_m: number }[]; landmarks: { id: string; x: number; y: number }[];
  base_xy: XY;
};

export type LosResult = {
  status: "LINE_OF_SIGHT" | "BLOCKED_BY_TERRAIN" | "OUT_OF_RANGE" | "UNKNOWN"; reason: string;
  distance_m: number | null; obstructions: { x: number; y: number; distance_m: number; excess_m: number }[];
  min_clearance_m: number | null; profile: { d: number; ground: number; ray: number }[];
};

/** Typed client for the read-only ABAAD API (proxied by Next.js at /api/v1). */

export type SourceRef = {
  id: number;
  title: string;
  citation: string | null;
  url: string | null;
  doi: string | null;
  source_access: string;
  accessed_on: string | null;
};

export type Geometry = {
  lon: number;
  lat: number;
  crs_code: string;
  latitude_type: string;
  longitude_domain: string;
  geometry_status: string; // source_traced | approximate
  geometry_method: string | null;
  uncertainty_note: string | null;
  source: SourceRef | null;
  source_locator: string | null;
};

export type Outline = {
  rings: number[][][];
  crs_code: string;
  geometry_status: string; // source_traced | approximate
  uncertainty_note: string | null;
  source: SourceRef | null;
};

export type Region = {
  code: string;
  name: string;
  body: string;
  region_level: string;
  parent_code: string | null;
  country_code: string | null;
  site_type: string | null;
  origin_status: string;
  group: "egyptian" | "global" | "reference";
  geometry: Geometry | null;
  outline?: Outline | null;
  geometry_gap: string | null;
};

export type Task = { code: string; name: string; description: string; applies_to: string };

export type Dimension = {
  dimension: string;
  name: string;
  weight: number;
  similarity: number | null;
  rubric_level: string | null;
  contribution: number | null;
  evidence_basis: string | null;
  rationale: string | null;
  analog_source: SourceRef | null;
  analog_locator: string | null;
  reference_source: SourceRef | null;
  reference_locator: string | null;
};

export type ClaimSummary = {
  id: number;
  task_code: string;
  reference_region_code: string | null;
  reference_body: string;
  claim_evidence_class: { code: string; label: string };
  reference_pairing_basis: string;
  publication_state: string;
  unpublished: boolean;
  limitations: string;
  supported_claim: string | null;
  similarities: string | null;
  differences: string | null;
};

export type EvidenceQuality = {
  claim_class: { code: string; label: string } | null;
  assessed_dimensions: number;
  source_access: Record<string, number>;
  evidence_basis: Record<string, number>;
};

/** Backend result states. "excluded"/"not_available" are not produced by the
 * current engine; the UI handles them so a future state is never shown as ranked. */
export type CandidateStatus = "ranked" | "insufficient_evidence" | "excluded" | "not_available";

export type Candidate = {
  region: Region;
  status: CandidateStatus;
  score: number | null;
  coverage: number;
  rank: number | null;
  dimensions: Dimension[];
  claims: ClaimSummary[];
  /** Absent from pre-UI-upgrade API builds: rendered as "not reported". */
  evidence_quality?: EvidenceQuality;
};

export type CompareResponse = {
  reference: Region;
  task: Task;
  weights: { dimension: string; name: string; weight: number }[];
  weight_rationale: string | null;
  method: {
    score_formula: string;
    coverage_formula: string;
    missing_data: string;
    ranking: string;
    rubric: Record<string, number>;
    min_coverage?: number;
    not_a_similarity_percentage: string;
  };
  candidates: Candidate[];
  limitations: string[];
  generated_at: string;
};

export type OptionsResponse = {
  bodies: { code: string; name: string }[];
  references: { region: Region; tasks: Task[] }[];
};

export type ApiError = { code: string; message: string; details: unknown };

export class ApiRequestError extends Error {
  constructor(public status: number, public body: ApiError | null) {
    super(body?.message ?? `Request failed (${status})`);
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let r: Response;
  try {
    r = await fetch(path, { cache: "no-store", signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiRequestError(0, { code: "unreachable", message: "The ABAAD API is unreachable. Is the backend running (make dev)?", details: null });
  }
  if (!r.ok) {
    let body: ApiError | null = null;
    try {
      body = (await r.json()) as ApiError;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiRequestError(r.status, body);
  }
  return (await r.json()) as T;
}

export const fetchOptions = (signal?: AbortSignal) => getJson<OptionsResponse>("/api/v1/compare/options", signal);

export const fetchCompare = (reference: string, task: string, signal?: AbortSignal) =>
  getJson<CompareResponse>(
    `/api/v1/compare?reference=${encodeURIComponent(reference)}&task=${encodeURIComponent(task)}`,
    signal,
  );

export type RegionSummary = {
  code: string;
  body: string;
  region_role: string;
  region_level: string;
  validation_status: string;
  name: string;
  parent_code: string | null;
  country_code: string | null;
  site_type: string | null;
  origin_status: string;
};

export const fetchRegions = (params: Record<string, string>, signal?: AbortSignal) =>
  getJson<{ items: RegionSummary[]; total: number }>(`/api/v1/regions?${new URLSearchParams({ limit: "200", ...params })}`, signal);

/** Every distinct source cited anywhere in a comparison, in first-seen order. */
export function collectSources(c: CompareResponse): SourceRef[] {
  const seen = new Map<number, SourceRef>();
  const add = (s: SourceRef | null | undefined) => {
    if (s && !seen.has(s.id)) seen.set(s.id, s);
  };
  add(c.reference.geometry?.source);
  for (const cand of c.candidates) {
    add(cand.region.geometry?.source);
    for (const d of cand.dimensions) {
      add(d.analog_source);
      add(d.reference_source);
    }
  }
  return [...seen.values()];
}

export function formatCoord(g: Geometry): string {
  const lat = `${Math.abs(g.lat).toFixed(2)}° ${g.lat >= 0 ? "N" : "S"}`;
  const lon = `${g.lon.toFixed(2)}° E`;
  return `${lat}, ${lon}`;
}

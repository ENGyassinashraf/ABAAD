"""Mission Lab catalogue: destination, reference region, mission template,
sources, and the evidence-based training-site selection.

Every statement here is tagged with its basis: ``source`` (with a source id),
``project_curated`` (an ABAAD design decision), ``derived`` (computed by this
code) or ``assumption`` (a configurable training value).
"""

from __future__ import annotations

from sqlalchemy import Engine, text

SOURCES = [
    {
        "id": "SRC-NASA-ARTEMIS3-REGIONS-2022",
        "title": "NASA Identifies Candidate Regions for Landing Next Americans on Moon",
        "organization": "NASA (news release)",
        "date": "2022-08-19 (page last updated 2024-01-08)",
        "url": "https://www.nasa.gov/news-release/nasa-identifies-candidate-regions-for-landing-next-americans-on-Moon/",
        "supports": "13 candidate regions near the lunar South Pole; regions were evaluated using criteria "
                    "including terrain slope, ease of communications with Earth and lighting conditions; "
                    "the South Pole contains permanently shadowed regions.",
        "access": "page excerpt read (2026-11-13); not a peer-reviewed source",
    },
    {
        "id": "SRC-RTTNEWS-ARTEMIS3-2022",
        "title": "NASA Identifies Candidate Regions For Landing Next Americans On Moon",
        "organization": "RTTNews (report quoting the NASA release)",
        "date": "2022-08",
        "url": "https://www.rttnews.com/amp/3306698/nasa-identifies-candidate-regions-for-landing-next-americans-on-moon.aspx",
        "supports": "Each candidate region is located within six degrees of latitude of the lunar South Pole "
                    "(secondary report of the NASA release).",
        "access": "secondary record; the six-degree statement was not read on the NASA page itself",
    },
    {
        "id": "SRC-NASA-LUGRE-2025",
        "title": "NASA Successfully Acquires GPS Signals on Moon",
        "organization": "NASA Space Communications and Navigation (SCaN)",
        "date": "2025-03 (page last updated 2025-03-07)",
        "url": "https://www.nasa.gov/directorates/somd/space-communications-navigation-program/nasa-successfully-acquires-gps-signals-on-moon",
        "supports": "On 3 March 2025 the LuGRE payload acquired and tracked GNSS signals on the lunar surface "
                    "and achieved a navigation fix. GNSS at the Moon is therefore not treated as impossible; "
                    "its loss is an injected training event.",
        "access": "page excerpt read (2026-11-13); technology demonstration, not an operational service",
    },
]

BODIES = [
    {"code": "moon", "name": "Moon", "available": True, "note": "MVP destination"},
    {"code": "mars", "name": "Mars", "available": False, "note": "not available in the Mission Lab MVP"},
]

REGIONS = [
    {
        "code": "MOON-SOUTH-POLAR-6DEG",
        "body": "moon",
        "name": "Lunar south polar region (within 6 deg of the South Pole)",
        "bounds": {"kind": "latitude_cap", "min_latitude_deg": -90.0, "max_latitude_deg": -84.0,
                   "crs": "IAU_2015:30100 (Moon sphere, planetocentric)",
                   "wkt": "POLYGON((-180 -84, 180 -84, 180 -90, -180 -90, -180 -84))",
                   "basis": "project_curated",
                   "note": "Latitude cap chosen to enclose the Artemis III candidate regions, which are reported "
                           "to lie within six degrees of the South Pole (SRC-RTTNEWS-ARTEMIS3-2022). It is not an "
                           "official region boundary, and no individual landing region or coordinate is used."},
        "relevance": [
            {"text": "Candidate crewed landing regions were assessed on terrain slope, ease of communications "
                     "with Earth and lighting - the same factors this mission trains (route slope, communication "
                     "visibility, navigation).", "basis": "source", "source": "SRC-NASA-ARTEMIS3-REGIONS-2022"},
            {"text": "The region contains permanently shadowed regions, a reason for surface reconnaissance.",
             "basis": "source", "source": "SRC-NASA-ARTEMIS3-REGIONS-2022"},
        ],
    }
]

OBJECTIVES = [
    {
        "code": "LUNAR-RECON-NAV",
        "name": "Lunar Surface Reconnaissance & Navigation",
        "region": "MOON-SOUTH-POLAR-6DEG",
        "primary": "Navigate from the staging point to the target area, survey it, select a safe sampling "
                   "location, complete a simulated sampling operation, return the data and reach a safe final state.",
        "secondary": [
            "Maintain or recover communication with the base station and Earth.",
            "Keep position uncertainty inside the safety limit, using landmark or beacon corrections when "
            "external positioning is lost.",
            "Exercise the autonomous fallback policy under terrain occlusion and positioning loss.",
        ],
        "expected_observations": [
            "Loss of direct line of sight to the base behind the ridge (terrain occlusion).",
            "Growth of dead-reckoning uncertainty after positioning loss and its reduction at beacons.",
            "Data queuing while the Earth path is unavailable and transmission after recovery.",
        ],
        "success_criteria": [
            "Simulated sampling completed with position uncertainty <= the science limit.",
            "All queued data transmitted to Earth.",
            "Rover back at the staging point (safe point) without entering safe hold.",
        ],
        "abort_conditions": [
            "Position uncertainty above the safety threshold with no correction source in view.",
            "No command link for the command timeout while autonomy is disabled.",
            "Maximum simulated mission time exceeded.",
        ],
        "tasks_trained": ["route following on slopes", "communication-loss handling",
                          "navigation fallback decisions", "store-and-forward data handling",
                          "relay and beacon placement"],
    }
]

EARTH_MOON_DIFFERENCES = [
    "Gravity: about one sixth of Earth's; rover traction and slope limits differ.",
    "No atmosphere: no air for convective cooling, no weather, different dust behaviour.",
    "Illumination at the lunar poles: very low Sun angles and long shadows.",
    "Thermal environment: extreme temperature differences between sunlit and shadowed ground.",
    "Radiation environment and regolith properties have no direct terrestrial equivalent.",
    "Earth-Moon light-time (about 1.3 s one way) cannot be reproduced by distance at a terrestrial site; it "
    "can only be imposed artificially.",
]


def select_training_site(engine: Engine | None, objective_code: str) -> dict:
    """Pick the most defensible Earth training site for this objective from ABAAD's curated records.

    A site qualifies only if a curated Earth analog record exists with documented evidence for a LUNAR
    task. Phase 1 has no claim table and Phase 2 curation registers Mars tasks only (owner decision
    D-P2-02: no unsupported Earth lunar analog), so the selection falls back to a synthetic environment.
    """
    counts = {"earth_analog_regions": None, "lunar_task_claims": 0}
    if engine is not None:
        try:
            with engine.connect() as conn:
                counts["earth_analog_regions"] = int(conn.execute(text(
                    "SELECT count(*) FROM region r JOIN planetary_body b ON b.id = r.body_id "
                    "WHERE b.code = 'earth' AND r.region_role = 'analog'")).scalar() or 0)
                has_claims = conn.execute(text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='site_task_claim'")).scalar()
                if has_claims:
                    counts["lunar_task_claims"] = int(conn.execute(text(
                        "SELECT count(*) FROM site_task_claim c JOIN research_task t ON t.id = c.task_id "
                        "WHERE t.applies_to IN ('moon','both') AND c.publication_state = 'published'")).scalar() or 0)
        except Exception as exc:  # report, never invent
            counts["error"] = f"{type(exc).__name__}: {exc}"
    candidates: list = []
    return {
        "objective": objective_code,
        "curated_record_counts": counts,
        "candidates": candidates,
        "selected": {
            "kind": "synthetic_environment",
            "code": "SYNTH-TRAINING-RANGE-1",
            "name": "Synthetic lunar-operations training range (procedural terrain)",
            "label": "Synthetic / Demonstration",
            "is_validated_lunar_analog": False,
            "why_selected": "No curated Earth analog record in ABAAD has documented evidence for a lunar "
                            "reconnaissance or navigation task, so no real Earth site is selected. A reproducible "
                            "synthetic training environment is used instead.",
            "tasks_supported": OBJECTIVES[0]["tasks_trained"],
            "relevant_properties": [
                "slopes up to and beyond the rover limit (crater walls, ridge flanks) - derived from the terrain",
                "a ridge that hides the target from the base station (communication occlusion) - template feature",
                "no-go boulder fields - template feature",
                "mapped crater landmarks for navigation corrections - derived",
            ],
            "cannot_reproduce": [
                "real lunar terrain, regolith, lighting or thermal conditions",
                "real rover terramechanics or energy use (no energy model is implemented)",
                "real RF propagation (only geometric line of sight is computed)",
                "any property of a specific Earth field site",
            ],
            "differences_from_moon": EARTH_MOON_DIFFERENCES,
            "note": "Using this environment does not establish that any Earth site is a validated lunar analog. "
                    "To run the scenario in the field, the team must substitute a surveyed site with its own DEM "
                    "and documented evidence.",
            "data_status": "synthetic",
        },
    }


def catalog() -> dict:
    from .config import DEFAULT_CONFIG, SPEED_PROFILES

    return {"bodies": BODIES, "regions": REGIONS, "objectives": OBJECTIVES, "sources": SOURCES,
            "default_config": DEFAULT_CONFIG, "speed_profiles_mps": SPEED_PROFILES}

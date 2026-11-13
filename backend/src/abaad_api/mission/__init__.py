"""Mission Lab: lunar rover training-scenario simulation (MVP).

Pure domain code (terrain, line of sight, route planning, communications,
navigation, simulation engine, report assembly). It has no FastAPI imports;
HTTP lives in ``abaad_api.routes.mission`` and persistence in ``store``.

Everything this package computes is a *training simulation* on a
procedurally generated, clearly labelled synthetic terrain. It is not a
flight-qualified navigation, RF or rover-dynamics model.
"""

SIMULATION_MODEL_VERSION = "mission-sim 1.0.0"
PLANNER_VERSION = "grid-astar 1.0.0"
REPORT_VERSION = "mission-report 1.0.0"

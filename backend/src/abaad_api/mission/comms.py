"""Communication link segments, propagation delay and data queue.

Three separate quantities are modelled:
  * propagation delay  = distance / c (one way; the round trip is reported
    only as a theoretical 2x estimate before system/processing overhead);
  * link availability  = geometric visibility of each segment, plus
    injected outages, segment by segment;
  * message delivery   = a data queue drained at an ASSUMED throughput only
    while the full rover -> ... -> Earth path is available.
No RF link budget is implemented, so no signal strength is reported.
"""

from __future__ import annotations

SPEED_OF_LIGHT_MPS = 299_792_458.0  # exact (SI definition)
# Reference mean Earth-Moon distance used for the delay estimate; the actual
# distance varies over the orbit. User-configurable.
EARTH_MOON_REFERENCE_DISTANCE_M = 384_400_000.0


def one_way_light_time_s(distance_m: float) -> float:
    return distance_m / SPEED_OF_LIGHT_MPS


def round_trip_estimate_s(distance_m: float) -> float:
    """Theoretical two-way propagation only, before any system or processing overhead."""
    return 2 * one_way_light_time_s(distance_m)


def outage_active(outages: list[dict], segment: str, t: float) -> bool:
    return any(o["segment"] == segment and o["start_s"] <= t < o["start_s"] + o["duration_s"] for o in outages)


def end_to_end(segments: dict, comm_mode: str) -> dict:
    """Combine segment availabilities into local and Earth path availability.

    ``segments`` maps name -> {"available": bool, ...}. A relay only helps if
    BOTH rover->relay and relay->base are available; nothing restores the
    Earth path if base->Earth is down.
    """
    direct = segments["rover_base"]["available"]
    via_relay = (comm_mode == "relay" and segments.get("rover_relay", {}).get("available", False)
                 and segments.get("relay_base", {}).get("available", False))
    local = direct or via_relay
    earth = local and segments["base_earth"]["available"]
    path = "direct" if direct else ("relay" if via_relay else "none")
    return {"local_link": local, "earth_path": earth, "active_path": path}

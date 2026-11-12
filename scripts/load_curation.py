"""Load the committed curation files (`curation/*.json`) into the database.

Idempotent: every table is upserted by its natural code (region.code,
publication.doi-or-url, research_task.code, dataset.code, claim.code via
(analog_region, task, reference_region)). Safe to run repeatedly.

This also enforces, at load time, the session correction that a
``site_task_claim`` can never be assigned evidence class ``A`` unless its
``supports`` source is ``full_text_checked`` (never from an abstract alone).
This is a stronger, load-time version of the ``trg_claim_publish_requires_support``
trigger, which only fires when a claim is moved to ``published``.

Usage: python scripts/load_curation.py [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from abaad_api.config import get_settings  # noqa: E402

CURATION_DIR = ROOT / "curation"


class CurationError(ValueError):
    """A curation record is missing a required provenance field, or otherwise invalid."""


def _require(record: dict, fields: list[str], where: str) -> None:
    missing = [f for f in fields if record.get(f) in (None, "")]
    if missing:
        raise CurationError(f"{where}: missing required field(s) {missing}")


def _load_json(name: str) -> dict:
    path = CURATION_DIR / name
    if not path.exists():
        raise CurationError(f"curation file not found: {path}")
    return json.loads(path.read_text())


def load_sources(conn: sqlite3.Connection) -> dict[str, int]:
    """Returns {source_code: publication_id}."""
    data = _load_json("sources.json")
    codes: dict[str, int] = {}
    for src in data["sources"]:
        _require(src, ["code", "title", "year", "source_type", "source_access", "accessed_on"], f"source {src.get('code')}")
        if not src.get("doi") and not src.get("url"):
            raise CurationError(f"source {src['code']}: needs a doi or a url")
        key = src.get("doi") or src.get("url")
        row = conn.execute("SELECT id FROM publication WHERE doi = ? OR url = ?", (src.get("doi"), src.get("url"))).fetchone()
        values = (
            src.get("doi"), src["title"], src["year"], src["source_access"], 1 if src.get("peer_reviewed") else 0,
            src["source_type"], src.get("authors"), src.get("institution"), src.get("url"), src.get("licence"),
            src.get("citation"), src["accessed_on"],
        )
        if row:
            pub_id = row[0]
            conn.execute(
                "UPDATE publication SET doi=?, title=?, year=?, source_access=?, peer_reviewed=?, source_type=?,"
                " authors=?, institution=?, url=?, licence=?, citation=?, accessed_on=? WHERE id=?",
                (*values, pub_id),
            )
        else:
            cur = conn.execute(
                "INSERT INTO publication (doi, title, year, source_access, peer_reviewed, source_type, authors,"
                " institution, url, licence, citation, accessed_on) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            pub_id = cur.lastrowid
        codes[src["code"]] = pub_id
        del key
    return codes


def load_regions(conn: sqlite3.Connection) -> dict[str, int]:
    """Returns {region_code: region_id}. Two passes: create rows, then set parent_region_id."""
    data = _load_json("regions.json")
    body_ids = {code: rid for code, rid in conn.execute("SELECT code, id FROM planetary_body")}
    codes: dict[str, int] = {}
    for r in data["regions"]:
        _require(r, ["code", "body", "region_role", "region_level", "validation_status", "name"], f"region {r.get('code')}")
        if r["body"] not in body_ids:
            raise CurationError(f"region {r['code']}: unknown body {r['body']!r}")
        row = conn.execute("SELECT id FROM region WHERE code = ?", (r["code"],)).fetchone()
        values = (
            r["code"], body_ids[r["body"]], r["region_role"], r["region_level"], r["validation_status"], r["name"],
            r.get("country_code"), r.get("site_type"), r.get("origin_status", "not_applicable"),
        )
        if row:
            region_id = row[0]
            conn.execute(
                "UPDATE region SET body_id=?, region_role=?, region_level=?, validation_status=?, name=?,"
                " country_code=?, site_type=?, origin_status=? WHERE id=?",
                (*values[1:], region_id),
            )
        else:
            cur = conn.execute(
                "INSERT INTO region (code, body_id, region_role, region_level, validation_status, name,"
                " country_code, site_type, origin_status) VALUES (?,?,?,?,?,?,?,?,?)",
                values,
            )
            region_id = cur.lastrowid
        codes[r["code"]] = region_id

    for r in data["regions"]:
        parent_id = codes[r["parent_code"]] if r.get("parent_code") else None
        conn.execute("UPDATE region SET parent_region_id = ? WHERE id = ?", (parent_id, codes[r["code"]]))

    for r in data["regions"]:
        for alias in r.get("aliases", []):
            exists = conn.execute(
                "SELECT 1 FROM region_alias WHERE region_id = ? AND alias = ?", (codes[r["code"]], alias["alias"])
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO region_alias (region_id, alias, alias_kind, language) VALUES (?,?,?,?)",
                    (codes[r["code"]], alias["alias"], alias["alias_kind"], alias.get("language")),
                )
    return codes


def load_geometries(conn: sqlite3.Connection, region_codes: dict[str, int], source_codes: dict[str, int]) -> None:
    data = _load_json("geometries.json")
    kept_geometry_keys: set[tuple[int, str]] = set()
    kept_gap_keys: set[tuple[int, str]] = set()
    for g in data["geometries"]:
        _require(
            g, ["region_code", "geometry_role", "encoding", "geometry_text", "crs_code", "coordinate_units",
                "latitude_type", "longitude_direction", "longitude_domain", "axis_order", "geometry_status",
                "geometry_method", "source_code", "uncertainty_note"],
            f"geometry for {g.get('region_code')}",
        )
        region_id = region_codes[g["region_code"]]
        kept_geometry_keys.add((region_id, g["geometry_role"]))
        body_id = conn.execute("SELECT body_id FROM region WHERE id = ?", (region_id,)).fetchone()[0]
        pub_id = source_codes[g["source_code"]]
        exists = conn.execute(
            "SELECT id FROM region_geometry WHERE region_id = ? AND geometry_role = ?", (region_id, g["geometry_role"])
        ).fetchone()
        values = (
            region_id, body_id, g["geometry_role"], g["encoding"], g["geometry_text"], g["crs_code"],
            g["coordinate_units"], g["latitude_type"], g["longitude_direction"], g["longitude_domain"],
            g["axis_order"], g.get("min_x"), g.get("min_y"), g.get("max_x"), g.get("max_y"),
            g["geometry_status"], pub_id, g.get("source_locator"), g["geometry_method"],
            g.get("positional_uncertainty_m"), g["uncertainty_note"],
        )
        if exists:
            conn.execute(
                "UPDATE region_geometry SET body_id=?, encoding=?, geometry_text=?, crs_code=?, coordinate_units=?,"
                " latitude_type=?, longitude_direction=?, longitude_domain=?, axis_order=?, min_x=?, min_y=?,"
                " max_x=?, max_y=?, geometry_status=?, source_publication_id=?, source_locator=?, geometry_method=?,"
                " positional_uncertainty_m=?, uncertainty_note=? WHERE id=?",
                (values[1], *values[3:], exists[0]),
            )
        else:
            conn.execute(
                "INSERT INTO region_geometry (region_id, body_id, geometry_role, encoding, geometry_text, crs_code,"
                " coordinate_units, latitude_type, longitude_direction, longitude_domain, axis_order, min_x, min_y,"
                " max_x, max_y, geometry_status, source_publication_id, source_locator, geometry_method,"
                " positional_uncertainty_m, uncertainty_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
    for gap in data.get("gaps", []):
        _require(gap, ["region_code", "slot", "state", "reason"], f"gap for {gap.get('region_code')}")
        region_id = region_codes[gap["region_code"]]
        kept_gap_keys.add((region_id, gap["slot"]))
        exists = conn.execute(
            "SELECT id FROM coverage_gap WHERE region_id = ? AND slot = ?", (region_id, gap["slot"])
        ).fetchone()
        if exists:
            conn.execute(
                "UPDATE coverage_gap SET state=?, reason=?, resolution_hint=? WHERE id=?",
                (gap["state"], gap["reason"], gap.get("resolution_hint"), exists[0]),
            )
        else:
            conn.execute(
                "INSERT INTO coverage_gap (region_id, slot, state, reason, resolution_hint) VALUES (?,?,?,?,?)",
                (region_id, gap["slot"], gap["state"], gap["reason"], gap.get("resolution_hint")),
            )

    # Hardening F-10: both tables are loader-managed; remove anything stale.
    for row_id, region_id, role in conn.execute("SELECT id, region_id, geometry_role FROM region_geometry"):
        if (region_id, role) not in kept_geometry_keys:
            conn.execute("DELETE FROM region_geometry WHERE id = ?", (row_id,))
    for row_id, region_id, slot in conn.execute("SELECT id, region_id, slot FROM coverage_gap"):
        if (region_id, slot) not in kept_gap_keys:
            conn.execute("DELETE FROM coverage_gap WHERE id = ?", (row_id,))


# Session correction + hardening F-07: class A requires a 'supports' source that
# is both full_text_checked (the COMPLETE source, not merely most of it -- see
# F-06) and peer-reviewed. Class B needs a program_page/data_release or
# peer-reviewed supports source (abstract_only/partial_full_text qualify here).
# A claim with NO supporting source at all is rejected outright, regardless of
# publication_state -- drafts are validated exactly like published claims; the
# publish-time trigger (trg_claim_publish_requires_support) is a second,
# independent layer, not the only check.
def _check_class_matches_access(claim_code: str, claim_class: str, supports: list[dict], source_codes_meta: dict[str, dict]) -> None:
    if not supports:
        raise CurationError(f"claim {claim_code}: needs at least one 'supports' source; a claim is never silently accepted without one")
    qualifies_a = any(
        source_codes_meta[s["source_code"]]["source_access"] == "full_text_checked"
        and source_codes_meta[s["source_code"]]["peer_reviewed"]
        for s in supports
    )
    qualifies_b = any(
        source_codes_meta[s["source_code"]]["source_type"] in ("program_page", "data_release")
        or source_codes_meta[s["source_code"]]["peer_reviewed"]
        for s in supports
    )
    if claim_class == "A" and not qualifies_a:
        raise CurationError(
            f"claim {claim_code}: class A requires a full_text_checked (the COMPLETE source), peer-reviewed"
            " supports source -- never assigned from an abstract, a partial read, or a secondary record"
        )
    if claim_class == "B" and not qualifies_b:
        raise CurationError(f"claim {claim_code}: class B requires a program_page/data_release or peer-reviewed supports source")


def load_claims(
    conn: sqlite3.Connection, region_codes: dict[str, int], source_codes: dict[str, int]
) -> None:
    data = _load_json("claims.json")
    task_codes = {code: tid for code, tid in conn.execute("SELECT code, id FROM research_task")}
    body_ids = {code: rid for code, rid in conn.execute("SELECT code, id FROM planetary_body")}
    task_meta = {tid: applies_to for tid, applies_to in conn.execute("SELECT id, applies_to FROM research_task")}
    source_meta = {
        row[0]: {"source_access": row[1], "peer_reviewed": bool(row[2]), "source_type": row[3]}
        for row in conn.execute(
            "SELECT p.id, p.source_access, p.peer_reviewed, p.source_type FROM publication p"
        )
    }
    # Re-key source_meta by curation source code for the validator.
    meta_by_code = {code: source_meta[pub_id] for code, pub_id in source_codes.items()}

    kept_claim_keys: set[tuple[int, int, int | None]] = set()

    for c in data["claims"]:
        _require(
            c, ["code", "analog_region_code", "task_code", "claim_evidence_class", "reference_pairing_basis",
                "reference_body", "supported_claim", "similarities", "differences", "not_supported",
                "spatial_scale", "limitations"],
            f"claim {c.get('code')}",
        )
        supports = [s for s in c.get("sources", []) if s["role"] == "supports"]
        _check_class_matches_access(c["code"], c["claim_evidence_class"], supports, meta_by_code)

        analog_id = region_codes[c["analog_region_code"]]
        task_id = task_codes[c["task_code"]]
        reference_id = region_codes[c["reference_region_code"]] if c.get("reference_region_code") else None
        if c["reference_body"] not in body_ids:
            raise CurationError(f"claim {c['code']}: unknown reference_body {c['reference_body']!r}")
        reference_body_id = body_ids[c["reference_body"]]

        # Hardening F-01: validate the claim/body/task matrix at load time too
        # (the database trigger trg_claim_reference_matrix_* is the hard gate;
        # this gives a clear, claim-code-scoped error before it ever gets there).
        if c["reference_body"] == "earth":
            raise CurationError(f"claim {c['code']}: reference_body must never be earth")
        applies_to = task_meta[task_id]
        if applies_to != "both" and applies_to != c["reference_body"]:
            raise CurationError(
                f"claim {c['code']}: task {c['task_code']!r} applies_to={applies_to!r} but reference_body="
                f"{c['reference_body']!r}"
            )
        if reference_id is not None:
            region_body = conn.execute("SELECT body_id FROM region WHERE id = ?", (reference_id,)).fetchone()[0]
            if region_body != reference_body_id:
                raise CurationError(f"claim {c['code']}: reference_region_code's body does not match reference_body")

        kept_claim_keys.add((analog_id, task_id, reference_id))
        row = conn.execute(
            "SELECT id FROM site_task_claim WHERE analog_region_id = ? AND task_id = ? AND"
            " (reference_region_id = ? OR (reference_region_id IS NULL AND ? IS NULL))",
            (analog_id, task_id, reference_id, reference_id),
        ).fetchone()
        values = (
            analog_id, task_id, reference_id, reference_body_id, c["claim_evidence_class"],
            c["reference_pairing_basis"], c["supported_claim"], c["similarities"], c["differences"],
            c["not_supported"], c["spatial_scale"], c["limitations"], c.get("publication_state", "draft"),
        )
        if row:
            claim_id = row[0]
            conn.execute(
                "UPDATE site_task_claim SET reference_body_id=?, claim_evidence_class=?, reference_pairing_basis=?,"
                " supported_claim=?, similarities=?, differences=?, not_supported=?, spatial_scale=?,"
                " limitations=?, publication_state=? WHERE id=?",
                (*values[3:], claim_id),
            )
            conn.execute("DELETE FROM site_task_claim_source WHERE claim_id = ?", (claim_id,))
        else:
            cur = conn.execute(
                "INSERT INTO site_task_claim (analog_region_id, task_id, reference_region_id, reference_body_id,"
                " claim_evidence_class, reference_pairing_basis, supported_claim, similarities, differences,"
                " not_supported, spatial_scale, limitations, publication_state)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            claim_id = cur.lastrowid
        for s in c.get("sources", []):
            conn.execute(
                "INSERT INTO site_task_claim_source (claim_id, publication_id, role, locator, note) VALUES (?,?,?,?,?)",
                (claim_id, source_codes[s["source_code"]], s["role"], s.get("locator"), s.get("note")),
            )

    # Hardening F-10: site_task_claim is entirely loader-managed (the API is
    # read-only), so any row whose (analog, task, reference) key is no longer
    # in the current curation/claims.json -- e.g. the old Atacama-wide
    # drilling claim -- is stale and must be removed, not left behind.
    all_rows = conn.execute("SELECT id, analog_region_id, task_id, reference_region_id FROM site_task_claim").fetchall()
    for claim_id, analog_id, task_id, reference_id in all_rows:
        if (analog_id, task_id, reference_id) not in kept_claim_keys:
            conn.execute("DELETE FROM site_task_claim WHERE id = ?", (claim_id,))


def load_datasets(conn: sqlite3.Connection) -> dict[str, int]:
    data = _load_json("datasets.json")
    body_ids = {code: rid for code, rid in conn.execute("SELECT code, id FROM planetary_body")}
    codes: dict[str, int] = {}
    # horizontal_crs is deliberately NOT required (hardening F-02): a product
    # with horizontal_crs_status='pending' stores horizontal_crs=NULL rather
    # than a guessed IAU/EPSG code.
    required = [
        "code", "provider", "collection_id", "product_id", "product_name", "product_version", "body", "variable",
        "surface_type", "horizontal_crs_status", "vertical_reference", "value_units", "native_resolution_value",
        "native_resolution_unit", "file_format", "licence_summary", "access_conditions", "source_url",
    ]
    for d in data["datasets"]:
        _require(d, required, f"dataset {d.get('code')}")
        if d["body"] not in body_ids:
            raise CurationError(f"dataset {d['code']}: unknown body {d['body']!r}")
        if d["horizontal_crs_status"] == "verified" and not d.get("horizontal_crs"):
            raise CurationError(f"dataset {d['code']}: horizontal_crs_status='verified' needs a non-null horizontal_crs")
        row = conn.execute("SELECT id FROM dataset WHERE code = ?", (d["code"],)).fetchone()
        values = (
            d["code"], d["provider"], d.get("collection_id"), d["product_id"], d["product_name"], d["product_version"],
            body_ids[d["body"]], d["variable"], d["surface_type"], d.get("horizontal_crs"), d["horizontal_crs_status"],
            d["vertical_reference"], d["value_units"], d.get("nodata_value"), d["native_resolution_value"],
            d["native_resolution_unit"], d.get("temporal_coverage"), d["file_format"], d["licence_summary"],
            d["access_conditions"], d["source_url"], d.get("download_url"),
        )
        if row:
            dataset_id = row[0]
            conn.execute(
                "UPDATE dataset SET provider=?, collection_id=?, product_id=?, product_name=?, product_version=?,"
                " body_id=?, variable=?, surface_type=?, horizontal_crs=?, horizontal_crs_status=?,"
                " vertical_reference=?, value_units=?, nodata_value=?, native_resolution_value=?,"
                " native_resolution_unit=?, temporal_coverage=?, file_format=?, licence_summary=?,"
                " access_conditions=?, source_url=?, download_url=? WHERE id=?",
                (*values[1:], dataset_id),
            )
        else:
            cur = conn.execute(
                "INSERT INTO dataset (code, provider, collection_id, product_id, product_name, product_version,"
                " body_id, variable, surface_type, horizontal_crs, horizontal_crs_status, vertical_reference,"
                " value_units, nodata_value, native_resolution_value, native_resolution_unit, temporal_coverage,"
                " file_format, licence_summary, access_conditions, source_url, download_url)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            dataset_id = cur.lastrowid
        codes[d["code"]] = dataset_id

    # Hardening F-10: dataset is loader-managed too; drop anything no longer
    # in curation/datasets.json (e.g. if a product is ever withdrawn).
    kept_ids = set(codes.values())
    for row_id, in conn.execute("SELECT id FROM dataset"):
        if row_id not in kept_ids:
            conn.execute("DELETE FROM dataset WHERE id = ?", (row_id,))
    return codes


def load_all(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("BEGIN")
    try:
        source_codes = load_sources(conn)
        region_codes = load_regions(conn)
        load_geometries(conn, region_codes, source_codes)
        load_claims(conn, region_codes, source_codes)
        dataset_codes = load_datasets(conn)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return {
        "sources": len(source_codes), "regions": len(region_codes), "datasets": len(dataset_codes),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=get_settings().db_path)
    args = parser.parse_args(argv)
    if not args.db.exists():
        print(f"ERROR: database {args.db} does not exist. Run `make migrate` first.", file=sys.stderr)
        return 1
    try:
        counts = load_all(args.db)
    except CurationError as exc:
        print(f"CURATION ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Loaded curation data: {counts['sources']} sources, {counts['regions']} regions, {counts['datasets']} datasets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

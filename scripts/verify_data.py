"""Validate data/manifest.json against the files under data/, and (Phase 2)
the curated database against the Phase 2 spec section 13 rules: provenance
completeness, geometry validity, coverage-gap consistency, status agreement
and no test/synthetic codes in a production database.

* No entries and no files  -> "No data files yet" (success).
* Every manifest entry must exist with the recorded size and SHA-256.
* Files present under data/ but missing from the manifest are reported (failure).

Usage: python scripts/verify_data.py [--data-dir DIR] [--db PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import shapely.wkt
from shapely.errors import ShapelyError

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {"README.md", "manifest.json", ".gitkeep", ".DS_Store"}

# Phase 2 spec section 17: verification gates still open. Listed as
# "candidates" information, never silently resolved.
OPEN_VERIFICATION_GATES = [
    "V-1 Dakhla Table 1 / Figure 13 (owner-reported, not independently verified)",
    "V-2 Yungay vs ARADS coordinates (owner DMS value does not match Stoker et al. 2023's decimal point)",
    "V-3 Holuhraun outline source",
    "V-4 source-traced extents for North Polar Sand Sea and Elysium Planitia",
    "V-5 Arabia Terra latitude convention and datum (assumed, not stated)",
    "V-6 University Valley position",
    "V-7 access routes: Copernicus GLO-30, REMA CRS/tile index, MOLA/LOLA PDS4 paths",
    "V-8 can GDAL/rasterio open PDS3 .LBL/.IMG? (not tested)",
    "V-9 CRS declarations against the real MOLA/LOLA product labels",
    "V-10 read full texts of S01, S02, S05, S07 and upgrade source_access",
    "V-11 latitude coverage of SRTM/ASTER; GLO-30 tile pixel size at high latitude",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(data_dir: Path) -> tuple[bool, list[str]]:
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        return False, [f"ERROR: {manifest_path} not found"]
    manifest = json.loads(manifest_path.read_text())
    entries = manifest.get("files", [])
    on_disk = {
        p.relative_to(data_dir).as_posix()
        for p in data_dir.rglob("*")
        if p.is_file() and p.name not in IGNORED
    }
    messages: list[str] = []
    ok = True
    listed = set()
    for entry in entries:
        rel = entry["path"]
        listed.add(rel)
        path = data_dir / rel
        if not path.exists():
            ok = False
            messages.append(f"MISSING   {rel}")
            continue
        if "bytes" in entry and path.stat().st_size != entry["bytes"]:
            ok = False
            messages.append(f"SIZE      {rel}: expected {entry['bytes']}, found {path.stat().st_size}")
            continue
        digest = sha256(path)
        if digest != entry["sha256"]:
            ok = False
            messages.append(f"CHECKSUM  {rel}: expected {entry['sha256'][:12]}…, found {digest[:12]}…")
        else:
            messages.append(f"OK        {rel}")
    for rel in sorted(on_disk - listed):
        ok = False
        messages.append(f"UNLISTED  {rel} (present in data/ but not in manifest.json)")
    if not entries and not on_disk:
        messages.append("No data files yet: manifest has 0 entries and data/ holds no data files. OK.")
    return ok, messages


def _expected_status(validation_status: str, has_published_ab_claim: bool, has_source_traced_geometry: bool,
                      has_any_own_claim: bool, is_reference: bool) -> str | None:
    """Section 4.2 of the Phase 2 spec. Returns the one rule that was violated, or None."""
    if validation_status == "site_confirmed" and not (has_published_ab_claim and has_source_traced_geometry):
        return "site_confirmed requires a published class A/B claim AND a source_traced geometry"
    if validation_status == "regional_only" and has_any_own_claim and not is_reference:
        return "regional_only is for a parent/context region with no site-level claim of its own, or a Mars reference region"
    return None


def verify_curation_db(db_path: Path) -> tuple[bool, list[str]]:
    """Phase 2 spec section 13. Returns (ok, messages); 'information' lines never fail the check."""
    if not db_path.exists():
        return True, [f"INFO      no database at {db_path}; skipping curation checks"]
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    ok = True
    messages: list[str] = []

    def error(msg: str) -> None:
        nonlocal ok
        ok = False
        messages.append(f"ERROR     {msg}")

    def info(msg: str) -> None:
        messages.append(f"INFO      {msg}")

    # --- Inventory (information only) ---------------------------------------
    for label, sql in [
        ("regions by body/role/level",
         "SELECT b.code, r.region_role, r.region_level, count(*) FROM region r"
         " JOIN planetary_body b ON b.id = r.body_id GROUP BY 1,2,3 ORDER BY 1,2,3"),
        ("sources by type/access", "SELECT source_type, source_access, count(*) FROM publication GROUP BY 1,2 ORDER BY 1,2"),
        ("claims by class/state",
         "SELECT claim_evidence_class, publication_state, count(*) FROM site_task_claim GROUP BY 1,2 ORDER BY 1,2"),
        ("datasets by body", "SELECT b.code, count(*) FROM dataset d JOIN planetary_body b ON b.id = d.body_id GROUP BY 1"),
    ]:
        rows = conn.execute(sql).fetchall()
        info(f"inventory: {label}: {rows}")
    asset_bytes = conn.execute("SELECT coalesce(sum(size_bytes), 0), count(*) FROM data_asset").fetchone()
    info(f"inventory: {asset_bytes[1]} data assets, {asset_bytes[0]} bytes total")

    # --- Provenance -----------------------------------------------------------
    for pub_id, title in conn.execute(
        "SELECT id, title FROM publication WHERE source_type IS NULL OR (authors IS NULL AND institution IS NULL)"
        " OR citation IS NULL OR accessed_on IS NULL"
    ):
        error(f"publication {pub_id} ({title!r}): missing source_type/authors-or-institution/citation/accessed_on")
    for geom_id, in conn.execute(
        "SELECT id FROM region_geometry WHERE geometry_status <> 'undefined' AND"
        " (geometry_method IS NULL OR uncertainty_note IS NULL"
        " OR (source_publication_id IS NULL AND source_dataset_id IS NULL))"
    ):
        error(f"region_geometry {geom_id}: non-undefined geometry without source/method/uncertainty_note")
    non_full_text_a = conn.execute(
        "SELECT count(*) FROM site_task_claim stc JOIN site_task_claim_source s ON s.claim_id = stc.id"
        " JOIN publication p ON p.id = s.publication_id"
        " WHERE stc.claim_evidence_class = 'A' AND s.role = 'supports' AND p.source_access <> 'full_text_checked'"
    ).fetchone()[0]
    info(f"provenance: {non_full_text_a} class-A claims resting on a non-full-text-checked supports source")

    # --- Geometry ---------------------------------------------------------------
    for geom_id, geom_text, encoding in conn.execute("SELECT id, geometry_text, encoding FROM region_geometry"):
        try:
            if encoding == "ogc_wkt":
                shapely.wkt.loads(geom_text)
            elif encoding == "rfc7946_geojson":
                import shapely.geometry

                shapely.geometry.shape(json.loads(geom_text))
        except (ShapelyError, ValueError, json.JSONDecodeError) as exc:
            error(f"region_geometry {geom_id}: invalid geometry ({exc})")
    parentless_with_geometry = conn.execute(
        "SELECT count(*) FROM region r WHERE r.parent_region_id IS NULL AND NOT EXISTS"
        " (SELECT 1 FROM region_geometry g WHERE g.region_id = r.id)"
    ).fetchone()[0]
    info(f"geometry: {parentless_with_geometry} parent/top-level regions have no geometry row yet")

    # --- Status agreement ---------------------------------------------------------
    for region_id, code, status, region_role in conn.execute("SELECT id, code, validation_status, region_role FROM region"):
        has_ab_published = conn.execute(
            "SELECT count(*) FROM site_task_claim WHERE analog_region_id = ? AND publication_state = 'published'"
            " AND claim_evidence_class IN ('A','B')",
            (region_id,),
        ).fetchone()[0] > 0
        has_source_traced_geom = conn.execute(
            "SELECT count(*) FROM region_geometry WHERE region_id = ? AND geometry_status = 'source_traced'",
            (region_id,),
        ).fetchone()[0] > 0
        has_any_own_claim = conn.execute(
            "SELECT count(*) FROM site_task_claim WHERE analog_region_id = ?", (region_id,)
        ).fetchone()[0] > 0
        violation = _expected_status(status, has_ab_published, has_source_traced_geom, has_any_own_claim, region_role == "reference")
        if violation:
            error(f"region {code}: validation_status={status!r} disagrees with section 4.2 ({violation})")

    # --- Gaps -----------------------------------------------------------------
    both = conn.execute(
        "SELECT r.code, g.slot FROM coverage_gap g JOIN region r ON r.id = g.region_id"
        " WHERE g.slot = 'geometry' AND EXISTS (SELECT 1 FROM region_geometry rg WHERE rg.region_id = g.region_id)"
    ).fetchall()
    for code, slot in both:
        error(f"region {code}: both a coverage_gap and a region_geometry row exist for slot {slot!r}")
    for code, slot, state, reason in conn.execute(
        "SELECT r.code, g.slot, g.state, g.reason FROM coverage_gap g JOIN region r ON r.id = g.region_id ORDER BY r.code, g.slot"
    ):
        info(f"gap: {code}/{slot} [{state}] {reason}")

    # --- Candidates (information only) -----------------------------------------
    for code, cls, state in conn.execute(
        "SELECT ar.code, stc.claim_evidence_class, stc.publication_state FROM site_task_claim stc"
        " JOIN region ar ON ar.id = stc.analog_region_id WHERE stc.publication_state <> 'published' OR stc.claim_evidence_class = 'C'"
    ):
        info(f"candidate: claim on {code} is class {cls}, state {state} -- not yet published")
    for code, in conn.execute("SELECT code FROM region WHERE validation_status = 'validation_pending'"):
        info(f"candidate: region {code} is validation_pending")
    for gate in OPEN_VERIFICATION_GATES:
        info(f"candidate: open verification gate {gate}")

    # --- Test data --------------------------------------------------------------
    for code, in conn.execute("SELECT code FROM region WHERE code LIKE 'TEST-%' OR code LIKE 'SYNTH-%'"):
        error(f"region {code}: TEST-/SYNTH- codes must never appear in a production database")
    for code, in conn.execute("SELECT code FROM dataset WHERE code LIKE 'TEST-%' OR code LIKE 'SYNTH-%'"):
        error(f"dataset {code}: TEST-/SYNTH- codes must never appear in a production database")

    gap_count = sum(1 for m in messages if m.startswith("INFO      gap:"))
    conn.close()
    messages.append(f"gaps: {len(both)} inconsistent with an existing geometry, {gap_count} recorded with reasons")
    messages.append("Scientific completeness is not claimed by this report.")
    return ok, messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--db", type=Path, default=ROOT / "var" / "abaad.sqlite")
    args = parser.parse_args()
    ok, messages = verify(args.data_dir)
    print("\n".join(messages))
    print("verify-data (files): PASSED" if ok else "verify-data (files): FAILED")

    db_ok, db_messages = verify_curation_db(args.db)
    print("\n".join(db_messages))
    print("verify-data (curation): PASSED" if db_ok else "verify-data (curation): FAILED")

    overall_ok = ok and db_ok
    print("verify-data: PASSED" if overall_ok else "verify-data: FAILED")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())

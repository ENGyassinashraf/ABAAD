"""The science engine must stay a plain-Python package: no web framework,
database or UI imports (Revision 1, Document 1)."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import abaad_science

FORBIDDEN = {"fastapi", "starlette", "sqlalchemy", "alembic", "uvicorn", "sqlite3", "maplibre"}
PACKAGE_DIR = Path(abaad_science.__file__).parent


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_forbidden_imports_in_source():
    for path in PACKAGE_DIR.rglob("*.py"):
        bad = _imported_roots(path) & FORBIDDEN
        assert not bad, f"{path.name} imports {bad}"


def test_importing_engine_loads_no_web_or_db_modules():
    code = (
        "import sys, abaad_science; "
        f"bad = {sorted(FORBIDDEN)!r}; "
        "print(','.join(m for m in bad if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""


def test_public_api_is_exactly_the_scoring_engine():
    assert set(abaad_science.__all__) == {
        "DEFAULT_MIN_COVERAGE", "METHODOLOGY_BASELINE", "RUBRIC", "DimensionResult", "ScoreResult",
        "rank_candidates", "score_candidate", "similarity_from_rubric",
    }

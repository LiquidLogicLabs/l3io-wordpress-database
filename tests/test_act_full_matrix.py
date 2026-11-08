"""Act must replay the full CI matrix — never a LOCAL_ACT-narrowed subset.

Owner rule (Shawn, 2026-11-08): narrowed local matrices are how engine-specific
failures escape. The test job starts databases from steps (like transfer), so
act can run every Python × engine cell with --concurrent-jobs 1.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_matrices_are_not_narrowed_under_local_act() -> None:
    document = yaml.safe_load(CI.read_text(encoding="utf-8"))
    jobs = document["jobs"]
    assert jobs, "ci.yml has no jobs — vacuous"
    offenders: list[str] = []
    for job_id, job in jobs.items():
        matrix = ((job or {}).get("strategy") or {}).get("matrix") or {}
        if not isinstance(matrix, dict):
            continue
        for axis, value in matrix.items():
            if isinstance(value, str) and "LOCAL_ACT" in value:
                offenders.append(f"{job_id}.matrix.{axis}")
    assert not offenders, (
        "LOCAL_ACT must not narrow matrices (owner rule 2026-11-08); "
        f"offenders: {offenders}"
    )


def test_test_job_starts_database_from_a_step_not_services() -> None:
    """Workflow services bind ports for every act matrix leg up front."""
    document = yaml.safe_load(CI.read_text(encoding="utf-8"))
    test = document["jobs"]["test"]
    assert "services" not in test, (
        "test job must not use workflow services:; use make test-engine so act "
        "can run the full matrix without a shared 3306 collision"
    )
    steps = " ".join(str(s.get("run", "")) for s in test.get("steps") or [])
    assert "test-engine" in steps, "test job no longer calls make test-engine"


def test_test_matrix_covers_every_python_and_engine() -> None:
    document = yaml.safe_load(CI.read_text(encoding="utf-8"))
    matrix = document["jobs"]["test"]["strategy"]["matrix"]
    assert matrix["python"] == ["3.11", "3.12", "3.13", "3.14"]
    engines = {row["name"]: row["image"] for row in matrix["engine"]}
    assert engines == {
        "mysql80": "mysql:8.0",
        "mysql84": "mysql:8.4",
        "mysql97": "mysql:9.7",
        "mariadb": "mariadb:11.4",
        "mariadb102": "mariadb:10.2",
    }

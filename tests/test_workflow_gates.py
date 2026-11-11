"""Workflow conditions a release depends on.

``publish.yml`` must start only on a three-component release tag: a floating
``v0`` or ``v0.1`` pushed by hand must never start a publish. Its release notes
must start from the previous three-component tag, because a changelog builder
left to detect its lower bound takes the nearest tag, which a floating tag on
the same commit would be -- and the notes would read "no changes".
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
FLOATING = ["v0", "v0.1", "v1", "v1.2"]
RELEASES = ["v0.0.2", "v0.1.0", "v1.2.3"]


def _workflows() -> list[Path]:
    found = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert found, f"no workflows under {WORKFLOWS} -- an empty scope skips, not fails"
    return found


def _load(path: Path) -> dict[Any, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def tag_triggers(workflow: dict[Any, Any]) -> list[str]:
    # PyYAML (YAML 1.1) parses the key `on` as the boolean True.
    on = workflow.get("on", workflow.get(True)) or {}
    return list(((on.get("push") or {}) if isinstance(on, dict) else {}).get("tags", []))


def starts_a_run(tag: str, patterns: list[str]) -> bool:
    """GitHub's tag filter: the last matching pattern wins, `!` negates."""
    hit = False
    for pattern in patterns:
        if fnmatchcase(tag, pattern.removeprefix("!")):
            hit = not pattern.startswith("!")
    return hit


@pytest.mark.parametrize("path", _workflows(), ids=lambda p: p.name)
def test_no_floating_tag_starts_a_workflow(path: Path) -> None:
    patterns = tag_triggers(_load(path))
    started = [t for t in FLOATING if starts_a_run(t, patterns)]
    assert not started, f"{path.name} runs on floating tag(s) {started}: {patterns}"


def test_a_release_tag_still_starts_publish() -> None:
    patterns = tag_triggers(_load(WORKFLOWS / "publish.yml"))
    assert patterns, "publish.yml has no tag trigger -- the check above is vacuous"
    assert all(starts_a_run(t, patterns) for t in RELEASES), patterns
    assert not starts_a_run("v0.0.0", patterns), "v0.0.0 is the baseline, never a release"


def test_the_tag_filter_check_reads_negation_and_order() -> None:
    assert starts_a_run("v0.0.2", ["v*", "!v0.0.0"])
    assert not starts_a_run("v0.0.0", ["v*", "!v0.0.0"])
    assert starts_a_run("v0", ["v*"]), "a bare v* filter does start a run on a floating tag"
    assert not starts_a_run("v0", ["v*.*.*"])


def test_release_notes_never_start_from_a_floating_tag() -> None:
    job = (_load(WORKFLOWS / "publish.yml").get("jobs") or {}).get("release") or {}
    steps: list[dict[str, Any]] = job.get("steps", [])
    assert steps, "publish.yml has no release job -- this check is vacuous"
    builder = next(
        s
        for s in steps
        if str(s.get("uses", "")).startswith("LiquidLogicLabs/git-action-release-changelog-builder")
    )
    assert "steps.previous.outputs.tag" in str(builder.get("with", {}).get("from-tag", ""))
    previous = next((s for s in steps if s.get("id") == "previous"), None)
    assert previous is not None, "no step with id 'previous' computes the lower bound"
    assert "--match 'v[0-9]*.[0-9]*.[0-9]*'" in str(previous.get("run", ""))
    assert steps.index(previous) < steps.index(builder)


def _release_steps() -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for job in (_load(WORKFLOWS / "release.yml").get("jobs") or {}).values():
        steps += job.get("steps", [])
    return steps


def _index(steps: list[dict[str, Any]], action: str) -> int:
    found = [i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith(action)]
    assert found, f"release.yml has no step using {action}"
    return found[-1]


def test_floating_tags_move_after_the_release_tag_and_before_the_dispatch() -> None:
    steps = _release_steps()
    created = _index(steps, "LiquidLogicLabs/git-action-tag-create-update")
    floated = _index(steps, "LiquidLogicLabs/git-action-tag-floating-version")
    dispatched = _index(steps, "LiquidLogicLabs/git-action-trigger-workflow")
    assert created < floated < dispatched


def test_the_latest_release_lookup_ignores_floating_tags() -> None:
    steps = _release_steps()
    lookup = steps[_index(steps, "LiquidLogicLabs/git-action-tag-info")]
    assert lookup.get("with", {}).get("tag-format") == "v*.*.*"


def test_github_release_waits_on_publish_pypi_without_failing_when_skipped() -> None:
    job = (_load(WORKFLOWS / "publish.yml").get("jobs") or {}).get("release") or {}
    needs = job.get("needs") or []
    assert "publish-pypi" in needs
    assert "smoke" in needs
    condition = str(job.get("if", ""))
    assert "always()" in condition
    assert "needs.publish-pypi.result != 'failure'" in condition


def test_an_index_upload_runs_only_on_a_release_tag() -> None:
    """A dispatch from a branch would upload a .dev build, and PyPI burns the filename."""
    jobs: dict[str, Any] = _load(WORKFLOWS / "publish.yml").get("jobs") or {}
    uploads = [
        name
        for name, job in jobs.items()
        if any("pypa/gh-action-pypi-publish" in str(s.get("uses", "")) for s in job["steps"])
    ]
    assert uploads, "publish.yml uploads to no index -- this check is vacuous"
    ungated = [n for n in uploads if "startsWith(github.ref, 'refs/tags/v')" not in jobs[n]["if"]]
    assert not ungated, f"{ungated} can upload from a branch ref"


def pypi_org_uploads_with_credentials(workflows: Path) -> list[str]:
    """pypa uploads to pypi.org that pass ``user`` or ``password`` (disables OIDC).

    TestPyPI may still use a token until a trusted publisher is registered there.
    """
    bad: list[str] = []
    for workflow in sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")]):
        document = _load(workflow)
        for job_id, job in (document.get("jobs") or {}).items():
            for step in (job or {}).get("steps") or []:
                if not str(step.get("uses", "")).startswith("pypa/gh-action-pypi-publish"):
                    continue
                with_ = step.get("with") or {}
                target = str(with_.get("repository-url", ""))
                if "test.pypi.org" in target:
                    continue
                for key in ("user", "password"):
                    if key in with_:
                        bad.append(f"{workflow.name}:{job_id} passes {key}= to pypi.org")
    return bad


def test_pypi_org_upload_uses_trusted_publishing() -> None:
    assert pypi_org_uploads_with_credentials(WORKFLOWS) == []


def test_a_pypi_org_token_is_caught(tmp_path: Path) -> None:
    (tmp_path / "token.yml").write_text(
        "on: push\njobs:\n  up:\n    steps:\n"
        "      - uses: pypa/gh-action-pypi-publish@release/v1\n"
        "        with:\n"
        "          password: ${{ secrets.PYPI_TOKEN }}\n",
        encoding="utf-8",
    )
    assert pypi_org_uploads_with_credentials(tmp_path) == [
        "token.yml:up passes password= to pypi.org"
    ]


def test_a_testpypi_token_is_allowed(tmp_path: Path) -> None:
    (tmp_path / "test.yml").write_text(
        "on: push\njobs:\n  up:\n    steps:\n"
        "      - uses: pypa/gh-action-pypi-publish@release/v1\n"
        "        with:\n"
        "          repository-url: https://test.pypi.org/legacy/\n"
        "          password: ${{ secrets.PYPI_TEST_TOKEN }}\n",
        encoding="utf-8",
    )
    assert pypi_org_uploads_with_credentials(tmp_path) == []


# ---- release assets must match this build ------------------------------------
#
# softprops (and a skipped git-action-release) can leave a second dispatch able
# to replace same-named assets. publish.yml skips creation when the release
# exists, then checks each dist file's sha256 (upload missing without --clobber;
# fail on mismatch).

_RELEASE_ACTIONS = ("git-action-release@", "action-gh-release@")
_WHEEL = "l3io_wordpress_database-9.9.9-py3-none-any.whl"
_SDIST = "l3io_wordpress_database-9.9.9.tar.gz"

_STUB_GH = """#!/usr/bin/env bash
set -eu
echo "$*" >> "$STUB_LOG"
case "$1 $2" in
  "release view") cat "$STUB_LISTING" ;;
  "release download")
    shift 3; name=""; dir=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --pattern) name=$2; shift 2 ;;
        --dir) dir=$2; shift 2 ;;
        *) shift ;;
      esac
    done
    cp "$STUB_ASSETS/$name" "$dir/$name" ;;
  "release upload") ;;
  *) echo "unexpected gh call: $*" >&2; exit 2 ;;
esac
"""


def _creates_a_release(step: dict[str, Any]) -> bool:
    uses = str(step.get("uses", ""))
    return any(a in uses for a in _RELEASE_ACTIONS) or "gh release create" in str(
        step.get("run", "")
    )


def _skip_flag(step: dict[str, Any]) -> str | None:
    with_ = step.get("with") or {}
    for key in ("skip-if-release-exists", "skip_if_exists"):
        if key in with_:
            return str(with_[key])
    return None


def _release_findings(doc: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for job_id, job in (doc.get("jobs") or {}).items():
        steps = job.get("steps") or []
        for i, step in enumerate(steps):
            if not _creates_a_release(step):
                continue
            where = f"{job_id}: {step.get('uses') or step.get('name')}"
            if str(_skip_flag(step)).lower() != "true":
                findings.append(f"{where} does not skip when the release already exists")
            checks = [
                s
                for s in steps[i + 1 :]
                if "gh release view" in str(s.get("run", ""))
                and "gh release upload" in str(s.get("run", ""))
            ]
            if not checks:
                findings.append(f"{where} has no later step checking the assets")
            elif any("--clobber" in str(s.get("run", "")) for s in checks):
                findings.append(f"{where}: the asset check may overwrite (--clobber)")
    return findings


def _publish_release_job(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return doc["jobs"]["release"]["steps"]


def _release_creator(doc: dict[str, Any]) -> dict[str, Any]:
    return next(s for s in _publish_release_job(doc) if _creates_a_release(s))


def _asset_step(doc: dict[str, Any]) -> dict[str, Any]:
    return next(
        s for s in _publish_release_job(doc) if "gh release upload" in str(s.get("run", ""))
    )


def test_there_is_a_release_step_to_check() -> None:
    assert any(
        _creates_a_release(s)
        for j in (_load(WORKFLOWS / "publish.yml").get("jobs") or {}).values()
        for s in j.get("steps") or []
    )


def test_every_release_step_tolerates_an_existing_release() -> None:
    for path in _workflows():
        assert _release_findings(_load(path)) == [], path.name


def test_the_release_rule_rejects_removing_the_asset_check() -> None:
    doc = _load(WORKFLOWS / "publish.yml")
    assert _release_findings(doc) == []
    _publish_release_job(doc).remove(_asset_step(doc))
    assert _release_findings(doc)


def test_the_release_rule_rejects_clobber() -> None:
    doc = _load(WORKFLOWS / "publish.yml")
    step = _asset_step(doc)
    step["run"] = step["run"].replace(
        'gh release upload "$TAG"', 'gh release upload --clobber "$TAG"'
    )
    assert _release_findings(doc)


def _digest(data: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(data).hexdigest()


def _run_asset_check(
    tmp_path: Path, release: dict[str, tuple[bytes, bool]]
) -> tuple[int, str, list[str]]:
    import os
    import subprocess

    work = tmp_path / "work"
    (work / "dist").mkdir(parents=True)
    (work / "dist" / _WHEEL).write_bytes(b"wheel")
    (work / "dist" / _SDIST).write_bytes(b"sdist")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "gh").write_text(_STUB_GH, encoding="utf-8")
    (bin_ / "gh").chmod(0o755)
    assets = tmp_path / "assets"
    assets.mkdir()
    rows = []
    for name, (data, recorded) in release.items():
        (assets / name).write_bytes(data)
        rows.append(f"{name}\t{_digest(data) if recorded else ''}\n")
    (tmp_path / "listing").write_text("".join(rows), encoding="utf-8")
    log = tmp_path / "gh.log"
    log.touch()
    env = {
        **os.environ,
        "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}",
        "STUB_LOG": str(log),
        "STUB_LISTING": str(tmp_path / "listing"),
        "STUB_ASSETS": str(assets),
        "TAG": "v9.9.9",
    }
    proc = subprocess.run(  # noqa: S603
        ["bash", "-c", _asset_step(_load(WORKFLOWS / "publish.yml"))["run"]],  # noqa: S607
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr, log.read_text().splitlines()


def _uploads(calls: list[str]) -> list[str]:
    return [c for c in calls if c.startswith("release upload")]


def test_the_asset_check_passes_a_release_that_already_has_this_build(tmp_path: Path) -> None:
    code, out, calls = _run_asset_check(
        tmp_path, {_WHEEL: (b"wheel", True), _SDIST: (b"sdist", True)}
    )
    assert code == 0, out
    assert _uploads(calls) == []


def test_the_asset_check_uploads_only_the_missing_name(tmp_path: Path) -> None:
    code, out, calls = _run_asset_check(tmp_path, {_WHEEL: (b"wheel", True)})
    assert code == 0, out
    assert _uploads(calls) == [f"release upload v9.9.9 dist/{_SDIST}"]


def test_the_asset_check_fails_on_different_content_and_uploads_nothing(tmp_path: Path) -> None:
    code, out, calls = _run_asset_check(tmp_path, {_WHEEL: (b"another build", True)})
    assert code != 0
    assert f"already has {_WHEEL}" in out
    assert _uploads(calls) == []

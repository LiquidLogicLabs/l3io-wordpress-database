"""Make recipes whose failure modes leak something."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = REPO / "Makefile"
TOOLS = REPO / "tools"
TRANSFER_SH = TOOLS / "test-transfer.sh"
ENGINE_SH = TOOLS / "test-engine.sh"

# ``docker rm -f`` without ``-v`` pre-empts ``--rm`` and leaves the image's
# anonymous VOLUME (MySQL/MariaDB: /var/lib/mysql) behind on every CI leg.
_DOCKER_RM = re.compile(r"\bdocker\s+rm\b(?P<flags>(?:\s+-[^\s]+)*)")
_RM_HAS_V = re.compile(r"(?:^|\s)-[^\s]*v|--volumes\b")


def recipe(target: str) -> str:
    lines = MAKEFILE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{target}:"))
    body = []
    for line in lines[start + 1 :]:
        if not line.startswith("\t"):
            break
        body.append(line)
    assert body, f"{target} has no recipe"
    return "\n".join(body)


def test_test_transfer_delegates_to_the_script() -> None:
    body = recipe("test-transfer")
    assert "tools/test-transfer.sh" in body
    assert "flock" in body


def test_an_interrupted_transfer_run_removes_its_server() -> None:
    """Ctrl-C must remove both containers, or a server is left holding the port.

    Under dash an EXIT trap does not run on a signal unless the signal is trapped
    too. And the shell runs no trap until its foreground child returns, while
    the ``docker run`` client catches Ctrl-C and keeps waiting on a container
    whose PID 1 ignores it. So the client runs in the background, the shell
    blocks in ``wait`` (which a trapped signal interrupts), and the EXIT trap
    removes the test container by name.
    """
    body = TRANSFER_SH.read_text(encoding="utf-8")
    assert "trap 'exit 130' INT TERM" in body
    [exit_trap] = [line for line in body.splitlines() if line.rstrip(" ;\\").endswith("EXIT")]
    assert "-tests" in exit_trap, "the EXIT trap does not remove the test container"
    assert '--name "${name}-tests"' in body
    assert "wait $!" in body, "a foreground docker run defers every trap until it returns"


def test_test_engine_measures_coverage() -> None:
    assert "tools/test-engine.sh" in recipe("test-engine")
    assert "--cov=l3io.wp.database" in ENGINE_SH.read_text(encoding="utf-8")


def test_docker_rm_in_tools_scripts_always_removes_volumes() -> None:
    """Every ``docker rm`` in tools/ must pass ``-v`` (or ``--volumes``).

    Globs ``tools/*.sh`` so a new helper is covered without editing this list.
    """
    offenders: list[str] = []
    for path in sorted(TOOLS.glob("*.sh")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = _DOCKER_RM.search(line)
            if match is None:
                continue
            if _RM_HAS_V.search(match.group("flags")) is None:
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, "docker rm without -v leaves anonymous volumes behind:\n" + "\n".join(
        offenders
    )

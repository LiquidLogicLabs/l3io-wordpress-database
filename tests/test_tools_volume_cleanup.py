"""Test scripts must not leave a database container's data volume behind.

MySQL and MariaDB images declare VOLUME /var/lib/mysql, so every run creates an anonymous
volume. `docker rm -f <name>` removes the container but NOT that volume -- even for a container
started with --rm, because the explicit remove pre-empts the auto-remove. On rwusdevl2 this
left 155 orphaned database volumes (~24 GB) in three weeks of act runs. `-v` removes them.

Scope is every shell script under tools/, so a new script is covered without editing this test.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
SCRIPTS = sorted(TOOLS.glob("*.sh"))
RM = re.compile(r"docker\s+(?:container\s+)?rm\b([^|;&\n'\"]*)")


def test_there_are_scripts_to_check():
    assert SCRIPTS, f"no shell scripts found under {TOOLS}"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_container_removal_also_removes_anonymous_volumes(script: Path):
    bad = []
    for n, line in enumerate(script.read_text().splitlines(), 1):
        for m in RM.finditer(line):
            flags = re.findall(r"(?<!\S)-(\w+)|--(volumes)\b", m.group(1))
            short = "".join(f for f, _ in flags)
            if "v" not in short and not any(lng for _, lng in flags):
                bad.append(f"{script.name}:{n}: {line.strip()}")
    assert not bad, "docker rm without -v leaves the container's anonymous volume behind:\n" + "\n".join(bad)

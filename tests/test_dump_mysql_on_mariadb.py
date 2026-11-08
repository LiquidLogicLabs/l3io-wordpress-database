"""MySQL mysqldump 8+ against a MariaDB server (Ubuntu mysql-client fallback).

Skipped unless ``DB_HOST`` points at MariaDB and a MySQL-family ``mysqldump``
>= 8.0 is on PATH. CI installs ``mysql-client`` on MariaDB matrix legs so this
runs there; locally: ``make test-engine ENGINE=mariadb:11.4`` with mysql-client.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pymysql
import pytest

from l3io.wp.database import _client, dump
from l3io.wp.database.connection import Connection
from l3io.wp.database.credentials import Explicit
from l3io.wp.database.server import ServerFamily

pytestmark = pytest.mark.skipif(
    not os.environ.get("DB_HOST"), reason="DB_HOST not set; integration tests skipped"
)

HOST = os.environ.get("DB_HOST", "127.0.0.1")
PORT = int(os.environ.get("DB_PORT", "3306"))
ADMIN_PASSWORD = os.environ.get("DB_ADMIN_PASSWORD", "root")


def _mysql_mysqldump() -> _client.ClientTool | None:
    path = shutil.which("mysqldump")
    if path is None:
        return None
    try:
        done = subprocess.run(  # noqa: S603
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            env=_client.child_env(),
            check=False,
        )
        tool = _client.parse_client_version("mysqldump", path, done.stdout or done.stderr)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if tool.family is not ServerFamily.MYSQL or tool.version < (8, 0, 0):
        return None
    return tool


def _server_is_mariadb() -> bool:
    conn = pymysql.connect(
        host=HOST, port=PORT, user="root", password=ADMIN_PASSWORD, connect_timeout=10
    )
    with conn, conn.cursor() as cur:
        cur.execute("SELECT VERSION()")
        version = str(cur.fetchone()[0])
    return "mariadb" in version.casefold()


def _admin(*statements: str) -> None:
    conn = pymysql.connect(
        host=HOST, port=PORT, user="root", password=ADMIN_PASSWORD, connect_timeout=10
    )
    with conn, conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
        conn.commit()


@pytest.fixture
def source_db() -> Iterator[str]:
    name = f"colstat_{uuid.uuid4().hex[:8]}"
    _admin(
        f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4",
        f"CREATE TABLE `{name}`.`wp_options` ("
        "option_id INT PRIMARY KEY, option_name VARCHAR(64), option_value LONGBLOB)",
        f"INSERT INTO `{name}`.`wp_options` VALUES (1, 'siteurl', 'http://x')",  # noqa: S608
    )
    yield name
    _admin(f"DROP DATABASE IF EXISTS `{name}`")


def test_mysql_mysqldump_dumps_mariadb_with_column_statistics_disabled(
    source_db: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not _server_is_mariadb():
        pytest.skip("server is not MariaDB")
    tool = _mysql_mysqldump()
    if tool is None:
        pytest.skip("MySQL mysqldump >= 8.0 not on PATH")

    def _force_mysql_dump(purpose: str, family: ServerFamily) -> _client.ClientTool | None:
        if purpose == _client.PURPOSE_DUMP:
            return tool
        return _client.find_tool(purpose, family)

    monkeypatch.setattr(_client, "find_tool", _force_mysql_dump)
    path = tmp_path / "site.sql"
    result = dump(
        Connection(host=HOST, port=PORT, database=source_db),
        Explicit("root", ADMIN_PASSWORD),
        path,
    )
    assert result.bytes == path.stat().st_size > 0
    assert b"COLUMN_STATISTICS" not in path.read_bytes()
    assert b"CREATE TABLE" in path.read_bytes()

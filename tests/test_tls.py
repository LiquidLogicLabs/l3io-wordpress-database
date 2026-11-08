"""TLS settings on Connection, option-file lines, and failure classification."""

from __future__ import annotations

import shutil
import ssl
import subprocess
from pathlib import Path

import pytest

from l3io.wp.database import (
    Connection,
    TlsHandshakeError,
    TlsMode,
    TlsSettings,
    TlsVerificationError,
    _client,
    tls_required_unless_local,
)
from l3io.wp.database._sql import classify
from l3io.wp.database.credentials import ResolvedCredentials
from l3io.wp.database.errors import InvalidArgumentsError
from l3io.wp.database.inspection import _connect_or_raise
from l3io.wp.database.server import ServerFamily
from l3io.wp.database.state import ConnectionState
from l3io.wp.database.tls import is_tls_failure, is_verification_failure, option_file_lines


def test_default_tls_is_off() -> None:
    assert Connection(host="db", database="wp").tls.mode is TlsMode.OFF


def test_tls_required_unless_local() -> None:
    assert tls_required_unless_local("localhost").mode is TlsMode.OFF
    assert tls_required_unless_local("127.0.0.1").mode is TlsMode.OFF
    assert tls_required_unless_local("::1").mode is TlsMode.OFF
    remote = tls_required_unless_local("db.example")
    assert remote.mode is TlsMode.VERIFY_IDENTITY
    assert remote.ca_file is None


def test_cert_and_key_must_be_paired() -> None:
    with pytest.raises(InvalidArgumentsError):
        TlsSettings(mode=TlsMode.REQUIRED, cert_file=Path("/c.pem"))


def test_paths_require_tls_on() -> None:
    with pytest.raises(InvalidArgumentsError):
        TlsSettings(mode=TlsMode.OFF, ca_file=Path("/ca.pem"))


def test_option_file_omits_tls_when_off() -> None:
    text = _client.option_file_text(
        ResolvedCredentials("u", "p"),
        Connection(host="db.example", database="wp", port=3307),
        ServerFamily.MYSQL,
    )
    assert text.splitlines() == [
        "[client]",
        'user="u"',
        'password="p"',
        'host="db.example"',
        "port=3307",
        "protocol=TCP",
    ]


def test_option_file_mysql_uses_ssl_mode_only(tmp_path: Path) -> None:
    ca = tmp_path / "ca.pem"
    ca.write_text("ca")
    conn = Connection(
        host="db.example",
        database="wp",
        tls=TlsSettings(mode=TlsMode.VERIFY_IDENTITY, ca_file=ca),
    )
    text = _client.option_file_text(ResolvedCredentials("u", "p"), conn, ServerFamily.MYSQL)
    assert "ssl=1" not in text
    assert "ssl-verify-server-cert" not in text
    assert "ssl-mode=VERIFY_IDENTITY" in text
    assert f'ssl-ca="{ca}"' in text


def test_option_file_mariadb_uses_ssl_and_verify_cert(tmp_path: Path) -> None:
    ca = tmp_path / "ca.pem"
    ca.write_text("ca")
    conn = Connection(
        host="db.example",
        database="wp",
        tls=TlsSettings(mode=TlsMode.VERIFY_IDENTITY, ca_file=ca),
    )
    text = _client.option_file_text(ResolvedCredentials("u", "p"), conn, ServerFamily.MARIADB)
    assert "ssl=1" in text
    assert "ssl-verify-server-cert=1" in text
    assert "ssl-mode=" not in text
    assert f'ssl-ca="{ca}"' in text


def test_option_file_lines_required_only() -> None:
    assert option_file_lines(TlsSettings(mode=TlsMode.REQUIRED), ServerFamily.MYSQL) == (
        "ssl-mode=REQUIRED",
    )
    assert option_file_lines(TlsSettings(mode=TlsMode.REQUIRED), ServerFamily.MARIADB) == ("ssl=1",)


def test_option_file_lines_never_use_loose_prefix() -> None:
    for family in (ServerFamily.MYSQL, ServerFamily.MARIADB):
        for mode in (TlsMode.REQUIRED, TlsMode.VERIFY_CA, TlsMode.VERIFY_IDENTITY):
            for line in option_file_lines(TlsSettings(mode=mode), family):
                assert not line.startswith("loose-"), line


def _client_on_path(*names: str) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path is not None and Path(path).is_absolute():
            return path
    return None


@pytest.mark.parametrize(
    ("family", "binaries", "must_accept"),
    [
        (
            ServerFamily.MYSQL,
            ("mysql", "mysqldump"),
            ("ssl-mode=VERIFY_IDENTITY", 'ssl-ca="/nonexistent/ca.pem"'),
        ),
        (
            ServerFamily.MARIADB,
            ("mariadb", "mariadb-dump", "mysql", "mysqldump"),
            ("ssl=1", "ssl-verify-server-cert=1", 'ssl-ca="/nonexistent/ca.pem"'),
        ),
    ],
)
def test_real_client_print_defaults_accepts_family_tls_options(
    tmp_path: Path,
    family: ServerFamily,
    binaries: tuple[str, ...],
    must_accept: tuple[str, ...],
) -> None:
    """Family TLS lines must parse; foreign names must fail when the client removed them.

    MySQL 8.0 still accepts deprecated ``ssl=1``; only 8.4+ rejects it. MariaDB
    rejects ``ssl-mode``. Always assert the family's own lines are accepted.
    """
    binary = _client_on_path(*binaries)
    if binary is None:
        pytest.skip(f"no {'/'.join(binaries)} on PATH")
    version = subprocess.run(  # noqa: S603
        [binary, "--version"],
        capture_output=True,
        text=True,
        env=_client.child_env(),
        check=False,
    )
    banner_text = version.stdout or version.stderr
    banner = banner_text.lower()
    if family is ServerFamily.MYSQL and "mariadb" in banner:
        pytest.skip(f"{binary} is a MariaDB client; need a MySQL client for this case")
    if (
        family is ServerFamily.MARIADB
        and "mariadb" not in banner
        and Path(binary).name in {"mysql", "mysqldump"}
    ):
        pytest.skip(f"{binary} is not a MariaDB client")

    good = tmp_path / "good.cnf"
    good.write_text("[client]\n" + "\n".join(must_accept) + "\n")
    accepted = subprocess.run(  # noqa: S603
        [binary, f"--defaults-file={good}", "--print-defaults"],
        capture_output=True,
        text=True,
        env=_client.child_env(),
        check=False,
    )
    assert accepted.returncode == 0, accepted.stderr
    assert "unknown variable" not in accepted.stderr.lower()

    must_reject: tuple[str, ...]
    if family is ServerFamily.MARIADB:
        must_reject = ("ssl-mode=VERIFY_IDENTITY",)
    else:
        tool = _client.parse_client_version(Path(binary).name, binary, banner_text)
        # MySQL 8.0 still accepts deprecated ssl=1; 8.4 removed it (sidecar failure).
        must_reject = ("ssl=1",) if tool.version >= (8, 4, 0) else ()

    for bad_line in must_reject:
        bad = tmp_path / f"bad-{bad_line.split('=')[0]}.cnf"
        bad.write_text(f"[client]\n{bad_line}\n")
        rejected = subprocess.run(  # noqa: S603
            [binary, f"--defaults-file={bad}", "--print-defaults"],
            capture_output=True,
            text=True,
            env=_client.child_env(),
            check=False,
        )
        err = (rejected.stderr + rejected.stdout).lower()
        assert rejected.returncode != 0, f"{binary} accepted foreign option {bad_line!r}"
        assert "unknown variable" in err or "unknown option" in err, err


def test_classify_tls_failure() -> None:
    assert classify(ssl.SSLError("CERTIFICATE_VERIFY_FAILED")) is ConnectionState.TLS_FAILED
    assert is_verification_failure(ssl.SSLCertVerificationError("bad"))
    assert is_tls_failure(RuntimeError("SSL connection error: protocol"))


def test_connect_or_raise_maps_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        msg = "certificate verify failed"
        raise ssl.SSLCertVerificationError(msg)

    monkeypatch.setattr("l3io.wp.database.inspection.open_connection", boom)
    with pytest.raises(TlsVerificationError):
        _connect_or_raise(
            Connection(host="db.example", database="wp", tls=TlsSettings(mode=TlsMode.REQUIRED)),
            ResolvedCredentials("u", "p"),
            None,
        )


def test_connect_or_raise_maps_handshake(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        msg = "SSL connection has been closed unexpectedly"
        raise OSError(msg)

    monkeypatch.setattr("l3io.wp.database.inspection.open_connection", boom)
    with pytest.raises(TlsHandshakeError):
        _connect_or_raise(
            Connection(host="db.example", database="wp", tls=TlsSettings(mode=TlsMode.REQUIRED)),
            ResolvedCredentials("u", "p"),
            None,
        )


def test_from_db_host_accepts_tls() -> None:
    tls = TlsSettings(mode=TlsMode.REQUIRED)
    conn = Connection.from_db_host("db:3307", "wp", tls=tls)
    assert conn == Connection(host="db", database="wp", port=3307, tls=tls)


def test_tls_failed_blocks_provisioning() -> None:
    assert ConnectionState.TLS_FAILED.blocks_provisioning

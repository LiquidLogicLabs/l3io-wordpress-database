"""TLS settings on Connection, option-file lines, and failure classification."""

from __future__ import annotations

import ssl
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
        ResolvedCredentials("u", "p"), Connection(host="db.example", database="wp", port=3307)
    )
    assert text.splitlines() == [
        "[client]",
        'user="u"',
        'password="p"',
        'host="db.example"',
        "port=3307",
        "protocol=TCP",
    ]


def test_option_file_includes_tls_when_required(tmp_path: Path) -> None:
    ca = tmp_path / "ca.pem"
    ca.write_text("ca")
    conn = Connection(
        host="db.example",
        database="wp",
        tls=TlsSettings(mode=TlsMode.VERIFY_IDENTITY, ca_file=ca),
    )
    text = _client.option_file_text(ResolvedCredentials("u", "p"), conn)
    assert "ssl=1" in text
    assert "ssl-mode=VERIFY_IDENTITY" in text
    assert "ssl-verify-server-cert=1" in text
    assert f'ssl-ca="{ca}"' in text


def test_option_file_lines_required_only() -> None:
    assert option_file_lines(TlsSettings(mode=TlsMode.REQUIRED)) == (
        "ssl=1",
        "ssl-mode=REQUIRED",
    )


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

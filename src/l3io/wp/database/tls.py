"""TLS settings for database connections.

AD-3 keeps the site descriptor free of credentials; TLS is about *how* the
host is reached, so it lives on :class:`~l3io.wp.database.Connection` rather
than on a credential source. The same settings drive PyMySQL and the client
option-file pipe (ADR-0002).
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .errors import InvalidArgumentsError

#: Hosts treated as local by :func:`tls_required_unless_local`.
DEFAULT_LOCAL_HOSTS: frozenset[str] = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "0:0:0:0:0:0:0:1",
    }
)


class TlsMode(StrEnum):
    """How strongly TLS is required for a connection."""

    OFF = "off"
    """No TLS. Today's default; plaintext TCP."""

    REQUIRED = "required"
    """TLS required; server certificate is not verified."""

    VERIFY_CA = "verify_ca"
    """TLS required; certificate chain verified against a CA (hostname not checked)."""

    VERIFY_IDENTITY = "verify_identity"
    """TLS required; certificate chain and hostname verified."""


@dataclass(frozen=True, slots=True)
class TlsSettings:
    """TLS options for one :class:`~l3io.wp.database.Connection`."""

    mode: TlsMode = TlsMode.OFF
    ca_file: Path | None = None
    cert_file: Path | None = None
    key_file: Path | None = None

    def __post_init__(self) -> None:
        if self.mode is TlsMode.OFF:
            if self.ca_file is not None or self.cert_file is not None or self.key_file is not None:
                msg = "ca_file, cert_file and key_file require a TLS mode other than OFF"
                raise InvalidArgumentsError(msg)
            return
        if (self.cert_file is None) ^ (self.key_file is None):
            msg = "cert_file and key_file must be supplied together"
            raise InvalidArgumentsError(msg)
        if self.mode in (TlsMode.VERIFY_CA, TlsMode.VERIFY_IDENTITY) and self.ca_file is None:
            # System store is allowed: ca_file None means the default context CAs.
            return
        for label, path in (
            ("ca_file", self.ca_file),
            ("cert_file", self.cert_file),
            ("key_file", self.key_file),
        ):
            if path is not None and not isinstance(path, Path):
                msg = f"{label} must be a Path, not {type(path).__name__}"
                raise InvalidArgumentsError(msg)


def tls_required_unless_local(
    host: str,
    *,
    local_hosts: frozenset[str] = DEFAULT_LOCAL_HOSTS,
    ca_file: Path | None = None,
    cert_file: Path | None = None,
    key_file: Path | None = None,
) -> TlsSettings:
    """Require verified TLS for non-local hosts; leave local hosts plaintext.

    ``localhost``, ``127.0.0.1`` and ``::1`` (and any extra names in
    ``local_hosts``) get :attr:`TlsMode.OFF`. Everything else gets
    :attr:`TlsMode.VERIFY_IDENTITY` against ``ca_file`` or the system store.
    """
    if not host:
        msg = "host must not be empty"
        raise InvalidArgumentsError(msg)
    if host.lower() in {h.lower() for h in local_hosts}:
        return TlsSettings(mode=TlsMode.OFF)
    return TlsSettings(
        mode=TlsMode.VERIFY_IDENTITY,
        ca_file=ca_file,
        cert_file=cert_file,
        key_file=key_file,
    )


def pymysql_ssl(settings: TlsSettings) -> ssl.SSLContext | None:
    """An :class:`ssl.SSLContext` for PyMySQL, or ``None`` when TLS is off."""
    if settings.mode is TlsMode.OFF:
        return None
    if settings.mode is TlsMode.REQUIRED:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx = ssl.create_default_context(cafile=_path_str(settings.ca_file))
        if settings.mode is TlsMode.VERIFY_CA:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_REQUIRED
        else:
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
    if settings.cert_file is not None and settings.key_file is not None:
        ctx.load_cert_chain(str(settings.cert_file), str(settings.key_file))
    return ctx


def option_file_lines(settings: TlsSettings) -> tuple[str, ...]:
    """``[client]`` option-file lines for MySQL/MariaDB client tools."""
    if settings.mode is TlsMode.OFF:
        return ()
    lines = [
        "ssl=1",
        f"ssl-mode={_client_ssl_mode(settings.mode)}",
    ]
    if settings.mode in (TlsMode.VERIFY_CA, TlsMode.VERIFY_IDENTITY):
        # Older MariaDB clients honour this when ssl-mode is unknown.
        lines.append("ssl-verify-server-cert=1")
    if settings.ca_file is not None:
        lines.append(f"ssl-ca={_quote_path(settings.ca_file)}")
    if settings.cert_file is not None:
        lines.append(f"ssl-cert={_quote_path(settings.cert_file)}")
    if settings.key_file is not None:
        lines.append(f"ssl-key={_quote_path(settings.key_file)}")
    return tuple(lines)


def is_tls_failure(exc: BaseException) -> bool:
    """Whether a connect failure is a TLS/SSL problem rather than plain unreachability."""
    if isinstance(exc, ssl.SSLError):
        return True
    text = str(exc).lower()
    markers = (
        "ssl",
        "tls",
        "certificate",
        "cert verify",
        "certificate verify failed",
        "wrong version number",
        "handshake",
    )
    return any(m in text for m in markers)


def is_verification_failure(exc: BaseException) -> bool:
    """Whether a TLS failure is specifically certificate verification."""
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    text = str(exc).lower()
    markers = (
        "certificate verify failed",
        "certificate_verify_failed",
        "hostname mismatch",
        "certificate has expired",
        "self-signed certificate",
        "unable to get local issuer",
    )
    return any(m in text for m in markers)


def _client_ssl_mode(mode: TlsMode) -> str:
    return {
        TlsMode.REQUIRED: "REQUIRED",
        TlsMode.VERIFY_CA: "VERIFY_CA",
        TlsMode.VERIFY_IDENTITY: "VERIFY_IDENTITY",
    }[mode]


def _path_str(path: Path | None) -> str | None:
    return None if path is None else str(path)


def _quote_path(path: Path) -> str:
    """Quote a filesystem path for an option-file value (same escaping as credentials)."""
    value = str(path)
    if "\x00" in value:
        msg = "a TLS path cannot contain a NUL character"
        raise InvalidArgumentsError(msg)
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    try:
        size = len(escaped.encode())
    except UnicodeEncodeError as exc:
        msg = "a TLS path is not valid UTF-8 text"
        raise InvalidArgumentsError(msg) from exc
    if size > 1024:
        msg = "a TLS path is longer than 1024 bytes once escaped"
        raise InvalidArgumentsError(msg)
    return f'"{escaped}"'

"""Authentication-plugin policy for every PyMySQL connection.

A server chooses the auth method. PyMySQL will honour ``mysql_clear_password``
(password bytes on the wire), ``mysql_old_password``, and ``dialog``. An
attacker who presents a valid TLS certificate and asks for cleartext auth can
collect the administrator password. Connections opened by this package therefore
refuse those plugins and allow only the hashed methods below (plus MariaDB's
``client_ed25519``, which PyMySQL already implements).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import AuthPluginRefusedError

#: Plugins this package will complete a handshake for.
ALLOWED_AUTH_PLUGINS: frozenset[str] = frozenset(
    {
        "mysql_native_password",
        "caching_sha2_password",
        "sha256_password",
        "client_ed25519",  # MariaDB; built into PyMySQL
    }
)

#: Plugins PyMySQL would otherwise honour that send or prompt for a password
#: in a form we refuse. Mapped to a refusing handler via :func:`auth_plugin_map`.
REFUSED_AUTH_PLUGINS: frozenset[str] = frozenset(
    {
        "mysql_clear_password",
        "mysql_old_password",
        "dialog",
    }
)


def _refuse_class(plugin: str) -> Callable[[Any], Any]:
    """A PyMySQL ``auth_plugin_map`` handler that refuses ``plugin``."""

    class _Refuse:
        def __init__(self, connection: object) -> None:
            self.connection = connection

        def authenticate(self, packet: object) -> None:
            del packet
            msg = f"authentication plugin {plugin!r} is not allowed"
            raise AuthPluginRefusedError(plugin, msg)

        def prompt(self, echo: bool, prompt: object) -> str:
            # dialog falls back to prompt() if authenticate is missing; keep both.
            del echo, prompt
            msg = f"authentication plugin {plugin!r} is not allowed"
            raise AuthPluginRefusedError(plugin, msg)

    _Refuse.__name__ = f"Refuse_{plugin}"
    _Refuse.__qualname__ = f"Refuse_{plugin}"
    return _Refuse


def auth_plugin_map() -> dict[str, Callable[[Any], Any]]:
    """Handlers that raise :class:`AuthPluginRefusedError` for refused plugins."""
    return {name: _refuse_class(name) for name in sorted(REFUSED_AUTH_PLUGINS)}

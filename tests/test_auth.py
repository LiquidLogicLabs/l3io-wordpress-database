"""Auth-plugin allow-list: refuse cleartext / old / dialog."""

from __future__ import annotations

import pytest

from l3io.wp.database import _client
from l3io.wp.database.auth import (
    ALLOWED_AUTH_PLUGINS,
    REFUSED_AUTH_PLUGINS,
    auth_plugin_map,
)
from l3io.wp.database.errors import AuthPluginRefusedError
from l3io.wp.database.state import ConnectionState


def test_refused_plugins_are_exactly_the_cleartext_family() -> None:
    assert frozenset({"mysql_clear_password", "mysql_old_password", "dialog"}) == (
        REFUSED_AUTH_PLUGINS
    )
    assert ALLOWED_AUTH_PLUGINS.isdisjoint(REFUSED_AUTH_PLUGINS)
    assert "client_ed25519" in ALLOWED_AUTH_PLUGINS


@pytest.mark.parametrize("plugin", sorted(REFUSED_AUTH_PLUGINS))
def test_auth_plugin_map_handlers_refuse_without_echoing_a_password(plugin: str) -> None:
    secret = "never-appear-in-the-error"
    handler = auth_plugin_map()[plugin](object())
    with pytest.raises(AuthPluginRefusedError) as caught:
        handler.authenticate(object())
    assert caught.value.plugin == plugin
    assert secret not in str(caught.value)
    assert plugin in str(caught.value)


def test_dialog_prompt_path_also_refuses() -> None:
    handler = auth_plugin_map()["dialog"](object())
    with pytest.raises(AuthPluginRefusedError) as caught:
        handler.prompt(False, b"Password: ")
    assert caught.value.plugin == "dialog"
    assert "Password" not in str(caught.value)


def test_cli_option_lists_refuse_cleartext_plugin() -> None:
    assert "--enable-cleartext-plugin" not in _client.DUMP_OPTIONS
    assert "--enable-cleartext-plugin" not in _client.LOAD_OPTIONS
    assert _client.disallowed_options(["--enable-cleartext-plugin"], _client.DUMP_OPTIONS) == [
        "--enable-cleartext-plugin"
    ]
    assert _client.disallowed_options(["--enable-cleartext-plugin"], _client.LOAD_OPTIONS) == [
        "--enable-cleartext-plugin"
    ]


def test_auth_plugin_refused_blocks_provisioning() -> None:
    assert ConnectionState.AUTH_PLUGIN_REFUSED.blocks_provisioning
    assert not ConnectionState.AUTH_PLUGIN_REFUSED.needs_provisioning

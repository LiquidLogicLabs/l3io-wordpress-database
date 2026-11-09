"""Prefix validation and LIKE escaping for drop_tables / prune_prefix."""

from __future__ import annotations

import pytest

from l3io.wp.database.errors import InvalidArgumentsError
from l3io.wp.database.transfer import _prefix_like, validate_table_prefix


def test_validate_table_prefix_accepts_a_wordpress_prefix() -> None:
    assert validate_table_prefix("wp_") == "wp_"
    assert validate_table_prefix("wp_2_") == "wp_2_"


@pytest.mark.parametrize(
    "prefix",
    ["", " wp_", "wp_ ", "wp`", "wp/x", "wp\\x", "wp.x", "a" * 65, "\x00wp"],
)
def test_validate_table_prefix_refuses_invalid(prefix: str) -> None:
    with pytest.raises(InvalidArgumentsError):
        validate_table_prefix(prefix)


def test_prefix_like_treats_underscore_as_literal() -> None:
    # Unescaped, LIKE 'wp_%' would also match 'wpXoptions'.
    assert _prefix_like("wp_") == r"wp\_%"
    assert _prefix_like("wp_%rare") == r"wp\_\%rare%"

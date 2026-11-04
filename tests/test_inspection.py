from __future__ import annotations

from dataclasses import fields

import pytest

from l3io.wp.database.connection import Connection
from l3io.wp.database.credentials import Explicit
from l3io.wp.database.errors import DatabaseUnreachableError
from l3io.wp.database.inspection import Survey, inspect, survey
from l3io.wp.database.state import ConnectionState


def test_survey_counts_views_separately_from_routines_and_events() -> None:
    """table_count includes views; routines and events are their own fields."""
    names = {f.name for f in fields(Survey)}
    assert {"table_count", "routine_count", "event_count"} <= names
    assert "views" in (Survey.__doc__ or "").lower()


def test_unreachable_server_is_a_state_not_an_exception() -> None:
    state = inspect(Connection(host="127.0.0.1", database="wp", port=1), Explicit("u", "p"))
    assert state is ConnectionState.UNREACHABLE


class _Unobtainable:
    source = "broken"

    def resolve(self):  # type: ignore[no-untyped-def]
        from l3io.wp.database.errors import CredentialsUnobtainableError

        msg = "nope"
        raise CredentialsUnobtainableError(msg)


def test_unobtainable_credentials_are_a_state() -> None:
    state = inspect(Connection(host="127.0.0.1", database="wp", port=1), _Unobtainable())
    assert state is ConnectionState.CREDENTIALS_UNOBTAINABLE


def test_survey_of_an_unreachable_server_raises_a_package_error() -> None:
    with pytest.raises(DatabaseUnreachableError):
        survey(Connection(host="127.0.0.1", database="wp", port=1), Explicit("u", "p"))

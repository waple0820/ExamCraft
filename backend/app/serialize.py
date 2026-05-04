"""ISO datetime serialization helpers used by the API layer.

We store datetimes as naive UTC (via datetime.utcnow()), so without an
explicit tz marker the JSON value would be misinterpreted by JS as local
time. These helpers always emit ISO with a `Z` suffix, and the frontend
formats them with timeZone: 'Asia/Shanghai'.
"""

from __future__ import annotations

from datetime import datetime, timezone


def iso_z(dt: datetime | None) -> str:
    """Serialize a datetime as ISO 8601 with `Z`. Empty string when None.

    Naive datetimes are assumed to already be in UTC (matches our use of
    datetime.utcnow throughout the codebase)."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def iso_z_opt(dt: datetime | None) -> str | None:
    """Like iso_z, but returns None instead of '' when input is None.

    Use for fields whose schema is `string | null`."""
    if dt is None:
        return None
    return iso_z(dt)

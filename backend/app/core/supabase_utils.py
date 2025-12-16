from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Optional


def raise_for_error(response: Any) -> None:
    """Raise a RuntimeError if the Supabase response contains an error."""
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(str(error))
    if isinstance(response, Mapping) and response.get("error"):
        raise RuntimeError(str(response["error"]))


def get_data(response: Any) -> list[dict]:
    """Extract row data from a Supabase response as a list of dicts."""
    data = getattr(response, "data", None)
    if data is None and isinstance(response, Mapping):
        data = response.get("data")
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return list(data)


def get_single_data(response: Any) -> Optional[dict]:
    """Extract the first row (or None) from a Supabase response."""
    rows = get_data(response)
    return rows[0] if rows else None


def get_count(response: Any) -> Optional[int]:
    """Extract count (if present) from a Supabase response."""
    count = getattr(response, "count", None)
    if count is None and isinstance(response, Mapping):
        count = response.get("count")
    return count


def to_jsonable(value: Any) -> Any:
    """Convert Python objects to JSON-serializable values for PostgREST."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    return value


def prepare_record(data: Mapping[str, Any]) -> dict:
    """Prepare a dict for Supabase insert/update/upsert (datetime/date to ISO)."""
    return {k: to_jsonable(v) for k, v in data.items()}

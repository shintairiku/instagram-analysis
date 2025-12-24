from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional


class Record(dict):
    """Dict-like row object with attribute access (row.id, row.username, ...)."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as e:
            raise AttributeError(key) from e

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def to_record(row: Optional[Mapping[str, Any]]) -> Optional[Record]:
    if row is None:
        return None
    return Record(row)


def to_records(rows: Iterable[Mapping[str, Any]]) -> list[Record]:
    return [Record(r) for r in rows]


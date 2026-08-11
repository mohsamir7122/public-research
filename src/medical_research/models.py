from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class StudyRecord:
    title: str
    doi: str = ""
    year: int | None = None
    journal: str = ""
    abstract: str = ""
    source: str = ""
    source_id: str = ""
    url: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

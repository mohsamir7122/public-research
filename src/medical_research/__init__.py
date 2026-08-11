"""Public-safe foundations for reproducible medical research."""

from .dedupe import DedupeDecision, deduplicate
from .models import StudyRecord
from .search_strategy import build_queries

__all__ = ["DedupeDecision", "StudyRecord", "build_queries", "deduplicate"]
__version__ = "0.1.0"

"""Public-safe foundations for reproducible medical research."""

from .dedupe import DedupeDecision, deduplicate
from .models import StudyRecord
from .pilot import run_pilot
from .search_strategy import build_queries

__all__ = ["DedupeDecision", "StudyRecord", "build_queries", "deduplicate", "run_pilot"]
__version__ = "0.1.0"

"""Public-safe foundations for reproducible medical research."""

from .dedupe import DedupeDecision, deduplicate
from .meta_analysis import (
    EffectEstimate,
    MetaAnalysisResult,
    PoolingApproval,
    combine_effects,
    estimate_tau_squared_paule_mandel,
)
from .models import StudyRecord
from .original_study_workflow import (
    OriginalStudyIntake,
    OriginalStudyIntakeError,
    OriginalStudyWorkflow,
    build_original_study_manifest,
    validate_original_study_intake,
)
from .pilot import run_pilot
from .review_workflow import (
    IntakeValidationError,
    ReviewWorkflow,
    ScreeningEvent,
    TopicIntake,
    build_project_manifest,
    corrected_covered_area,
    derive_prior_counts,
    derive_prisma_counts,
    validate_topic_intake,
)
from .search_strategy import build_queries
from .topic_project import (
    ProvisionalTopicError,
    assess_provisional_topic,
    build_provisional_topic_manifest,
    initialize_provisional_topic_project,
)

__all__ = [
    "DedupeDecision",
    "EffectEstimate",
    "IntakeValidationError",
    "MetaAnalysisResult",
    "OriginalStudyIntake",
    "OriginalStudyIntakeError",
    "OriginalStudyWorkflow",
    "PoolingApproval",
    "ProvisionalTopicError",
    "ReviewWorkflow",
    "ScreeningEvent",
    "StudyRecord",
    "TopicIntake",
    "build_original_study_manifest",
    "build_provisional_topic_manifest",
    "build_project_manifest",
    "build_queries",
    "combine_effects",
    "corrected_covered_area",
    "deduplicate",
    "derive_prisma_counts",
    "derive_prior_counts",
    "estimate_tau_squared_paule_mandel",
    "initialize_provisional_topic_project",
    "run_pilot",
    "validate_original_study_intake",
    "validate_topic_intake",
    "assess_provisional_topic",
]
__version__ = "0.2.0"

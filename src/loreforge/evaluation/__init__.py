"""Deterministic evaluation contracts and metric helpers."""

from loreforge.evaluation.answers import (
    evaluate_answer,
    evaluate_citations,
    normalize_answer_text,
)
from loreforge.evaluation.cli import (
    EXIT_CONFIGURATION_ERROR,
    EXIT_REGRESSION,
    EXIT_SUCCESS,
)
from loreforge.evaluation.dataset import (
    EvaluationDataset,
    EvaluationDatasetCase,
    load_dataset,
)
from loreforge.evaluation.gate import (
    EvaluationThresholds,
    GateResult,
    evaluate_gate,
    load_thresholds,
)
from loreforge.evaluation.models import (
    AnswerMetrics,
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationReport,
    RetrievalMetrics,
)
from loreforge.evaluation.quality import (
    CitationQualityMetrics,
    GroundednessMetrics,
    RetrievalQualityMetrics,
    evaluate_citation_quality,
    evaluate_groundedness,
    evaluate_retrieval_quality,
)
from loreforge.evaluation.reporting import EvaluationRunReport, human_report
from loreforge.evaluation.retrieval import evaluate_retrieval
from loreforge.evaluation.runner import run_fixture_evaluation
from loreforge.evaluation.suite import build_evaluation_report, evaluate_case

__all__ = [
    "run_fixture_evaluation",
    "load_thresholds",
    "load_dataset",
    "human_report",
    "evaluate_retrieval_quality",
    "evaluate_groundedness",
    "evaluate_gate",
    "evaluate_citation_quality",
    "RetrievalQualityMetrics",
    "GroundednessMetrics",
    "GateResult",
    "EXIT_SUCCESS",
    "EXIT_REGRESSION",
    "EXIT_CONFIGURATION_ERROR",
    "EvaluationThresholds",
    "EvaluationRunReport",
    "EvaluationDatasetCase",
    "EvaluationDataset",
    "CitationQualityMetrics",
    "AnswerMetrics",
    "EvaluationCase",
    "EvaluationCaseResult",
    "EvaluationReport",
    "RetrievalMetrics",
    "build_evaluation_report",
    "evaluate_answer",
    "evaluate_case",
    "evaluate_citations",
    "evaluate_retrieval",
    "normalize_answer_text",
]

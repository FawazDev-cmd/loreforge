"""Deterministic evaluation contracts and metric helpers."""

from loreforge.evaluation.answers import (
    evaluate_answer,
    evaluate_citations,
    normalize_answer_text,
)
from loreforge.evaluation.models import (
    AnswerMetrics,
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationReport,
    RetrievalMetrics,
)
from loreforge.evaluation.retrieval import evaluate_retrieval
from loreforge.evaluation.suite import build_evaluation_report, evaluate_case

__all__ = [
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

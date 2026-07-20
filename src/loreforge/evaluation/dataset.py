"""Versioned deterministic evaluation dataset contracts."""

from dataclasses import dataclass, field
from json import loads
from pathlib import Path
from typing import Any
from uuid import UUID

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class ExpectedSource:
    """Expected source document target for one evaluation case."""

    document_id: UUID


@dataclass(frozen=True, slots=True)
class EvaluationDatasetCase:
    """One deterministic evaluation case with expected and observed fixture data."""

    case_id: str
    question: str
    tags: tuple[str, ...] = ()
    expected_chunk_ids: tuple[UUID, ...] = ()
    expected_source_document_ids: tuple[UUID, ...] = ()
    expected_citation_ids: tuple[str, ...] = ()
    relevance_grades: dict[UUID, int] = field(default_factory=dict)
    required_facts: tuple[str, ...] = ()
    forbidden_claims: tuple[str, ...] = ()
    expect_no_evidence: bool = False
    expect_abstention: bool = False
    observed_retrieved_chunk_ids: tuple[UUID, ...] = ()
    observed_retrieved_source_document_ids: tuple[UUID, ...] = ()
    observed_evidence_chunk_ids: tuple[UUID, ...] = ()
    observed_citation_ids: tuple[str, ...] = ()
    observed_answer_text: str | None = None
    observed_error: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            msg = "case_id must not be empty"
            raise ValueError(msg)
        if not self.question.strip():
            msg = "question must not be empty"
            raise ValueError(msg)
        if not self.expect_no_evidence and not (
            self.expected_chunk_ids
            or self.expected_source_document_ids
            or self.expected_citation_ids
            or self.required_facts
        ):
            msg = "case must define expected targets or expect_no_evidence"
            raise ValueError(msg)
        _validate_unique(self.expected_chunk_ids, "expected_chunk_ids")
        _validate_unique(
            self.expected_source_document_ids,
            "expected_source_document_ids",
        )
        _validate_unique(self.expected_citation_ids, "expected_citation_ids")
        _validate_unique(
            self.observed_retrieved_chunk_ids, "observed_retrieved_chunk_ids"
        )
        _validate_unique(
            self.observed_evidence_chunk_ids, "observed_evidence_chunk_ids"
        )
        _validate_grades(self.relevance_grades)
        for tag in self.tags:
            if not tag.strip():
                msg = "tags must not be empty"
                raise ValueError(msg)
        if (
            self.observed_answer_text is not None
            and not self.observed_answer_text.strip()
        ):
            msg = "observed_answer_text must not be empty when provided"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    """Validated deterministic evaluation dataset."""

    name: str
    schema_version: str
    description: str
    cases: tuple[EvaluationDatasetCase, ...]
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            msg = "unsupported evaluation dataset schema_version"
            raise ValueError(msg)
        if not self.name.strip():
            msg = "dataset name must not be empty"
            raise ValueError(msg)
        if not self.description.strip():
            msg = "dataset description must not be empty"
            raise ValueError(msg)
        if not self.cases:
            msg = "dataset cases must not be empty"
            raise ValueError(msg)
        case_ids = tuple(case.case_id for case in self.cases)
        _validate_unique(case_ids, "case_ids")


def load_dataset(path: Path | str) -> EvaluationDataset:
    """Load and validate a JSON evaluation dataset."""
    payload = loads(Path(path).read_text(encoding="utf-8"))
    if type(payload) is not dict:
        msg = "dataset JSON root must be an object"
        raise ValueError(msg)
    return dataset_from_dict(payload)


def dataset_from_dict(payload: dict[str, Any]) -> EvaluationDataset:
    """Build an evaluation dataset from parsed JSON-compatible data."""
    schema_version = _string(payload, "schema_version")
    if schema_version != SCHEMA_VERSION:
        msg = "unsupported evaluation dataset schema_version"
        raise ValueError(msg)
    cases_raw = payload.get("cases")
    if type(cases_raw) is not list:
        msg = "cases must be a list"
        raise ValueError(msg)
    return EvaluationDataset(
        name=_string(payload, "name"),
        schema_version=schema_version,
        description=_string(payload, "description"),
        metadata=_string_dict(payload.get("metadata", {}), "metadata"),
        cases=tuple(_case_from_dict(item) for item in cases_raw),
    )


def _case_from_dict(payload: object) -> EvaluationDatasetCase:
    if type(payload) is not dict:
        msg = "case must be an object"
        raise ValueError(msg)
    data: dict[str, Any] = payload
    return EvaluationDatasetCase(
        case_id=_string(data, "case_id"),
        question=_string(data, "question"),
        tags=_strings(data.get("tags", []), "tags"),
        expected_chunk_ids=_uuids(
            data.get("expected_chunk_ids", []), "expected_chunk_ids"
        ),
        expected_source_document_ids=_uuids(
            data.get("expected_source_document_ids", []),
            "expected_source_document_ids",
        ),
        expected_citation_ids=_strings(
            data.get("expected_citation_ids", []),
            "expected_citation_ids",
        ),
        relevance_grades=_grades(data.get("relevance_grades", {})),
        required_facts=_strings(data.get("required_facts", []), "required_facts"),
        forbidden_claims=_strings(data.get("forbidden_claims", []), "forbidden_claims"),
        expect_no_evidence=_bool(
            data.get("expect_no_evidence", False), "expect_no_evidence"
        ),
        expect_abstention=_bool(
            data.get("expect_abstention", False), "expect_abstention"
        ),
        observed_retrieved_chunk_ids=_uuids(
            data.get("observed_retrieved_chunk_ids", []),
            "observed_retrieved_chunk_ids",
        ),
        observed_retrieved_source_document_ids=_uuids(
            data.get("observed_retrieved_source_document_ids", []),
            "observed_retrieved_source_document_ids",
        ),
        observed_evidence_chunk_ids=_uuids(
            data.get("observed_evidence_chunk_ids", []),
            "observed_evidence_chunk_ids",
        ),
        observed_citation_ids=_strings(
            data.get("observed_citation_ids", []),
            "observed_citation_ids",
        ),
        observed_answer_text=_optional_string(data.get("observed_answer_text")),
        observed_error=_optional_string(data.get("observed_error")),
        notes=_optional_string(data.get("notes")),
    )


def _string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if type(value) is not str or not value.strip():
        msg = f"{key} must be a non-empty string"
        raise ValueError(msg)
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value.strip():
        msg = "optional strings must be non-empty strings when provided"
        raise ValueError(msg)
    return value


def _strings(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not list:
        msg = f"{name} must be a list"
        raise ValueError(msg)
    values = tuple(_item_string(item, name) for item in value)
    _validate_unique(values, name)
    return values


def _item_string(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        msg = f"{name} values must be non-empty strings"
        raise ValueError(msg)
    return value


def _uuids(value: object, name: str) -> tuple[UUID, ...]:
    return tuple(UUID(item) for item in _strings(value, name))


def _grades(value: object) -> dict[UUID, int]:
    if type(value) is not dict:
        msg = "relevance_grades must be an object"
        raise ValueError(msg)
    grades: dict[UUID, int] = {}
    for key, grade in value.items():
        if type(key) is not str:
            msg = "relevance grade keys must be UUID strings"
            raise ValueError(msg)
        grade_object: object = grade
        if type(grade_object) is not int or not 0 <= grade <= 3:
            msg = "relevance grades must be integers from 0 to 3"
            raise ValueError(msg)
        grades[UUID(key)] = grade
    return grades


def _string_dict(value: object, name: str) -> dict[str, str]:
    if type(value) is not dict:
        msg = f"{name} must be an object"
        raise ValueError(msg)
    result: dict[str, str] = {}
    for key, item in value.items():
        if type(key) is not str or type(item) is not str:
            msg = f"{name} keys and values must be strings"
            raise ValueError(msg)
        result[key] = item
    return result


def _bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        msg = f"{name} must be a boolean"
        raise ValueError(msg)
    return value


def _validate_unique(values: tuple[object, ...], name: str) -> None:
    if len(set(values)) != len(values):
        msg = f"{name} must contain unique values"
        raise ValueError(msg)


def _validate_grades(grades: dict[UUID, int]) -> None:
    for grade in grades.values():
        if not 0 <= grade <= 3:
            msg = "relevance grades must be integers from 0 to 3"
            raise ValueError(msg)

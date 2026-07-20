from pathlib import Path

import pytest

from loreforge.evaluation import EvaluationDataset, load_dataset
from loreforge.evaluation.dataset import dataset_from_dict

FIXTURE = Path("tests/fixtures/evaluation/golden_dataset.json")


def test_load_golden_dataset() -> None:
    dataset = load_dataset(FIXTURE)

    assert type(dataset) is EvaluationDataset
    assert dataset.schema_version == "1.0"
    assert tuple(case.case_id for case in dataset.cases) == (
        "exact-lexical-refund-window",
        "semantic-plan-cancellation",
        "hybrid-address-update",
        "metadata-filter-eu-policy",
        "ownership-isolation",
        "multi-source-escalation",
    )


def test_duplicate_case_ids_rejected() -> None:
    payload = _minimal_payload()
    payload["cases"].append(dict(payload["cases"][0]))

    with pytest.raises(ValueError, match="case_ids"):
        dataset_from_dict(payload)


def test_invalid_schema_version_rejected() -> None:
    payload = _minimal_payload()
    payload["schema_version"] = "9.9"

    with pytest.raises(ValueError, match="schema_version"):
        dataset_from_dict(payload)


def test_invalid_relevance_grade_rejected() -> None:
    payload = _minimal_payload()
    payload["cases"][0]["relevance_grades"] = {
        "00000000-0000-0000-0000-000000000101": 4
    }

    with pytest.raises(ValueError, match="relevance grades"):
        dataset_from_dict(payload)


def test_empty_case_without_expected_targets_rejected() -> None:
    payload = _minimal_payload()
    payload["cases"][0].pop("expected_chunk_ids")
    payload["cases"][0].pop("expected_citation_ids")

    with pytest.raises(ValueError, match="expected targets"):
        dataset_from_dict(payload)


def _minimal_payload() -> dict:
    return {
        "name": "minimal",
        "schema_version": "1.0",
        "description": "minimal synthetic dataset",
        "cases": [
            {
                "case_id": "case-1",
                "question": "Question?",
                "expected_chunk_ids": ["00000000-0000-0000-0000-000000000101"],
                "expected_citation_ids": ["S1"],
                "observed_retrieved_chunk_ids": [
                    "00000000-0000-0000-0000-000000000101"
                ],
                "observed_evidence_chunk_ids": ["00000000-0000-0000-0000-000000000101"],
                "observed_citation_ids": ["S1"],
                "observed_answer_text": "Answer.",
            }
        ],
    }

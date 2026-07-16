from dataclasses import FrozenInstanceError

import pytest

from loreforge.retrieval import SemanticSearchRequest, SemanticSearchResponse


def test_semantic_search_request_accepts_valid_values() -> None:
    request = SemanticSearchRequest(question="What is LoreForge?", top_k=3)

    assert request.question == "What is LoreForge?"
    assert request.top_k == 3


@pytest.mark.parametrize("question", ["", "   "])
def test_semantic_search_request_rejects_blank_question(question: str) -> None:
    with pytest.raises(ValueError, match="question"):
        SemanticSearchRequest(question=question, top_k=1)


@pytest.mark.parametrize("top_k", [0, -1])
def test_semantic_search_request_rejects_invalid_top_k(top_k: int) -> None:
    with pytest.raises(ValueError, match="top_k"):
        SemanticSearchRequest(question="What is indexed?", top_k=top_k)


def test_semantic_search_request_is_immutable() -> None:
    request = SemanticSearchRequest(question="What is indexed?", top_k=1)

    with pytest.raises(FrozenInstanceError):
        request.top_k = 2


def test_semantic_search_response_is_immutable() -> None:
    response = SemanticSearchResponse(question="What is indexed?", results=())

    with pytest.raises(FrozenInstanceError):
        response.results = ()

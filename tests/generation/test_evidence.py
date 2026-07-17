from dataclasses import FrozenInstanceError
from math import inf, nan
from uuid import UUID

import pytest

from loreforge.documents import DocumentChunk, DocumentSource
from loreforge.generation import (
    EvidenceContext,
    EvidenceContextConfig,
    EvidenceContextError,
    EvidenceItem,
    build_evidence_context,
)
from loreforge.reranking import RerankedSearchResult
from loreforge.retrieval import HybridSearchResult, RetrievalContribution

CHUNK_ID_1 = UUID("00000000-0000-0000-0000-000000000101")
CHUNK_ID_2 = UUID("00000000-0000-0000-0000-000000000102")
DOCUMENT_ID_1 = UUID("00000000-0000-0000-0000-000000000201")
DOCUMENT_ID_2 = UUID("00000000-0000-0000-0000-000000000202")


def test_evidence_context_config_accepts_default_value() -> None:
    config = EvidenceContextConfig()

    assert config.max_characters == 12000


def test_evidence_context_config_accepts_custom_value() -> None:
    config = EvidenceContextConfig(max_characters=256)

    assert config.max_characters == 256


@pytest.mark.parametrize("max_characters", [0, -1])
def test_evidence_context_config_rejects_non_positive_values(
    max_characters: int,
) -> None:
    with pytest.raises(ValueError, match="max_characters"):
        EvidenceContextConfig(max_characters=max_characters)


def test_evidence_context_config_rejects_boolean_value() -> None:
    with pytest.raises(ValueError, match="max_characters"):
        EvidenceContextConfig(max_characters=True)  # type: ignore[arg-type]


def test_evidence_context_config_is_immutable() -> None:
    config = EvidenceContextConfig()

    with pytest.raises(FrozenInstanceError):
        config.max_characters = 1


def test_evidence_item_accepts_positive_reranker_score() -> None:
    item = _evidence_item(reranker_score=1.5)

    assert item.reranker_score == 1.5


def test_evidence_item_accepts_negative_reranker_score() -> None:
    item = _evidence_item(reranker_score=-1.5)

    assert item.reranker_score == -1.5


@pytest.mark.parametrize("filename", ["", "   "])
def test_evidence_item_rejects_blank_filename(filename: str) -> None:
    with pytest.raises(ValueError, match="filename"):
        _evidence_item(filename=filename)


@pytest.mark.parametrize("citation_id", ["", "1", "s1", "S", "S 1"])
def test_evidence_item_rejects_invalid_citation_marker(citation_id: str) -> None:
    with pytest.raises(ValueError, match="citation_id"):
        _evidence_item(citation_id=citation_id)


def test_evidence_item_rejects_zero_citation_number() -> None:
    with pytest.raises(ValueError, match="citation_id"):
        _evidence_item(citation_id="S0")


def test_evidence_item_rejects_invalid_page_number() -> None:
    with pytest.raises(ValueError, match="page_number"):
        _evidence_item(page_number=0)


@pytest.mark.parametrize("text", ["", "   "])
def test_evidence_item_rejects_blank_text(text: str) -> None:
    with pytest.raises(ValueError, match="text"):
        _evidence_item(text=text)


def test_evidence_item_rejects_integer_score() -> None:
    with pytest.raises(ValueError, match="reranker_score"):
        _evidence_item(reranker_score=1)  # type: ignore[arg-type]


def test_evidence_item_rejects_boolean_score() -> None:
    with pytest.raises(ValueError, match="reranker_score"):
        _evidence_item(reranker_score=True)  # type: ignore[arg-type]


@pytest.mark.parametrize("reranker_score", [nan, inf, -inf])
def test_evidence_item_rejects_non_finite_scores(reranker_score: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        _evidence_item(reranker_score=reranker_score)


def test_evidence_item_rejects_invalid_retrieval_rank() -> None:
    with pytest.raises(ValueError, match="retrieval_rank"):
        _evidence_item(retrieval_rank=0)


def test_evidence_item_is_immutable() -> None:
    item = _evidence_item()

    with pytest.raises(FrozenInstanceError):
        item.text = "changed"


def test_evidence_context_accepts_valid_context() -> None:
    item = _evidence_item()
    rendered = _rendered_for(item)

    context = EvidenceContext(
        items=(item,),
        rendered_text=rendered,
        total_characters=len(rendered),
        truncated=False,
    )

    assert context.items == (item,)


def test_evidence_context_rejects_empty_items() -> None:
    with pytest.raises(ValueError, match="items"):
        EvidenceContext(
            items=(), rendered_text="text", total_characters=4, truncated=False
        )


def test_evidence_context_rejects_duplicate_citation_ids() -> None:
    first = _evidence_item(citation_id="S1", chunk_id=CHUNK_ID_1)
    second = _evidence_item(citation_id="S1", chunk_id=CHUNK_ID_2)

    with pytest.raises(ValueError, match="unique"):
        EvidenceContext(
            items=(first, second),
            rendered_text="text",
            total_characters=4,
            truncated=False,
        )


def test_evidence_context_rejects_non_sequential_citation_ids() -> None:
    item = _evidence_item(citation_id="S2")

    with pytest.raises(ValueError, match="sequential"):
        EvidenceContext(
            items=(item,), rendered_text="text", total_characters=4, truncated=False
        )


def test_evidence_context_rejects_duplicate_chunk_ids() -> None:
    first = _evidence_item(citation_id="S1", chunk_id=CHUNK_ID_1)
    second = _evidence_item(citation_id="S2", chunk_id=CHUNK_ID_1)

    with pytest.raises(ValueError, match="chunk IDs"):
        EvidenceContext(
            items=(first, second),
            rendered_text="text",
            total_characters=4,
            truncated=False,
        )


@pytest.mark.parametrize("rendered_text", ["", "   "])
def test_evidence_context_rejects_blank_rendered_text(rendered_text: str) -> None:
    with pytest.raises(ValueError, match="rendered_text"):
        EvidenceContext(
            items=(_evidence_item(),),
            rendered_text=rendered_text,
            total_characters=len(rendered_text),
            truncated=False,
        )


def test_evidence_context_rejects_incorrect_character_count() -> None:
    with pytest.raises(ValueError, match="total_characters"):
        EvidenceContext(
            items=(_evidence_item(),),
            rendered_text="text",
            total_characters=99,
            truncated=False,
        )


def test_evidence_context_rejects_non_boolean_truncated_value() -> None:
    with pytest.raises(ValueError, match="truncated"):
        EvidenceContext(
            items=(_evidence_item(),),
            rendered_text="text",
            total_characters=4,
            truncated=1,  # type: ignore[arg-type]
        )


def test_evidence_context_preserves_supplied_order() -> None:
    first = _evidence_item(citation_id="S1", chunk_id=CHUNK_ID_1, text="First")
    second = _evidence_item(citation_id="S2", chunk_id=CHUNK_ID_2, text="Second")

    context = EvidenceContext(
        items=(first, second),
        rendered_text="text",
        total_characters=4,
        truncated=False,
    )

    assert context.items == (first, second)


def test_evidence_context_is_immutable() -> None:
    context = _context()

    with pytest.raises(FrozenInstanceError):
        context.truncated = True


def test_build_one_candidate_creates_s1() -> None:
    context = build_evidence_context(candidates=(_candidate(text="Alpha"),))

    assert context.items[0].citation_id == "S1"


def test_build_multiple_candidates_create_sequential_markers() -> None:
    context = build_evidence_context(
        candidates=(
            _candidate(chunk_id=CHUNK_ID_1, text="Alpha", rank=1),
            _candidate(chunk_id=CHUNK_ID_2, text="Beta", rank=2),
        )
    )

    assert [item.citation_id for item in context.items] == ["S1", "S2"]


def test_build_candidate_order_is_preserved() -> None:
    first = _candidate(chunk_id=CHUNK_ID_1, text="First", rank=1)
    second = _candidate(chunk_id=CHUNK_ID_2, text="Second", rank=2)

    context = build_evidence_context(candidates=(first, second))

    assert [item.text for item in context.items] == ["First", "Second"]


def test_build_preserves_complete_provenance() -> None:
    candidate = _candidate(
        chunk_id=CHUNK_ID_1,
        document_id=DOCUMENT_ID_1,
        filename="handbook.pdf",
        page_number=7,
        text="Exact policy text",
        reranker_score=-0.25,
        rank=3,
    )

    context = build_evidence_context(candidates=(candidate,))
    item = context.items[0]

    assert item.chunk_id == CHUNK_ID_1
    assert item.document_id == DOCUMENT_ID_1
    assert item.filename == "handbook.pdf"
    assert item.page_number == 7
    assert item.text == "Exact policy text"
    assert item.reranker_score == -0.25
    assert item.retrieval_rank == 3


def test_build_preserves_exact_chunk_text() -> None:
    text = "Line one.\nLine two. Keep spacing."

    context = build_evidence_context(candidates=(_candidate(text=text),))

    assert context.items[0].text == text
    assert context.rendered_text.endswith(text)


def test_build_rendered_block_format_is_exact() -> None:
    context = build_evidence_context(
        candidates=(
            _candidate(filename="guide.pdf", page_number=4, text="Use backups."),
        )
    )

    assert context.rendered_text == (
        "[S1]\nSource: guide.pdf\nPage: 4\nContent:\nUse backups."
    )


def test_build_blocks_are_separated_by_exactly_two_newlines() -> None:
    context = build_evidence_context(
        candidates=(
            _candidate(chunk_id=CHUNK_ID_1, text="Alpha", rank=1),
            _candidate(chunk_id=CHUNK_ID_2, text="Beta", rank=2),
        )
    )

    assert "Alpha\n\n[S2]" in context.rendered_text
    assert "Alpha\n\n\n[S2]" not in context.rendered_text


def test_build_internal_retrieval_scores_are_not_rendered() -> None:
    context = build_evidence_context(
        candidates=(
            _candidate(text="Policy text", reranker_score=0.12345, fused_score=0.6789),
        )
    )

    assert "0.12345" not in context.rendered_text
    assert "0.6789" not in context.rendered_text
    assert "semantic" not in context.rendered_text


def test_build_total_character_count_is_exact() -> None:
    context = build_evidence_context(candidates=(_candidate(text="Alpha"),))

    assert context.total_characters == len(context.rendered_text)


def test_build_all_candidates_fit_within_budget() -> None:
    candidates = (
        _candidate(chunk_id=CHUNK_ID_1, text="Alpha", rank=1),
        _candidate(chunk_id=CHUNK_ID_2, text="Beta", rank=2),
    )

    context = build_evidence_context(
        candidates=candidates, config=EvidenceContextConfig(max_characters=1000)
    )

    assert len(context.items) == 2
    assert context.truncated is False


def test_build_later_candidates_omitted_when_budget_is_reached() -> None:
    first = _candidate(chunk_id=CHUNK_ID_1, text="Alpha", rank=1)
    second = _candidate(chunk_id=CHUNK_ID_2, text="Beta", rank=2)
    first_block = _expected_block("S1", "sample.pdf", 1, "Alpha")

    context = build_evidence_context(
        candidates=(first, second),
        config=EvidenceContextConfig(max_characters=len(first_block)),
    )

    assert context.items == (context.items[0],)
    assert context.items[0].text == "Alpha"
    assert context.truncated is True


def test_build_truncated_false_when_all_candidates_fit() -> None:
    context = build_evidence_context(candidates=(_candidate(text="Alpha"),))

    assert context.truncated is False


def test_build_no_passage_is_partially_truncated() -> None:
    first = _candidate(chunk_id=CHUNK_ID_1, text="Alpha", rank=1)
    second = _candidate(chunk_id=CHUNK_ID_2, text="Beta should not appear", rank=2)
    first_block = _expected_block("S1", "sample.pdf", 1, "Alpha")

    context = build_evidence_context(
        candidates=(first, second),
        config=EvidenceContextConfig(max_characters=len(first_block)),
    )

    assert "Beta" not in context.rendered_text
    assert context.rendered_text == first_block


def test_build_first_block_exceeding_budget_raises_error() -> None:
    candidate = _candidate(text="Alpha")

    with pytest.raises(EvidenceContextError, match="budget"):
        build_evidence_context(
            candidates=(candidate,), config=EvidenceContextConfig(max_characters=1)
        )


def test_build_empty_candidates_raise_error() -> None:
    with pytest.raises(EvidenceContextError, match="candidate"):
        build_evidence_context(candidates=())


def test_build_repeated_construction_is_deterministic() -> None:
    candidates = (_candidate(text="Alpha"),)

    first = build_evidence_context(candidates=candidates)
    second = build_evidence_context(candidates=candidates)

    assert first == second


def test_build_input_candidates_remain_unchanged() -> None:
    candidates = (_candidate(text="Alpha"),)
    before = candidates

    build_evidence_context(candidates=candidates)

    assert candidates == before


def _evidence_item(
    *,
    citation_id: str = "S1",
    chunk_id: UUID = CHUNK_ID_1,
    document_id: UUID = DOCUMENT_ID_1,
    filename: str = "sample.pdf",
    page_number: int = 1,
    text: str = "Evidence text",
    reranker_score: float = 1.0,
    retrieval_rank: int = 1,
) -> EvidenceItem:
    return EvidenceItem(
        citation_id=citation_id,
        chunk_id=chunk_id,
        document_id=document_id,
        filename=filename,
        page_number=page_number,
        text=text,
        reranker_score=reranker_score,
        retrieval_rank=retrieval_rank,
    )


def _context() -> EvidenceContext:
    item = _evidence_item()
    rendered = _rendered_for(item)
    return EvidenceContext(
        items=(item,),
        rendered_text=rendered,
        total_characters=len(rendered),
        truncated=False,
    )


def _rendered_for(item: EvidenceItem) -> str:
    return _expected_block(item.citation_id, item.filename, item.page_number, item.text)


def _expected_block(
    citation_id: str, filename: str, page_number: int, text: str
) -> str:
    return f"[{citation_id}]\nSource: {filename}\nPage: {page_number}\nContent:\n{text}"


def _source(*, filename: str = "sample.pdf") -> DocumentSource:
    return DocumentSource(
        filename=filename, media_type="application/pdf", size_bytes=128
    )


def _chunk(
    *,
    chunk_id: UUID = CHUNK_ID_1,
    document_id: UUID = DOCUMENT_ID_1,
    filename: str = "sample.pdf",
    page_number: int = 1,
    text: str = "Evidence text",
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        source=_source(filename=filename),
        page_number=page_number,
        chunk_index=0,
        text=text,
    )


def _candidate(
    *,
    chunk_id: UUID = CHUNK_ID_1,
    document_id: UUID = DOCUMENT_ID_1,
    filename: str = "sample.pdf",
    page_number: int = 1,
    text: str = "Evidence text",
    reranker_score: float = 1.0,
    fused_score: float = 1.0,
    rank: int = 1,
) -> RerankedSearchResult:
    return RerankedSearchResult(
        hybrid_result=HybridSearchResult(
            chunk=_chunk(
                chunk_id=chunk_id,
                document_id=document_id,
                filename=filename,
                page_number=page_number,
                text=text,
            ),
            fused_score=fused_score,
            rank=rank,
            contributions=(
                RetrievalContribution(strategy="semantic", rank=1, score=0.5),
            ),
        ),
        reranker_score=reranker_score,
        rank=rank,
    )

from dataclasses import FrozenInstanceError
from math import inf, nan
from uuid import uuid4

import pytest

from loreforge.embeddings import EmbeddingRequest, EmbeddingResult, EmbeddingVector


def test_embedding_request_accepts_valid_text() -> None:
    item_id = uuid4()

    request = EmbeddingRequest(item_id=item_id, text="Chunk text")

    assert request.item_id == item_id
    assert request.text == "Chunk text"


def test_embedding_request_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="text"):
        EmbeddingRequest(item_id=uuid4(), text="")


def test_embedding_request_rejects_whitespace_only_text() -> None:
    with pytest.raises(ValueError, match="text"):
        EmbeddingRequest(item_id=uuid4(), text="   ")


def test_embedding_request_is_immutable() -> None:
    request = EmbeddingRequest(item_id=uuid4(), text="Chunk text")

    with pytest.raises(FrozenInstanceError):
        request.text = "Changed text"


def test_embedding_vector_accepts_valid_values() -> None:
    item_id = uuid4()

    vector = EmbeddingVector(item_id=item_id, values=(0.1, -0.2, 1.0))

    assert vector.item_id == item_id
    assert vector.values == (0.1, -0.2, 1.0)


def test_embedding_vector_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="at least one"):
        EmbeddingVector(item_id=uuid4(), values=())


def test_embedding_vector_rejects_integer_value() -> None:
    with pytest.raises(ValueError, match="floats"):
        EmbeddingVector(item_id=uuid4(), values=(1,))  # type: ignore[arg-type]


def test_embedding_vector_rejects_string_value() -> None:
    with pytest.raises(ValueError, match="floats"):
        EmbeddingVector(item_id=uuid4(), values=("1.0",))  # type: ignore[arg-type]


def test_embedding_vector_rejects_boolean_value() -> None:
    with pytest.raises(ValueError, match="floats"):
        EmbeddingVector(item_id=uuid4(), values=(True,))  # type: ignore[arg-type]


def test_embedding_vector_rejects_nan() -> None:
    with pytest.raises(ValueError, match="finite"):
        EmbeddingVector(item_id=uuid4(), values=(nan,))


def test_embedding_vector_rejects_positive_infinity() -> None:
    with pytest.raises(ValueError, match="finite"):
        EmbeddingVector(item_id=uuid4(), values=(inf,))


def test_embedding_vector_rejects_negative_infinity() -> None:
    with pytest.raises(ValueError, match="finite"):
        EmbeddingVector(item_id=uuid4(), values=(-inf,))


def test_embedding_vector_is_immutable() -> None:
    vector = EmbeddingVector(item_id=uuid4(), values=(0.1,))

    with pytest.raises(FrozenInstanceError):
        vector.values = (0.2,)


def test_embedding_result_accepts_valid_vectors() -> None:
    first = EmbeddingVector(item_id=uuid4(), values=(0.1, 0.2))
    second = EmbeddingVector(item_id=uuid4(), values=(0.3, 0.4))

    result = EmbeddingResult(
        model="test-model",
        dimensions=2,
        vectors=(first, second),
    )

    assert result.model == "test-model"
    assert result.dimensions == 2
    assert result.vectors == (first, second)


def test_embedding_result_rejects_blank_model() -> None:
    with pytest.raises(ValueError, match="model"):
        EmbeddingResult(
            model=" ",
            dimensions=1,
            vectors=(EmbeddingVector(item_id=uuid4(), values=(0.1,)),),
        )


def test_embedding_result_rejects_non_positive_dimensions() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        EmbeddingResult(
            model="test-model",
            dimensions=0,
            vectors=(EmbeddingVector(item_id=uuid4(), values=(0.1,)),),
        )


def test_embedding_result_rejects_empty_vectors() -> None:
    with pytest.raises(ValueError, match="vectors"):
        EmbeddingResult(model="test-model", dimensions=1, vectors=())


def test_embedding_result_rejects_vector_dimension_mismatch() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        EmbeddingResult(
            model="test-model",
            dimensions=2,
            vectors=(EmbeddingVector(item_id=uuid4(), values=(0.1,)),),
        )


def test_embedding_result_rejects_duplicate_item_ids() -> None:
    item_id = uuid4()

    with pytest.raises(ValueError, match="unique"):
        EmbeddingResult(
            model="test-model",
            dimensions=1,
            vectors=(
                EmbeddingVector(item_id=item_id, values=(0.1,)),
                EmbeddingVector(item_id=item_id, values=(0.2,)),
            ),
        )


def test_embedding_result_preserves_vector_order() -> None:
    first = EmbeddingVector(item_id=uuid4(), values=(0.1,))
    second = EmbeddingVector(item_id=uuid4(), values=(0.2,))

    result = EmbeddingResult(
        model="test-model",
        dimensions=1,
        vectors=(first, second),
    )

    assert result.vectors == (first, second)


def test_embedding_result_is_immutable() -> None:
    result = EmbeddingResult(
        model="test-model",
        dimensions=1,
        vectors=(EmbeddingVector(item_id=uuid4(), values=(0.1,)),),
    )

    with pytest.raises(FrozenInstanceError):
        result.model = "changed-model"

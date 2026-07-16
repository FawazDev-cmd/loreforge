from math import inf, nan, sqrt

import pytest

from loreforge.vector_index import SimilarityError, cosine_similarity


def test_cosine_similarity_returns_one_for_identical_vectors() -> None:
    assert cosine_similarity((1.0, 2.0), (1.0, 2.0)) == pytest.approx(1.0)


def test_cosine_similarity_returns_negative_one_for_opposite_vectors() -> None:
    assert cosine_similarity((1.0, 0.0), (-1.0, 0.0)) == pytest.approx(-1.0)


def test_cosine_similarity_returns_zero_for_orthogonal_vectors() -> None:
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)


def test_cosine_similarity_handles_non_normalized_vectors() -> None:
    expected = 7.0 / (sqrt(25.0) * sqrt(2.0))

    assert cosine_similarity((3.0, 4.0), (1.0, 1.0)) == pytest.approx(expected)


def test_cosine_similarity_rejects_mismatched_dimensions() -> None:
    with pytest.raises(SimilarityError, match="dimensions"):
        cosine_similarity((1.0, 2.0), (1.0,))


def test_cosine_similarity_rejects_empty_vectors() -> None:
    with pytest.raises(SimilarityError, match="at least one"):
        cosine_similarity((), (1.0,))


def test_cosine_similarity_rejects_zero_magnitude_left_vector() -> None:
    with pytest.raises(SimilarityError, match="left"):
        cosine_similarity((0.0, 0.0), (1.0, 0.0))


def test_cosine_similarity_rejects_zero_magnitude_right_vector() -> None:
    with pytest.raises(SimilarityError, match="right"):
        cosine_similarity((1.0, 0.0), (0.0, 0.0))


def test_cosine_similarity_rejects_integer_values() -> None:
    with pytest.raises(SimilarityError, match="floats"):
        cosine_similarity((1,), (1.0,))  # type: ignore[arg-type]


def test_cosine_similarity_rejects_boolean_values() -> None:
    with pytest.raises(SimilarityError, match="floats"):
        cosine_similarity((True,), (1.0,))  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_cosine_similarity_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(SimilarityError, match="finite"):
        cosine_similarity((value,), (1.0,))


def test_cosine_similarity_does_not_mutate_inputs() -> None:
    left = (1.0, 2.0)
    right = (2.0, 1.0)

    cosine_similarity(left, right)

    assert left == (1.0, 2.0)
    assert right == (2.0, 1.0)

"""Strict cosine-similarity calculation."""

from math import isfinite, sqrt


class SimilarityError(ValueError):
    """Raised when vectors cannot be compared safely."""


def cosine_similarity(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> float:
    """Return exact cosine similarity for two finite non-zero float vectors."""
    _validate_vector(left, name="left")
    _validate_vector(right, name="right")

    if len(left) != len(right):
        msg = "vectors must have matching dimensions"
        raise SimilarityError(msg)

    left_magnitude = sqrt(sum(value * value for value in left))
    if left_magnitude == 0.0:
        msg = "left vector must not have zero magnitude"
        raise SimilarityError(msg)

    right_magnitude = sqrt(sum(value * value for value in right))
    if right_magnitude == 0.0:
        msg = "right vector must not have zero magnitude"
        raise SimilarityError(msg)

    dot_product = sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    )
    return float(dot_product / (left_magnitude * right_magnitude))


def _validate_vector(vector: tuple[float, ...], *, name: str) -> None:
    if not vector:
        msg = f"{name} vector must contain at least one value"
        raise SimilarityError(msg)

    for value in vector:
        if type(value) is not float:
            msg = f"{name} vector must contain only floats"
            raise SimilarityError(msg)

        if not isfinite(value):
            msg = f"{name} vector values must be finite"
            raise SimilarityError(msg)

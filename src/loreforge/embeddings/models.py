"""Framework-independent embedding domain contracts."""

from dataclasses import dataclass
from math import isfinite
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    """Text item to be embedded by a provider."""

    item_id: UUID
    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            msg = "text must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """Embedding values returned for a single requested item."""

    item_id: UUID
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if type(self.values) is not tuple:
            msg = "values must be a tuple of floats"
            raise ValueError(msg)

        if not self.values:
            msg = "values must contain at least one value"
            raise ValueError(msg)

        for value in self.values:
            if type(value) is not float:
                msg = "values must contain only floats"
                raise ValueError(msg)

            if not isfinite(value):
                msg = "values must be finite"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Embedding vectors produced by one model."""

    model: str
    dimensions: int
    vectors: tuple[EmbeddingVector, ...]

    def __post_init__(self) -> None:
        if not self.model.strip():
            msg = "model must not be empty"
            raise ValueError(msg)

        if self.dimensions <= 0:
            msg = "dimensions must be greater than zero"
            raise ValueError(msg)

        if not self.vectors:
            msg = "vectors must contain at least one vector"
            raise ValueError(msg)

        item_ids = tuple(vector.item_id for vector in self.vectors)
        if len(set(item_ids)) != len(item_ids):
            msg = "vector item_id values must be unique"
            raise ValueError(msg)

        for vector in self.vectors:
            if len(vector.values) != self.dimensions:
                msg = "vector dimensions must match result dimensions"
                raise ValueError(msg)

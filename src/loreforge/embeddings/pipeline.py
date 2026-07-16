"""Framework-independent chunk embedding pipeline."""

from dataclasses import dataclass

from loreforge.documents.models import DocumentChunk
from loreforge.embeddings.models import EmbeddingRequest, EmbeddingVector
from loreforge.embeddings.provider import EmbeddingProvider


class EmbeddingPipelineError(ValueError):
    """Raised when a provider violates the ordered chunk embedding contract."""


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    """Document chunk paired with its validated embedding vector."""

    chunk: DocumentChunk
    vector: EmbeddingVector

    def __post_init__(self) -> None:
        if self.vector.item_id != self.chunk.chunk_id:
            msg = "vector item_id must match chunk chunk_id"
            raise ValueError(msg)


def embed_chunks(
    *,
    chunks: tuple[DocumentChunk, ...],
    provider: EmbeddingProvider,
) -> tuple[EmbeddedChunk, ...]:
    """Embed ordered document chunks with a provider and validate the response."""
    if not chunks:
        msg = "chunks must contain at least one chunk"
        raise ValueError(msg)

    requests = tuple(
        EmbeddingRequest(item_id=chunk.chunk_id, text=chunk.text) for chunk in chunks
    )
    result = provider.embed(requests)

    if len(result.vectors) != len(chunks):
        msg = "provider returned a different number of vectors than chunks"
        raise EmbeddingPipelineError(msg)

    embedded_chunks: list[EmbeddedChunk] = []
    for chunk, vector in zip(chunks, result.vectors, strict=True):
        if vector.item_id != chunk.chunk_id:
            msg = "provider returned vectors out of chunk order"
            raise EmbeddingPipelineError(msg)

        embedded_chunks.append(EmbeddedChunk(chunk=chunk, vector=vector))

    return tuple(embedded_chunks)

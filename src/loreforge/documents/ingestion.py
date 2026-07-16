"""Framework-independent PDF ingestion orchestration."""

from dataclasses import dataclass
from uuid import UUID

from loreforge.documents.chunking import ChunkingConfig, chunk_document
from loreforge.documents.models import DocumentChunk, DocumentSource, ParsedDocument
from loreforge.documents.normalization import normalize_document
from loreforge.documents.parsing import parse_pdf


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Normalized parsed document and its citation-aware chunks."""

    document: ParsedDocument
    chunks: tuple[DocumentChunk, ...]


def ingest_pdf(
    *,
    document_id: UUID,
    source: DocumentSource,
    content: bytes,
    chunking_config: ChunkingConfig = ChunkingConfig(),
) -> IngestionResult:
    """Parse, normalize, and chunk PDF bytes without persistence."""
    parsed_document = parse_pdf(
        document_id=document_id,
        source=source,
        content=content,
    )
    normalized_document = normalize_document(parsed_document)
    chunks = chunk_document(normalized_document, chunking_config)

    return IngestionResult(document=normalized_document, chunks=chunks)

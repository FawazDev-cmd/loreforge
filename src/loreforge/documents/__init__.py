"""Public document contracts for LoreForge."""

from loreforge.documents.chunking import (
    LOREFORGE_CHUNK_NAMESPACE,
    ChunkingConfig,
    chunk_document,
)
from loreforge.documents.ingestion import IngestionResult, ingest_pdf
from loreforge.documents.models import (
    DocumentChunk,
    DocumentPage,
    DocumentSource,
    ParsedDocument,
)
from loreforge.documents.normalization import (
    TextNormalizationError,
    normalize_document,
)
from loreforge.documents.parsing import PdfParsingError, parse_pdf
from loreforge.documents.upload import (
    MAX_UPLOAD_SIZE_BYTES,
    PDF_MEDIA_TYPE,
    PDF_SIGNATURE,
    UnsupportedDocumentError,
    ValidatedUpload,
    validate_pdf_upload,
)

__all__ = [
    "DocumentPage",
    "DocumentSource",
    "DocumentChunk",
    "ChunkingConfig",
    "IngestionResult",
    "LOREFORGE_CHUNK_NAMESPACE",
    "MAX_UPLOAD_SIZE_BYTES",
    "PDF_MEDIA_TYPE",
    "PDF_SIGNATURE",
    "PdfParsingError",
    "ParsedDocument",
    "TextNormalizationError",
    "UnsupportedDocumentError",
    "ValidatedUpload",
    "chunk_document",
    "ingest_pdf",
    "normalize_document",
    "parse_pdf",
    "validate_pdf_upload",
]

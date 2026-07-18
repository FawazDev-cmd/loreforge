# Ingestion Pipeline

LoreForge's document ingestion pipeline is a framework-independent document-processing use case. It connects verified stages for validating PDF inputs, extracting page text, normalizing content, and creating citation-aware chunks.

The core ingestion package does not depend on FastAPI, embeddings, indexes, retrieval, generation, or persistence. API indexing support is implemented separately in `loreforge.indexing`, which composes ingestion with embedding and index writers.

## Core Flow

```text
PDF bytes
  -> validate_pdf_upload
  -> parse_pdf
  -> normalize_document
  -> chunk_document
  -> IngestionResult
```

The public orchestration entry point is `ingest_pdf(...)` in `loreforge.documents`. It returns an immutable `IngestionResult` containing:

- `document`: the normalized `ParsedDocument`
- `chunks`: citation-aware `DocumentChunk` values generated from that normalized document

## Stage Responsibilities

### Upload Validation

`validate_pdf_upload(...)` validates client-provided PDF metadata and bytes. It checks filename, media type, size, and PDF signature. It does not parse, persist, normalize, embed, or index content.

### Parsing

`parse_pdf(...)` reads PDF bytes from memory, extracts page text with `pypdf`, preserves the supplied document ID and source metadata, and returns page-aware `ParsedDocument` values. It rejects malformed, unreadable, encrypted, zero-page, and textless PDFs through `PdfParsingError`.

### Normalization

`normalize_document(...)` makes page text deterministic enough for downstream chunking while preserving page boundaries, punctuation, capitalization, Unicode text, and paragraph structure. It does not remove repeated headers or footers, reconstruct layout, dehyphenate text, or join lines into sentences.

### Chunking

`chunk_document(...)` creates immutable, page-bounded `DocumentChunk` values. Chunks preserve document ID, source metadata, page number, document-wide chunk index, and deterministic UUID5 chunk IDs. Chunks never cross page boundaries.

### Orchestration

`ingest_pdf(...)` calls the existing stages in order and returns their composed result. It does not catch or wrap expected stage exceptions, so `PdfParsingError`, `TextNormalizationError`, and invalid chunk configuration errors remain visible to callers.

## Runtime Indexing Integration

The document-indexing service in `loreforge.indexing` composes the core ingestion pipeline with runtime application state:

```text
registered catalog entry
  -> PDF validation and ingestion
  -> document embedding
  -> shared in-memory vector index
  -> shared in-memory BM25 index
  -> catalog status update
```

The admin route `POST /admin/documents/{document_id}/index` exposes this indexing workflow. It requires a previously registered catalog entry, validates the uploaded PDF, populates both shared indexes, and marks the catalog entry `READY` after successful indexing.

If indexing fails after the document enters `INGESTING`, the service rolls back semantic and lexical index writes for the generated chunks, marks the catalog entry `FAILED`, and returns a safe unavailable error through the API.

## Tradeoffs

The current pipeline is intentionally conservative:

- It uses character-based chunking rather than token-aware or semantic chunking.
- It prefers deterministic behavior over clever layout interpretation.
- It keeps all processing and runtime indexes in memory for the current portfolio-sized slice.
- It keeps FastAPI outside the document-processing core.
- It favors page-level citation traceability over cross-page chunk continuity.

These tradeoffs keep the pipeline easy to test, explain, and replace later.

## Current Limitations

The document-processing and indexing path does not currently implement:

- file or chunk persistence
- OCR
- repeated-header or repeated-footer removal
- table or multi-column reconstruction
- token-aware chunking
- persistent vector or BM25 storage
- authentication or authorization around indexing endpoints
- background jobs for long-running ingestion

Retrieval, reranking, grounded generation, citation validation, runtime observability, and API integration exist elsewhere in the backend, but live provider reliability and durable storage are still future hardening work.

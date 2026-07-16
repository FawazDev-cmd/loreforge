# Ingestion Pipeline

LoreForge's ingestion pipeline is a framework-independent document-processing use case. It connects already verified stages without adding API integration, persistence, embeddings, indexing, retrieval, or generation.

## Flow

```text
PDF bytes
  -> parse_pdf
  -> normalize_document
  -> chunk_document
  -> IngestionResult
```

The public entry point is `ingest_pdf(...)` in `loreforge.documents`. It returns an immutable `IngestionResult` containing:

* `document`: the normalized `ParsedDocument`
* `chunks`: citation-aware `DocumentChunk` values generated from that normalized document

## Stage Responsibilities

### Upload Validation

`validate_pdf_upload(...)` validates client-provided PDF metadata and bytes. It checks filename, media type, size, and PDF signature. It does not parse, persist, or normalize content.

### Parsing

`parse_pdf(...)` reads PDF bytes from memory, extracts page text with `pypdf`, preserves the supplied document ID and source metadata, and returns page-aware `ParsedDocument` values. It rejects malformed, unreadable, encrypted, zero-page, and textless PDFs through `PdfParsingError`.

### Normalization

`normalize_document(...)` makes page text deterministic enough for downstream chunking while preserving page boundaries, punctuation, capitalization, Unicode text, and paragraph structure. It does not remove repeated headers or footers, reconstruct layout, dehyphenate text, or join lines into sentences.

### Chunking

`chunk_document(...)` creates immutable, page-bounded `DocumentChunk` values. Chunks preserve document ID, source metadata, page number, document-wide chunk index, and deterministic UUID5 chunk IDs. Chunks never cross page boundaries.

### Orchestration

`ingest_pdf(...)` calls the existing stages in order and returns their composed result. It does not catch or wrap expected stage exceptions, so `PdfParsingError`, `TextNormalizationError`, and invalid chunk configuration errors remain visible to callers.

## Tradeoffs

The current pipeline is intentionally conservative:

* It uses character-based chunking rather than token-aware or semantic chunking.
* It prefers deterministic behavior over clever layout interpretation.
* It keeps all work in memory for the current portfolio-sized slice.
* It keeps FastAPI outside the document-processing core.
* It favors page-level citation traceability over cross-page chunk continuity.

These tradeoffs keep the pipeline easy to test, explain, and replace later.

## Current Limitations

The pipeline does not currently implement:

* upload-to-ingestion API integration
* file or chunk persistence
* OCR
* repeated-header or repeated-footer removal
* table or multi-column reconstruction
* embeddings
* vector or BM25 indexing
* retrieval
* answer generation
* citation rendering

Those capabilities should be added only through scoped, verified milestones.

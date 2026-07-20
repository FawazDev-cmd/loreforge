# Architecture Guide

LoreForge is organized around Clean Architecture: framework-specific code is kept
at the edges, while document processing, retrieval, generation, evaluation, and
observability logic stay framework-independent where practical.

## Request Lifecycle

```mermaid
sequenceDiagram
  participant Client
  participant FastAPI
  participant Container as ApplicationContainer
  participant Service as Application Service
  participant Core as Core Logic
  Client->>FastAPI: HTTP request
  FastAPI->>FastAPI: request ID, auth, validation
  FastAPI->>Container: resolve service
  Container->>Service: invoke use case
  Service->>Core: execute domain workflow
  Core-->>Service: typed result or typed error
  Service-->>FastAPI: response model
  FastAPI-->>Client: HTTP response + X-Request-ID
```

Transport concerns such as request parsing, response codes, and auth headers live
under `src/loreforge/api`. Core services receive typed inputs and do not depend
on FastAPI request objects.

## Ingestion Lifecycle

```mermaid
flowchart LR
  A[Registered catalog entry] --> B[PDF upload validation]
  B --> C[Page-aware parsing]
  C --> D[Text normalization]
  D --> E[Citation-aware chunking]
  E --> F[Embedding provider]
  F --> G[Chunk and embedding persistence]
  G --> H[Vector index + BM25 index]
  H --> I[Catalog READY]
```

Failures after indexing begins attempt rollback for semantic, lexical, chunk, and
embedding writes, then mark the document failed. Ownership is enforced before
document metadata, indexing, and retrieval operations.

## Retrieval Lifecycle

```mermaid
flowchart LR
  Q[Question] --> E[Query embedding]
  E --> S[Vector retrieval]
  Q --> B[BM25 retrieval]
  S --> F[Reciprocal Rank Fusion]
  B --> F
  F --> R[Reranking]
  R --> C[Evidence context]
  C --> P[Grounded prompt]
  P --> G[Provider generation]
  G --> V[Citation validation]
```

The production query engine composes existing retrieval, reranking, evidence,
prompt, generation, and citation components. It does not instantiate providers or
read configuration. Concrete dependencies are supplied by the application
composition root.

## Evaluation Lifecycle

```mermaid
flowchart LR
  D[JSON dataset] --> L[Dataset validation]
  T[Threshold JSON] --> G[Regression gate]
  L --> R[Fixture runner]
  R --> M[Metrics]
  M --> G
  G --> J[JSON report]
  G --> H[Human report]
```

The current evaluator is deterministic fixture mode. It is suitable for CI and
portfolio review because it avoids live providers, live databases, network
access, and nondeterministic model judging.

## Observability Flow

```mermaid
flowchart LR
  H[HTTP middleware] --> C[Request-local context]
  H --> L[Structured request log]
  H --> M[HTTP metrics]
  R[Readiness] --> M
  Q[Query engine] --> T[Query trace]
  Q --> M
  I[Indexing service] --> M
  P[Provider adapters] --> M
  M --> E[/metrics snapshot]
```

Metrics use bounded labels and avoid request IDs, user IDs, document IDs,
filenames, prompts, full questions, answers, raw document text, vectors, secrets,
and provider payloads.

## Dependency Direction

```text
API adapters
  -> application composition/services
  -> LoreForge-owned protocols and core workflows
  -> infrastructure adapters
  -> external libraries/providers
```

Provider-specific clients belong at infrastructure boundaries. Business logic
should depend on LoreForge contracts or narrow callables, not hosted vendor SDKs.

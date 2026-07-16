"""Semantic retrieval over an existing vector index."""

from loreforge.embeddings import QueryEmbeddingProvider
from loreforge.retrieval.models import SemanticSearchRequest, SemanticSearchResponse
from loreforge.vector_index import InMemoryVectorIndex


def semantic_search(
    *,
    request: SemanticSearchRequest,
    provider: QueryEmbeddingProvider,
    index: InMemoryVectorIndex,
) -> SemanticSearchResponse:
    """Embed a user question and search the supplied vector index."""
    query_vector = provider.embed_query(request.question)
    results = index.search(
        query_vector=query_vector.values,
        top_k=request.top_k,
    )

    return SemanticSearchResponse(
        question=request.question,
        results=results,
    )

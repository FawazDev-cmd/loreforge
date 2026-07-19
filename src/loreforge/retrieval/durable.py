"""Repository-backed durable hybrid retrieval."""

from loreforge.embeddings import QueryEmbeddingProvider
from loreforge.retrieval.filters import RetrievalFilter
from loreforge.retrieval.hybrid import reciprocal_rank_fusion
from loreforge.retrieval.hybrid_models import HybridSearchRequest, HybridSearchResponse
from loreforge.retrieval.lexical_models import LexicalSearchRequest
from loreforge.retrieval.repository import RetrievalRepository


def durable_hybrid_search(
    *,
    request: HybridSearchRequest,
    semantic_provider: QueryEmbeddingProvider,
    repository: RetrievalRepository,
    filters: RetrievalFilter = RetrievalFilter(),
    rrf_k: int = 60,
) -> HybridSearchResponse:
    """Run hybrid retrieval over persisted chunks and embeddings."""
    query_vector = semantic_provider.embed_query(request.question)
    semantic_results = repository.vector_search(
        query_vector=query_vector.values,
        top_k=request.semantic_top_k,
        filters=filters,
    )
    lexical_response = repository.lexical_search(
        LexicalSearchRequest(query=request.question, top_k=request.lexical_top_k),
        filters=filters,
    )
    results = reciprocal_rank_fusion(
        semantic_results=semantic_results,
        lexical_results=lexical_response.results,
        top_k=request.top_k,
        rrf_k=rrf_k,
    )
    return HybridSearchResponse(question=request.question, results=results)

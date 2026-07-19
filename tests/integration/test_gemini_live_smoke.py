import os
from uuid import UUID

import pytest

from loreforge.embeddings import (
    EmbeddingRequest,
    GeminiEmbeddingConfig,
    GeminiEmbeddingProvider,
)
from loreforge.generation import (
    GeminiGenerationConfig,
    GeminiLLMProvider,
    GenerationRequest,
)
from loreforge.settings import load_settings


def test_live_gemini_provider_smoke_requires_explicit_opt_in() -> None:
    if os.environ.get("LOREFORGE_RUN_LIVE_GEMINI_SMOKE") != "true":
        pytest.skip("Set LOREFORGE_RUN_LIVE_GEMINI_SMOKE=true to run live smoke.")

    settings = load_settings()
    if settings.providers.gemini.api_key is None:
        pytest.skip("Gemini API key is not configured.")
    if settings.providers.gemini.embedding_model is None:
        pytest.skip("Gemini embedding model is not configured.")
    if settings.providers.gemini.generation_model is None:
        pytest.skip("Gemini generation model is not configured.")

    embedding_provider = GeminiEmbeddingProvider(
        GeminiEmbeddingConfig(
            api_key=settings.providers.gemini.api_key,
            model=settings.providers.gemini.embedding_model,
            timeout_seconds=settings.providers.gemini.timeout_seconds,
        )
    )
    document_result = embedding_provider.embed_documents(
        (
            EmbeddingRequest(
                item_id=_stable_uuid(),
                text="LoreForge smoke document about citation-grounded answers.",
            ),
        )
    )
    query_vector = embedding_provider.embed_query("What does the smoke document cover?")

    assert document_result.model == settings.providers.gemini.embedding_model
    assert document_result.dimensions > 0
    assert len(query_vector.values) == document_result.dimensions

    llm_provider = GeminiLLMProvider(
        GeminiGenerationConfig(
            api_key=settings.providers.gemini.api_key,
            model=settings.providers.gemini.generation_model,
            timeout_seconds=settings.providers.gemini.timeout_seconds,
        )
    )
    generation = llm_provider.generate(
        GenerationRequest(
            system_prompt="Answer with exactly: Gemini smoke OK [S1].",
            user_prompt="Return the required smoke-test answer.",
            max_output_tokens=32,
            temperature=0.0,
        )
    )

    assert generation.model == settings.providers.gemini.generation_model
    assert generation.text.strip()


def _stable_uuid() -> UUID:
    return UUID("00000000-0000-0000-0000-000000009999")

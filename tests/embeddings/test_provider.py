from uuid import uuid4

from loreforge.embeddings import (
    EmbeddingProvider,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingVector,
)


class FakeEmbeddingProvider:
    def embed(
        self,
        requests: tuple[EmbeddingRequest, ...],
    ) -> EmbeddingResult:
        vectors = tuple(
            EmbeddingVector(
                item_id=request.item_id,
                values=(float(index), float(len(request.text))),
            )
            for index, request in enumerate(requests)
        )
        return EmbeddingResult(
            model="fake-embedding-model",
            dimensions=2,
            vectors=vectors,
        )


class IncompatibleProvider:
    pass


def test_fake_provider_satisfies_embedding_provider_protocol() -> None:
    fake = FakeEmbeddingProvider()

    assert isinstance(fake, EmbeddingProvider)


def test_fake_provider_returns_embedding_result() -> None:
    fake = FakeEmbeddingProvider()
    requests = (
        EmbeddingRequest(item_id=uuid4(), text="First chunk"),
        EmbeddingRequest(item_id=uuid4(), text="Second chunk"),
    )

    result = fake.embed(requests)

    assert isinstance(result, EmbeddingResult)
    assert result.model == "fake-embedding-model"
    assert result.dimensions == 2


def test_fake_provider_preserves_request_item_ids_and_order() -> None:
    fake = FakeEmbeddingProvider()
    requests = (
        EmbeddingRequest(item_id=uuid4(), text="First chunk"),
        EmbeddingRequest(item_id=uuid4(), text="Second chunk"),
        EmbeddingRequest(item_id=uuid4(), text="Third chunk"),
    )

    result = fake.embed(requests)

    assert [vector.item_id for vector in result.vectors] == [
        request.item_id for request in requests
    ]


def test_incompatible_object_does_not_satisfy_embedding_provider_protocol() -> None:
    assert not isinstance(IncompatibleProvider(), EmbeddingProvider)

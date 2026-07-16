from uuid import uuid4

from loreforge.reranking import RerankerProvider, RerankingRequest, RerankingScore


class FakeRerankerProvider:
    def score(
        self, requests: tuple[RerankingRequest, ...]
    ) -> tuple[RerankingScore, ...]:
        return tuple(
            RerankingScore(item_id=request.item_id, score=float(index))
            for index, request in enumerate(requests, start=1)
        )


class IncompatibleProvider:
    pass


def test_fake_provider_satisfies_reranker_provider_protocol() -> None:
    assert isinstance(FakeRerankerProvider(), RerankerProvider)


def test_incompatible_object_does_not_satisfy_reranker_provider_protocol() -> None:
    assert not isinstance(IncompatibleProvider(), RerankerProvider)


def test_fake_provider_returns_ordered_ids_and_scores() -> None:
    first_id = uuid4()
    second_id = uuid4()
    provider = FakeRerankerProvider()

    scores = provider.score(
        (
            RerankingRequest(item_id=first_id, query="q", passage="first"),
            RerankingRequest(item_id=second_id, query="q", passage="second"),
        )
    )

    assert [score.item_id for score in scores] == [first_id, second_id]
    assert [score.score for score in scores] == [1.0, 2.0]

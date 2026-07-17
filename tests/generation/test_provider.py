from loreforge.generation import GenerationRequest, GenerationResponse, LLMProvider


class FakeProvider:
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        return GenerationResponse(text="answer", model="fake", finish_reason="stop")


class IncompatibleProvider:
    pass


def test_compatible_fake_satisfies_llm_provider() -> None:
    assert isinstance(FakeProvider(), LLMProvider)


def test_incompatible_object_does_not_satisfy_llm_provider() -> None:
    assert not isinstance(IncompatibleProvider(), LLMProvider)


def test_fake_provider_returns_valid_response() -> None:
    request = GenerationRequest(system_prompt="system", user_prompt="user")

    response = FakeProvider().generate(request)

    assert response == GenerationResponse(
        text="answer", model="fake", finish_reason="stop"
    )

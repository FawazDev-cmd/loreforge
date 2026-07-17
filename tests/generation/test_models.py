from dataclasses import FrozenInstanceError
from math import inf, nan
from uuid import UUID

import pytest

from loreforge.generation import (
    EvidenceContext,
    EvidenceItem,
    GenerationRequest,
    GenerationResponse,
    PromptPackage,
    generation_request_from_prompt,
)


def test_generation_request_accepts_valid_defaults() -> None:
    request = GenerationRequest(system_prompt="system", user_prompt="user")

    assert request.system_prompt == "system"
    assert request.user_prompt == "user"
    assert request.max_output_tokens == 800
    assert request.temperature == 0.0


def test_generation_request_accepts_valid_custom_values() -> None:
    request = GenerationRequest(
        system_prompt="system",
        user_prompt="user",
        max_output_tokens=128,
        temperature=1.25,
    )

    assert request.max_output_tokens == 128
    assert request.temperature == 1.25


@pytest.mark.parametrize("system_prompt", ["", "   "])
def test_generation_request_rejects_blank_system_prompt(system_prompt: str) -> None:
    with pytest.raises(ValueError, match="system_prompt"):
        GenerationRequest(system_prompt=system_prompt, user_prompt="user")


@pytest.mark.parametrize("user_prompt", ["", "   "])
def test_generation_request_rejects_blank_user_prompt(user_prompt: str) -> None:
    with pytest.raises(ValueError, match="user_prompt"):
        GenerationRequest(system_prompt="system", user_prompt=user_prompt)


@pytest.mark.parametrize("max_output_tokens", [0, -1])
def test_generation_request_rejects_non_positive_output_tokens(
    max_output_tokens: int,
) -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        GenerationRequest(
            system_prompt="system",
            user_prompt="user",
            max_output_tokens=max_output_tokens,
        )


def test_generation_request_rejects_boolean_output_tokens() -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        GenerationRequest(
            system_prompt="system",
            user_prompt="user",
            max_output_tokens=True,  # type: ignore[arg-type]
        )


def test_generation_request_rejects_non_float_temperature() -> None:
    with pytest.raises(ValueError, match="temperature"):
        GenerationRequest(
            system_prompt="system",
            user_prompt="user",
            temperature=1,  # type: ignore[arg-type]
        )


def test_generation_request_rejects_boolean_temperature() -> None:
    with pytest.raises(ValueError, match="temperature"):
        GenerationRequest(
            system_prompt="system",
            user_prompt="user",
            temperature=True,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("temperature", [nan, inf, -inf])
def test_generation_request_rejects_non_finite_temperature(
    temperature: float,
) -> None:
    with pytest.raises(ValueError, match="finite"):
        GenerationRequest(
            system_prompt="system", user_prompt="user", temperature=temperature
        )


def test_generation_request_rejects_temperature_below_zero() -> None:
    with pytest.raises(ValueError, match="temperature"):
        GenerationRequest(system_prompt="system", user_prompt="user", temperature=-0.1)


def test_generation_request_rejects_temperature_above_two() -> None:
    with pytest.raises(ValueError, match="temperature"):
        GenerationRequest(system_prompt="system", user_prompt="user", temperature=2.1)


@pytest.mark.parametrize("temperature", [0.0, 2.0])
def test_generation_request_accepts_boundary_temperatures(temperature: float) -> None:
    request = GenerationRequest(
        system_prompt="system", user_prompt="user", temperature=temperature
    )

    assert request.temperature == temperature


def test_generation_request_is_immutable() -> None:
    request = GenerationRequest(system_prompt="system", user_prompt="user")

    with pytest.raises(FrozenInstanceError):
        request.temperature = 1.0


def test_generation_response_accepts_finish_reason() -> None:
    response = GenerationResponse(text="answer", model="model", finish_reason="stop")

    assert response.finish_reason == "stop"


def test_generation_response_accepts_missing_finish_reason() -> None:
    response = GenerationResponse(text="answer", model="model", finish_reason=None)

    assert response.finish_reason is None


@pytest.mark.parametrize("text", ["", "   "])
def test_generation_response_rejects_blank_text(text: str) -> None:
    with pytest.raises(ValueError, match="text"):
        GenerationResponse(text=text, model="model", finish_reason="stop")


@pytest.mark.parametrize("model", ["", "   "])
def test_generation_response_rejects_blank_model(model: str) -> None:
    with pytest.raises(ValueError, match="model"):
        GenerationResponse(text="answer", model=model, finish_reason="stop")


@pytest.mark.parametrize("finish_reason", ["", "   "])
def test_generation_response_rejects_blank_finish_reason(
    finish_reason: str,
) -> None:
    with pytest.raises(ValueError, match="finish_reason"):
        GenerationResponse(text="answer", model="model", finish_reason=finish_reason)


def test_generation_response_is_immutable() -> None:
    response = GenerationResponse(text="answer", model="model", finish_reason="stop")

    with pytest.raises(FrozenInstanceError):
        response.text = "changed"


def test_prompt_conversion_copies_exact_system_prompt() -> None:
    prompt = _prompt_package(system_prompt="  exact system  ")

    request = generation_request_from_prompt(prompt)

    assert request.system_prompt == "  exact system  "


def test_prompt_conversion_copies_exact_user_prompt() -> None:
    prompt = _prompt_package(user_prompt="  exact user  ")

    request = generation_request_from_prompt(prompt)

    assert request.user_prompt == "  exact user  "


def test_prompt_conversion_applies_generation_settings() -> None:
    request = generation_request_from_prompt(
        _prompt_package(), max_output_tokens=64, temperature=0.5
    )

    assert request.max_output_tokens == 64
    assert request.temperature == 0.5


def test_prompt_conversion_does_not_mutate_evidence() -> None:
    prompt = _prompt_package()
    before = prompt.evidence

    generation_request_from_prompt(prompt)

    assert prompt.evidence == before


def test_prompt_conversion_is_deterministic() -> None:
    prompt = _prompt_package()

    first = generation_request_from_prompt(prompt)
    second = generation_request_from_prompt(prompt)

    assert first == second


def _prompt_package(
    *, system_prompt: str = "system", user_prompt: str = "user"
) -> PromptPackage:
    return PromptPackage(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        evidence=_evidence_context(),
    )


def _evidence_context() -> EvidenceContext:
    item = EvidenceItem(
        citation_id="S1",
        chunk_id=UUID("00000000-0000-0000-0000-000000000101"),
        document_id=UUID("00000000-0000-0000-0000-000000000201"),
        filename="guide.pdf",
        page_number=1,
        text="Evidence.",
        reranker_score=0.5,
        retrieval_rank=1,
    )
    rendered_text = "[S1]\nSource: guide.pdf\nPage: 1\nContent:\nEvidence."
    return EvidenceContext(
        items=(item,),
        rendered_text=rendered_text,
        total_characters=len(rendered_text),
        truncated=False,
    )

import pytest

from loreforge.retrieval import tokenize


def test_tokenize_normal_lowercase_words() -> None:
    assert tokenize("leave policy") == ("leave", "policy")


def test_tokenize_normalizes_uppercase() -> None:
    assert tokenize("Leave Policy 2026") == ("leave", "policy", "2026")


def test_tokenize_extracts_numbers() -> None:
    assert tokenize("Section 42 version 2026") == ("section", "42", "version", "2026")


def test_tokenize_excludes_surrounding_punctuation() -> None:
    assert tokenize("...Hello, world!") == ("hello", "world")


def test_tokenize_handles_repeated_whitespace() -> None:
    assert tokenize("alpha    beta") == ("alpha", "beta")


def test_tokenize_handles_newlines_and_tabs() -> None:
    assert tokenize("alpha\nbeta\tgamma") == ("alpha", "beta", "gamma")


def test_tokenize_preserves_unicode_words() -> None:
    assert tokenize("Café résumé") == ("café", "résumé")


def test_tokenize_preserves_internal_apostrophes() -> None:
    assert tokenize("Employee's guide isn't optional") == (
        "employee's",
        "guide",
        "isn't",
        "optional",
    )


def test_tokenize_splits_hyphens_and_underscores() -> None:
    assert tokenize("API_ERROR-42") == ("api", "error", "42")


def test_tokenize_rejects_blank_input() -> None:
    with pytest.raises(ValueError, match="text"):
        tokenize("   ")


def test_tokenize_returns_immutable_tuple() -> None:
    assert isinstance(tokenize("alpha beta"), tuple)


def test_tokenize_is_deterministic() -> None:
    text = "Policy API_ERROR-42"

    assert tokenize(text) == tokenize(text)


def test_tokenize_does_not_mutate_input() -> None:
    text = "Employee's guide"

    tokenize(text)

    assert text == "Employee's guide"

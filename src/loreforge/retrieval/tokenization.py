"""Deterministic tokenization for lexical retrieval."""

import re

_TOKEN_PATTERN = re.compile(r"[^\W_]+(?:'[^\W_]+)*", re.UNICODE)


def tokenize(text: str) -> tuple[str, ...]:
    """Return lowercase Unicode word tokens, splitting underscores and hyphens."""
    if not text.strip():
        msg = "text must not be empty"
        raise ValueError(msg)

    return tuple(match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text))

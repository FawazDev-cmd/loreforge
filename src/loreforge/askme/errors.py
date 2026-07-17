"""AskMe application-level errors."""


class AskMeError(Exception):
    """Base class for safe AskMe application errors."""


class AskMeUnavailableError(AskMeError):
    """Raised when AskMe cannot currently answer a request."""


class AskMeGroundingError(AskMeError):
    """Raised when a grounded answer is structurally unsafe to return."""

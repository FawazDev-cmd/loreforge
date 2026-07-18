"""Safe query-composition errors."""


class QueryCompositionError(Exception):
    """Raised when grounded query composition cannot produce a safe answer."""


class NoRelevantEvidenceError(QueryCompositionError):
    """Raised when retrieval and evidence construction produce no usable evidence."""


class QueryExecutionError(QueryCompositionError):
    """Raised when a query pipeline collaborator fails unexpectedly."""

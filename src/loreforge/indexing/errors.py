"""Safe document indexing errors."""


class DocumentIndexingError(Exception):
    """Base class for safe document indexing failures."""


class DocumentAlreadyIndexedError(DocumentIndexingError):
    """Raised when a ready catalog document is indexed again."""


class DocumentIndexingExecutionError(DocumentIndexingError):
    """Raised when indexing cannot complete safely."""

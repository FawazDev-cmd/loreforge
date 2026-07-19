"""Metadata filters for repository-backed retrieval."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RetrievalFilter:
    """Optional metadata constraints for retrieval candidates."""

    document_ids: tuple[UUID, ...] = ()
    filenames: tuple[str, ...] = ()
    owner_user_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        if type(self.document_ids) is not tuple:
            msg = "document_ids must be a tuple"
            raise ValueError(msg)
        if type(self.filenames) is not tuple:
            msg = "filenames must be a tuple"
            raise ValueError(msg)
        if type(self.owner_user_ids) is not tuple:
            msg = "owner_user_ids must be a tuple"
            raise ValueError(msg)

        for document_id in self.document_ids:
            if type(document_id) is not UUID:
                msg = "document_ids must contain only UUID values"
                raise ValueError(msg)

        for filename in self.filenames:
            if not filename.strip():
                msg = "filenames must not contain empty values"
                raise ValueError(msg)

        for owner_user_id in self.owner_user_ids:
            if type(owner_user_id) is not UUID:
                msg = "owner_user_ids must contain only UUID values"
                raise ValueError(msg)

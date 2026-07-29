"""In-process application lifecycle readiness state."""

from dataclasses import dataclass


@dataclass(slots=True)
class ApplicationRuntimeState:
    """Mutable readiness flag owned by one application runtime instance."""

    ready: bool = False

    def mark_ready(self) -> None:
        """Mark the application as ready to serve traffic."""
        self.ready = True

    def mark_not_ready(self) -> None:
        """Mark the application as not ready to serve traffic."""
        self.ready = False


__all__ = ["ApplicationRuntimeState"]

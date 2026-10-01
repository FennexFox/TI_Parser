"""Structured user-facing errors for save input and entity selection."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


class UserInputError(ValueError):
    """Base class for expected, JSON-serializable input failures."""

    default_code = "invalid-input"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        candidates: Sequence[Mapping[str, Any]] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code or self.default_code
        self.message = message
        self.candidates = [dict(candidate) for candidate in candidates] if candidates is not None else None
        self.context = dict(context) if context is not None else None

    def to_dict(self) -> dict[str, Any]:
        """Return the stable payload emitted by user-facing command handlers."""

        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.candidates is not None:
            payload["candidates"] = [dict(candidate) for candidate in self.candidates]
        if self.context is not None:
            payload["context"] = dict(self.context)
        return payload


class EntityLookupError(UserInputError):
    """Raised when an entity selector cannot resolve to exactly one state."""

    default_code = "entity-lookup-failed"


class SaveIntegrityError(UserInputError):
    """Raised when a save cannot be decoded or violates its state structure."""

    default_code = "invalid-save"

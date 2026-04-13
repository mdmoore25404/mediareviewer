"""Companion file actions for lock/trash/seen media state."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CompanionStatus:
    """State represented by companion files for a media item."""

    locked: bool
    trashed: bool
    seen: bool


class CompanionActionService:
    """Create or remove companion files for media review actions."""

    def apply(self, media_path: Path, action: str) -> CompanionStatus:
        """Apply a review action and return the resulting companion status."""

        lock_path = media_path.with_suffix(f"{media_path.suffix}.lock")
        trash_path = media_path.with_suffix(f"{media_path.suffix}.trash")
        seen_path = media_path.with_suffix(f"{media_path.suffix}.seen")

        if action == "lock":
            self._touch(lock_path)
            self._touch(seen_path)
            self._remove_if_exists(trash_path)
        elif action == "unlock":
            self._remove_if_exists(lock_path)
        elif action == "trash":
            self._touch(trash_path)
            self._touch(seen_path)
            self._remove_if_exists(lock_path)
        elif action == "untrash":
            self._remove_if_exists(trash_path)
        elif action == "seen":
            self._touch(seen_path)
        elif action == "unseen":
            self._remove_if_exists(seen_path)
        else:
            raise ValueError("Unsupported action.")

        return CompanionStatus(
            locked=lock_path.exists(),
            trashed=trash_path.exists(),
            seen=seen_path.exists(),
        )

    def _touch(self, target_path: Path) -> None:
        target_path.write_text("", encoding="utf-8")

    def _remove_if_exists(self, target_path: Path) -> None:
        if target_path.exists():
            target_path.unlink()

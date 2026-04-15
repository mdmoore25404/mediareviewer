"""Companion file actions for lock/trash/seen media state."""

from dataclasses import dataclass
from pathlib import Path


class LockedItemError(ValueError):
    """Raised when a protected action is attempted on a locked media item."""


@dataclass(frozen=True, slots=True)
class CompanionStatus:
    """State represented by companion files for a media item."""

    locked: bool
    trashed: bool
    seen: bool


class CompanionActionService:
    """Create or remove companion files for media review actions.

    Trash state is represented by physically moving the media file into a
    ``.trash/`` sibling directory rather than a companion file.  This allows
    rescans of the parent folder to skip trashed items entirely (hidden
    directories are pruned by the scanner) and simplifies empty-trash to a
    single directory deletion.

    Lock and seen state continue to use ``.lock`` / ``.seen`` companion files
    next to the media file at its current location.
    """

    def apply(self, media_path: Path, action: str) -> CompanionStatus:
        """Apply a review action and return the resulting companion status."""

        lock_path = media_path.with_suffix(f"{media_path.suffix}.lock")
        seen_path = media_path.with_suffix(f"{media_path.suffix}.seen")

        if action == "lock":
            self._touch(lock_path)
            self._touch(seen_path)
        elif action == "unlock":
            self._remove_if_exists(lock_path)
        elif action == "trash":
            if lock_path.exists():
                raise LockedItemError("Cannot trash a locked item. Unlock it first.")
            trash_dir = media_path.parent / ".trash"
            trash_dir.mkdir(exist_ok=True)
            media_path.rename(trash_dir / media_path.name)
            # Remove any seen companion that may exist at the original location.
            self._remove_if_exists(seen_path)
            return CompanionStatus(locked=False, trashed=True, seen=True)
        elif action == "untrash":
            # media_path is the file inside the .trash/ subdirectory.
            dest = media_path.parent.parent / media_path.name
            media_path.rename(dest)
            return CompanionStatus(locked=False, trashed=False, seen=False)
        elif action == "seen":
            self._touch(seen_path)
        elif action == "unseen":
            self._remove_if_exists(seen_path)
        else:
            raise ValueError("Unsupported action.")

        return CompanionStatus(
            locked=lock_path.exists(),
            trashed=media_path.parent.name == ".trash",
            seen=seen_path.exists(),
        )

    def _touch(self, target_path: Path) -> None:
        target_path.write_text("", encoding="utf-8")

    def _remove_if_exists(self, target_path: Path) -> None:
        if target_path.exists():
            target_path.unlink()

"""In-memory transcription history for Vocalinux.

Keeps a bounded, newest-first list of recent dictation snippets so the user
can review and re-copy recent voice input from the tray menu.

The history lives only for the lifetime of the running process — nothing is
written to disk — so dictated text never persists past the current session.
This is a deliberate privacy choice: a dictation tool sees everything the user
types by voice, and that should not silently accumulate in a file.
"""

import logging
import threading
from collections import deque
from typing import Any, Callable, List, Optional

logger = logging.getLogger(__name__)

# Default number of snippets to retain. Kept small so the tray menu stays
# readable; configurable via the "history" config section.
DEFAULT_MAX_ITEMS = 10


def sanitize_max_items(value: Any) -> int:
    """Coerce a configured snippet cap to a positive int.

    config.json is user-editable, so a saved ``history.max_items`` may be
    missing, non-numeric, or out of range. An unusable value falls back to
    ``DEFAULT_MAX_ITEMS`` rather than raising: a malformed preference must
    never prevent the app from starting.
    """
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        logger.warning(
            "Invalid transcription history max_items %r; falling back to %d",
            value,
            DEFAULT_MAX_ITEMS,
        )
        return DEFAULT_MAX_ITEMS


class TranscriptionHistory:
    """A bounded, thread-safe, in-memory store of recent dictation snippets.

    A "snippet" is the text of a single dictation session (everything said
    between starting and stopping voice typing). Entries are stored oldest to
    newest internally and returned newest-first for display.

    Recording happens on the speech-recognition thread while the tray menu is
    rebuilt on the GTK main thread, so all access is guarded by a lock. The
    optional change callback lets the UI refresh when entries are added,
    cleared, or trimmed; callers are responsible for marshalling that callback
    onto the correct thread (e.g. via ``GLib.idle_add``).
    """

    def __init__(self, max_items: int = DEFAULT_MAX_ITEMS, enabled: bool = True):
        self._max_items = sanitize_max_items(max_items)
        self._enabled = bool(enabled)
        self._entries: deque = deque(maxlen=self._max_items)
        self._lock = threading.Lock()
        self._change_callback: Optional[Callable[[], None]] = None

    def set_change_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Register a callback invoked whenever the history changes."""
        self._change_callback = callback

    @property
    def enabled(self) -> bool:
        """Whether new snippets are being recorded."""
        return self._enabled

    @property
    def max_items(self) -> int:
        """The maximum number of snippets retained."""
        return self._max_items

    def set_max_items(self, max_items: int) -> None:
        """Change the retained-snippet cap, trimming oldest entries if needed."""
        max_items = sanitize_max_items(max_items)
        with self._lock:
            if max_items == self._max_items:
                return
            self._max_items = max_items
            # deque(maxlen=...) keeps the rightmost (newest) items on trim.
            self._entries = deque(self._entries, maxlen=max_items)
        self._notify()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable recording. Disabling also clears existing entries."""
        enabled = bool(enabled)
        with self._lock:
            if enabled == self._enabled:
                return
            self._enabled = enabled
            if not enabled:
                self._entries.clear()
        self._notify()

    def add(self, text: str) -> None:
        """Add a snippet. No-op when disabled or when text is empty."""
        if not text:
            return
        text = text.strip()
        if not text:
            return
        with self._lock:
            if not self._enabled:
                return
            self._entries.append(text)
        self._notify()

    def extend_latest(self, text: str) -> bool:
        """Append a late-arriving segment to the most recent snippet.

        The recognition worker can emit a final segment after its session
        already ended (the manager stops waiting for it after a bounded
        timeout and reports IDLE anyway). That text belongs to the just-ended
        session's snippet, so it is merged into the newest entry instead of
        becoming a snippet of its own or leaking into the next session.

        Returns False when there is nothing to extend (empty or disabled
        history, or empty text).
        """
        if not text or not text.strip():
            return False
        with self._lock:
            if not self._enabled or not self._entries:
                return False
            self._entries[-1] = f"{self._entries[-1]} {text.strip()}"
        self._notify()
        return True

    def get_all(self) -> List[str]:
        """Return all snippets, newest first."""
        with self._lock:
            return list(reversed(self._entries))

    def clear(self) -> None:
        """Remove all snippets."""
        with self._lock:
            if not self._entries:
                return
            self._entries.clear()
        self._notify()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def _notify(self) -> None:
        callback = self._change_callback
        if callback is None:
            return
        try:
            callback()
        except Exception:
            # A misbehaving UI callback must never break recording.
            logger.exception("Transcription history change callback failed")

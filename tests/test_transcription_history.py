"""
Tests for the in-memory transcription history.
"""

import unittest

from vocalinux.ui.transcription_history import DEFAULT_MAX_ITEMS, TranscriptionHistory


class TestTranscriptionHistory(unittest.TestCase):
    """Test cases for the TranscriptionHistory store."""

    def test_defaults(self):
        history = TranscriptionHistory()
        self.assertEqual(history.max_items, DEFAULT_MAX_ITEMS)
        self.assertTrue(history.enabled)
        self.assertEqual(len(history), 0)
        self.assertEqual(history.get_all(), [])

    def test_add_and_newest_first(self):
        history = TranscriptionHistory()
        history.add("first")
        history.add("second")
        history.add("third")
        self.assertEqual(history.get_all(), ["third", "second", "first"])
        self.assertEqual(len(history), 3)

    def test_add_strips_whitespace(self):
        history = TranscriptionHistory()
        history.add("  hello world  ")
        self.assertEqual(history.get_all(), ["hello world"])

    def test_empty_and_whitespace_ignored(self):
        history = TranscriptionHistory()
        history.add("")
        history.add("   ")
        history.add(None)  # type: ignore[arg-type]
        self.assertEqual(len(history), 0)

    def test_max_items_cap_drops_oldest(self):
        history = TranscriptionHistory(max_items=3)
        for text in ["a", "b", "c", "d"]:
            history.add(text)
        # "a" dropped; newest first.
        self.assertEqual(history.get_all(), ["d", "c", "b"])
        self.assertEqual(len(history), 3)

    def test_set_max_items_trims_keeping_newest(self):
        history = TranscriptionHistory(max_items=5)
        for text in ["a", "b", "c", "d", "e"]:
            history.add(text)
        history.set_max_items(2)
        self.assertEqual(history.max_items, 2)
        self.assertEqual(history.get_all(), ["e", "d"])

    def test_max_items_floor_is_one(self):
        history = TranscriptionHistory(max_items=0)
        self.assertEqual(history.max_items, 1)
        history.add("a")
        history.add("b")
        self.assertEqual(history.get_all(), ["b"])

    def test_invalid_max_items_falls_back_to_default(self):
        self.assertEqual(TranscriptionHistory(max_items="abc").max_items, DEFAULT_MAX_ITEMS)
        self.assertEqual(TranscriptionHistory(max_items=None).max_items, DEFAULT_MAX_ITEMS)
        self.assertEqual(TranscriptionHistory(max_items=[1]).max_items, DEFAULT_MAX_ITEMS)

    def test_numeric_string_max_items_accepted(self):
        history = TranscriptionHistory(max_items="4")
        self.assertEqual(history.max_items, 4)

    def test_set_max_items_invalid_falls_back_to_default(self):
        history = TranscriptionHistory(max_items=3)
        history.set_max_items("bogus")
        self.assertEqual(history.max_items, DEFAULT_MAX_ITEMS)

    def test_extend_latest_appends_to_newest_entry(self):
        history = TranscriptionHistory()
        history.add("one")
        self.assertTrue(history.extend_latest("late tail"))
        self.assertEqual(history.get_all(), ["one late tail"])

    def test_extend_latest_only_touches_newest_entry(self):
        history = TranscriptionHistory()
        history.add("one")
        history.add("two")
        history.extend_latest("tail")
        self.assertEqual(history.get_all(), ["two tail", "one"])

    def test_extend_latest_strips_segment_whitespace(self):
        history = TranscriptionHistory()
        history.add("one")
        history.extend_latest("  tail  ")
        self.assertEqual(history.get_all(), ["one tail"])

    def test_extend_latest_empty_history_returns_false(self):
        self.assertFalse(TranscriptionHistory().extend_latest("x"))

    def test_extend_latest_disabled_returns_false(self):
        self.assertFalse(TranscriptionHistory(enabled=False).extend_latest("x"))

    def test_extend_latest_blank_text_returns_false(self):
        history = TranscriptionHistory()
        history.add("one")
        self.assertFalse(history.extend_latest("   "))
        self.assertEqual(history.get_all(), ["one"])

    def test_extend_latest_after_clear_returns_false(self):
        history = TranscriptionHistory()
        history.add("a")
        history.clear()
        self.assertFalse(history.extend_latest("x"))

    def test_extend_latest_fires_change_callback(self):
        history = TranscriptionHistory()
        history.add("a")
        calls = []
        history.set_change_callback(lambda: calls.append(1))
        history.extend_latest("b")
        self.assertEqual(calls, [1])

    def test_clear(self):
        history = TranscriptionHistory()
        history.add("a")
        history.add("b")
        history.clear()
        self.assertEqual(history.get_all(), [])
        self.assertEqual(len(history), 0)

    def test_disabled_does_not_record(self):
        history = TranscriptionHistory(enabled=False)
        self.assertFalse(history.enabled)
        history.add("ignored")
        self.assertEqual(len(history), 0)

    def test_set_enabled_false_clears_entries(self):
        history = TranscriptionHistory()
        history.add("a")
        history.set_enabled(False)
        self.assertFalse(history.enabled)
        self.assertEqual(len(history), 0)
        history.add("b")  # still ignored while disabled
        self.assertEqual(len(history), 0)
        history.set_enabled(True)
        history.add("c")
        self.assertEqual(history.get_all(), ["c"])

    def test_change_callback_fires_on_mutations(self):
        history = TranscriptionHistory()
        calls = []
        history.set_change_callback(lambda: calls.append(1))

        history.add("a")  # fires
        history.clear()  # fires
        history.clear()  # no-op, already empty -> no fire
        self.assertEqual(len(calls), 2)

    def test_change_callback_not_fired_when_disabled_add(self):
        history = TranscriptionHistory(enabled=False)
        calls = []
        history.set_change_callback(lambda: calls.append(1))
        history.add("a")
        self.assertEqual(calls, [])

    def test_change_callback_exception_is_swallowed(self):
        history = TranscriptionHistory()

        def boom():
            raise RuntimeError("callback failure")

        history.set_change_callback(boom)
        # Must not propagate.
        history.add("a")
        self.assertEqual(history.get_all(), ["a"])


if __name__ == "__main__":
    unittest.main()

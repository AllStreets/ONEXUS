"""Tests for nexus.tui.input_handler -- keyboard input and history navigation."""
from __future__ import annotations

import pytest
from nexus.tui.input_handler import InputHandler, InputResult


class TestCharacterInput:
    """Test basic character-by-character input."""

    def test_single_character(self):
        handler = InputHandler()
        result = handler.handle_key("a")
        assert result.changed is True
        assert handler.current_input == "a"
        assert handler.cursor_pos == 1

    def test_multiple_characters(self):
        handler = InputHandler()
        for ch in "hello":
            handler.handle_key(ch)
        assert handler.current_input == "hello"
        assert handler.cursor_pos == 5

    def test_space(self):
        handler = InputHandler()
        handler.handle_key("a")
        handler.handle_key(" ")
        handler.handle_key("b")
        assert handler.current_input == "a b"

    def test_non_printable_ignored(self):
        handler = InputHandler()
        result = handler.handle_key("\x1b")  # bare escape
        assert result.changed is False
        assert handler.current_input == ""


class TestBackspace:
    """Test backspace behavior."""

    def test_backspace_removes_character(self):
        handler = InputHandler()
        for ch in "abc":
            handler.handle_key(ch)
        result = handler.handle_key("\x7f")
        assert result.changed is True
        assert handler.current_input == "ab"

    def test_backspace_on_empty(self):
        handler = InputHandler()
        result = handler.handle_key("\x7f")
        assert result.changed is False
        assert handler.current_input == ""

    def test_backspace_alternate_code(self):
        handler = InputHandler()
        handler.handle_key("x")
        handler.handle_key("\x08")
        assert handler.current_input == ""


class TestSubmit:
    """Test enter/submit behavior."""

    def test_enter_submits(self):
        handler = InputHandler()
        for ch in "hello":
            handler.handle_key(ch)
        result = handler.handle_key("\r")
        assert result.submitted == "hello"
        assert result.changed is True
        assert handler.current_input == ""

    def test_enter_newline_submits(self):
        handler = InputHandler()
        handler.handle_key("x")
        result = handler.handle_key("\n")
        assert result.submitted == "x"

    def test_submit_adds_to_history(self):
        handler = InputHandler()
        for ch in "test":
            handler.handle_key(ch)
        handler.handle_key("\r")
        assert handler.history == ["test"]

    def test_empty_submit_does_not_add_to_history(self):
        handler = InputHandler()
        handler.handle_key("\r")
        assert handler.history == []

    def test_whitespace_only_not_added_to_history(self):
        handler = InputHandler()
        handler.handle_key(" ")
        handler.handle_key(" ")
        handler.handle_key("\r")
        assert handler.history == []


class TestExitSignals:
    """Test Ctrl-C and Ctrl-D."""

    def test_ctrl_c_exit(self):
        handler = InputHandler()
        result = handler.handle_key("\x03")
        assert result.exit_requested is True

    def test_ctrl_d_exit(self):
        handler = InputHandler()
        result = handler.handle_key("\x04")
        assert result.exit_requested is True


class TestHistory:
    """Test up/down arrow history navigation."""

    def _populate_history(self, handler: InputHandler, entries: list[str]) -> None:
        for entry in entries:
            for ch in entry:
                handler.handle_key(ch)
            handler.handle_key("\r")

    def test_up_arrow_recalls_last(self):
        handler = InputHandler()
        self._populate_history(handler, ["first", "second", "third"])

        handler.handle_key("UP")
        assert handler.current_input == "third"

    def test_up_arrow_twice(self):
        handler = InputHandler()
        self._populate_history(handler, ["first", "second", "third"])

        handler.handle_key("UP")
        handler.handle_key("UP")
        assert handler.current_input == "second"

    def test_up_arrow_all_the_way(self):
        handler = InputHandler()
        self._populate_history(handler, ["first", "second"])

        handler.handle_key("UP")
        handler.handle_key("UP")
        assert handler.current_input == "first"

        # Going past the beginning stays at the first entry
        handler.handle_key("UP")
        assert handler.current_input == "first"

    def test_down_arrow_returns_to_current(self):
        handler = InputHandler()
        self._populate_history(handler, ["first", "second"])

        # Type something, then navigate history, then come back
        for ch in "partial":
            handler.handle_key(ch)

        handler.handle_key("UP")
        assert handler.current_input == "second"

        handler.handle_key("DOWN")
        assert handler.current_input == "partial"

    def test_down_arrow_without_history_navigation(self):
        handler = InputHandler()
        result = handler.handle_key("DOWN")
        assert result.changed is False

    def test_up_arrow_empty_history(self):
        handler = InputHandler()
        result = handler.handle_key("UP")
        assert result.changed is False
        assert handler.current_input == ""


class TestLineClear:
    """Test Ctrl-U line clear."""

    def test_ctrl_u_clears_line(self):
        handler = InputHandler()
        for ch in "some text":
            handler.handle_key(ch)
        result = handler.handle_key("\x15")
        assert result.changed is True
        assert handler.current_input == ""
        assert handler.cursor_pos == 0


class TestWordDelete:
    """Test Ctrl-W word deletion."""

    def test_ctrl_w_deletes_word(self):
        handler = InputHandler()
        for ch in "hello world":
            handler.handle_key(ch)
        handler.handle_key("\x17")
        assert handler.current_input == "hello "

    def test_ctrl_w_on_empty(self):
        handler = InputHandler()
        result = handler.handle_key("\x17")
        assert result.changed is False


class TestDisplayText:
    """Test the display_text property."""

    def test_display_text_matches_current_input(self):
        handler = InputHandler()
        for ch in "test":
            handler.handle_key(ch)
        assert handler.display_text == "test"

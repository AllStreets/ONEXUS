"""
Input handler for the NEXUS TUI -- keyboard input, command history, line editing.
"""
from __future__ import annotations

import sys
import tty
import termios
from dataclasses import dataclass, field


@dataclass
class InputResult:
    """Result of processing a keypress."""
    submitted: str | None = None   # Non-None when user presses Enter
    exit_requested: bool = False   # True when user presses Ctrl-C / Ctrl-D
    changed: bool = False          # True when the display buffer changed


class InputHandler:
    """Handles character-by-character keyboard input with history navigation."""

    def __init__(self) -> None:
        self.history: list[str] = []
        self.history_index: int = -1
        self.current_input: str = ""
        self.cursor_pos: int = 0
        self._saved_input: str = ""

    @property
    def display_text(self) -> str:
        """The current text to display in the input area."""
        return self.current_input

    def handle_key(self, key: str) -> InputResult:
        """Process a single key or escape sequence and return the result."""
        # Ctrl-C or Ctrl-D -- exit
        if key in ("\x03", "\x04"):
            return InputResult(exit_requested=True)

        # Enter -- submit
        if key in ("\r", "\n"):
            text = self.current_input.strip()
            if text:
                self.history.append(text)
            submitted = self.current_input
            self.current_input = ""
            self.cursor_pos = 0
            self.history_index = -1
            self._saved_input = ""
            return InputResult(submitted=submitted, changed=True)

        # Backspace
        if key in ("\x7f", "\x08"):
            if self.cursor_pos > 0:
                self.current_input = (
                    self.current_input[: self.cursor_pos - 1]
                    + self.current_input[self.cursor_pos :]
                )
                self.cursor_pos -= 1
                return InputResult(changed=True)
            return InputResult()

        # Escape sequences (arrows, etc.)
        if key == "\x1b":
            return InputResult()

        # Up arrow sequence
        if key == "\x1b[A" or key == "UP":
            return self._history_prev()

        # Down arrow sequence
        if key == "\x1b[B" or key == "DOWN":
            return self._history_next()

        # Ctrl-U -- clear line
        if key == "\x15":
            self.current_input = ""
            self.cursor_pos = 0
            return InputResult(changed=True)

        # Ctrl-W -- delete word backward
        if key == "\x17":
            if self.cursor_pos > 0:
                # Find the start of the previous word
                pos = self.cursor_pos - 1
                while pos > 0 and self.current_input[pos - 1] == " ":
                    pos -= 1
                while pos > 0 and self.current_input[pos - 1] != " ":
                    pos -= 1
                self.current_input = (
                    self.current_input[:pos] + self.current_input[self.cursor_pos:]
                )
                self.cursor_pos = pos
                return InputResult(changed=True)
            return InputResult()

        # Regular printable character
        if len(key) == 1 and (key.isprintable() or key == " "):
            self.current_input = (
                self.current_input[: self.cursor_pos]
                + key
                + self.current_input[self.cursor_pos :]
            )
            self.cursor_pos += 1
            return InputResult(changed=True)

        return InputResult()

    def _history_prev(self) -> InputResult:
        """Navigate to the previous history entry."""
        if not self.history:
            return InputResult()

        if self.history_index == -1:
            self._saved_input = self.current_input
            self.history_index = len(self.history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        else:
            return InputResult()

        self.current_input = self.history[self.history_index]
        self.cursor_pos = len(self.current_input)
        return InputResult(changed=True)

    def _history_next(self) -> InputResult:
        """Navigate to the next history entry."""
        if self.history_index == -1:
            return InputResult()

        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.current_input = self.history[self.history_index]
        else:
            self.history_index = -1
            self.current_input = self._saved_input
            self._saved_input = ""

        self.cursor_pos = len(self.current_input)
        return InputResult(changed=True)

    def read_key(self) -> str:
        """Read a single keypress from stdin (blocking).

        Handles multi-byte escape sequences for arrow keys.
        Returns the key as a string.
        """
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ch3 = sys.stdin.read(1)
                    if ch3 == "A":
                        return "UP"
                    elif ch3 == "B":
                        return "DOWN"
                    elif ch3 == "C":
                        return "RIGHT"
                    elif ch3 == "D":
                        return "LEFT"
                    return "\x1b[" + ch3
                return "\x1b" + ch2
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

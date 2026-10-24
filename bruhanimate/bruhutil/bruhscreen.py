"""
Copyright 2023 Ethan Christensen
Copied, Guided, and Adapted from Asciimatics <https://github.com/peterbrittain/asciimatics/blob/master/asciimatics/screen.py>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import signal
import sys
import time
from contextlib import ExitStack

ENABLE_EXTENDED_FLAGS = 0x0080
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


def _wait_for_enter(screen):
    """Explicit legacy end prompt, using the same normalized input as playback."""
    while True:
        if screen.get_event() in (3, 10, 13, -1, 27):
            return
        time.sleep(0.05)


if sys.platform == "win32":
    import pywintypes
    import win32con
    import win32console
    import win32event  # -->. for keyboard events
    import win32file

    class Screen:
        """
        Class for creating and managing a terminal screen in a WINDOWS OS terminal
        """

        wait_for_enter = _wait_for_enter

        # Standard extended key codes.
        KEY_ESCAPE = -1
        KEY_F1 = -2
        KEY_F2 = -3
        KEY_F3 = -4
        KEY_F4 = -5
        KEY_F5 = -6
        KEY_F6 = -7
        KEY_F7 = -8
        KEY_F8 = -9
        KEY_F9 = -10
        KEY_F10 = -11
        KEY_F11 = -12
        KEY_F12 = -13
        KEY_F13 = -14
        KEY_F14 = -15
        KEY_F15 = -16
        KEY_F16 = -17
        KEY_F17 = -18
        KEY_F18 = -19
        KEY_F19 = -20
        KEY_F20 = -21
        KEY_F21 = -22
        KEY_F22 = -23
        KEY_F23 = -24
        KEY_F24 = -25
        KEY_PRINT_SCREEN = -100
        KEY_INSERT = -101
        KEY_DELETE = -102
        KEY_HOME = -200
        KEY_END = -201
        KEY_LEFT = -203
        KEY_UP = -204
        KEY_RIGHT = -205
        KEY_DOWN = -206
        KEY_PAGE_UP = -207
        KEY_PAGE_DOWN = -208
        KEY_BACK = -300
        KEY_TAB = -301
        KEY_BACK_TAB = -302
        KEY_NUMPAD0 = -400
        KEY_NUMPAD1 = -401
        KEY_NUMPAD2 = -402
        KEY_NUMPAD3 = -403
        KEY_NUMPAD4 = -404
        KEY_NUMPAD5 = -405
        KEY_NUMPAD6 = -406
        KEY_NUMPAD7 = -407
        KEY_NUMPAD8 = -408
        KEY_NUMPAD9 = -409
        KEY_MULTIPLY = -410
        KEY_ADD = -411
        KEY_SUBTRACT = -412
        KEY_DECIMAL = -413
        KEY_DIVIDE = -414
        KEY_CAPS_LOCK = -500
        KEY_NUM_LOCK = -501
        KEY_SCROLL_LOCK = -502
        KEY_SHIFT = -600
        KEY_CONTROL = -601
        KEY_MENU = -602

        def __init__(self, stdout, stdin, old_out, old_in):
            info = stdout.GetConsoleScreenBufferInfo()["Window"]
            self.width = info.Right - info.Left + 1
            self.height = info.Bottom - info.Top + 1
            self._stdout = stdout
            self._stdin = stdin
            self._last_width = self.width
            self._last_height = self.height
            self._last_start = 0
            self._old_out = old_out
            self._old_in = old_in
            self._current_x = 0
            self._current_y = 0
            self._buffering = False
            self._frame_parts = []
            self._KEY_MAP = {
                win32con.VK_ESCAPE: Screen.KEY_ESCAPE,
                win32con.VK_F1: Screen.KEY_F1,
                win32con.VK_F2: Screen.KEY_F2,
                win32con.VK_F3: Screen.KEY_F3,
                win32con.VK_F4: Screen.KEY_F4,
                win32con.VK_F5: Screen.KEY_F5,
                win32con.VK_F6: Screen.KEY_F6,
                win32con.VK_F7: Screen.KEY_F7,
                win32con.VK_F8: Screen.KEY_F8,
                win32con.VK_F9: Screen.KEY_F9,
                win32con.VK_F10: Screen.KEY_F10,
                win32con.VK_F11: Screen.KEY_F11,
                win32con.VK_F12: Screen.KEY_F12,
                win32con.VK_F13: Screen.KEY_F13,
                win32con.VK_F14: Screen.KEY_F14,
                win32con.VK_F15: Screen.KEY_F15,
                win32con.VK_F16: Screen.KEY_F16,
                win32con.VK_F17: Screen.KEY_F17,
                win32con.VK_F18: Screen.KEY_F18,
                win32con.VK_F19: Screen.KEY_F19,
                win32con.VK_F20: Screen.KEY_F20,
                win32con.VK_F21: Screen.KEY_F21,
                win32con.VK_F22: Screen.KEY_F22,
                win32con.VK_F23: Screen.KEY_F23,
                win32con.VK_F24: Screen.KEY_F24,
                win32con.VK_PRINT: Screen.KEY_PRINT_SCREEN,
                win32con.VK_INSERT: Screen.KEY_INSERT,
                win32con.VK_DELETE: Screen.KEY_DELETE,
                win32con.VK_HOME: Screen.KEY_HOME,
                win32con.VK_END: Screen.KEY_END,
                win32con.VK_LEFT: Screen.KEY_LEFT,
                win32con.VK_UP: Screen.KEY_UP,
                win32con.VK_RIGHT: Screen.KEY_RIGHT,
                win32con.VK_DOWN: Screen.KEY_DOWN,
                win32con.VK_PRIOR: Screen.KEY_PAGE_UP,
                win32con.VK_NEXT: Screen.KEY_PAGE_DOWN,
                win32con.VK_BACK: Screen.KEY_BACK,
                win32con.VK_TAB: Screen.KEY_TAB,
            }
            self._keys = set()
            self._map_all = False

        def close(self, restore=True):
            """
            Close the screen and restore the previous console buffer and input modes.

            :param restore: Boolean flag to restore the original console buffer and input mode
                            when closing the screen. Default is True.
            """
            if getattr(self, "_closed", False):
                return
            self._closed = True
            with ExitStack() as cleanup:
                cleanup.callback(self._old_out.Close)
                cleanup.callback(self._stdout.Close)
                cleanup.callback(self._stdin.Close)
                if restore:
                    cleanup.callback(self._stdin.SetConsoleMode, self._old_in)
                    cleanup.callback(self._old_out.SetConsoleActiveScreenBuffer)

        def print_at(self, text, x, y, width):
            """
            Print text at a specified position (x, y) on the console screen.

            :param text: The text to print on the screen.
            :param x: The x-coordinate where the text begins.
            :param y: The y-coordinate where the text begins.
            :param width: The width of the text to be displayed, used to update the cursor position.
            """
            try:
                if self._buffering:
                    cursor = (
                        f"\x1b[{y + 1};{x + 1}H"
                        if x != self._current_x or y != self._current_y
                        else ""
                    )
                    self._frame_parts.append(cursor + str(text))
                    self._current_x = x + width
                    self._current_y = y
                else:
                    if x != self._current_x or y != self._current_y:
                        self._stdout.SetConsoleCursorPosition(
                            win32console.PyCOORDType(x, y)
                        )
                    self._stdout.WriteConsole(str(text))
                    self._current_x = x + width
                    self._current_y = y
            except pywintypes.error:
                pass

        def begin_frame(self):
            """Enter frame-batching mode; print_at() calls accumulate until flush_frame()."""
            self._buffering = True
            self._frame_parts = []

        def flush_frame(self):
            """
            Flush accumulated frame as a single WriteConsole call.
            ANSI cursor-positioning sequences replace SetConsoleCursorPosition,
            reducing Win32 syscalls from O(changed_cells) to 1 per frame.
            Requires ENABLE_VIRTUAL_TERMINAL_PROCESSING on the console output buffer.
            """
            if self._frame_parts:
                try:
                    self._stdout.WriteConsole("".join(self._frame_parts))
                except pywintypes.error:
                    pass
                self._frame_parts = []
            self._buffering = False

        def print_center(self, text, y, width):
            """
            Print text centrally aligned horizontally at a given y-coordinate.

            :param text: The text to print on the screen.
            :param y: The y-coordinate where the text is to be centered.
            :param width: The width of the text to be displayed, used to calculate and update the left padding and cursor position.
            """
            try:
                left_pad = (self.width - width) // 2
                self._stdout.SetConsoleCursorPosition(
                    win32console.PyCOORDType(left_pad, y)
                )
                self._stdout.WriteConsole(str(text))
                self._current_x = left_pad + width
                self._current_y = y
            except pywintypes.error:
                pass

        def clear(self):
            """
            Clear the console screen by filling the console buffer with spaces and resetting the cursor position.
            """
            info = self._stdout.GetConsoleScreenBufferInfo()["Window"]
            width = info.Right - info.Left + 1
            height = info.Bottom - info.Top + 1
            box_size = width * height
            self._stdout.FillConsoleOutputAttribute(
                0, box_size, win32console.PyCOORDType(0, 0)
            )
            self._stdout.FillConsoleOutputCharacter(
                " ", box_size, win32console.PyCOORDType(0, 0)
            )
            self._stdout.SetConsoleCursorPosition(win32console.PyCOORDType(0, 0))
            self._current_x = 0
            self._current_y = 0

        def has_resized(self):
            """
            Determine if the console screen has been resized since the last check.

            :return: Boolean indicating whether the screen has been resized.
            """
            re_sized = False
            info = self._stdout.GetConsoleScreenBufferInfo()["Window"]
            width = info.Right - info.Left + 1
            height = info.Bottom - info.Top + 1
            if width != self._last_width or height != self._last_height:
                re_sized = True
            return re_sized

        def refresh_size(self) -> bool:
            """Accept current dimensions and reset cursor state; False if empty."""
            info = self._stdout.GetConsoleScreenBufferInfo()["Window"]
            width, height = info.Right - info.Left + 1, info.Bottom - info.Top + 1
            if width < 1 or height < 1:
                return False
            self.width = self._last_width = width
            self.height = self._last_height = height
            self._current_x = self._current_y = -1
            self._frame_parts = []
            return True

        def set_title(self, title: str) -> None:
            """
            Set the console window title.

            :param title: The title to set for the console window.
            """
            win32console.SetConsoleTitle(title)

        def wait_for_input(self, timeout: int) -> None:
            """
            Wait for user input in the console with a specified timeout period.

            :param timeout: The time in seconds to wait for user input before timing out.
            :raises RuntimeError: If an unexpected return code is encountered during the wait.
            """
            rc = win32event.WaitForSingleObject(self._stdin, int(timeout * 1000))
            if rc not in [0, 258]:
                raise RuntimeError(rc)

        def get_event(self):
            """
            Check for any console input event without waiting and return the corresponding key code.

            This method processes the input events in the console's event queue to find key press events.
            It translates these key events into a keyboard event object and returns the appropriate key code.
            Modifier states are not mapped in a cross-platform manner, but standard bindings for extended keys are considered.

            :return: The translated key code for the key event if available, otherwise None.
            """
            # Look for a new event and consume it if there is one.
            while len(self._stdin.PeekConsoleInput(1)) > 0:
                event = self._stdin.ReadConsoleInput(1)[0]
                if event.EventType == win32console.KEY_EVENT:
                    # Handle key-down events and Alt key states for unicode pasting.
                    key_code = ord(event.Char)
                    if event.KeyDown or (
                        key_code > 0
                        and key_code not in self._keys
                        and event.VirtualKeyCode == win32con.VK_MENU
                    ):
                        # Record any keys that were pressed.
                        if event.KeyDown:
                            self._keys.add(key_code)

                        # Translate keys into a KeyboardEvent object.
                        if event.VirtualKeyCode in self._KEY_MAP:
                            key_code = self._KEY_MAP[event.VirtualKeyCode]

                        # Handle cross-platform key mapping or any special mappings.
                        if (
                            self._map_all
                            and event.VirtualKeyCode in self._EXTRA_KEY_MAP
                        ):
                            key_code = self._EXTRA_KEY_MAP[event.VirtualKeyCode]
                        elif (
                            event.VirtualKeyCode == win32con.VK_TAB
                            and event.ControlKeyState & win32con.SHIFT_PRESSED
                        ):
                            key_code = Screen.KEY_BACK_TAB
                        elif event.VirtualKeyCode == win32con.VK_RETURN:
                            key_code = 10
                        elif event.VirtualKeyCode == win32con.VK_TAB:
                            key_code = Screen.KEY_TAB

                        # Return the key code if a valid mapping exists.
                        if key_code:
                            return key_code
                    else:
                        # Remove any previously pressed key that is no longer down.
                        if key_code in self._keys:
                            self._keys.remove(key_code)

            # Return None if no interesting event was found.
            return None

        @classmethod
        def open(cls):
            """
            Opens and initializes a new console screen buffer for the Screen class on a Windows platform.

            This method creates a new console screen buffer, sets it as the active buffer, configures
            input and output modes, and prepares the screen for rendering text. It disables the cursor
            visibility and scroll settings to provide an optimized setup for terminal-based applications.

            :return: An initialized Screen object with the configured console screen buffer.
            """
            with ExitStack() as cleanup:
                old_out = win32console.PyConsoleScreenBufferType(
                    win32file.CreateFile(
                        "CONOUT$",
                        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                        win32file.FILE_SHARE_WRITE,
                        None,
                        win32file.OPEN_ALWAYS,
                        0,
                        None,
                    )
                )
                cleanup.callback(old_out.Close)
                try:
                    info = old_out.GetConsoleScreenBufferInfo()
                except pywintypes.error:
                    info = None
                win_out = win32console.CreateConsoleScreenBuffer()
                cleanup.callback(win_out.Close)
                if info:
                    win_out.SetConsoleScreenBufferSize(info["Size"])
                cleanup.callback(old_out.SetConsoleActiveScreenBuffer)
                win_out.SetConsoleActiveScreenBuffer()
                win_in = win32console.PyConsoleScreenBufferType(
                    win32file.CreateFile(
                        "CONIN$",
                        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                        win32file.FILE_SHARE_READ,
                        None,
                        win32file.OPEN_ALWAYS,
                        0,
                        None,
                    )
                )
                cleanup.callback(win_in.Close)
                win_out.SetConsoleCursorInfo(1, 0)
                out_mode = win_out.GetConsoleMode()
                out_mode &= ~win32console.ENABLE_WRAP_AT_EOL_OUTPUT
                out_mode |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
                try:
                    win_out.SetConsoleMode(out_mode)
                except pywintypes.error:
                    win_out.SetConsoleMode(
                        out_mode & ~ENABLE_VIRTUAL_TERMINAL_PROCESSING
                    )
                in_mode = win_in.GetConsoleMode()
                cleanup.callback(win_in.SetConsoleMode, in_mode)
                new_mode = (
                    in_mode | win32console.ENABLE_MOUSE_INPUT | ENABLE_EXTENDED_FLAGS
                )
                new_mode &= ~ENABLE_QUICK_EDIT_MODE
                new_mode &= ~win32console.ENABLE_PROCESSED_INPUT
                win_in.SetConsoleMode(new_mode)
                screen = cls(win_out, win_in, old_out, in_mode)
                cleanup.pop_all()
                return screen

        @classmethod
        def show(cls, function, args=None):
            """
            Display the provided function's output on the terminal screen with optional arguments.

            This method initializes the terminal screen, invokes the provided function, and passes
            any additional arguments to it. After the function execution, the screen is closed to
            restore the previous terminal settings.

            :param function: A callable to be executed within the context of the screen.
            :param args: An optional list of arguments to be passed to the function.
            """
            screen = cls.open()
            try:
                if args:
                    return function(screen, *args)
                else:
                    return function(screen)
            finally:
                screen.close()

else:
    import curses

    class Screen:
        wait_for_enter = _wait_for_enter

        KEY_ESCAPE = -1
        KEY_F1 = -2
        KEY_F2 = -3
        KEY_F3 = -4
        KEY_F4 = -5
        KEY_F5 = -6
        KEY_F6 = -7
        KEY_F7 = -8
        KEY_F8 = -9
        KEY_F9 = -10
        KEY_F10 = -11
        KEY_F11 = -12
        KEY_F12 = -13
        KEY_F13 = -14
        KEY_F14 = -15
        KEY_F15 = -16
        KEY_F16 = -17
        KEY_F17 = -18
        KEY_F18 = -19
        KEY_F19 = -20
        KEY_F20 = -21
        KEY_F21 = -22
        KEY_F22 = -23
        KEY_F23 = -24
        KEY_F24 = -25
        KEY_PRINT_SCREEN = -100
        KEY_INSERT = -101
        KEY_DELETE = -102
        KEY_HOME = -200
        KEY_END = -201
        KEY_LEFT = -203
        KEY_UP = -204
        KEY_RIGHT = -205
        KEY_DOWN = -206
        KEY_PAGE_UP = -207
        KEY_PAGE_DOWN = -208
        KEY_BACK = -300
        KEY_TAB = -301
        KEY_BACK_TAB = -302
        KEY_NUMPAD0 = -400
        KEY_NUMPAD1 = -401
        KEY_NUMPAD2 = -402
        KEY_NUMPAD3 = -403
        KEY_NUMPAD4 = -404
        KEY_NUMPAD5 = -405
        KEY_NUMPAD6 = -406
        KEY_NUMPAD7 = -407
        KEY_NUMPAD8 = -408
        KEY_NUMPAD9 = -409
        KEY_MULTIPLY = -410
        KEY_ADD = -411
        KEY_SUBTRACT = -412
        KEY_DECIMAL = -413
        KEY_DIVIDE = -414
        KEY_CAPS_LOCK = -500
        KEY_NUM_LOCK = -501
        KEY_SCROLL_LOCK = -502
        KEY_SHIFT = -600
        KEY_CONTROL = -601
        KEY_MENU = -602

        def get_event(self):
            c = self.screen.getch()
            if c != curses.ERR:
                if c in (curses.KEY_BACKSPACE, 127, 8):
                    return self.KEY_BACK
                elif c in (10, 13, curses.KEY_ENTER):
                    return 10
                elif c == 27:
                    return self.KEY_ESCAPE
                elif c == 9:
                    return self.KEY_TAB
                navigation = {
                    curses.KEY_BTAB: self.KEY_BACK_TAB,
                    curses.KEY_LEFT: self.KEY_LEFT,
                    curses.KEY_RIGHT: self.KEY_RIGHT,
                    curses.KEY_UP: self.KEY_UP,
                    curses.KEY_DOWN: self.KEY_DOWN,
                    curses.KEY_HOME: self.KEY_HOME,
                    curses.KEY_END: self.KEY_END,
                    curses.KEY_PPAGE: self.KEY_PAGE_UP,
                    curses.KEY_NPAGE: self.KEY_PAGE_DOWN,
                    curses.KEY_IC: self.KEY_INSERT,
                    curses.KEY_DC: self.KEY_DELETE,
                    **{
                        getattr(curses, f"KEY_F{i}"): getattr(self, f"KEY_F{i}")
                        for i in range(1, 13)
                    },
                }
                if c in navigation:
                    return navigation[c]
                return c
            return None

        def __init__(self, window, height=None):
            self.screen = window
            self.screen.keypad(1)
            self.height = window.getmaxyx()[0]
            self.width = window.getmaxyx()[1]
            curses.curs_set(0)
            self.screen.nodelay(1)
            self.signal_state = SignalState()
            self._re_sized = False
            self.signal_state.set(signal.SIGWINCH, self._resize_handler)
            self.signal_state.set(signal.SIGCONT, self._continue_handler)
            curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
            self._move_y_x = curses.tigetstr("cup")
            self._up_line = curses.tigetstr("ri").decode("utf-8")
            self._down_line = curses.tigetstr("ind").decode("utf-8")
            self._fg_color = curses.tigetstr("setaf")
            self._bg_color = curses.tigetstr("setab")
            self._default_colours = curses.tigetstr("op")
            if curses.tigetflag("hs"):
                self._start_title = curses.tigetstr("tsl").decode("utf-8")
                self._end_title = curses.tigetstr("fsl").decode("utf-8")
            else:
                self._start_title = self._end_title = None
            self._a_normal = curses.tigetstr("sgr0").decode("utf-8")
            self._a_bold = curses.tigetstr("bold").decode("utf-8")
            self._a_reverse = curses.tigetstr("rev").decode("utf-8")
            self._a_underline = curses.tigetstr("smul").decode("utf-8")
            self._clear_screen = curses.tigetstr("clear").decode("utf-8")
            self._bytes_to_read = 0
            self._bytes_to_return = b""
            self._cur_x = 0
            self._cur_y = 0
            self._buffering = False
            self._frame_parts = []

        def _resize_handler(self, *_):
            self._re_sized = True

        def _continue_handler(self, *_):
            self.force_update(full_refresh=True)

        def has_resized(self):
            return self._re_sized

        def refresh_size(self) -> bool:
            """Refresh curses outside the signal handler, then acknowledge resize."""
            # Clear first so a new signal during refresh remains pending.
            self._re_sized = False
            try:
                dimensions = os.get_terminal_size(sys.stdout.fileno())
                width, height = dimensions.columns, dimensions.lines
                if width < 1 or height < 1:
                    self._re_sized = True
                    return False
                curses.resizeterm(height, width)
            except (OSError, ValueError):
                curses.update_lines_cols()
                height, width = self.screen.getmaxyx()
            if width < 1 or height < 1:
                self._re_sized = True
                return False
            self.width, self.height = width, height
            self._cur_x = self._cur_y = -1
            self._frame_parts = []
            return True

        def close(self, restore=True):
            if getattr(self, "_closed", False):
                return
            self._closed = True
            with ExitStack() as cleanup:
                if restore:
                    cleanup.callback(curses.endwin)
                    cleanup.callback(curses.nocbreak)
                    cleanup.callback(curses.echo)
                    cleanup.callback(self.screen.keypad, 0)
                if hasattr(self, "signal_state"):
                    cleanup.callback(self.signal_state.restore)

        def clear(self):
            try:
                sys.stdout.flush()
                os.system("clear")
                self._cur_x = 0
                self._cur_y = 0
            except IOError:
                pass

        @classmethod
        def open(cls):
            stdcrs = curses.initscr()
            screen = cls.__new__(cls)
            screen.screen = stdcrs
            try:
                curses.noecho()
                curses.cbreak()
                stdcrs.keypad(1)
                screen.__init__(stdcrs)
            except BaseException:
                screen.close()
                raise
            return screen

        @staticmethod
        def _safe_write(msg):
            try:
                try:
                    sys.stdout.write(msg)
                except UnicodeEncodeError as error:
                    # Handle encoding where writing actually happens, including
                    # batched frames. Preserve encodable glyphs and ANSI escapes;
                    # each unsupported single-cell glyph becomes one question mark.
                    sys.stdout.write(
                        msg.encode(error.encoding, errors="replace").decode(
                            error.encoding
                        )
                    )
            except IOError:
                pass

        def print_at(self, text, x, y, width):
            cursor = ""
            if x != self._cur_x or y != self._cur_y:
                cursor = curses.tparm(self._move_y_x, y, x).decode("utf-8")
            piece = cursor + str(text)
            if self._buffering:
                self._frame_parts.append(piece)
            else:
                self._safe_write(piece)
            self._cur_x = x + width
            self._cur_y = y

        def begin_frame(self):
            """Enter frame-batching mode; print_at() calls accumulate until flush_frame()."""
            self._buffering = True
            self._frame_parts = []

        def flush_frame(self):
            """
            Flush accumulated frame output as a single sys.stdout.write() + flush().
            Goes from O(cells_changed) write() calls to 1 write + 1 flush per frame.
            """
            if self._frame_parts:
                self._safe_write("".join(self._frame_parts))
                self._frame_parts = []
            sys.stdout.flush()
            self._buffering = False

        @classmethod
        def show(cls, function, args=None):
            screen = cls.open()
            try:
                if args:
                    return function(screen, *args)
                else:
                    return function(screen)
            finally:
                screen.close()

    class SignalState(object):
        def __init__(self):
            self._old_signal_states = []

        def set(self, signalnum, handler):
            old_handler = signal.getsignal(signalnum)
            if old_handler is None:
                old_handler = signal.SIG_DFL
            self._old_signal_states.append((signalnum, old_handler))
            signal.signal(signalnum, handler)

        def restore(self):
            with ExitStack() as cleanup:
                for signalnum, handler in self._old_signal_states:
                    cleanup.callback(signal.signal, signalnum, handler)
                self._old_signal_states = []

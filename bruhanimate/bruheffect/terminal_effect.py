import os
import queue
import signal
import subprocess
import sys
import threading
from contextlib import ExitStack

from ..bruhutil.bruhffer import Buffer
from ._resize import raster
from .base_effect import BaseEffect


class TerminalEffect(BaseEffect):
    """A pipe-based command console; Player owns pacing and input polling.

    This is a line-oriented shell, not a PTY or terminal escape interpreter.
    Construction opens no processes. Pass handle_event to Player explicitly.
    """

    def __init__(self, buffer: Buffer, background: str = " "):
        super().__init__(buffer, background)
        self.width = buffer.width()
        self.height = buffer.height()
        self.terminal_history = []
        self.current_line_output = ""
        self.current_input = ""
        self.prompt = "> "
        self.max_lines = max(1, self.height - 2)
        self.output_queue = queue.Queue(maxsize=10000)
        self.active_process = None
        self._reader_threads = []
        self._reader_stop = threading.Event()
        self._process_job = None
        self._job_assigned = False

    def _enqueue_output(self, out, output_queue):
        """Thread worker to read output character by character."""
        try:
            while not self._reader_stop.is_set():
                char = out.read(1)
                if not char:
                    break
                while not self._reader_stop.is_set():
                    try:
                        output_queue.put(char, timeout=0.05)
                        break
                    except queue.Full:
                        continue
        except (OSError, ValueError):
            pass
        finally:
            out.close()

    def execute_command(self):
        """Starts a command or sends input to an active process."""
        user_text = self.current_input

        if self.active_process and self.active_process.poll() is None:
            self.terminal_history.append(user_text)
            try:
                # Use os.linesep to ensure the correct Enter key behavior for the OS
                self.active_process.stdin.write(user_text + os.linesep)
                self.active_process.stdin.flush()
            except Exception as e:
                self.terminal_history.append(f"[Stdin Error: {e}]")
            self.current_input = ""
            return

        self.terminal_history.append(self.prompt + user_text)
        self.current_input = ""

        cmd = user_text.strip()
        if not cmd:
            return

        if cmd.lower() in ("exit", "quit"):
            self.terminal_history.append("Type ESC to exit.")
            return

        try:
            self._close_process()
            self._reader_stop.clear()
            # Spoof environment to trick some CLIs into working over pipes
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            env["PYTHONUNBUFFERED"] = "1"
            env["FORCE_COLOR"] = "1"  # Try to force color support

            # Windows must own the launcher before it can create the shell or
            # descendants. Assigning a running shell races its first child.
            # The isolated launcher consumes exactly one gate byte, leaving
            # subsequent stdin for the command, and exits if the pipe closes.
            # Use the base interpreter: a Windows venv redirector can spawn its
            # real interpreter before we assign the redirector to the job.
            launch = (
                [
                    getattr(sys, "_base_executable", sys.executable),
                    "-I",
                    "-S",
                    "-u",
                    "-c",
                    "import os,sys; gate=os.read(0,1); "
                    "import subprocess; "
                    "sys.exit(subprocess.call(sys.argv[1], shell=True, "
                    "stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, "
                    "creationflags=subprocess.CREATE_NO_WINDOW) if gate==b'G' else 1)",
                    cmd,
                ]
                if sys.platform == "win32"
                else cmd
            )
            self.active_process = subprocess.Popen(
                launch,
                shell=sys.platform != "win32",
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                env=env,
                universal_newlines=True,
                start_new_session=sys.platform != "win32",
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0,
            )
            if sys.platform == "win32":
                # Closing an owned job kills descendants even if the shell has
                # already exited. No helper window is opened for shell commands.
                import pywintypes
                import win32api
                import win32con
                import win32job

                self._process_job = win32job.CreateJobObject(None, "")
                info = win32job.QueryInformationJobObject(
                    self._process_job, win32job.JobObjectExtendedLimitInformation
                )
                info["BasicLimitInformation"]["LimitFlags"] |= (
                    win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                )
                win32job.SetInformationJobObject(
                    self._process_job, win32job.JobObjectExtendedLimitInformation, info
                )
                try:
                    handle = win32api.OpenProcess(
                        win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE,
                        False,
                        self.active_process.pid,
                    )
                    try:
                        win32job.AssignProcessToJobObject(self._process_job, handle)
                        self._job_assigned = True
                    finally:
                        handle.Close()
                except (OSError, pywintypes.error):
                    if self.active_process.poll() is None:
                        raise
                if self._job_assigned:
                    self.active_process.stdin.write("G")
                    self.active_process.stdin.flush()
            for out in (self.active_process.stdout, self.active_process.stderr):
                worker = threading.Thread(
                    target=self._enqueue_output,
                    args=(out, self.output_queue),
                    daemon=True,
                )
                worker.start()
                self._reader_threads.append(worker)

        except Exception as e:
            self.terminal_history.append(f"[Start Error: {e}]")
            self._close_process()

    def update_history_from_queue(self):
        """Assembles lines from characters in the queue."""
        for _ in range(10000):
            try:
                char = self.output_queue.get_nowait()
                if char == "\n":
                    self.terminal_history.append(self.current_line_output)
                    self.current_line_output = ""
                elif char == "\r":
                    continue
                else:
                    self.current_line_output += char
                    if len(self.current_line_output) >= max(1, self.width - 2):
                        self.terminal_history.append(self.current_line_output)
                        self.current_line_output = ""
            except queue.Empty:
                break

    def update(self, dt: float) -> None:
        self.update_history_from_queue()
        del self.terminal_history[: -max(100, self.height * 4)]
        self._paint()

    def _paint(self) -> None:
        self.buffer.clear_buffer(val=None)

        all_lines = list(self.terminal_history)
        if self.current_line_output:
            all_lines.append(self.current_line_output)

        display_lines = all_lines[-(self.max_lines - 1) :] if self.max_lines > 1 else []

        x_offset = 1 if self.width > 2 else 0
        y_offset = 1 if self.height > 2 else 0
        for line in display_lines:
            self.buffer.put_at(x_offset, y_offset, line, transparent=False)
            y_offset += 1

        is_active = self.active_process and self.active_process.poll() is None
        current_prompt = self.prompt if not is_active else ""
        self.buffer.put_at(
            x_offset,
            y_offset,
            current_prompt + self.current_input + "_",
            transparent=False,
        )

    def handle_event(self, event: int) -> bool:
        if event in (-1, 3, 27):
            return True
        if event in (10, 13):
            self.execute_command()
        elif event in (-300, 8, 127):
            self.current_input = self.current_input[:-1]
        elif isinstance(event, int) and 32 <= event <= 126:
            self.current_input += chr(event)
        return False

    def _close_process(self):
        """Reap owned processes and readers; never silently abandon live workers."""
        self._reader_stop.set()
        process = self.active_process
        if self._process_job is not None:
            self._process_job.Close()
            self._process_job = None
        if process is not None:
            if sys.platform == "win32":
                if not self._job_assigned and process.poll() is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        timeout=2,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            finally:
                if sys.platform != "win32":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            for worker in self._reader_threads:
                worker.join(timeout=2)
            if any(worker.is_alive() for worker in self._reader_threads):
                raise RuntimeError(
                    "Terminal output worker did not stop before the timeout"
                )
            with ExitStack() as cleanup:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        cleanup.callback(stream.close)
            self.active_process = None
        self._reader_threads.clear()
        self._job_assigned = False

    def close(self):
        with ExitStack() as cleanup:
            cleanup.callback(super().close)
            cleanup.callback(self._close_process)

    def resize(self, size: tuple[int, int]) -> None:
        """Repaint output/input without draining the queue or resizing a process."""
        self.buffer = raster(self.buffer, size, self.background)
        self.width, self.height = size
        self.max_lines = max(1, self.height - 2)
        self._paint()
        super().resize(size)

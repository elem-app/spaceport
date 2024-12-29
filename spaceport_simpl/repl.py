import fcntl
import os
import pty
import re
import select
import signal
import subprocess
import threading
import time
from abc import abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import override

from spaceport.op import fs, repl
from spaceport.subject import TSL, Handle, Subject, TSLError
from spaceport.subject.factory import ManagedSubject


class InputQuery(int):
    pass


class OutputQuery(int):
    """A query for output.

    Its value is an non-positive integer. ``0`` queries for the current buffer, ``-1``
    queries for the previous buffer, and so on.
    """


class KeyboardEvent(list[str]):
    def __str__(self) -> str:
        return f"[{'+'.join(self)}]"


class Buffer(list[str | KeyboardEvent]):
    @override
    def copy(self) -> "Buffer":
        return Buffer(super().copy())

    def __str__(self) -> str:
        return "\n".join(map(str, self))

    def str_without_enter(self) -> str:
        if self[-1] == KeyboardEvent(["Enter"]):
            return str(Buffer(self[:-1]))
        else:
            return str(self)


class Cursor(Handle, repl.CheckState, repl.Input, repl.Read, repl.Wait):
    @override
    @asynccontextmanager
    async def bind(self):
        yield

    def __init__(self, query: InputQuery | OutputQuery | None, subject: "REPLSubject"):
        self.query = query
        self.subject = subject

    def _assert_alive(self, is_alive: bool = True) -> None:
        assert self.subject.is_alive == is_alive, (
            "Subject is dead" if is_alive else "Subject should be dead but is alive"
        )

    @override
    async def size(self) -> int:
        return 1

    @override
    def is_collection(self) -> bool:
        return False

    @override
    def is_alive(self) -> bool:
        return self.subject.is_alive

    @override
    def read_text(self, encoding: str = "utf-8") -> str:
        match self.query:
            case InputQuery():
                return str(self.subject.inputs[self.query - 1])
            case OutputQuery():
                assert self.query < 0, "Output buffer index should be negative"
                return self.subject.outputs[self.query]
            case None:
                raise ValueError("Cannot read the entire subject")

    @override
    def read_bytes(self) -> bytes:
        return self.read_text().encode("utf-8")

    @override
    def input_enter(self) -> None:
        self._assert_alive()
        self.subject.inputs[-1].append(KeyboardEvent(["Enter"]))
        if self.subject.try_execute(self.subject.inputs[-1].copy()):
            self.subject.inputs.append(Buffer())

    @override
    def input_text(self, text: str) -> None:
        self._assert_alive()
        self.subject.inputs[-1].append(text)

    @override
    def input_keys(self, keys: list[str]) -> None:
        self._assert_alive()
        self.subject.inputs[-1].append(KeyboardEvent(keys))
        if self.subject.try_execute(self.subject.inputs[-1].copy()):
            self.subject.inputs.append(Buffer())

    @override
    def wait_till_complete(
        self, timeout: float | None = None, return_error: bool = False
    ) -> None | Exception:
        last_cmd = self.subject.inputs[-2].str_without_enter()
        if not self.subject.execution_complete.wait(timeout):
            raise RuntimeError(f"Timeout while waiting for '{last_cmd}'")
        err = (
            RuntimeError(
                f"'{last_cmd}' failed with exit code {self.subject.last_exit_code}; "
                f"output: {self.subject.outputs[-1]}"
            )
            if self.subject.last_exit_code != 0
            else None
        )
        if return_error:
            return err
        elif err:
            raise err


class REPLSubject(Subject[Cursor]):
    def __init__(self):
        self.is_alive = True
        self.execution_complete = threading.Event()
        self.execution_complete.set()
        self.last_exit_code = 0
        self.inputs = [Buffer()]
        self.outputs = [""]

    @override
    async def search(self, tsl: TSL, op_name: str) -> Cursor:
        if tsl.header not in ("term", "cli", "repl"):
            raise TSLError(f"Cannot get a cursor for {tsl}")

        body_parts = iter(tsl.body_parts())
        query_cls_str = next(body_parts)
        match query_cls_str:
            case "input":
                query_cls = InputQuery
            case "output":
                query_cls = OutputQuery
            case "":
                # No query, return a cursor that represents the entire subject
                return Cursor(None, self)
            case _:
                raise TSLError(f"Cannot get a cursor for {tsl}")

        query_idx_str = next(body_parts, "0")
        try:
            query_idx = int(query_idx_str)
        except ValueError:
            raise TSLError(f"Cannot get a cursor for {tsl}")
        if query_idx > 0:
            raise TSLError(f"Cannot get a cursor for {tsl}")

        return Cursor(query_cls(query_idx), self)

    @abstractmethod
    def try_execute(self, buf: Buffer) -> bool:
        """Try to execute the given buffer.

        Returns ``True`` if the buffer resulted in a command execution, regardless of
        whether it completed successfully or not.
        """


class ShellCursor(Cursor, fs.WorkingDir):
    def __init__(self, query: InputQuery | OutputQuery | None, subject: "BashREPL"):
        super().__init__(query, subject)
        self.subject = subject

    @override
    def set_working_dir(self, dest: str) -> None:
        self._assert_alive()
        self.subject.change_cwd(dest)

    @override
    def get_working_dir(self) -> str:
        self._assert_alive()
        return self.subject.get_cwd()


class BashREPL(REPLSubject, ManagedSubject[ShellCursor]):
    """A subject implementation that interacts with a local bash shell for
    non-interactive use.

    This implementation only supports interactions in an REPL manner. Interactive
    programs like vim, nano, tmux, etc. are not supported.

    Acceptable TSL headers: ``term``, ``cli``, and ``repl``.
    """

    CUSTOM_PROMPT = "__SP_BASH_# "

    def __init__(self, *, max_timeout: float = 300.0, cwd: str = "."):
        """Initialize a local bash REPL subject.

        :param max_timeout: The maximum time to wait for a command to complete. Defaults
            to 300 seconds.
        :param cwd: The initial working directory. Defaults to the current working
            directory.
        """
        super().__init__()
        self.max_timeout = max_timeout
        self.executor = ThreadPoolExecutor(max_workers=1)

        self.interrupt_handlers = {
            ("Control", "c"): lambda: self._send_signal(signal.SIGINT),
            ("Control", "z"): lambda: self._send_signal(signal.SIGTSTP),
            ("Control", "\\"): lambda: self._send_signal(signal.SIGQUIT),
            ("Control", "d"): lambda: self._handle_eof(),
        }

        # Create pseudoterminal for interactive programs
        master_fd, slave_fd = pty.openpty()
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Start bash with pseudo-terminal
        self.bash = subprocess.Popen(
            ["bash", "-c", f'PS1="{self.CUSTOM_PROMPT}" exec bash'],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
            cwd=cwd,
        )

        os.close(slave_fd)  # Close slave fd after passing to subprocess
        self.master_fd = master_fd

        self.outputs = [self._read_output_until_complete()]

    @override
    async def search(self, tsl: TSL, op_name: str) -> ShellCursor:
        cursor = await REPLSubject.search(self, tsl, op_name)
        return ShellCursor(cursor.query, self)

    @override
    async def destroy(self) -> None:
        try:
            self.bash.kill()
            self.bash.wait(timeout=1.0)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
        finally:
            # Clean up resources
            try:
                os.close(self.master_fd)
            except OSError:
                pass

    def change_cwd(self, to: str) -> None:
        self._write_to_stdin(f"mkdir -p {to} && cd {to}\n")
        # Discard the output of the commands
        self._read_output_until_complete()

    def get_cwd(self) -> str:
        self._write_to_stdin("pwd\n")
        # strip the trailing newline
        return self._read_output_until_complete(trim="pwd\n").rstrip()

    def _send_signal(self, sig: int) -> bool:
        """Send signal to bash process and return success status."""
        try:
            if self.bash.poll() is None:
                self.bash.send_signal(sig)
                return True
            self.is_alive = False
            return False
        except ProcessLookupError:
            self.is_alive = False
            return False

    def _handle_eof(self) -> bool:
        """Handle EOF (Ctrl+D) by closing the master file descriptor."""
        try:
            os.close(self.master_fd)
            self.is_alive = False
            self.bash.terminate()
            return True
        except OSError:
            self.is_alive = False
            return False

    def _write_to_stdin(self, data: str) -> bool:
        """Write accumulated input to bash stdin."""
        try:
            os.write(self.master_fd, data.encode())
            return True
        except (BrokenPipeError, IOError):
            self.is_alive = False
            return False

    @override
    def try_execute(self, buf: Buffer) -> bool:
        self.execution_complete.clear()
        current_input: list[str] = []

        for event in buf:
            if isinstance(event, KeyboardEvent):
                key_combo = tuple(sorted(event))

                if key_combo in self.interrupt_handlers:
                    current_input.clear()
                    event_sent = self.interrupt_handlers[key_combo]()
                    if event_sent and self.is_alive:
                        self.save_output_async()
                    else:
                        self.execution_complete.set()
                    return event_sent

                if "Enter" in event:
                    data = "".join(current_input)
                    # Ensure separation with printf to guarantee newlines
                    data_with_marker = f"{data}; printf '\\n%s\\n' X\"$?\"\n"
                    event_sent = self._write_to_stdin(data_with_marker)
                    if event_sent and self.is_alive:
                        self.save_output_async(trim=data_with_marker)
                    else:
                        self.execution_complete.set()
                    return event_sent

            else:
                current_input.append(event)

        self.execution_complete.set()
        return False

    def save_output_async(self, trim: str | None = None) -> None:
        def handle_output_complete(future: Future[str]) -> None:
            try:
                output = future.result()
            except Exception as e:
                output = f"Error reading output: {str(e)}"
            self.outputs.append(output)
            self.execution_complete.set()

        self.executor.submit(
            self._read_output_until_complete, trim=trim
        ).add_done_callback(handle_output_complete)

    def _read_output_until_complete(self, trim: str | None = None) -> str:
        """Read output until likely prompt is detected or timeout occurs."""
        buffer = ""
        start_time = time.monotonic()

        while time.monotonic() - start_time < self.max_timeout:
            try:
                ready, _, _ = select.select(
                    [self.master_fd], [], [], 0.1
                )  # Wait up to 0.1s for new output
                if ready:
                    data = os.read(self.master_fd, 4096)
                    if not data:
                        break
                    text = data.decode(errors="replace").replace("\r\n", "\n")
                    buffer += text

                    if buffer.endswith(self.CUSTOM_PROMPT):
                        output_text = buffer.split(self.CUSTOM_PROMPT)[0]
                        try:
                            x_idx = output_text.rindex("\nX")
                        except ValueError:
                            pass
                        else:
                            try:
                                self.last_exit_code = int(output_text[x_idx + 2 :])
                            except (IndexError, ValueError):
                                self.last_exit_code = 0
                            output_text = output_text[:x_idx]

                        if trim:
                            output_text = re.sub(
                                "[ \\r]*".join([re.escape(c) for c in trim]),
                                "",
                                output_text,
                                count=1,
                            )
                        return output_text

            except (OSError, IOError):
                self.is_alive = False
                break

        return buffer

from __future__ import annotations

import threading
from pathlib import Path


class _FakeStream:
    def __init__(self, text: str = "") -> None:
        self._lines = text.splitlines(keepends=True)
        self._closed = False
        self._condition = threading.Condition()

    def __iter__(self):
        index = 0
        with self._condition:
            while True:
                while index == len(self._lines) and not self._closed:
                    self._condition.wait()
                if index == len(self._lines):
                    return
                line = self._lines[index]
                index += 1
                yield line

    def read(self) -> str:
        with self._condition:
            return "".join(self._lines)

    def append(self, text: str) -> None:
        with self._condition:
            self._lines.extend(text.splitlines(keepends=True))
            self._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()


class _FakeStdin:
    def __init__(self, process: "FakeSandboxProcess") -> None:
        self._process = process

    def write(self, text: str) -> int:
        self._process.receive_input(text)
        return len(text)

    def flush(self) -> None:
        pass


class FakeSandboxProcess:
    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        exit_code: int | None = 0,
        echo_input: bool = False,
    ) -> None:
        self.stdin = _FakeStdin(self)
        self.stdout = _FakeStream(stdout)
        self.stderr = _FakeStream(stderr)
        self.exit_code = exit_code
        self.echo_input = echo_input
        self.terminate_tree_called = False

    def poll(self) -> int | None:
        return self.exit_code

    def wait(self, timeout: float | None = None) -> int:
        _ = timeout
        return 0 if self.exit_code is None else self.exit_code

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        _ = timeout
        return self.stdout.read(), self.stderr.read()

    def terminate_tree(self) -> None:
        self.terminate_tree_called = True
        self.exit_code = 1
        self.stdout.close()
        self.stderr.close()

    def receive_input(self, text: str) -> None:
        if not self.echo_input:
            return
        self.stdout.append(f"echo:{text.strip()}\n")
        self.exit_code = 0
        self.stdout.close()
        self.stderr.close()


class FakeSandboxRunner:
    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        exit_code: int | None = 0,
        echo_input: bool = False,
    ) -> None:
        self.requests: list[tuple[tuple[str, ...], Path]] = []
        self.processes: list[FakeSandboxProcess] = []
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.echo_input = echo_input

    def start(self, argv: tuple[str, ...] | list[str], *, cwd: Path) -> FakeSandboxProcess:
        self.requests.append((tuple(argv), cwd))
        process = FakeSandboxProcess(
            self.stdout,
            self.stderr,
            self.exit_code,
            self.echo_input,
        )
        self.processes.append(process)
        return process

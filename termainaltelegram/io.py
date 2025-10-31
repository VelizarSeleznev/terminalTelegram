from __future__ import annotations

from typing import List


class IOInterface:
    """Abstraction over terminal IO to simplify testing."""

    def read(self, prompt: str = "") -> str:  # pragma: no cover - interface contract
        raise NotImplementedError

    def write(self, text: str = "") -> None:  # pragma: no cover - interface contract
        raise NotImplementedError


class StdIO(IOInterface):
    """Standard stdin/stdout implementation."""

    def read(self, prompt: str = "") -> str:
        return input(prompt)

    def write(self, text: str = "") -> None:
        print(text)


class BufferedIO(IOInterface):
    """Test-double IO that consumes scripted input and captures output."""

    def __init__(self, scripted_inputs: List[str]):
        self._inputs = list(scripted_inputs)
        self.outputs: List[str] = []

    def read(self, prompt: str = "") -> str:
        self.outputs.append(prompt)
        if not self._inputs:
            raise EOFError("No more scripted inputs")
        return self._inputs.pop(0)

    def write(self, text: str = "") -> None:
        self.outputs.append(text)

# compiscript/codegen/temp_pool.py
from __future__ import annotations

class TempPool:
    def __init__(self, prefix: str = "t"):
        self.prefix = prefix
        self.n = 0

    def new(self) -> str:
        name = f"{self.prefix}{self.n}"
        self.n += 1
        return name

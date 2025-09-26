# compiscript/codegen/frame.py
# Very small activation-record helper for 32-bit cdecl x86
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional

WORD = 4

@dataclass
class Frame:
    name: str
    # map of names to stack offsets relative to EBP
    locals: Dict[str, int] = field(default_factory=dict)
    temps: Dict[str, int] = field(default_factory=dict)
    # next negative offset for locals/temps
    _next_local_off: int = -WORD

    def add_local(self, name: str, size: int = WORD) -> int:
        if name in self.locals:
            return self.locals[name]
        off = self._next_local_off
        self.locals[name] = off
        self._next_local_off -= max(size, WORD)
        return off

    def add_temp(self, tname: str) -> int:
        if tname in self.temps:
            return self.temps[tname]
        off = self._next_local_off
        self.temps[tname] = off
        self._next_local_off -= WORD
        return off

    def offset_of(self, name: str) -> Optional[int]:
        if name in self.locals:
            return self.locals[name]
        if name in self.temps:
            return self.temps[name]
        return None

    @property
    def frame_size(self) -> int:
        # space needed for all locals/temps; rounded to multiple of WORD
        size = (-self._next_local_off - WORD)
        return ((size + (WORD-1)) // WORD) * WORD

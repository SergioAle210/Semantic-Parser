# compiscript/codegen/frame.py
from __future__ import annotations
from typing import Dict, List, Optional

class Frame:
    """
    Frame muy simple para x86 (cdecl):
      [ebp+8]  1er parámetro
      [ebp+12] 2do parámetro ...
      [ebp-4]  1er local/temporal
      [ebp-8]  2do local/temporal ...
    """
    def __init__(self, func_name: str, params: List[str]):
        self.func_name = func_name
        # params: desplazamientos positivos
        self.param_off: Dict[str, int] = {}
        off = 8
        for p in params:
            self.param_off[p] = off
            off += 4
        # locals/temps: desplazamientos negativos
        self.local_off: Dict[str, int] = {}   # name -> positive slot index (1-based)
        self._locals_bytes = 0

    def ensure_local(self, name: str) -> int:
        if name in self.local_off:
            return self.local_off[name]
        # asigna un slot nuevo (4 bytes)
        self._locals_bytes += 4
        self.local_off[name] = self._locals_bytes
        return self.local_off[name]

    def get_local_disp(self, name: str) -> Optional[int]:
        return self.local_off.get(name, None)

    def get_param_disp(self, name: str) -> Optional[int]:
        return self.param_off.get(name, None)

    def local_size(self) -> int:
        return self._locals_bytes

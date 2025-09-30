from __future__ import annotations

class TempPool:
    def __init__(self, prefix: str = "t"):
        self.prefix = prefix
        self.n = 0
        self.free = []   # pila de nombres libres reutilizables

    def new(self) -> str:
        if self.free:
            return self.free.pop()
        name = f"{self.prefix}{self.n}"
        self.n += 1
        return name

    def release(self, name: str):
        # sólo recicla si coincide con el prefijo esperado
        if isinstance(name, str) and name.startswith(self.prefix):
            self.free.append(name)

# compiscript/codegen/temp_pool.py
# Simple temp pool that recycles temps, useful when lowering expressions.
from __future__ import annotations
from typing import List
from ..ir.tac import Addr, TACProgram

class TempPool:
    def __init__(self, program: TACProgram):
        self.prog = program
        self.pool: List[Addr] = []

    def get(self) -> Addr:
        if self.pool:
            return self.pool.pop()
        return self.prog.new_temp()

    def release(self, t: Addr):
        self.pool.append(t)

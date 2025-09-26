# compiscript/ir/tac.py
# Three-Address Code (TAC) data structures and helpers.
# This module is intentionally small and target-agnostic.

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Union, Iterable, Dict

# --- Addresses ---

class AddrKind(Enum):
    TEMP = auto()
    NAME = auto()
    CONST = auto()
    LABEL = auto()


@dataclass(frozen=True)
class Addr:
    kind: AddrKind
    value: Union[str, int, float, bool, None]

    def __str__(self) -> str:
        if self.kind == AddrKind.CONST:
            return str(self.value).lower() if isinstance(self.value, bool) else str(self.value)
        return str(self.value)


def Temp(name: str) -> Addr:
    return Addr(AddrKind.TEMP, name)


def Name(name: str) -> Addr:
    return Addr(AddrKind.NAME, name)


def Const(v: Union[int, float, bool, str, None]) -> Addr:
    # Strings are lowered as names handled elsewhere; for TAC keep integers/booleans/floats.
    if isinstance(v, str):
        return Addr(AddrKind.NAME, v)
    return Addr(AddrKind.CONST, v)


def Label(name: str) -> Addr:
    return Addr(AddrKind.LABEL, name)


# --- TAC ops ---

class Op(Enum):
    # arithmetic/logic
    ADD = auto(); SUB = auto(); MUL = auto(); DIV = auto(); MOD = auto()
    NEG = auto(); NOT = auto()
    AND = auto(); OR = auto(); XOR = auto(); SHL = auto(); SHR = auto()

    # comparisons (for value or branches)
    EQ = auto(); NE = auto(); LT = auto(); LE = auto(); GT = auto(); GE = auto()

    # data movement
    MOV = auto()  # res = a1
    LOAD = auto() # res = [a1]     (a1 holds address)
    STORE = auto() # [res] = a1    (res holds address)
    LEA = auto()  # res = &a1      (address-of)

    # array index helpers
    IDX_ADDR = auto()  # res = base + index * scale

    # control flow
    GOTO = auto()
    IF_GOTO = auto()        # if a1 != 0 goto label(res)
    IF_FALSE_GOTO = auto()  # if a1 == 0 goto label(res)
    IF_CMP_GOTO = auto()    # if a1 (cmp op) a2 goto label(res)
    LABEL = auto()
    RETURN = auto()

    # call ABI
    PARAM = auto()  # pass parameter (push-like)
    CALL = auto()   # call name in a1, with arg count in a2; result into res if not None

    # misc
    NOP = auto()


@dataclass
class Quad:
    op: Op
    a1: Optional[Addr] = None
    a2: Optional[Addr] = None
    res: Optional[Addr] = None
    comment: Optional[str] = None

    def __str__(self) -> str:
        c = f"    # {self.comment}" if self.comment else ""
        def fmt(a): return "" if a is None else str(a)
        if self.op == Op.LABEL:
            return f"{fmt(self.res)}:{c}"
        if self.op == Op.GOTO:
            return f"goto {fmt(self.res)}{c}"
        if self.op == Op.IF_GOTO:
            return f"if {fmt(self.a1)} goto {fmt(self.res)}{c}"
        if self.op == Op.IF_FALSE_GOTO:
            return f"ifFalse {fmt(self.a1)} goto {fmt(self.res)}{c}"
        if self.op == Op.IF_CMP_GOTO:
            return f"if {fmt(self.a1)} {fmt(self.a2)} goto {fmt(self.res)}{c}"
        if self.op == Op.PARAM:
            return f"param {fmt(self.a1)}{c}"
        if self.op == Op.CALL:
            if self.res is None:
                return f"call {fmt(self.a1)}, {fmt(self.a2)}{c}"
            return f"{fmt(self.res)} = call {fmt(self.a1)}, {fmt(self.a2)}{c}"
        if self.op == Op.RETURN:
            return f"return {fmt(self.a1)}{c}" if self.a1 else f"return{c}"
        if self.op == Op.MOV:
            return f"{fmt(self.res)} = {fmt(self.a1)}{c}"
        if self.op == Op.LOAD:
            return f"{fmt(self.res)} = *{fmt(self.a1)}{c}"
        if self.op == Op.STORE:
            return f"*{fmt(self.res)} = {fmt(self.a1)}{c}"
        if self.op == Op.LEA:
            return f"{fmt(self.res)} = &{fmt(self.a1)}{c}"
        if self.op == Op.IDX_ADDR:
            return f"{fmt(self.res)} = {fmt(self.a1)} + {fmt(self.a2)}{c}"
        # generic 3-address form
        if self.a2 is not None:
            return f"{fmt(self.res)} = {fmt(self.a1)} {self.op.name.lower()} {fmt(self.a2)}{c}"
        if self.a1 is not None and self.res is not None:
            return f"{fmt(self.res)} = {self.op.name.lower()} {fmt(self.a1)}{c}"
        return f"{self.op.name.lower()}{c}"


class TACProgram:
    """A simple, linear sequence of quads with helpers to create temps and labels."""
    def __init__(self, name: str = "<toplevel>"):
        self.name = name
        self.quads: List[Quad] = []
        self.temp_index = 0
        self.label_index = 0

    def new_temp(self) -> Addr:
        t = Temp(f"t{self.temp_index}")
        self.temp_index += 1
        return t

    def new_label(self, base: str = "L") -> Addr:
        l = Label(f"{base}{self.label_index}")
        self.label_index += 1
        return l

    def emit(self, q: Quad) -> Quad:
        self.quads.append(q)
        return q

    def label(self, lab: Addr, comment: Optional[str] = None):
        self.emit(Quad(Op.LABEL, res=lab, comment=comment))

    def goto(self, lab: Addr, comment: Optional[str] = None):
        self.emit(Quad(Op.GOTO, res=lab, comment=comment))

    def __str__(self) -> str:
        lines = [f"# TAC program: {self.name}"]
        lines += [str(q) for q in self.quads]
        return "\n".join(lines)


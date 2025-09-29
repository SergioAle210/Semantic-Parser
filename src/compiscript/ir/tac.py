# compiscript/ir/tac.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

# -------------------------
# Operands
# -------------------------
class Operand:
    pass

@dataclass(frozen=True)
class Temp(Operand):
    name: str

@dataclass(frozen=True)
class Local(Operand):
    name: str  # variable local (let/const)

@dataclass(frozen=True)
class Param(Operand):
    name: str  # parámetro de función

@dataclass(frozen=True)
class ConstInt(Operand):
    value: int

@dataclass(frozen=True)
class ConstStr(Operand):
    label: str  # etiqueta en .data

# -------------------------
# Instrucciones TAC
# -------------------------
class Instr:
    pass

@dataclass
class Label(Instr):
    name: str

@dataclass
class Jump(Instr):
    target: str

@dataclass
class CJump(Instr):
    op: str            # '==', '!=', '<', '<=', '>', '>='
    a: Operand
    b: Operand
    if_true: str
    if_false: str

@dataclass
class Move(Instr):
    dst: Operand
    src: Operand

@dataclass
class BinOp(Instr):
    op: str            # '+','-','*','/','%'
    dst: Operand
    a: Operand
    b: Operand

@dataclass
class UnaryOp(Instr):
    op: str            # 'neg' (unario -), 'not' (!)
    dst: Operand
    a: Operand

@dataclass
class Cmp(Instr):
    """dst = (a op b) ? 1 : 0, con op relacional."""
    op: str
    dst: Operand
    a: Operand
    b: Operand

@dataclass
class Call(Instr):
    dst: Optional[Operand]  # si None, se ignora el retorno
    func: str               # nombre (p.ej., 'print' o 'main')
    args: List[Operand]

@dataclass
class Return(Instr):
    value: Optional[Operand] = None

# -------------------------
# Unidades IR
# -------------------------
@dataclass
class IRFunction:
    name: str
    params: List[str]
    body: List[Instr] = field(default_factory=list)
    locals: List[str] = field(default_factory=list)  # nombres de locales (let/const)
    frame: Optional["Frame"] = None  # rellenado por IRGen/x86

@dataclass
class IRProgram:
    functions: Dict[str, IRFunction] = field(default_factory=dict)
    strings: Dict[str, bytes] = field(default_factory=dict)  # label -> bytes
    entry: Optional[str] = None

# compiscript/ir/pretty.py
from __future__ import annotations
from typing import Iterable
from .tac import TACProgram

def pretty(program: TACProgram) -> str:
    return str(program)
from typing import List
from compiscript.ir.tac import (
    IRProgram,
    IRFunction,
    Instr,
    Operand,
    Label,
    Jump,
    CJump,
    Move,
    BinOp,
    UnaryOp,
    Cmp,
    Call,
    Return,
    Temp,
    Local,
    Param,
    ConstInt,
    ConstStr,
)


def _opnd(o: Operand) -> str:
    if isinstance(o, Temp):
        return f"%{o.name}"
    if isinstance(o, Local):
        return f"${o.name}"
    if isinstance(o, Param):
        return f"@{o.name}"
    if isinstance(o, ConstInt):
        return str(o.value)
    if isinstance(o, ConstStr):
        return f"&{o.label}"
    return str(o)


def _ins(i: Instr) -> str:
    if isinstance(i, Label):
        return f"{i.name}:"
    if isinstance(i, Jump):
        return f"  goto {i.target}"
    if isinstance(i, CJump):
        return (
            f"  if {_opnd(i.a)} {i.op} {_opnd(i.b)} goto {i.if_true} else {i.if_false}"
        )
    if isinstance(i, Move):
        return f"  {_opnd(i.dst)} = {_opnd(i.src)}"
    if isinstance(i, BinOp):
        return f"  {_opnd(i.dst)} = {_opnd(i.a)} {i.op} {_opnd(i.b)}"
    if isinstance(i, UnaryOp):
        u = "neg" if i.op == "neg" else "not"
        return f"  {_opnd(i.dst)} = {u}({_opnd(i.a)})"
    if isinstance(i, Cmp):
        return f"  {_opnd(i.dst)} = ({_opnd(i.a)} {i.op} {_opnd(i.b)})"
    if isinstance(i, Call):
        args = ", ".join(_opnd(a) for a in i.args)
        if i.dst is None:
            return f"  call {i.func}({args})"
        return f"  {_opnd(i.dst)} = call {i.func}({args})"
    if isinstance(i, Return):
        if i.value is None:
            return "  return"
        return f"  return {_opnd(i.value)}"
    return f"  ; {i}"


def format_ir(prog: IRProgram) -> str:
    out: List[str] = []
    # strings
    if prog.strings:
        out.append("; .strings")
        for k, v in prog.strings.items():
            try:
                s = v.decode("utf-8")
            except Exception:
                s = repr(v)
            out.append(f";   {k}: {s}")
        out.append("")
    # functions
    for fname, fn in prog.functions.items():
        out.append(f"func {fname}({', '.join(fn.params)})")
        if fn.locals:
            out.append(f"  ; locals: {', '.join(fn.locals)}")
        for ins in fn.body:
            out.append(_ins(ins))
        out.append("endfunc\n")
    if prog.entry:
        out.append(f"; entry: {prog.entry}")
    return "\n".join(out)


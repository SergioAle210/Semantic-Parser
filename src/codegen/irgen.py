# compiscript/codegen/irgen.py
# AST -> TAC generator. This module assumes an AST with node classes similar
# to those used in your semantic checker (Identifier, Literal, Binary, If, While, etc.).
# It purposely implements just the essential subset so you can extend it.
from __future__ import annotations
from typing import Optional, List, Tuple
from..compiscript.ir.tac import *
from .temp_pool import TempPool

# --- A tiny AST "protocol" for demos ---
# If you already have real AST nodes, you can ignore this section.
class Identifier:
    def __init__(self, name, loc=None): self.name, self.loc = name, loc
class Literal:
    def __init__(self, kind, value, loc=None): self.kind, self.value, self.loc = kind, value, loc
class Binary:
    def __init__(self, op, left, right, loc=None): self.op, self.left, self.right, self.loc = op, left, right, loc
class Unary:
    def __init__(self, op, expr, loc=None): self.op, self.expr, self.loc = op, expr, loc
class Assign:
    def __init__(self, target, value, loc=None): self.target, self.value, self.loc = target, value, loc
class Return:
    def __init__(self, value=None, loc=None): self.value, self.loc = value, loc
class If:
    def __init__(self, cond, then_blk, else_blk=None, loc=None): self.cond, self.then_blk, self.else_blk, self.loc = cond, then_blk, else_blk, loc
class While:
    def __init__(self, cond, body, loc=None): self.cond, self.body, self.loc = cond, body, loc
class ExprStmt:
    def __init__(self, expr, loc=None): self.expr, self.loc = expr, loc
class Block:
    def __init__(self, statements): self.statements = statements
class Program:
    def __init__(self, statements): self.statements = statements

BIN_OP_MAP = {
    "+": Op.ADD, "-": Op.SUB, "*": Op.MUL, "/": Op.DIV, "%": Op.MOD,
    "&&": Op.AND, "||": Op.OR, "^": Op.XOR, "<<": Op.SHL, ">>": Op.SHR,
}
CMP_OPS = {"==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}

class IRGen:
    def __init__(self):
        self.prog = TACProgram("<main>")
        self.temp_pool = TempPool(self.prog)
        self.break_labels: List[Addr] = []
        self.continue_labels: List[Addr] = []

    def gen(self, node) -> TACProgram:
        self.visit(node)
        return self.prog

    # --- Visitors ---
    def visit(self, n):
        if n is None: return None
        m = getattr(self, "visit_" + n.__class__.__name__, None)
        if m: return m(n)
        raise NotImplementedError("No visitor for " + n.__class__.__name__)

    def visit_Program(self, n: Program):
        for s in n.statements:
            self.visit(s)

    def visit_Block(self, n: Block):
        for s in n.statements:
            self.visit(s)

    # Expressions produce an Addr
    def visit_Literal(self, n: Literal) -> Addr:
        if n.kind == "int": return Const(int(n.value))
        if n.kind == "boolean": return Const(bool(n.value))
        # strings/others simplified as names
        return Name(str(n.value))

    def visit_Identifier(self, n: Identifier) -> Addr:
        return Name(n.name)

    def visit_Unary(self, n: Unary) -> Addr:
        a = self.visit(n.expr)
        t = self.temp_pool.get()
        if n.op == "!":
            self.prog.emit(Quad(Op.NOT, a1=a, res=t))
            if isinstance(a, Addr) and a.kind == AddrKind.TEMP:
                self.temp_pool.release(a)
        elif n.op == "-":
            self.prog.emit(Quad(Op.NEG, a1=a, res=t))
            if isinstance(a, Addr) and a.kind == AddrKind.TEMP:
                self.temp_pool.release(a)
        else:
            self.prog.emit(Quad(Op.NOP, comment=f"unhandled unary {n.op}"))
        return t

    def visit_Binary(self, n: Binary) -> Addr:
        if n.op in BIN_OP_MAP:
            a1 = self.visit(n.left)
            a2 = self.visit(n.right)
            t = self.temp_pool.get()
            self.prog.emit(Quad(BIN_OP_MAP[n.op], a1=a1, a2=a2, res=t))
            # simple recycling: children temps are no longer needed
            if isinstance(a1, Addr) and a1.kind == AddrKind.TEMP:
                self.temp_pool.release(a1)
            if isinstance(a2, Addr) and a2.kind == AddrKind.TEMP:
                self.temp_pool.release(a2)
            return t
        if n.op in CMP_OPS:
            # Evaluate to boolean 0/1 via setcc pattern: use IF_CMP_GOTO + phi-like movs
            a1 = self.visit(n.left); a2 = self.visit(n.right)
            t_res = self.temp_pool.get()
            L_true = self.prog.new_label("L")
            L_end = self.prog.new_label("L")
            self.prog.emit(Quad(Op.IF_CMP_GOTO, a1=a1, a2=a2, res=L_true, comment=CMP_OPS[n.op]))
            self.prog.emit(Quad(Op.MOV, a1=Const(0), res=t_res))
            self.prog.emit(Quad(Op.GOTO, res=L_end))
            self.prog.label(L_true)
            self.prog.emit(Quad(Op.MOV, a1=Const(1), res=t_res))
            self.prog.label(L_end)
            return t_res
        raise NotImplementedError("binary op " + n.op)

    # Statements
    def visit_ExprStmt(self, n: ExprStmt):
        self.visit(n.expr)

    def visit_Assign(self, n: Assign):
        src = self.visit(n.value)
        if isinstance(n.target, Identifier):
            self.prog.emit(Quad(Op.MOV, a1=src, res=Name(n.target.name)))
        else:
            self.prog.emit(Quad(Op.NOP, comment="assign to complex lvalue not implemented"))

    def visit_Return(self, n: Return):
        a = self.visit(n.value) if n.value is not None else None
        self.prog.emit(Quad(Op.RETURN, a1=a))

    def _gen_bool_as_jumps(self, cond, L_true: Addr, L_false: Addr):
        # Short-circuit translation per classical approach.
        if isinstance(cond, Binary) and cond.op in ("&&", "||"):
            if cond.op == "&&":
                L_mid = self.prog.new_label("L")
                self._gen_bool_as_jumps(cond.left, L_mid, L_false)
                self.prog.label(L_mid)
                self._gen_bool_as_jumps(cond.right, L_true, L_false)
                return
            if cond.op == "||":
                L_mid = self.prog.new_label("L")
                self._gen_bool_as_jumps(cond.left, L_true, L_mid)
                self.prog.label(L_mid)
                self._gen_bool_as_jumps(cond.right, L_true, L_false)
                return
        elif isinstance(cond, Unary) and cond.op == "!":
            self._gen_bool_as_jumps(cond.expr, L_false, L_true)
            return
        else:
            # Fallback: evaluate to a temp and branch if not zero
            v = self.visit(cond)
            self.prog.emit(Quad(Op.IF_GOTO, a1=v, res=L_true))
            self.prog.emit(Quad(Op.GOTO, res=L_false))

    def visit_If(self, n: If):
        L_true = self.prog.new_label("L")
        L_false = self.prog.new_label("L")
        L_end = self.prog.new_label("L")
        self._gen_bool_as_jumps(n.cond, L_true, L_false)
        self.prog.label(L_true)
        self.visit(n.then_blk)
        self.prog.emit(Quad(Op.GOTO, res=L_end))
        self.prog.label(L_false)
        if n.else_blk:
            self.visit(n.else_blk)
        self.prog.label(L_end)

    def visit_While(self, n: While):
        L_begin = self.prog.new_label("L")
        L_true = self.prog.new_label("L")
        L_end = self.prog.new_label("L")
        self.break_labels.append(L_end)
        self.continue_labels.append(L_begin)
        self.prog.label(L_begin)
        self._gen_bool_as_jumps(n.cond, L_true, L_end)
        self.prog.label(L_true)
        self.visit(n.body)
        self.prog.emit(Quad(Op.GOTO, res=L_begin))
        self.prog.label(L_end)
        self.break_labels.pop()
        self.continue_labels.pop()

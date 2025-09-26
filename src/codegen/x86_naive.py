# compiscript/codegen/x86_naive.py
# Naïve TAC -> 32-bit x86 (cdecl) emitter.
from __future__ import annotations
from typing import List, Dict, Optional
from ..ir.tac import *
from .frame import Frame, WORD

class X86Naive:
    def __init__(self):
        self.lines: List[str] = []
        self.frame = Frame("<main>")
        self.labels_defined: Dict[str, bool] = {}

    # -- helpers --

    def _mem(self, a: Addr) -> str:
        # Return an assembly operand string for an Addr that lives in stack
        if a.kind == AddrKind.TEMP:
            off = self.frame.add_temp(str(a.value))
            return f"[ebp{off:+}]"
        if a.kind == AddrKind.NAME:
            off = self.frame.add_local(str(a.value))
            return f"[ebp{off:+}]"
        raise ValueError("Address not in stack: " + str(a))

    def _imm(self, a: Addr) -> str:
        if a.kind == AddrKind.CONST:
            if isinstance(a.value, bool):
                return "1" if a.value else "0"
            return str(a.value)
        raise ValueError("Not an immediate: " + str(a))

    def _mov_to_reg(self, reg: str, a: Addr):
        if a is None: return
        if a.kind in (AddrKind.TEMP, AddrKind.NAME):
            self.lines.append(f"    mov {reg}, {self._mem(a)}")
        elif a.kind == AddrKind.CONST:
            self.lines.append(f"    mov {reg}, {self._imm(a)}")
        else:
            raise ValueError("Unsupported addr kind for mov_to_reg: " + str(a.kind))

    def _store_from_reg(self, dst: Addr, reg: str):
        if dst.kind in (AddrKind.TEMP, AddrKind.NAME):
            self.lines.append(f"    mov {self._mem(dst)}, {reg}")
        else:
            raise ValueError("Unsupported store dest: " + str(dst.kind))

    def _emit_cmp(self, a1: Addr, a2: Addr):
        if a1.kind in (AddrKind.TEMP, AddrKind.NAME):
            self.lines.append(f"    mov eax, {self._mem(a1)}")
        elif a1.kind == AddrKind.CONST:
            self.lines.append(f"    mov eax, {self._imm(a1)}")
        else:
            raise ValueError("bad cmp a1")
        if a2.kind in (AddrKind.TEMP, AddrKind.NAME):
            self.lines.append(f"    cmp eax, {self._mem(a2)}")
        elif a2.kind == AddrKind.CONST:
            self.lines.append(f"    cmp eax, {self._imm(a2)}")
        else:
            raise ValueError("bad cmp a2")

    def _emit_arith(self, q: Quad):
        # eax = a1 op a2 ; res = eax
        self._mov_to_reg("eax", q.a1)
        if q.a2 is not None:
            if q.a2.kind in (AddrKind.TEMP, AddrKind.NAME):
                src = self._mem(q.a2)
            else:
                src = self._imm(q.a2)
        op = q.op
        if op == Op.ADD: self.lines.append(f"    add eax, {src}")
        elif op == Op.SUB: self.lines.append(f"    sub eax, {src}")
        elif op == Op.MUL: self.lines.append(f"    imul eax, {src}")
        elif op == Op.DIV:
            self.lines.append("    cdq")  # sign extend EAX into EDX:EAX
            if q.a2.kind in (AddrKind.TEMP, AddrKind.NAME):
                self.lines.append(f"    idiv dword {src}")
            else:
                # move immediate to ecx then divide
                self.lines.append(f"    mov ecx, {src}")
                self.lines.append("    idiv ecx")
        elif op == Op.MOD:
            self.lines.append("    cdq")
            if q.a2.kind in (AddrKind.TEMP, AddrKind.NAME):
                self.lines.append(f"    idiv dword {src}")
            else:
                self.lines.append(f"    mov ecx, {src}")
                self.lines.append("    idiv ecx")
            self.lines.append("    mov eax, edx")
        elif op == Op.AND: self.lines.append(f"    and eax, {src}")
        elif op == Op.OR: self.lines.append(f"    or eax, {src}")
        elif op == Op.XOR: self.lines.append(f"    xor eax, {src}")
        elif op == Op.SHL: self.lines.append(f"    shl eax, {src}")
        elif op == Op.SHR: self.lines.append(f"    sar eax, {src}")
        else:
            raise ValueError("Unsupported arith op: " + str(q.op))
        if q.res is not None:
            self._store_from_reg(q.res, "eax")

    def _emit_logic_not(self, res: Addr, a: Addr):
        self._mov_to_reg("eax", a)
        self.lines.append("    xor eax, eax")  # set EAX=0 ; the move above is overwritten, so fix:
        # Correction: compute logical not properly
        # We need (a == 0) ? 1 : 0
        self._mov_to_reg("eax", a)
        self.lines.append("    cmp eax, 0")
        self.lines.append("    sete al")
        self.lines.append("    movzx eax, al")
        self._store_from_reg(res, "eax")

    def _emit_mov(self, res: Addr, a: Addr):
        self._mov_to_reg("eax", a)
        self._store_from_reg(res, "eax")

    def _emit_label(self, lab: Addr):
        self.labels_defined[str(lab.value)] = True
        self.lines.append(f"{lab.value}:")

    def _emit_goto(self, lab: Addr):
        self.lines.append(f"    jmp {lab.value}")

    def _emit_if_goto(self, cond: Addr, lab: Addr, neg: bool = False):
        # if cond goto lab  (neg=False) ; ifFalse cond goto lab (neg=True)
        self._mov_to_reg("eax", cond)
        self.lines.append("    cmp eax, 0")
        self.lines.append(f"    {'je' if not neg else 'jne'} {lab.value}")

    def _emit_if_cmp_goto(self, q: Quad):
        # q.a1 holds lhs, q.a2 holds an encoded operator+rhs as NAME "op rhs" or tuple? We'll encode rhs in res label? Simpler:
        # We expect comment to carry real op; use q.comment as op string, res is label
        op = q.comment or "=="
        lhs, rhs = q.a1, q.a2
        self._emit_cmp(lhs, rhs)
        jmp = {"==": "je", "!=": "jne", "<": "jl", "<=": "jle", ">": "jg", ">=": "jge"}[op]
        self.lines.append(f"    {jmp} {q.res.value}")

    def _emit_return(self, a: Optional[Addr]):
        if a is not None:
            self._mov_to_reg("eax", a)
        # epilogue
        self.lines.append("    mov esp, ebp")
        self.lines.append("    pop ebp")
        self.lines.append("    ret")

    def _emit_idx_addr(self, res: Addr, base: Addr, index_scaled: Addr):
        # index_scaled is "index*scale" already emitted in TAC as a2; we just add base
        self._mov_to_reg("eax", base)
        if index_scaled.kind in (AddrKind.TEMP, AddrKind.NAME):
            self.lines.append(f"    add eax, {self._mem(index_scaled)}")
        else:
            self.lines.append(f"    add eax, {self._imm(index_scaled)}")
        self._store_from_reg(res, "eax")

    def lower(self, program: TACProgram, func_name: str = "main") -> str:
        # First pass: allocate stack slots for all res/a1/a2 temps and names
        for q in program.quads:
            for a in (q.a1, q.a2, q.res):
                if a is None: continue
                if a.kind == AddrKind.TEMP:
                    self.frame.add_temp(str(a.value))
                elif a.kind == AddrKind.NAME:
                    self.frame.add_local(str(a.value))
        # prologue
        self.lines.append("global _start")
        self.lines.append("section .text")
        self.lines.append(f"{func_name}:")
        self.lines.append("    push ebp")
        self.lines.append("    mov ebp, esp")
        if self.frame.frame_size:
            self.lines.append(f"    sub esp, {self.frame.frame_size}")
        # body
        for q in program.quads:
            if q.op == Op.LABEL:
                self._emit_label(q.res)
            elif q.op in (Op.ADD, Op.SUB, Op.MUL, Op.DIV, Op.MOD, Op.AND, Op.OR, Op.XOR, Op.SHL, Op.SHR):
                self._emit_arith(q)
            elif q.op == Op.NEG:
                self._mov_to_reg("eax", q.a1)
                self.lines.append("    neg eax")
                self._store_from_reg(q.res, "eax")
            elif q.op == Op.NOT:
                self._emit_logic_not(q.res, q.a1)
            elif q.op == Op.MOV:
                self._emit_mov(q.res, q.a1)
            elif q.op == Op.GOTO:
                self._emit_goto(q.res)
            elif q.op == Op.IF_GOTO:
                self._emit_if_goto(q.a1, q.res, neg=False)
            elif q.op == Op.IF_FALSE_GOTO:
                self._emit_if_goto(q.a1, q.res, neg=True)
            elif q.op == Op.IF_CMP_GOTO:
                self._emit_if_cmp_goto(q)
            elif q.op == Op.RETURN:
                self._emit_return(q.a1)
            elif q.op == Op.IDX_ADDR:
                self._emit_idx_addr(q.res, q.a1, q.a2)
            elif q.op in (Op.LOAD, Op.STORE, Op.LEA, Op.PARAM, Op.CALL):
                # For brevity, not fully implementing loads/stores and calls in this skeleton.
                self.lines.append(f"    ; TODO: {q}")
            else:
                self.lines.append(f"    ; unhandled {q}")
        # Ensure a proper exit if no explicit return; set eax=0
        if not any(q.op == Op.RETURN for q in program.quads):
            self.lines.append("    mov eax, 0")
            self.lines.append("    mov esp, ebp")
            self.lines.append("    pop ebp")
            self.lines.append("    ret")
        asm = "\n".join(self.lines)
        return asm

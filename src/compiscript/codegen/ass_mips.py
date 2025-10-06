from __future__ import annotations
from typing import Dict, List

from compiscript.codegen.frame import Frame
from compiscript.ir.tac import (
    IRProgram, IRFunction, Instr, Operand,
    Label, Jump, CJump, Move, BinOp, UnaryOp, Cmp, Call, Return,
    Temp, Local, Param, ConstInt, ConstStr,
    Load, Store, LoadI, StoreI
)

class MIPSNaive:
    """
    Backend MIPS32 (SPIM/MARS) con convención simple:
      - Caller pasa TODOS los args en stack (derecha→izquierda).
      - Retorno en $v0.
      - Callee guarda $fp/$ra y usa $fp como marco.
      - Locales/temps: -offset($fp). Params: (offset-8)($fp).
    """
    def __init__(self):
        self.lines: List[str] = []
        self.temp_slots: Dict[str, int] = {}

    # ---------- API principal ----------
    def compile(self, prog: IRProgram) -> str:
        self.lines = []
        self._emit_header()
        self._emit_data(prog)
        self._emit_text(prog)
        # runtime auxiliar (concat) siempre disponible
        self._emit_runtime_concat()
        # wrapper main si no existe un 'main' del usuario
        if "main" not in prog.functions:
            entry = prog.entry or "__toplevel"
            self._emit_main_wrapper(entry)
        return "\n".join(self.lines)

    # ---------- secciones ----------
    def _emit_header(self):
        self._w("# Compiscript MIPS (o32)")

    def _emit_data(self, prog: IRProgram):
        self._w(".data")
        # strings del programa como bytes (incluye NUL)
        for lab, b in prog.strings.items():
            bs = ", ".join(str(x) for x in b)
            self._w(f"{lab}: .byte {bs}")
        self._w("")
        self._w(".text")
        # exportar el entry real (útil para depurar y para wrapper)
        if prog.entry:
            self._w(f".globl {prog.entry}")

    def _emit_text(self, prog: IRProgram):
        for fname, fn in prog.functions.items():
            self._emit_function(fn, is_entry=(prog.entry == fname))

    # ---------- utils ----------
    def _w(self, s: str): self.lines.append(s)
    def _lbl(self, s: str): self._w(f"{s}:")

    def _addr(self, frame: Frame, op: Operand) -> str:
        # Devuelve desplazamiento($fp)
        if isinstance(op, Local):
            off = frame.get_local_disp(op.name)
            if off is None: off = frame.ensure_local(op.name)
            return f"-{off}($fp)"
        if isinstance(op, Temp):
            off = self.temp_slots.get(op.name)
            if off is None:
                off = frame.ensure_local(f"__t_{op.name}")
                self.temp_slots[op.name] = off
            return f"-{off}($fp)"
        if isinstance(op, Param):
            off = frame.get_param_disp(op.name)
            if off is None:
                raise RuntimeError(f"Param sin offset: {op.name}")
            # Ajuste: en nuestro prólogo $fp queda igual a SP de entrada → param0 = 0($fp)
            return f"{off - 8}($fp)"
        raise RuntimeError(f"Operando no direccionable: {op}")

    def _load_reg(self, frame: Frame, reg: str, op: Operand):
        if isinstance(op, ConstInt):
            self._w(f"  li {reg}, {op.value}")
        elif isinstance(op, ConstStr):
            self._w(f"  la {reg}, {op.label}")
        else:
            self._w(f"  lw {reg}, {self._addr(frame, op)}")

    def _store_from_reg(self, frame: Frame, dst: Operand, reg: str):
        if isinstance(dst, (Local, Temp, Param)):
            self._w(f"  sw {reg}, {self._addr(frame, dst)}")
        else:
            raise RuntimeError("Destino no soportado para store")

    # ---------- función ----------
    def _emit_function(self, fn: IRFunction, is_entry: bool):
        self.temp_slots.clear()
        frame = fn.frame or Frame(fn.name, fn.params)

        # Primera pasada: asignar slots a todos los Temp
        for ins in fn.body:
            if isinstance(ins, (Move, BinOp, UnaryOp, Cmp, Call, Return, CJump, Load, Store, LoadI, StoreI)):
                ops: List[Operand] = []
                if isinstance(ins, Move):      ops = [ins.dst, ins.src]
                if isinstance(ins, BinOp):     ops = [ins.dst, ins.a, ins.b]
                if isinstance(ins, UnaryOp):   ops = [ins.dst, ins.a]
                if isinstance(ins, Cmp):       ops = [ins.dst, ins.a, ins.b]
                if isinstance(ins, Call):
                    if ins.dst is not None: ops.append(ins.dst)
                    ops += list(ins.args)
                if isinstance(ins, Return):
                    if ins.value is not None: ops.append(ins.value)
                if isinstance(ins, CJump):
                    ops = [ins.a, ins.b]
                if isinstance(ins, Load):
                    ops = [ins.dst, ins.base]
                if isinstance(ins, Store):
                    ops = [ins.base, ins.src]
                if isinstance(ins, LoadI):
                    ops = [ins.dst, ins.base, ins.index]
                if isinstance(ins, StoreI):
                    ops = [ins.base, ins.index, ins.src]
                for o in ops:
                    if isinstance(o, Temp):
                        _ = self._addr(frame, o)

        # etiqueta y prólogo
        if is_entry: self._w(f".globl {fn.name}")
        self._lbl(fn.name)

        lsize = frame.local_size()
        self._w(f"  addiu $sp, $sp, -{lsize + 8}")
        self._w(f"  sw $ra, {lsize + 4}($sp)")
        self._w(f"  sw $fp, {lsize}($sp)")
        self._w(f"  addiu $fp, $sp, {lsize + 8}")  # $fp = SP de entrada (top de args)

        # cuerpo
        for ins in fn.body:
            self._emit_instr(frame, ins, lsize)

        # epílogo sólo si la última instr real NO fue Return
        last = None
        for ins in reversed(fn.body):
            if not isinstance(ins, Label):
                last = ins
                break
        if not isinstance(last, Return):
            self._emit_epilogue(lsize)

    def _emit_epilogue(self, lsize: int):
        self._w(f"  lw $fp, {lsize}($sp)")
        self._w(f"  lw $ra, {lsize + 4}($sp)")
        self._w(f"  addiu $sp, $sp, {lsize + 8}")
        self._w("  jr $ra")
        self._w("  nop")

    # ---------- instrucciones ----------
    def _emit_instr(self, frame: Frame, ins: Instr, lsize: int):
        if isinstance(ins, Label):
            self._lbl(ins.name); return

        if isinstance(ins, Jump):
            self._w(f"  j {ins.target}")
            self._w("  nop")
            return

        if isinstance(ins, CJump):
            self._load_reg(frame, "$t0", ins.a)
            if isinstance(ins.b, ConstInt):
                self._w(f"  li $t1, {ins.b.value}")
            elif isinstance(ins.b, ConstStr):
                self._w(f"  la $t1, {ins.b.label}")
            else:
                self._w(f"  lw $t1, {self._addr(frame, ins.b)}")

            op = ins.op
            if op == "==":
                self._w(f"  beq $t0, $t1, {ins.if_true}")
                self._w(f"  j {ins.if_false}"); self._w("  nop"); return
            if op == "!=":
                self._w(f"  bne $t0, $t1, {ins.if_true}")
                self._w(f"  j {ins.if_false}"); self._w("  nop"); return
            if op == "<":
                self._w("  slt $t2, $t0, $t1")
                self._w(f"  bne $t2, $zero, {ins.if_true}")
                self._w(f"  j {ins.if_false}"); self._w("  nop"); return
            if op == "<=":
                self._w("  slt $t2, $t1, $t0")
                self._w(f"  beq $t2, $zero, {ins.if_true}")
                self._w(f"  j {ins.if_false}"); self._w("  nop"); return
            if op == ">":
                self._w("  slt $t2, $t1, $t0")
                self._w(f"  bne $t2, $zero, {ins.if_true}")
                self._w(f"  j {ins.if_false}"); self._w("  nop"); return
            if op == ">=":
                self._w("  slt $t2, $t0, $t1")
                self._w(f"  beq $t2, $zero, {ins.if_true}")
                self._w(f"  j {ins.if_false}"); self._w("  nop"); return
            raise RuntimeError(f"CJump op desconocido: {op}")

        if isinstance(ins, Move):
            self._load_reg(frame, "$t0", ins.src)
            self._store_from_reg(frame, ins.dst, "$t0")
            return

        if isinstance(ins, BinOp):
            self._load_reg(frame, "$t0", ins.a)
            self._load_reg(frame, "$t1", ins.b)
            if ins.op == "+": self._w("  addu $t0, $t0, $t1")
            elif ins.op == "-": self._w("  subu $t0, $t0, $t1")
            elif ins.op == "*": self._w("  mul  $t0, $t0, $t1")
            elif ins.op in ("/", "%"):
                self._w("  div  $t0, $t1")
                if ins.op == "/": self._w("  mflo $t0")
                else:             self._w("  mfhi $t0")
            else:
                raise RuntimeError(f"BinOp no soportado: {ins.op}")
            self._store_from_reg(frame, ins.dst, "$t0")
            return

        if isinstance(ins, UnaryOp):
            self._load_reg(frame, "$t0", ins.a)
            if ins.op == "neg":
                self._w("  subu $t0, $zero, $t0")
                self._store_from_reg(frame, ins.dst, "$t0"); return
            if ins.op == "not":
                Lt = f"u_not_true_{id(ins)}"
                Le = f"u_not_end_{id(ins)}"
                self._w(f"  beq $t0, $zero, {Lt}")
                self._w("  li $t0, 0")
                self._w(f"  j {Le}"); self._w("  nop")
                self._lbl(Lt); self._w("  li $t0, 1")
                self._lbl(Le)
                self._store_from_reg(frame, ins.dst, "$t0"); return
            raise RuntimeError(f"Unary op no soportado: {ins.op}")

        if isinstance(ins, Cmp):
            self._load_reg(frame, "$t0", ins.a)
            if isinstance(ins.b, ConstInt):
                self._w(f"  li $t1, {ins.b.value}")
            elif isinstance(ins.b, ConstStr):
                self._w(f"  la $t1, {ins.b.label}")
            else:
                self._w(f"  lw $t1, {self._addr(frame, ins.b)}")

            L_true = f"cmp_true_{id(ins)}"
            L_end  = f"cmp_end_{id(ins)}"
            if ins.op == "==":
                self._w(f"  beq $t0, $t1, {L_true}")
            elif ins.op == "!=":
                self._w(f"  bne $t0, $t1, {L_true}")
            elif ins.op == "<":
                self._w("  slt $t2, $t0, $t1")
                self._w(f"  bne $t2, $zero, {L_true}")
            elif ins.op == "<=":
                self._w("  slt $t2, $t1, $t0")
                self._w(f"  beq $t2, $zero, {L_true}")
            elif ins.op == ">":
                self._w("  slt $t2, $t1, $t0")
                self._w(f"  bne $t2, $zero, {L_true}")
            elif ins.op == ">=":
                self._w("  slt $t2, $t0, $t1")
                self._w(f"  beq $t2, $zero, {L_true}")
            else:
                raise RuntimeError(f"Cmp op desconocido: {ins.op}")
            self._w("  li $t0, 0")
            self._w(f"  j {L_end}"); self._w("  nop")
            self._lbl(L_true); self._w("  li $t0, 1")
            self._lbl(L_end)
            self._store_from_reg(frame, ins.dst, "$t0")
            return

        if isinstance(ins, Load):
            self._load_reg(frame, "$t0", ins.base)
            self._w(f"  lw $t1, {ins.offset}($t0)")
            self._store_from_reg(frame, ins.dst, "$t1")
            return

        if isinstance(ins, Store):
            self._load_reg(frame, "$t0", ins.base)
            if isinstance(ins.src, ConstInt):
                self._w(f"  li $t1, {ins.src.value}")
            elif isinstance(ins.src, ConstStr):
                self._w(f"  la $t1, {ins.src.label}")
            else:
                self._w(f"  lw $t1, {self._addr(frame, ins.src)}")
            self._w(f"  sw $t1, {ins.offset}($t0)")
            return

        if isinstance(ins, LoadI):
            self._load_reg(frame, "$t0", ins.base)  # base
            if isinstance(ins.index, ConstInt):
                byte_off = 4 + ins.index.value * 4
                self._w(f"  lw $t1, {byte_off}($t0)")
                self._store_from_reg(frame, ins.dst, "$t1")
            else:
                self._load_reg(frame, "$t1", ins.index)   # idx
                self._w("  sll $t1, $t1, 2")             # idx*4
                self._w("  addu $t1, $t1, $t0")          # base + idx*4
                self._w("  lw $t2, 4($t1)")              # *(base + 4 + idx*4)
                self._store_from_reg(frame, ins.dst, "$t2")
            return

        if isinstance(ins, StoreI):
            self._load_reg(frame, "$t0", ins.base)
            if isinstance(ins.index, ConstInt):
                byte_off = 4 + ins.index.value * 4
                if isinstance(ins.src, ConstInt):
                    self._w(f"  li $t1, {ins.src.value}")
                elif isinstance(ins.src, ConstStr):
                    self._w(f"  la $t1, {ins.src.label}")
                else:
                    self._w(f"  lw $t1, {self._addr(frame, ins.src)}")
                self._w(f"  sw $t1, {byte_off}($t0)")
            else:
                self._load_reg(frame, "$t1", ins.index)
                self._w("  sll $t1, $t1, 2")
                self._w("  addu $t1, $t1, $t0")   # $t1 = base + idx*4
                if isinstance(ins.src, ConstInt):
                    self._w(f"  li $t2, {ins.src.value}")
                elif isinstance(ins.src, ConstStr):
                    self._w(f"  la $t2, {ins.src.label}")
                else:
                    self._w(f"  lw $t2, {self._addr(frame, ins.src)}")
                self._w("  sw $t2, 4($t1)")
            return

        if isinstance(ins, Call):
            # print -> syscalls (int=1 / string=4) + '\n' (11)
            if ins.func == "print":
                arg = ins.args[0] if len(ins.args) == 1 else None
                if isinstance(arg, ConstStr):
                    self._w(f"  la $a0, {arg.label}")
                    self._w("  li $v0, 4"); self._w("  syscall")
                    self._w("  li $a0, 10")  # '\n'
                    self._w("  li $v0, 11"); self._w("  syscall")
                else:
                    if arg is not None:
                        self._load_reg(frame, "$a0", arg)
                    else:
                        self._w("  move $a0, $zero")
                    self._w("  li $v0, 1"); self._w("  syscall")
                    self._w("  li $a0, 10")
                    self._w("  li $v0, 11"); self._w("  syscall")
                if ins.dst is not None:
                    self._w("  move $v0, $zero")
                    self._store_from_reg(frame, ins.dst, "$v0")
                return

            # malloc -> syscall 9 (sbrk)
            if ins.func == "malloc":
                if len(ins.args) != 1:
                    # si no cumple, hacemos llamada genérica
                    self._emit_generic_call(frame, ins); return
                self._load_reg(frame, "$a0", ins.args[0])
                self._w("  li $v0, 9")
                self._w("  syscall")
                if ins.dst is not None:
                    self._store_from_reg(frame, ins.dst, "$v0")
                return

            # llamada genérica: push args, jal, caller limpia
            self._emit_generic_call(frame, ins)
            return

        if isinstance(ins, Return):
            if ins.value is not None:
                self._load_reg(frame, "$v0", ins.value)
            self._emit_epilogue(lsize)
            return

        # fallback
        self._w(f"  # instr desconocida {ins}")

    def _emit_generic_call(self, frame: Frame, ins: Call):
        argc = len(ins.args)
        for a in reversed(ins.args):
            self._load_reg(frame, "$t0", a)
            self._w("  addiu $sp, $sp, -4")
            self._w("  sw $t0, 0($sp)")
        self._w(f"  jal {ins.func}")
        if argc > 0:
            self._w(f"  addiu $sp, $sp, {argc*4}")
        if ins.dst is not None:
            self._store_from_reg(frame, ins.dst, "$v0")

    # ---------- runtime auxiliar ----------
    def _emit_runtime_concat(self):
        self._w(".globl __concat")
        self._lbl("__concat")
        # prólogo
        self._w("  addiu $sp, $sp, -8")
        self._w("  sw $ra, 4($sp)")
        self._w("  sw $fp, 0($sp)")
        self._w("  addiu $fp, $sp, 8")
        # a=0($fp), b=4($fp)
        self._w("  lw $t0, 0($fp)     # a")
        self._w("  lw $t1, 4($fp)     # b")
        # len(a) -> $t2
        self._w("  move $t2, $zero")
        self._lbl("L_len_a")
        self._w("  addu $t5, $t0, $t2")
        self._w("  lbu  $t6, 0($t5)")
        self._w("  beq  $t6, $zero, L_len_a_done")
        self._w("  addiu $t2, $t2, 1")
        self._w("  j L_len_a"); self._w("  nop")
        self._lbl("L_len_a_done")
        # len(b) -> $t3
        self._w("  move $t3, $zero")
        self._lbl("L_len_b")
        self._w("  addu $t5, $t1, $t3")
        self._w("  lbu  $t6, 0($t5)")
        self._w("  beq  $t6, $zero, L_len_b_done")
        self._w("  addiu $t3, $t3, 1")
        self._w("  j L_len_b"); self._w("  nop")
        self._lbl("L_len_b_done")
        # total = lenA + lenB + 1 ; alloc
        self._w("  addu $t6, $t2, $t3")
        self._w("  addiu $a0, $t6, 1")
        self._w("  li $v0, 9")      # sbrk
        self._w("  syscall")
        self._w("  move $t4, $v0")  # dst
        # copy A
        self._w("  move $t6, $zero")
        self._lbl("L_cp_a")
        self._w("  beq $t6, $t2, L_cp_a_done")
        self._w("  addu $t5, $t0, $t6")
        self._w("  lbu $t7, 0($t5)")
        self._w("  addu $t5, $t4, $t6")
        self._w("  sb  $t7, 0($t5)")
        self._w("  addiu $t6, $t6, 1")
        self._w("  j L_cp_a"); self._w("  nop")
        self._lbl("L_cp_a_done")
        # copy B
        self._w("  move $t6, $zero")
        self._lbl("L_cp_b")
        self._w("  beq $t6, $t3, L_cp_b_done")
        self._w("  addu $t5, $t1, $t6")
        self._w("  lbu $t7, 0($t5)")
        self._w("  addu $t5, $t4, $t2")
        self._w("  addu $t5, $t5, $t6")
        self._w("  sb  $t7, 0($t5)")
        self._w("  addiu $t6, $t6, 1")
        self._w("  j L_cp_b"); self._w("  nop")
        self._lbl("L_cp_b_done")
        # NUL final
        self._w("  addu $t5, $t4, $t2")
        self._w("  addu $t5, $t5, $t3")
        self._w("  sb  $zero, 0($t5)")
        # return dst
        self._w("  move $v0, $t4")
        # epílogo
        self._w("  lw $fp, 0($sp)")
        self._w("  lw $ra, 4($sp)")
        self._w("  addiu $sp, $sp, 8")
        self._w("  jr $ra")
        self._w("  nop")

    def _emit_main_wrapper(self, entry: str):
        # Pequeño 'main' para contentar a QtSPIM/MARS
        self._w(".globl main")
        self._lbl("main")
        self._w(f"  jal {entry}")
        # salir limpiamente
        self._w("  li $v0, 10   # exit")
        self._w("  syscall")

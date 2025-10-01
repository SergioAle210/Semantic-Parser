# compiscript/codegen/x86_naive.py
from __future__ import annotations
from typing import Dict, List

from compiscript.codegen.frame import Frame
from compiscript.ir.tac import (
    IRProgram, IRFunction, Instr, Operand,
    Label, Jump, CJump, Move, BinOp, UnaryOp, Cmp, Call, Return,
    Temp, Local, Param, ConstInt, ConstStr,
    Load, Store, LoadI, StoreI
)

# Mapeo de cond a jcc
_JCC = {
    "==": "je",
    "!=": "jne",
    "<":  "jl",
    "<=": "jle",
    ">":  "jg",
    ">=": "jge",
}

class X86Naive:
    """
    Generador x86 (Intel/NASM). Convención cdecl:
      - parámetros por stack, derecha→izquierda
      - retorno en EAX
      - caller limpia el stack de argumentos
    Emite 'printf' para print enteros/strings.
    """
    def __init__(self):
        self.lines: List[str] = []
        # mapeo de temporales a slots de stack (como locales)
        self.temp_slots: Dict[str, int] = {}

    def compile(self, prog: IRProgram) -> str:
        self.lines = []
        self._emit_header()
        self._emit_data(prog)
        self._emit_text(prog)
        return "\n".join(self.lines)

    # ---------------- secciones ----------------
    def _emit_header(self):
        self.lines.append("; Compiscript x86 (NASM, Intel syntax)")
        self.lines.append("extern printf")
        self.lines.append("extern malloc")
        self.lines.append("extern __concat")
        self.lines.append("section .data")

    def _emit_data(self, prog: IRProgram):
        # formatos para print
        self.lines.append("fmt_int db \"%d\", 10, 0")
        self.lines.append("fmt_str db \"%s\", 10, 0")
        # strings del programa
        for lab, b in prog.strings.items():
            self.lines.append(f"{lab} db " + ", ".join(str(x) for x in b))
        self.lines.append("section .text")
        # exportar main si existe
        if prog.entry:
            self.lines.append(f"global {prog.entry}")

    def _emit_text(self, prog: IRProgram):
        for fname, fn in prog.functions.items():
            self._emit_function(fn, is_entry=(prog.entry == fname))

    # ---------------- utils ----------------
    def _w(self, s: str): self.lines.append(s)
    def _lbl(self, s: str): self._w(f"{s}:")

    # obtiene dirección (operando) en ASM
    def _mem_operand(self, frame: Frame, op: Operand) -> str:
        if isinstance(op, Local):
            off = frame.get_local_disp(op.name)
            if off is None:
                off = frame.ensure_local(op.name)
            return f"[ebp-{off}]"
        if isinstance(op, Param):
            off = frame.get_param_disp(op.name)
            if off is None:
                raise RuntimeError(f"Param sin offset: {op.name}")
            return f"[ebp+{off}]"
        if isinstance(op, Temp):
            off = self.temp_slots.get(op.name)
            if off is None:
                # asigna slot nuevo
                off = frame.ensure_local(f"__t_{op.name}")
                self.temp_slots[op.name] = off
            return f"[ebp-{off}]"
        raise RuntimeError(f"Operando no direccionable en memoria: {op}")

    def _load_eax(self, frame: Frame, op: Operand):
        if isinstance(op, ConstInt):
            self._w(f"    mov eax, {op.value}")
        elif isinstance(op, ConstStr):
            self._w(f"    mov eax, {op.label}")
        else:
            self._w(f"    mov eax, dword {self._mem_operand(frame, op)}")

    def _load_ebx(self, frame: Frame, op: Operand):
        if isinstance(op, ConstInt):
            self._w(f"    mov ebx, {op.value}")
        elif isinstance(op, ConstStr):
            self._w(f"    mov ebx, {op.label}")
        else:
            self._w(f"    mov ebx, dword {self._mem_operand(frame, op)}")

    def _store_from_eax(self, frame: Frame, dst: Operand):
        if isinstance(dst, (Local, Param, Temp)):
            self._w(f"    mov dword {self._mem_operand(frame, dst)}, eax")
        else:
            raise RuntimeError("Destino no soportado para store")

    # ---------------- función ----------------
    def _emit_function(self, fn: IRFunction, is_entry: bool):
        self.temp_slots.clear()
        frame = fn.frame or Frame(fn.name, fn.params)

        # Primera pasada: asignar slots a todos los Temp que aparezcan
        for ins in fn.body:
            if isinstance(ins, (Move, BinOp, UnaryOp, Cmp, Call, Return, CJump, Load, Store)):
                ops = []
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
                for o in ops:
                    if isinstance(o, Temp):
                        self._mem_operand(frame, o)  # fuerza asignación

        # prólogo
        self._lbl(fn.name)
        self._w("    push ebp")
        self._w("    mov ebp, esp")
        lsize = frame.local_size()
        if lsize > 0:
            self._w(f"    sub esp, {lsize}")

        # cuerpo
        for ins in fn.body:
            self._emit_instr(frame, ins)

        # Epílogo solo si el último ins (no etiqueta) NO es Return
        last = None
        for ins in reversed(fn.body):
            if not isinstance(ins, Label):
                last = ins
                break
        if not isinstance(last, Return):
            self._emit_epilogue(frame)

    def _emit_epilogue(self, frame: Frame, ensure: bool = False):
        # epílogo estándar
        self._w("    mov esp, ebp")
        self._w("    pop ebp")
        self._w("    ret")

    # ---------------- instrucciones ----------------
    def _emit_instr(self, frame: Frame, ins: Instr):
        if isinstance(ins, Label):
            self._lbl(ins.name)
            return
        if isinstance(ins, Jump):
            self._w(f"    jmp {ins.target}")
            return
        if isinstance(ins, CJump):
            self._load_eax(frame, ins.a)
            if isinstance(ins.b, ConstInt):
                self._w(f"    cmp eax, {ins.b.value}")
            elif isinstance(ins.b, ConstStr):
                self._w(f"    cmp eax, {ins.b.label}")
            else:
                self._w(f"    cmp eax, dword {self._mem_operand(frame, ins.b)}")
            jcc = _JCC.get(ins.op)
            if not jcc:
                raise RuntimeError(f"CJump op desconocido: {ins.op}")
            self._w(f"    {jcc} {ins.if_true}")
            self._w(f"    jmp {ins.if_false}")
            return
        if isinstance(ins, Move):
            # dst = src
            self._load_eax(frame, ins.src)
            self._store_from_eax(frame, ins.dst)
            return
        if isinstance(ins, BinOp):
            # dst = a op b
            self._load_eax(frame, ins.a)
            if ins.op in ("+","-","*"):
                self._load_ebx(frame, ins.b)
                if ins.op == "+": self._w("    add eax, ebx")
                if ins.op == "-": self._w("    sub eax, ebx")
                if ins.op == "*": self._w("    imul eax, ebx")
                self._store_from_eax(frame, ins.dst)
                return
            if ins.op in ("/","%"):
                # EAX = a; EDX:EAX / ebx
                self._load_ebx(frame, ins.b)
                self._w("    cdq")
                self._w("    idiv ebx")
                if ins.op == "/":
                    self._store_from_eax(frame, ins.dst)  # cociente en eax
                else:
                    self._w("    mov eax, edx")          # residuo en edx
                    self._store_from_eax(frame, ins.dst)
                return
            raise RuntimeError(f"BinOp no soportado: {ins.op}")
        if isinstance(ins, UnaryOp):
            self._load_eax(frame, ins.a)
            if ins.op == "neg":
                self._w("    neg eax")
                self._store_from_eax(frame, ins.dst)
                return
            if ins.op == "not":
                self._w("    cmp eax, 0")
                self._w("    sete al")
                self._w("    movzx eax, al")
                self._store_from_eax(frame, ins.dst)
                return
            raise RuntimeError(f"Unary op no soportado: {ins.op}")
        if isinstance(ins, Cmp):
            # dst = (a op b) ? 1 : 0
            self._load_eax(frame, ins.a)
            if isinstance(ins.b, ConstInt):
                self._w(f"    cmp eax, {ins.b.value}")
            elif isinstance(ins.b, ConstStr):
                self._w(f"    cmp eax, {ins.b.label}")
            else:
                self._w(f"    cmp eax, dword {self._mem_operand(frame, ins.b)}")
            jcc = _JCC.get(ins.op)
            if not jcc:
                raise RuntimeError(f"Cmp op desconocido: {ins.op}")
            L_true = f"cmp_true_{id(ins)}"
            L_end  = f"cmp_end_{id(ins)}"
            self._w(f"    {jcc} {L_true}")
            # false -> 0
            self._w("    mov eax, 0")
            self._w(f"    jmp {L_end}")
            # true -> 1
            self._lbl(L_true)
            self._w("    mov eax, 1")
            self._lbl(L_end)
            self._store_from_eax(frame, ins.dst)
            return
        if isinstance(ins, Load):
            # dst = *(base + offset)
            self._load_eax(frame, ins.base)
            self._w(f"    mov ebx, dword [eax+{ins.offset}]")
            self._w(f"    mov dword {self._mem_operand(frame, ins.dst)}, ebx")
            return
        if isinstance(ins, Store):
            # *(base + offset) = src
            self._load_eax(frame, ins.base)
            if isinstance(ins.src, ConstInt):
                self._w(f"    mov dword [eax+{ins.offset}], {ins.src.value}")
            elif isinstance(ins.src, ConstStr):
                self._w(f"    mov dword [eax+{ins.offset}], {ins.src.label}")
            else:
                self._load_ebx(frame, ins.src)
                self._w(f"    mov dword [eax+{ins.offset}], ebx")
            return
        if isinstance(ins, LoadI):
            # eax = base; ebx = index
            self._load_eax(frame, ins.base)
            # index a EBX
            if isinstance(ins.index, ConstInt):
                # [eax + 4 + idx*4]
                byte_off = 4 + ins.index.value * 4
                self._w(f"    mov ebx, dword [eax+{byte_off}]")
            else:
                self._load_ebx(frame, ins.index)
                self._w("    mov ecx, dword [eax + ebx*4 + 4]")
                self._w("    mov ebx, ecx")
            self._w(f"    mov dword {self._mem_operand(frame, ins.dst)}, ebx")
            return

        if isinstance(ins, StoreI):
            # eax = base; escribir src en [eax + 4 + idx*4]
            self._load_eax(frame, ins.base)
            if isinstance(ins.index, ConstInt):
                byte_off = 4 + ins.index.value * 4
                if isinstance(ins.src, ConstInt):
                    self._w(f"    mov dword [eax+{byte_off}], {ins.src.value}")
                elif isinstance(ins.src, ConstStr):
                    self._w(f"    mov dword [eax+{byte_off}], {ins.src.label}")
                else:
                    self._load_ebx(frame, ins.src)
                    self._w(f"    mov dword [eax+{byte_off}], ebx")
            else:
                self._load_ebx(frame, ins.index)
                if isinstance(ins.src, ConstInt):
                    self._w(f"    mov ecx, {ins.src.value}")
                elif isinstance(ins.src, ConstStr):
                    self._w(f"    mov ecx, {ins.src.label}")
                else:
                    self._load_ebx(frame, ins.src)   # src -> ebx
                    self._w("    mov ecx, ebx")
                # [eax + ebx*4 + 4] = ecx
                self._w("    mov dword [eax + ebx*4 + 4], ecx")
            return
        if isinstance(ins, Call):
            # caso especial: print
            if ins.func == "print":
                # un argumento
                if len(ins.args) != 1:
                    pass
                else:
                    arg = ins.args[0]
                    if isinstance(arg, ConstStr):
                        # printf("%s\n", arg)
                        self._w(f"    push {arg.label}")
                        self._w("    push fmt_str")
                        self._w("    call printf")
                        self._w("    add esp, 8")
                    else:
                        # entero
                        self._load_eax(frame, arg)
                        self._w("    push eax")
                        self._w("    push fmt_int")
                        self._w("    call printf")
                        self._w("    add esp, 8")
                # retorno de print es void
                if ins.dst is not None:
                    self._w("    mov eax, 0")
                    self._store_from_eax(frame, ins.dst)
                return

            # llamada genérica: push args (derecha->izquierda)
            for a in reversed(ins.args):
                if isinstance(a, ConstInt):
                    self._w(f"    push {a.value}")
                elif isinstance(a, ConstStr):
                    self._w(f"    push {a.label}")
                else:
                    self._load_eax(frame, a)
                    self._w("    push eax")
            self._w(f"    call {ins.func}")
            if len(ins.args) > 0:
                self._w(f"    add esp, {4*len(ins.args)}")
            if ins.dst is not None:
                self._store_from_eax(frame, ins.dst)
            return
        if isinstance(ins, Return):
            if ins.value is not None:
                self._load_eax(frame, ins.value)
            self._emit_epilogue(frame)
            return

        # fallback:
        self._w(f"    ; instr desconocida {ins}")

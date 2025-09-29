# compiscript/codegen/irgen.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from compiscript.codegen.temp_pool import TempPool
from compiscript.codegen.frame import Frame
from compiscript.ir.tac import (
    IRProgram, IRFunction,
    Instr, Operand,
    Temp, Local, Param, ConstInt, ConstStr,
    Label, Jump, CJump, Move, BinOp, UnaryOp, Cmp, Call, Return
)

# Utilidad para nombres de etiquetas
class LabelGen:
    def __init__(self, prefix: str = "L"):
        self.prefix = prefix
        self.n = 0
    def new(self) -> str:
        s = f"{self.prefix}{self.n}"
        self.n += 1
        return s

class IRGen:
    """
    Generador de IR desde el AST de tu proyecto.
    Cubre Program, FunctionDecl, Block, VarDecl/ConstDecl, Assign, If, While, Return,
    ExprStmt, Identifier, Literal, Unary, Binary, Call.
    """
    def __init__(self):
        self.prog = IRProgram()
        self.tpool = TempPool()
        self.lgen = LabelGen()
        self.current_fn: Optional[IRFunction] = None
        self.frame: Optional[Frame] = None
        # pila de scopes {name: Operand(Local|Param)}
        self.scopes: List[Dict[str, Operand]] = []

    # ------------- helpers de scopes -------------
    def _push_scope(self):
        self.scopes.append({})
    def _pop_scope(self):
        self.scopes.pop()
    def _bind(self, name: str, op: Operand):
        assert self.scopes, "No hay scope activo"
        self.scopes[-1][name] = op
    def _lookup(self, name: str) -> Optional[Operand]:
        for m in reversed(self.scopes):
            if name in m:
                return m[name]
        # Si no se encuentra, intentamos param por nombre
        if self.current_fn and name in self.current_fn.params:
            return Param(name)
        return None

    # ------------- API principal -------------
    def build(self, ast_root) -> IRProgram:
        """
        Recorre el AST y llena self.prog con funciones y strings.
        Espera que el código defina una función 'main' como punto de entrada.
        """
        self._visit(ast_root)
        if self.prog.entry is None and "main" in self.prog.functions:
            self.prog.entry = "main"
        return self.prog

    # ------------- despacho genérico -------------
    def _visit(self, n):
        if n is None:
            return None
        k = n.__class__.__name__
        m = getattr(self, f"_visit_{k}", None)
        if m is not None:
            return m(n)
        # nodos que no soportamos aún:
        unsupported = {
            "ClassDecl","MemberAccess","IndexAccess","ArrayLiteral",
            "Foreach","Switch","SwitchCase","TryCatch","This","For","Ternary"
        }
        if k in unsupported:
            raise NotImplementedError(f"IRGen: nodo {k} aún no soportado")
        raise NotImplementedError(f"IRGen: nodo desconocido {k}")

    # ---------------- Program / FunctionDecl / Block ----------------
    def _visit_Program(self, n):
        i = 0
        while i < len(n.statements):
            self._visit(n.statements[i])
            i += 1

    def _visit_FunctionDecl(self, n):
        fname = n.name
        params = [p.name for p in (getattr(n, "params", []) or [])]
        fn = IRFunction(name=fname, params=params)
        self.prog.functions[fname] = fn
        if fname == "main":
            self.prog.entry = "main"

        # prepara frame y scopes
        prev_fn, prev_frame = self.current_fn, self.frame
        self.current_fn, self.frame = fn, Frame(fname, params)
        self.scopes.clear()
        self._push_scope()
        # bind de parámetros en scope 0:
        for p in params:
            self._bind(p, Param(p))

        # cuerpo
        self._visit(n.body)

        # cerrar
        self._pop_scope()
        fn.frame = self.frame
        self.current_fn, self.frame = prev_fn, prev_frame

    def _visit_Block(self, n):
        self._push_scope()
        i = 0
        while i < len(n.statements):
            self._visit(n.statements[i])
            i += 1
        self._pop_scope()

    # ---------------- declaraciones ----------------
    def _visit_VarDecl(self, n):
        name = n.name
        # reserva slot local
        self.frame.ensure_local(name)
        if name not in self.current_fn.locals:
            self.current_fn.locals.append(name)
        loc = Local(name)
        self._bind(name, loc)
        # init
        if getattr(n, "init", None) is not None:
            val = self._eval_expr(n.init)
            self._emit(Move(loc, val))

    def _visit_ConstDecl(self, n):
        # tratamos const igual que local (solo IR); checker ya impide reasignación
        self._visit_VarDecl(n)

    # ---------------- statements ----------------
    def _visit_ExprStmt(self, n):
        self._eval_expr(n.expr)  # si es call, se emite; si no, se ignora resultado

    def _visit_Assign(self, n):
        # solo soportamos target = Identifier
        tgt = n.target
        if tgt.__class__.__name__ != "Identifier":
            raise NotImplementedError("Assign: solo Identifier como LHS por ahora")
        op = self._lookup(tgt.name)
        if op is None:
            raise RuntimeError(f"Variable no encontrada: {tgt.name}")
        val = self._eval_expr(n.value)
        self._emit(Move(op, val))

    def _visit_Return(self, n):
        if getattr(n, "value", None) is None:
            self._emit(Return(None))
        else:
            v = self._eval_expr(n.value)
            self._emit(Return(v))

    def _visit_If(self, n):
        L_then = self.lgen.new()
        L_end  = self.lgen.new()
        if getattr(n, "else_blk", None) is None:
            # if (cond) then { ... }
            self._emit_cond_jump(n.cond, L_then, L_end)
            self._emit(Label(L_then))
            self._visit(n.then_blk)
            self._emit(Label(L_end))
        else:
            L_else = self.lgen.new()
            self._emit_cond_jump(n.cond, L_then, L_else)
            self._emit(Label(L_then))
            self._visit(n.then_blk)
            self._emit(Jump(L_end))
            self._emit(Label(L_else))
            self._visit(n.else_blk)
            self._emit(Label(L_end))

    def _visit_While(self, n):
        L_cond = self.lgen.new()
        L_body = self.lgen.new()
        L_end  = self.lgen.new()
        self._emit(Label(L_cond))
        self._emit_cond_jump(n.cond, L_body, L_end)
        self._emit(Label(L_body))
        self._visit(n.body)
        self._emit(Jump(L_cond))
        self._emit(Label(L_end))

    # ---------------- expresiones ----------------
    def _eval_expr(self, e) -> Operand:
        k = e.__class__.__name__
        meth = getattr(self, f"_expr_{k}", None)
        if meth is None:
            raise NotImplementedError(f"Expr no soportada: {k}")
        return meth(e)

    def _expr_Identifier(self, e) -> Operand:
        op = self._lookup(e.name)
        if op is None:
            # podría ser un nombre de función usado como valor → no soportado
            raise RuntimeError(f"Identificador no encontrado: {e.name}")
        return op

    def _expr_Literal(self, e) -> Operand:
        if e.kind == "int":
            return ConstInt(int(e.value))
        if e.kind == "boolean":
            return ConstInt(1 if bool(e.value) else 0)
        if e.kind == "string":
            # registrar string en la tabla global
            label = self._new_string_label(str(e.value))
            return ConstStr(label)
        if e.kind == "null":
            return ConstInt(0)
        raise NotImplementedError(f"Literal '{e.kind}' no soportado")

    def _expr_Unary(self, e) -> Operand:
        v = self._eval_expr(e.expr)
        dst = Temp(self.tpool.new())
        if e.op == "-":
            self._emit(UnaryOp("neg", dst, v))
            return dst
        if e.op == "!":
            # dst = (v == 0) ? 1 : 0
            self._emit(Cmp("==", dst, v, ConstInt(0)))
            return dst
        raise NotImplementedError(f"Unary op {e.op} no soportado")

    def _expr_Binary(self, e) -> Operand:
        # aritméticos y relacionales
        if e.op in ("+","-","*","/","%"):
            a = self._eval_expr(e.left)
            b = self._eval_expr(e.right)
            dst = Temp(self.tpool.new())
            self._emit(BinOp(e.op, dst, a, b))
            return dst
        if e.op in ("==","!=", "<","<=",">",">="):
            a = self._eval_expr(e.left)
            b = self._eval_expr(e.right)
            dst = Temp(self.tpool.new())
            self._emit(Cmp(e.op, dst, a, b))
            return dst
        if e.op in ("&&","||"):
            # Short-circuit a boolean 0/1
            L_true = self.lgen.new()
            L_false = self.lgen.new()
            L_end = self.lgen.new()
            dst = Temp(self.tpool.new())
            # dst = 0
            self._emit(Move(dst, ConstInt(0)))
            if e.op == "&&":
                # if !left goto false; if !right goto false; dst=1; goto end; false:
                self._emit_cond_jump(self._mk_not(e.left), L_false, L_true)  # invertido
                self._emit(Label(L_true))
                self._emit_cond_jump(self._mk_not(e.right), L_false, L_end)
            else:
                # '||' : if left goto end (dst=1); if right goto end (dst=1); goto false
                self._emit_cond_jump(e.left, L_end, L_false)
                self._emit(Label(L_false))
                self._emit_cond_jump(e.right, L_end, L_false)
            # set dst=1 en la rama true de salida
            self._emit(Label(L_end))
            self._emit(Move(dst, ConstInt(1)))
            # false:
            L_tail = self.lgen.new()
            self._emit(Jump(L_tail))
            self._emit(Label(L_false))
            # dst ya es 0
            self._emit(Label(L_tail))
            return dst
        raise NotImplementedError(f"Binary op {e.op} no soportado")

    def _mk_not(self, expr):
        # wrapper pequeño: !(expr)
        class _Not:
            __slots__ = ("expr",)
            def __init__(self, expr): self.expr = expr
        return _Not(expr)

    def _expr_Call(self, e) -> Operand:
        args = []
        i = 0
        while i < len(e.args):
            args.append(self._eval_expr(e.args[i]))
            i += 1
        # ¿retorno?
        dst = Temp(self.tpool.new())
        self._emit(Call(dst, self._callee_name(e.callee), args))
        return dst

    def _callee_name(self, callee_node) -> str:
        cn = callee_node.__class__.__name__
        if cn == "Identifier":
            return callee_node.name
        raise NotImplementedError("Solo llamadas a identificadores simples (func)")

    # ---------------- condicionales en saltos ----------------
    def _emit_cond_jump(self, cond_expr, L_true: str, L_false: str):
        # cond genérica: si relacional → CJump directo; en otro caso: cond != 0
        # casos especiales: _Not wrapper (para &&/||)
        if cond_expr.__class__.__name__ == "_Not":
            val = self._eval_expr(cond_expr.expr)
            self._emit(CJump("==", val, ConstInt(0), L_true, L_false))
            return
        # relacionales directos
        if cond_expr.__class__.__name__ == "Binary" and cond_expr.op in ("==","!=", "<","<=",">",">="):
            a = self._eval_expr(cond_expr.left)
            b = self._eval_expr(cond_expr.right)
            self._emit(CJump(cond_expr.op, a, b, L_true, L_false))
            return
        # default: evaluar a entero y comparar != 0
        v = self._eval_expr(cond_expr)
        self._emit(CJump("!=", v, ConstInt(0), L_true, L_false))

    # ---------------- util ----------------
    def _emit(self, instr: Instr):
        assert self.current_fn is not None
        self.current_fn.body.append(instr)

    def _new_string_label(self, text: str) -> str:
        # deduplicación simple: si ya existe, devuelve el label existente
        for k, v in self.prog.strings.items():
            try:
                if v.decode("utf-8") == text:
                    return k
            except Exception:
                pass
        label = f"str{len(self.prog.strings)}"
        self.prog.strings[label] = text.encode("utf-8") + b"\x00"
        return label

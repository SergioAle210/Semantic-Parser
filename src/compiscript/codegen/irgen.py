# compiscript/codegen/irgen.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from compiscript.codegen.temp_pool import TempPool
from compiscript.codegen.frame import Frame
from compiscript.ir.tac import (
    IRProgram, IRFunction,
    Instr, Operand,
    Temp, Local, Param, ConstInt, ConstStr,
    Label, Jump, CJump, Move, BinOp, UnaryOp, Cmp, Call, Return,
    Load, Store, LoadI, StoreI
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
    Ahora cubre:
      - Program, FunctionDecl, Block
      - VarDecl/ConstDecl, Assign
      - If, While, Return, ExprStmt
      - Binary, Unary, Identifier, Literal, Call
      - ClassDecl (métodos y campos), This, MemberAccess (get/set)
      - Switch/SwitchCase, Foreach (sobre ArrayLiteral), TryCatch (compila solo try)
    """
    def __init__(self):
        self.prog = IRProgram()
        self.tpool = TempPool()
        self.lgen = LabelGen()

        self.current_fn: Optional[IRFunction] = None
        self.frame: Optional[Frame] = None

        # pila de scopes {name: Operand(Local|Param)}
        self.scopes: List[Dict[str, Operand]] = []
        # pila de tipos de variables {name: class_name or None}
        self.type_scopes: List[Dict[str, Optional[str]]] = []

        # info de clases
        # class_name -> { field_name: offset_en_bytes }
        self.class_field_off: Dict[str, Dict[str, int]] = {}
        # (class_name, method_name) -> ir_name 'Class__method'
        self.method_irname: Dict[Tuple[str, str], str] = {}
        # clase activa (dentro de método)
        self.cur_class: Optional[str] = None

        # pila de break/continue (pares de labels)
        self.break_stack: List[str] = []
        self.cont_stack: List[str] = []

        # herencia: clase -> base
        self.class_base: Dict[str, Optional[str]] = {}

        # función sintética para sentencias top-level
        self.toplevel: Optional[IRFunction] = None


    # ------------- helpers de scopes -------------
    def _push_scope(self):
        self.scopes.append({})
        self.type_scopes.append({})
    def _pop_scope(self):
        self.scopes.pop()
        self.type_scopes.pop()
    def _bind(self, name: str, op: Operand):
        assert self.scopes, "No hay scope activo"
        self.scopes[-1][name] = op
    def _bind_type(self, name: str, cls: Optional[str]):
        assert self.type_scopes, "No hay scope activo"
        self.type_scopes[-1][name] = cls
    def _lookup(self, name: str) -> Optional[Operand]:
        for m in reversed(self.scopes):
            if name in m:
                return m[name]
        if self.current_fn and name in self.current_fn.params:
            return Param(name)
        return None
    def _lookup_type(self, name: str) -> Optional[str]:
        for m in reversed(self.type_scopes):
            if name in m:
                return m[name]
        return None
    
    def _release_if_temp(self, op: Operand):
        if isinstance(op, Temp):
            self.tpool.release(op.name)

    def _loop_push(self, L_continue: str, L_break: str):
        self.cont_stack.append(L_continue)
        self.break_stack.append(L_break)

    def _loop_pop(self):
        self.cont_stack.pop()
        self.break_stack.pop()

    def _current_break(self) -> Optional[str]:
        return self.break_stack[-1] if self.break_stack else None

    def _current_continue(self) -> Optional[str]:
        return self.cont_stack[-1] if self.cont_stack else None

    def _ensure_toplevel(self):
        """Crea (una vez) la función sintética __toplevel para compilar sentencias globales."""
        if self.toplevel is not None and self.current_fn is self.toplevel:
            return
        if self.toplevel is None:
            fn = IRFunction(name="__toplevel", params=[])
            self.prog.functions["__toplevel"] = fn
            self.toplevel = fn
        # activar contexto de compilación del toplevel
        self.current_fn = self.toplevel
        self.frame = Frame(self.toplevel.name, [])
        # scopes frescos para el toplevel (no limpiar los ya existentes si venimos de otro lado)
        self.scopes = []
        self.type_scopes = []
        self._push_scope()


    # ------------- API principal -------------
    def build(self, ast_root) -> IRProgram:
        """
        Recorre el AST y llena self.prog con funciones y strings.
        Espera que el código defina una función 'main' como punto de entrada.
        """
        self._visit(ast_root)
        if self.prog.entry is None:
            if "main" in self.prog.functions:
                self.prog.entry = "main"
            elif self.toplevel is not None:
                self.prog.entry = self.toplevel.name
        return self.prog

    # ------------- despacho genérico -------------
    def _visit(self, n):
        if n is None:
            return None
        k = n.__class__.__name__
        m = getattr(self, f"_visit_{k}", None)
        if m is not None:
            return m(n)
        raise NotImplementedError(f"IRGen: nodo {k} aún no soportado")

    # ---------------- Program / FunctionDecl / Block ----------------
    def _visit_Program(self, n):
        i = 0
        while i < len(n.statements):
            s = n.statements[i]
            k = s.__class__.__name__
            if k in ("FunctionDecl", "ClassDecl"):
                self._visit(s)
            else:
                self._ensure_toplevel()
                self._visit(s)
            i += 1
        # cerrar frame del toplevel si existe
        if self.toplevel is not None and self.toplevel.frame is None:
            self.toplevel.frame = self.frame

    def _visit_FunctionDecl(self, n):
        fname = n.name
        params = [p.name for p in (getattr(n, "params", []) or [])]
        fn = IRFunction(name=fname, params=params)
        self.prog.functions[fname] = fn
        if fname == "main":
            self.prog.entry = "main"

        # guardar contexto actual
        prev_fn, prev_frame, prev_class = self.current_fn, self.frame, self.cur_class
        prev_scopes, prev_types = self.scopes, self.type_scopes

        # preparar contexto de la función
        self.current_fn, self.frame = fn, Frame(fname, params)
        self.cur_class = None
        self.scopes = []
        self.type_scopes = []
        self._push_scope()
        for p in params:
            self._bind(p, Param(p))
            self._bind_type(p, None)

        # cuerpo
        self._visit(n.body)

        # cerrar y restaurar
        self._pop_scope()
        fn.frame = self.frame
        self.current_fn, self.frame, self.cur_class = prev_fn, prev_frame, prev_class
        self.scopes, self.type_scopes = prev_scopes, prev_types

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
        self._bind_type(name, None)

        # init
        if getattr(n, "init", None) is not None:
            # Si es constructor Clase(...), rastrear el tipo
            is_ctor = False
            ctor_class: Optional[str] = None
            if n.init.__class__.__name__ == "Call":
                callee = n.init.callee
                if callee.__class__.__name__ == "Identifier":
                    cname = callee.name
                    if cname in self.class_field_off:
                        is_ctor = True
                        ctor_class = cname
            val = self._eval_expr(n.init)
            self._emit(Move(loc, val))
            if is_ctor and ctor_class:
                self._bind_type(name, ctor_class)

    def _visit_ConstDecl(self, n):
        # tratamos const igual que local (solo IR); checker ya impide reasignación
        self._visit_VarDecl(n)

    # ---------------- statements ----------------
    def _visit_ExprStmt(self, n):
        self._eval_expr(n.expr)

    def _visit_Assign(self, n):
        tgt = n.target
        k = tgt.__class__.__name__
        if k == "Identifier":
            op = self._lookup(tgt.name)
            if op is None:
                raise RuntimeError(f"Variable no encontrada: {tgt.name}")
            # rastreo de tipo por asignación con constructor
            ctor_class: Optional[str] = None
            if n.value.__class__.__name__ == "Call":
                callee = n.value.callee
                if callee.__class__.__name__ == "Identifier":
                    if callee.name in self.class_field_off:
                        ctor_class = callee.name
            val = self._eval_expr(n.value)
            self._emit(Move(op, val))
            if ctor_class is not None:
                self._bind_type(tgt.name, ctor_class)
            return

        if k == "MemberAccess":
            base_op, cls, field = self._resolve_member_target(tgt)
            offset = self.class_field_off[cls][field]
            src = self._eval_expr(n.value)
            self._emit(Store(base_op, offset, src))
            return

        if k == "IndexAccess":
            base = self._eval_expr(tgt.obj)
            idx  = self._eval_expr(tgt.index)
            src  = self._eval_expr(n.value)
            self._emit(StoreI(base, idx, src))
            # reciclar
            self._release_if_temp(base); self._release_if_temp(idx); self._release_if_temp(src)
            return


        raise NotImplementedError("Assign: solo Identifier, MemberAccess y IndexAccess soportados")

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
        self._loop_push(L_cond, L_end)
        self._emit(Label(L_body))
        self._visit(n.body)
        self._emit(Jump(L_cond))
        self._loop_pop()
        self._emit(Label(L_end))

    def _visit_DoWhile(self, n):
        L_cond = self.lgen.new()
        L_body = self.lgen.new()
        L_end  = self.lgen.new()
        self._emit(Label(L_body))
        self._loop_push(L_cond, L_end)
        self._visit(n.body)
        self._loop_pop()
        self._emit(Label(L_cond))
        self._emit_cond_jump(n.cond, L_body, L_end)
        self._emit(Label(L_end))


    def _visit_Switch(self, n):
        disc = self._eval_expr(n.expr)
        cases = getattr(n, "cases", []) or []
        has_default = getattr(n, "default_block", None) is not None
        L_end = self.lgen.new()
        labels = [self.lgen.new() for _ in cases]
        L_default = self.lgen.new() if has_default else L_end

        # cadena de comparaciones
        next_label = L_default
        for i, c in enumerate(cases):
            L_case = labels[i]
            L_next = labels[i+1] if i+1 < len(cases) else L_default
            cv = self._eval_expr(c.expr)
            self._emit(CJump("==", disc, cv, L_case, L_next))
            self._release_if_temp(cv)

        # compilar casos (fallthrough por omisión)
        self._loop_push(None, L_end)  # sólo break válido
        for i, c in enumerate(cases):
            self._emit(Label(labels[i]))
            self._visit(c.block)
            # sin salto al final: fallthrough si no hay break
        if has_default:
            self._emit(Label(L_default))
            self._visit(n.default_block)
        self._loop_pop()

        self._emit(Label(L_end))
        self._release_if_temp(disc)


    def _visit_Foreach(self, n):
        # variable del foreach
        var_name = n.var_name
        self._push_scope()
        self.frame.ensure_local(var_name)
        if var_name not in self.current_fn.locals:
            self.current_fn.locals.append(var_name)
        loc_var = Local(var_name)
        self._bind(var_name, loc_var)
        self._bind_type(var_name, None)

        arr = self._eval_expr(n.iterable)           # puntero al arreglo
        length = Temp(self.tpool.new())
        self._emit(Load(length, arr, 0))            # length = *(arr + 0)

        idx = Temp(self.tpool.new())
        self._emit(Move(idx, ConstInt(0)))

        L_cond = self.lgen.new()
        L_body = self.lgen.new()
        L_end  = self.lgen.new()

        self._emit(Label(L_cond))
        self._emit(CJump("<", idx, length, L_body, L_end))

        # cuerpo
        self._loop_push(L_cond, L_end)
        self._emit(Label(L_body))
        cur = Temp(self.tpool.new())
        self._emit(LoadI(cur, arr, idx))           # cur = arr[idx]
        self._emit(Move(loc_var, cur))
        self._release_if_temp(cur)
        self._visit(n.body)
        # idx++
        one = ConstInt(1)
        nxt = Temp(self.tpool.new())
        self._emit(BinOp("+", nxt, idx, one))
        self._emit(Move(idx, nxt))
        self._release_if_temp(nxt)
        self._emit(Jump(L_cond))
        self._loop_pop()

        self._emit(Label(L_end))
        # limpiar
        self._release_if_temp(arr); self._release_if_temp(length); self._release_if_temp(idx)
        self._pop_scope()


    def _visit_For(self, n):
        # init
        if n.init is not None:
            self._visit(n.init)
        L_cond = self.lgen.new()
        L_body = self.lgen.new()
        L_update = self.lgen.new()
        L_end = self.lgen.new()

        self._emit(Label(L_cond))
        if n.cond is not None:
            self._emit_cond_jump(n.cond, L_body, L_end)
        else:
            # for(;;) -> siempre true
            self._emit(Jump(L_body))

        self._loop_push(L_update, L_end)
        self._emit(Label(L_body))
        self._visit(n.body)
        self._emit(Label(L_update))
        if n.update is not None:
            self._visit(n.update)
        self._emit(Jump(L_cond))
        self._loop_pop()
        self._emit(Label(L_end))


    def _visit_TryCatch(self, n):
        # Sin runtime de excepciones: compilar solo el try
        # Creamos el scope del catch (y variable) para coincidir con checker
        self._push_scope()
        # err_name es la variable del catch; la declaramos pero NO se usa
        err_name = getattr(n, "err_name", None)
        if err_name:
            self.frame.ensure_local(err_name)
            if err_name not in self.current_fn.locals:
                self.current_fn.locals.append(err_name)
            self._bind(err_name, Local(err_name))
            self._bind_type(err_name, None)
        self._visit(n.try_block)
        self._pop_scope()

    def _visit_ClassDecl(self, n):
        cname = n.name
        base = getattr(n, "base_name", None)
        self.class_base[cname] = base

        # 1) layout de campos: incluir primero los de la base (si hay)
        base_fields = []
        if base and base in self.class_field_off:
            # reconstruir la lista de campos de la base a partir del mapa
            # (orden por offset)
            base_map = self.class_field_off[base]
            base_fields = [k for k,_ in sorted(base_map.items(), key=lambda kv: kv[1])]

        own_fields: List[str] = []
        i = 0
        while i < len(n.members):
            m = n.members[i]
            if m.__class__.__name__ in ("VarDecl", "ConstDecl"):
                own_fields.append(m.name)
            i += 1

        fields = base_fields + own_fields
        offmap: Dict[str, int] = {}
        off = 0
        for f in fields:
            offmap[f] = off
            off += 4
        self.class_field_off[cname] = offmap

        # 2) compilar métodos como funciones con primer param 'this'
        i = 0
        while i < len(n.members):
            m = n.members[i]
            if m.__class__.__name__ == "FunctionDecl":
                mname = m.name
                ir_name = f"{cname}__{mname}"
                self.method_irname[(cname, mname)] = ir_name
                self._compile_method(cname, ir_name, m)
            i += 1

    def _visit_Break(self, n):
        L = self._current_break()
        if L is None:
            # fuera de bucle/switch: ignoramos en CI
            return
        self._emit(Jump(L))

    def _visit_Continue(self, n):
        L = self._current_continue()
        if L is None:
            return
        self._emit(Jump(L))


    def _compile_method(self, cname: str, ir_name: str, mdecl):
        params = ["this"] + [p.name for p in (getattr(mdecl, "params", []) or [])]
        fn = IRFunction(name=ir_name, params=params)
        self.prog.functions[ir_name] = fn

        # guardar contexto actual (incluyendo scopes)
        prev_fn, prev_frame, prev_class = self.current_fn, self.frame, self.cur_class
        prev_scopes, prev_types = self.scopes, self.type_scopes

        # activar contexto del método
        self.current_fn, self.frame = fn, Frame(ir_name, params)
        self.cur_class = cname
        self.scopes = []
        self.type_scopes = []
        self._push_scope()

        # bind this y parámetros
        self._bind("this", Param("this"))
        self._bind_type("this", cname)
        for p in params[1:]:
            self._bind(p, Param(p))
            self._bind_type(p, None)

        # cuerpo
        self._visit(mdecl.body)

        # cerrar y restaurar
        self._pop_scope()
        fn.frame = self.frame
        self.current_fn, self.frame, self.cur_class = prev_fn, prev_frame, prev_class
        self.scopes, self.type_scopes = prev_scopes, prev_types


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
            raise RuntimeError(f"Identificador no encontrado: {e.name}")
        return op

    def _expr_This(self, e) -> Operand:
        # Primer parámetro de métodos
        return Param("this")

    def _expr_MemberAccess(self, e) -> Operand:
        # R-value: leer campo (this.campo o var.campo)
        base_op, cls, field = self._resolve_member_target(e)
        offset = self.class_field_off[cls][field]
        dst = Temp(self.tpool.new())
        self._emit(Load(dst, base_op, offset))
        return dst
    
    def _expr_ArrayLiteral(self, e) -> Operand:
        # tamaño en bytes = 4 (length) + n*4
        n = len(e.elements)
        size = 4 + n*4
        arr = Temp(self.tpool.new())
        self._emit(Call(arr, "malloc", [ConstInt(size)]))
        # length
        self._emit(Store(arr, 0, ConstInt(n)))
        # elementos
        i = 0
        while i < n:
            val = self._eval_expr(e.elements[i])
            self._emit(Store(arr, 4 + i*4, val))
            self._release_if_temp(val)
            i += 1
        return arr

    def _expr_IndexAccess(self, e) -> Operand:
        base = self._eval_expr(e.obj)
        idx  = self._eval_expr(e.index)
        dst  = Temp(self.tpool.new())
        self._emit(LoadI(dst, base, idx))
        # reciclar
        self._release_if_temp(base); self._release_if_temp(idx)
        return dst


    def _resolve_member_target(self, e):
        """Devuelve (base_operand, class_name, field_name) para MemberAccess."""
        obj = e.obj
        field = e.name
        ck = obj.__class__.__name__
        if ck == "This":
            if not self.cur_class:
                raise RuntimeError("Uso de 'this' fuera de método")
            return Param("this"), self.cur_class, field
        if ck == "Identifier":
            base = self._lookup(obj.name)
            if base is None:
                raise RuntimeError(f"Variable no encontrada: {obj.name}")
            c = self._lookup_type(obj.name)
            if not c:
                raise RuntimeError(f"No se conoce clase de '{obj.name}' para acceso a miembro")
            if c not in self.class_field_off:
                raise RuntimeError(f"Clase '{c}' sin layout registrado")
            return base, c, field
        raise NotImplementedError("MemberAccess: solo 'this.x' o 'var.x' por ahora")

    def _expr_Literal(self, e) -> Operand:
        if e.kind == "int":
            return ConstInt(int(e.value))
        if e.kind == "boolean":
            return ConstInt(1 if bool(e.value) else 0)
        if e.kind == "string":
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
            self._emit(Cmp("==", dst, v, ConstInt(0)))
            return dst
        raise NotImplementedError(f"Unary op {e.op} no soportado")

    def _expr_Binary(self, e) -> Operand:
        # '+' especial: si cualquiera es ConstStr, llamar a __concat (opcional)
        if e.op == "+" and (e.left.__class__.__name__ == "Literal" and e.left.kind == "string"
                            or e.right.__class__.__name__ == "Literal" and e.right.kind == "string"):
            a = self._eval_expr(e.left)
            b = self._eval_expr(e.right)
            dst = Temp(self.tpool.new())
            self._emit(Call(dst, "__concat", [a, b]))  # runtime opcional
            self._release_if_temp(a); self._release_if_temp(b)
            return dst

        if e.op in ("+","-","*","/","%"):
            a = self._eval_expr(e.left)
            b = self._eval_expr(e.right)
            dst = Temp(self.tpool.new())
            self._emit(BinOp(e.op, dst, a, b))
            self._release_if_temp(a); self._release_if_temp(b)
            return dst

        if e.op in ("==","!=", "<","<=",">",">="):
            a = self._eval_expr(e.left)
            b = self._eval_expr(e.right)
            dst = Temp(self.tpool.new())
            self._emit(Cmp(e.op, dst, a, b))
            self._release_if_temp(a); self._release_if_temp(b)
            return dst

        if e.op in ("&&", "||"):
            L_true  = self.lgen.new()
            L_false = self.lgen.new()
            L_end   = self.lgen.new()
            dst = Temp(self.tpool.new())
            # init dst = 0
            self._emit(Move(dst, ConstInt(0)))
            if e.op == "&&":
                # if !left goto false
                self._emit_cond_jump(("NOT", e.left), L_false, L_true)
                self._emit(Label(L_true))
                # if !right goto false
                L_true2 = self.lgen.new()
                self._emit_cond_jump(("NOT", e.right), L_false, L_true2)
                self._emit(Label(L_true2))
                self._emit(Move(dst, ConstInt(1)))
                self._emit(Jump(L_end))
            else:
                # '||'
                self._emit_cond_jump(e.left, L_true, L_false)
                self._emit(Label(L_false))
                self._emit_cond_jump(e.right, L_true, L_false)
                self._emit(Label(L_true))
                self._emit(Move(dst, ConstInt(1)))
                self._emit(Jump(L_end))
            self._emit(Label(L_false))
            # dst ya es 0
            self._emit(Label(L_end))
            return dst

        raise NotImplementedError(f"Binary op {e.op} no soportado")


    def _expr_Call(self, e) -> Operand:
        # Call puede ser:
        #   - función global: id(args)
        #   - constructor:  Clase(args)  => malloc + Clase__constructor(this, args)
        #   - método:       obj.metodo(args) => Clase__metodo(obj, args)
        cn = e.callee.__class__.__name__
        args_ops: List[Operand] = []
        i = 0
        while i < len(e.args):
            args_ops.append(self._eval_expr(e.args[i]))
            i += 1

        # 1) método obj.metodo(...)
        if cn == "MemberAccess":
            obj = e.callee.obj
            meth = e.callee.name
            cls: Optional[str] = None
            base_op: Operand

            ok_simple = False
            if obj.__class__.__name__ == "This":
                base_op = Param("this")
                cls = self.cur_class
                ok_simple = True
            elif obj.__class__.__name__ == "Identifier":
                base_op = self._lookup(obj.name)
                if base_op is None:
                    raise RuntimeError(f"Variable no encontrada: {obj.name}")
                cls = self._lookup_type(obj.name)
                ok_simple = (cls is not None)
            if not ok_simple or not cls:
                raise NotImplementedError("Llamada a método solo soporta 'this.m()' o 'var.m()' con tipo conocido")

            irname = self._lookup_method_irname(cls, meth)
            dst = Temp(self.tpool.new())
            self._emit(Call(dst, irname, [base_op] + args_ops))
            return dst

        # 2) constructor Clase(...)
        if cn == "Identifier" and e.callee.name in self.class_field_off:
            cname = e.callee.name
            size = self._class_size(cname)
            this_tmp = Temp(self.tpool.new())
            # this = malloc(size)
            self._emit(Call(this_tmp, "malloc", [ConstInt(size)]))
            # llamar constructor si existe
            ctor_ir = self.method_irname.get((cname, "constructor"))
            if ctor_ir:
                self._emit(Call(None, ctor_ir, [this_tmp] + args_ops))
            return this_tmp

        # 3) función global normal
        if cn == "Identifier":
            fname = e.callee.name
            dst = Temp(self.tpool.new())
            self._emit(Call(dst, fname, args_ops))
            return dst

        raise NotImplementedError("Call no soportada para este tipo de callee")

    def _lookup_method_irname(self, cls: str, meth: str) -> str:
        c = cls
        visited = set()
        while c and c not in visited:
            visited.add(c)
            ir = self.method_irname.get((c, meth))
            if ir:
                return ir
            c = self.class_base.get(c)
        raise RuntimeError(f"Método '{meth}' no existe en clase '{cls}' ni en su base")

    # ---------------- condicionales en saltos ----------------
    def _emit_cond_jump(self, cond_expr, L_true: str, L_false: str):
        # soporta wrapper ("NOT", expr)
        if isinstance(cond_expr, tuple) and len(cond_expr) == 2 and cond_expr[0] == "NOT":
            v = self._eval_expr(cond_expr[1])
            self._emit(CJump("==", v, ConstInt(0), L_true, L_false))
            self._release_if_temp(v)
            return
        # relacionales directos
        if cond_expr.__class__.__name__ == "Binary" and cond_expr.op in ("==","!=", "<","<=",">",">="):
            a = self._eval_expr(cond_expr.left)
            b = self._eval_expr(cond_expr.right)
            self._emit(CJump(cond_expr.op, a, b, L_true, L_false))
            self._release_if_temp(a); self._release_if_temp(b)
            return
        # default: evaluar != 0
        v = self._eval_expr(cond_expr)
        self._emit(CJump("!=", v, ConstInt(0), L_true, L_false))
        self._release_if_temp(v)


    # ---------------- util ----------------
    def _emit(self, instr: Instr):
        assert self.current_fn is not None
        self.current_fn.body.append(instr)

    def _new_string_label(self, text: str) -> str:
        for k, v in self.prog.strings.items():
            try:
                if v.decode("utf-8") == text:
                    return k
            except Exception:
                pass
        label = f"str{len(self.prog.strings)}"
        self.prog.strings[label] = text.encode("utf-8") + b"\x00"
        return label

    def _class_size(self, cname: str) -> int:
        offmap = self.class_field_off.get(cname, {})
        # tamaño = (num_campos) * 4
        return 4 * len(offmap)

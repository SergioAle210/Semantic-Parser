# cheker semantico recorre tu AST no el ParseTree
from antlr.sema.types import *
from antlr.sema.symbols import (
    Env,
    Symbol,
    VarSymbol,
    ConstSymbol,
    FunctionSymbol,
    ClassSymbol,
)


# clase principal del verificador semántico
class Checker:
    def __init__(self):
        self.errors = []
        self.env = Env()
        self.loop_depth = 0
        self._dead_stack = []
        self._in_collect = False

    # registra un error con ubicación
    def err(self, loc, msg):
        self.errors.append("[" + str(loc.line) + ":" + str(loc.col) + "] " + msg)

    # inicia una nueva región para detección de código muerto
    def _dead_push(self):
        self._dead_stack.append(False)

    # finaliza la región de código muerto actual
    def _dead_pop(self):
        if len(self._dead_stack) > 0:
            self._dead_stack.pop()

    # marca que a partir de aquí el código es inalcanzable
    def _dead_mark(self):
        if len(self._dead_stack) > 0:
            self._dead_stack[len(self._dead_stack) - 1] = True

    # consulta si se está en zona de código muerto
    def _dead_is(self):
        if len(self._dead_stack) == 0:
            return False
        return self._dead_stack[len(self._dead_stack) - 1]

    # busca un hijo de tipo 'Block' dentro de cualquier atributo del nodo
    def _find_block_child(self, n):
        for k in dir(n):
            if len(k) > 0 and k[0] == "_":
                continue
            try:
                v = getattr(n, k)
            except Exception:
                continue
            # Evita callables
            if hasattr(v, "__class__"):
                cname = v.__class__.__name__
                if cname == "Block":
                    return v
        return None

    # obtiene la lista de parámetros de un nodo que luce como función
    def _find_params_list(self, n):
        # intenta 'params' o 'parameters'
        if hasattr(n, "params"):
            return n.params
        if hasattr(n, "parameters"):
            return n.parameters
        # como fallback primer atributo que sea lista de nodos con atributo 'name'
        for k in dir(n):
            if len(k) > 0 and k[0] == "_":
                continue
            try:
                v = getattr(n, k)
            except Exception:
                continue
            if isinstance(v, list) and len(v) >= 0:
                # lista vacía sirve
                if len(v) == 0:
                    return v
                first = v[0]
                if hasattr(first, "name"):
                    return v
        return []

    # heurística para saber si un nodo es tipo función
    def _is_func_like(self, n):
        # por nombre de clase
        cname = n.__class__.__name__
        low = ""
        i = 0
        while i < len(cname):
            ch = cname[i]
            # tolower manual sin helpers solo A-Z
            if "A" <= ch <= "Z":
                low = low + chr(ord(ch) + 32)
            else:
                low = low + ch
            i += 1
        if ("func" in low) or ("function" in low):
            return True
        #  heurística por atributos debe tener 'name' y un Block hijo
        if hasattr(n, "name"):
            blk = self._find_block_child(n)
            if blk is not None:
                return True
        return False

    # devuelve los parámetros de una función
    def _func_params(self, n):
        return self._find_params_list(n)

    # devuelve el cuerpo block de una función
    def _func_body(self, n):
        # intenta 'body' y 'block' primero
        if hasattr(n, "body"):
            return n.body
        if hasattr(n, "block"):
            return n.block
        # fallback: buscar Block en atributos
        return self._find_block_child(n)

    # obtiene la anotación de retorno de la función si existe
    def _func_ret_ann(self, n):
        # intentos comunes
        if hasattr(n, "ret_ann"):
            return n.ret_ann
        if hasattr(n, "return_ann"):
            return n.return_ann
        # a veces el AST guarda la anotación como string en 'type_ann' del nodo
        if hasattr(n, "type_ann"):
            return n.type_ann
        return None

    # ejecuta los dos pases: colección y chequeo
    def run(self, root):
        self._declare_builtins()
        self._in_collect = True
        self._collect(root)
        self._in_collect = False
        self.visit(root)

    # recorre el árbol recogiendo firmas de funciones/clases
    def _collect(self, n):
        if n is None:
            return
        name = n.__class__.__name__
        m = getattr(self, "_collect_" + name, None)
        if m is not None:
            m(n)
            return
        if self._is_func_like(n):
            self._collect_FunctionLike(n)
            return
        if name == "Program" or name == "Block":
            i = 0
            while i < len(n.statements):
                self._collect(n.statements[i])
                i += 1

    # recolecta una función genérica (no necesariamente FunctionDecl)
    def _collect_FunctionLike(self, n):
        ret_t = T_VOID()
        ra = self._func_ret_ann(n)
        if ra is not None:
            ret_t = parse_type_text(ra)
        try:
            f = self.env.declare_func(n.name, ret_t)
        except Exception as e:
            self.err(n.loc, str(e))
            return
        pts = []
        ps = self._func_params(n)
        i = 0
        while i < len(ps):
            p = ps[i]
            pt = T_UNKNOWN()
            if hasattr(p, "type_ann") and p.type_ann is not None:
                pt = parse_type_text(p.type_ann)
            pts.append(pt)
            i += 1
        f.params = []
        f.return_type = ret_t
        f.typ = T_FUNC(pts, ret_t)

        body = self._func_body(n)
        if body is not None:
            self.env.push_function(f)  # ámbito de la función
            self._collect(body)  # aquí se verán funciones anidadas
            self.env.pop()

    # recolecta a nivel programa
    def _collect_Program(self, n):
        i = 0
        while i < len(n.statements):
            self._collect(n.statements[i])
            i += 1

    # recolecta una declaración de función clásica
    def _collect_FunctionDecl(self, n):
        ret_t = T_VOID()
        if getattr(n, "ret_ann", None) is not None:
            ret_t = parse_type_text(n.ret_ann)
        try:
            f = self.env.declare_func(n.name, ret_t)
        except Exception as e:
            self.err(n.loc, str(e))
            return
        # prepara firma paramétrica
        params = getattr(n, "params", [])
        pts = []
        i = 0
        while i < len(params):
            p = params[i]
            pt = T_UNKNOWN()
            if getattr(p, "type_ann", None) is not None:
                pt = parse_type_text(p.type_ann)
            pts.append(pt)
            i += 1
        f.params = []  # se llenan en pase 2
        f.return_type = ret_t
        f.typ = T_FUNC(pts, ret_t)

    # recolecta una declaración de clase y sus miembros
    def _collect_ClassDecl(self, n):
        try:
            C = self.env.declare_class(n.name)
        except Exception as e:
            self.err(n.loc, str(e))
            return

        self.env.push_class(C)
        i = 0
        while i < len(n.members):
            m = n.members[i]
            k = m.__class__.__name__
            if k == "VarDecl":
                t = None
                if getattr(m, "type_ann", None) is not None:
                    t = parse_type_text(m.type_ann)
                try:
                    self.env.class_add_field(C, m.name, t)
                except Exception as ex:
                    self.err(m.loc, str(ex))
            elif k == "ConstDecl":
                t = None
                if getattr(m, "type_ann", None) is not None:
                    t = parse_type_text(m.type_ann)
                try:
                    self.env.class_add_field(C, m.name, t)
                    if m.init is None:
                        self.err(
                            m.loc,
                            "Const de clase '" + m.name + "' requiere inicialización",
                        )
                except Exception as ex:
                    self.err(m.loc, str(ex))
            elif k == "FunctionDecl":
                if getattr(m, "name", "") == "constructor":
                    try:
                        ctor = self.env.class_set_ctor(C, T_VOID())
                    except Exception as ex:
                        self.err(m.loc, str(ex))
                        i += 1
                        continue
                    pts = []
                    j = 0
                    while j < len(m.params):
                        p = m.params[j]
                        pt = T_UNKNOWN()
                        if getattr(p, "type_ann", None) is not None:
                            pt = parse_type_text(p.type_ann)
                        pts.append(pt)
                        j += 1
                    ctor.typ = T_FUNC(pts, T_VOID())

                    if getattr(m, "body", None) is not None:
                        self.env.push_function(ctor)
                        self._collect(m.body)
                        self.env.pop()
                else:
                    ret_t = T_VOID()
                    if getattr(m, "ret_ann", None) is not None:
                        ret_t = parse_type_text(m.ret_ann)
                    try:
                        meth = self.env.class_add_method(C, m.name, ret_t)
                    except Exception as ex:
                        self.err(m.loc, str(ex))
                        i += 1
                        continue
                    pts = []
                    j = 0
                    while j < len(m.params):
                        p = m.params[j]
                        pt = T_UNKNOWN()
                        if getattr(p, "type_ann", None) is not None:
                            pt = parse_type_text(p.type_ann)
                        pts.append(pt)
                        j += 1
                    meth.typ = T_FUNC(pts, ret_t)

                    if getattr(m, "body", None) is not None:
                        self.env.push_function(meth)
                        self._collect(m.body)
                        self.env.pop()
            i += 1

        if getattr(n, "base_name", None):
            C.base_name = n.base_name

        self.env.pop()

    # abre un nuevo ámbito de bloque durante la colección
    def _collect_Block(self, n):
        self.env.push_block()
        i = 0
        while i < len(n.statements):
            self._collect(n.statements[i])
            i += 1
        self.env.pop()

    # declara funciones builtin básicas
    def _declare_builtins(self):
        try:
            f = self.env.declare_func("print", T_VOID())
            f.typ = T_FUNC([T_UNKNOWN()], T_VOID())
            f.return_type = T_VOID()
            f.is_builtin = True
        except Exception:
            pass

    def _is_void_type(self, t):
        # Evita depender de helpers externos; str(t) suele ser "void"
        return str(t) == "void"

    def _block_or_stmt_returns(self, n) -> bool:
        if n is None:
            return False
        if n.__class__.__name__ == "Block":
            return self._block_guarantees_return(n)
        return self._stmt_guarantees_return(n)

    def _block_guarantees_return(self, blk) -> bool:
        # Un bloque garantiza return si alguna sentencia lo garantiza
        i = 0
        while i < len(blk.statements):
            if self._stmt_guarantees_return(blk.statements[i]):
                return True
            i += 1
        return False

    def _stmt_guarantees_return(self, s) -> bool:
        k = s.__class__.__name__
        if k == "Return":
            return True
        if k == "Block":
            return self._block_guarantees_return(s)
        if k == "If":
            then_ok = self._block_or_stmt_returns(getattr(s, "then_blk", None))
            else_blk = getattr(s, "else_blk", None)
            else_ok = self._block_or_stmt_returns(else_blk) if else_blk is not None else False
            return then_ok and else_ok
        if k == "TryCatch":
            # Conservador: exige return en try y en catch
            return (self._block_or_stmt_returns(getattr(s, "try_block", None)) and
                    self._block_or_stmt_returns(getattr(s, "catch_block", None)))
        if k == "Switch":
            # Conservador: exige default y que todos los cases retornen
            cases = getattr(s, "cases", []) or []
            all_cases = True
            i = 0
            while i < len(cases):
                if not self._block_or_stmt_returns(cases[i].block):
                    all_cases = False
                    break
                i += 1
            default_blk = getattr(s, "default_block", None)
            return (default_blk is not None and
                    all_cases and
                    self._block_or_stmt_returns(default_blk))
        # Bucles y demás sentencias no garantizan retorno (conservador)
        return False

    # paso 2 chequeo
    # despacha a visit_* según el tipo de nodo
    def visit(self, node):
        if node is None:
            return None
        name = node.__class__.__name__
        m = getattr(self, "visit_" + name, None)
        if m is not None:
            return m(node)
        if self._is_func_like(node):
            return self.visit_FunctionLike(node)
        return T_UNKNOWN()

    # programa / bloque
    def visit_Program(self, n):
        self._dead_push()
        i = 0
        while i < len(n.statements):
            if self._dead_is():
                self.err(n.statements[i].loc, "Código muerto no alcanzable")
            else:
                self.visit(n.statements[i])
            i += 1
        self._dead_pop()
        return None

    # visita un bloque con manejo de ámbito y código muerto
    def visit_Block(self, n):
        self.env.push_block()
        self._dead_push()
        i = 0
        while i < len(n.statements):
            if self._dead_is():
                self.err(n.statements[i].loc, "Código muerto no alcanzable")
            else:
                self.visit(n.statements[i])
            i += 1
        self._dead_pop()
        self.env.pop()
        return None

    # declaraciones
    def visit_VarDecl(self, n):
        t = None
        if getattr(n, "type_ann", None) is not None:
            t = parse_type_text(n.type_ann)
        try:
            sym = self.env.declare_var(n.name, t)
        except Exception as e:
            self.err(n.loc, str(e))
            sym = None
        if getattr(n, "init", None) is not None:
            rhs = self.visit(n.init)
            if sym is not None:
                if sym.typ is None or is_unknown(sym.typ):
                    sym.typ = rhs
                    sym.inited = True
                else:
                    if not assignable(rhs, sym.typ):
                        self.err(
                            n.loc,
                            "Asignación incompatible en declaración de '"
                            + n.name
                            + "': "
                            + str(rhs)
                            + " → "
                            + str(sym.typ),
                        )
                    else:
                        sym.inited = True
        return None

    # declara constantes y obliga a inicialización compatible
    def visit_ConstDecl(self, n):
        if getattr(n, "init", None) is None:
            self.err(n.loc, "Const '" + n.name + "' requiere inicialización")
        t = None
        if getattr(n, "type_ann", None) is not None:
            t = parse_type_text(n.type_ann)
        try:
            sym = self.env.declare_const(n.name, t)
        except Exception as e:
            self.err(n.loc, str(e))
            sym = None
        rhs = T_UNKNOWN()
        if getattr(n, "init", None) is not None:
            rhs = self.visit(n.init)
        if sym is not None:
            if sym.typ is None or is_unknown(sym.typ):
                sym.typ = rhs
            elif not assignable(rhs, sym.typ):
                self.err(
                    n.loc,
                    "Const '"
                    + n.name
                    + "': tipo incompatible "
                    + str(rhs)
                    + " → "
                    + str(sym.typ),
                )
            sym.inited = True
        return None

    # funciones y clases
    def visit_FunctionLike(self, n):
        fun_sym, _ = self.env.resolve(n.name)
        if fun_sym is None or fun_sym.kind != "func":
            ret_t = T_VOID()
            ra = self._func_ret_ann(n)
            if ra is not None:
                ret_t = parse_type_text(ra)
            try:
                fun_sym = self.env.declare_func(n.name, ret_t)
            except Exception as e:
                self.err(n.loc, str(e))
                return None
            fun_sym.typ = T_FUNC([], ret_t)
            fun_sym.return_type = ret_t

        self.env.push_function(fun_sym)
        fun_sym.params = []
        ps = self._func_params(n)
        i = 0
        while i < len(ps):
            p = ps[i]
            pt = T_UNKNOWN()
            if hasattr(p, "type_ann") and p.type_ann is not None:
                pt = parse_type_text(p.type_ann)
            try:
                psym = self.env.declare_param(p.name, pt)
            except Exception as e:
                self.err(p.loc, str(e))
                psym = None
            if psym is not None:
                fun_sym.params.append(psym)
            i += 1

        pts = []
        j = 0
        while j < len(fun_sym.params):
            pts.append(fun_sym.params[j].typ)
            j += 1
        rt = fun_sym.return_type if fun_sym.return_type is not None else T_VOID()
        fun_sym.typ = T_FUNC(pts, rt)

        body = self._func_body(n)
        self._dead_push()
        if body is not None:
            self.visit(body)
        self._dead_pop()

        if not self._is_void_type(rt):
            if body is None or not self._block_or_stmt_returns(body):
                self.err(n.loc, "Función '" + n.name + "' debe retornar un tipo de dato "
                        + str(rt) + " en todos los caminos")
                
        self.env.pop()
        return None

    # visita una clase y verifica compatibilidad de miembros
    def visit_ClassDecl(self, n):
        class_sym, _ = self.env.resolve(n.name)
        if class_sym is None or class_sym.kind != "class":
            try:
                class_sym = self.env.declare_class(n.name)
            except Exception as e:
                self.err(n.loc, str(e))
                return None

        self.env.push_class(class_sym)
        i = 0
        while i < len(n.members):
            m = n.members[i]
            k = m.__class__.__name__
            if k == "VarDecl":
                if getattr(m, "init", None) is not None:
                    rhs = self.visit(m.init)
                    fld = self.env.class_lookup_member(class_sym, m.name)
                    if (
                        fld is not None
                        and fld.typ is not None
                        and not assignable(rhs, fld.typ)
                    ):
                        self.err(
                            m.loc,
                            "Campo '"
                            + m.name
                            + "': tipo incompatible "
                            + str(rhs)
                            + " → "
                            + str(fld.typ),
                        )
            elif k == "ConstDecl":
                if getattr(m, "init", None) is None:
                    self.err(
                        m.loc, "Const de clase '" + m.name + "' requiere inicialización"
                    )
                else:
                    rhs = self.visit(m.init)
                    fld = self.env.class_lookup_member(class_sym, m.name)
                    if (
                        fld is not None
                        and fld.typ is not None
                        and not assignable(rhs, fld.typ)
                    ):
                        self.err(
                            m.loc,
                            "Const de clase '"
                            + m.name
                            + "': incompatible "
                            + str(rhs)
                            + " → "
                            + str(fld.typ),
                        )
            elif k == "FunctionDecl":
                if getattr(m, "name", "") == "constructor":
                    ctor = class_sym.ctor
                    if ctor is None:
                        ctor = self.env.class_set_ctor(class_sym, T_VOID())
                    self.env.push_function(ctor)
                    ctor.params = []
                    j = 0
                    while j < len(m.params):
                        p = m.params[j]
                        pt = T_UNKNOWN()
                        if getattr(p, "type_ann", None) is not None:
                            pt = parse_type_text(p.type_ann)
                        try:
                            ps = self.env.declare_param(p.name, pt)
                        except Exception as e:
                            self.err(p.loc, str(e))
                            ps = None
                        if ps is not None:
                            ctor.params.append(ps)
                        j += 1
                    self._dead_push()
                    self.visit(m.body)
                    self._dead_pop()
                    self.env.pop()

                else:
                    meth = self.env.class_lookup_member(class_sym, m.name)
                    if meth is None or meth.kind != "func":
                        meth = self.env.class_add_method(class_sym, m.name, T_VOID())
                    self.env.push_function(meth)
                    meth.is_method = True
                    meth.params = []
                    j = 0
                    while j < len(m.params):
                        p = m.params[j]
                        pt = T_UNKNOWN()
                        if getattr(p, "type_ann", None) is not None:
                            pt = parse_type_text(p.type_ann)
                        try:
                            ps = self.env.declare_param(p.name, pt)
                        except Exception as e:
                            self.err(p.loc, str(e))
                            ps = None
                        if ps is not None:
                            meth.params.append(ps)
                        j += 1
                    if getattr(m, "ret_ann", None) is not None:
                        meth.return_type = parse_type_text(m.ret_ann)
                    else:
                        meth.return_type = T_VOID()
                    self._dead_push()
                    self.visit(m.body)
                    self._dead_pop()
                    self.env.pop()

                    if not self._is_void_type(meth.return_type):
                        if getattr(m, "body", None) is None or not self._block_or_stmt_returns(m.body):
                            self.err(m.loc, "Método '" + m.name + "' debe retornar un tipo de dato "
                                    + str(meth.return_type) + " en todos los caminos")
            i += 1

        if getattr(class_sym, "base_name", None):
            base_sym, _ = self.env.resolve(class_sym.base_name)
            if base_sym is None or base_sym.kind != "class":
                self.err(n.loc, "Clase base no declarada: " + class_sym.base_name)

        return None

    # statements
    # valida una asignación lhs = rhs
    def visit_Assign(self, n):
        lhs_t = None
        lhs_sym = None
        tn = n.target.__class__.__name__

        if tn == "Identifier":
            lhs_sym, _ = self.env.resolve(n.target.name)
            if lhs_sym is None:
                self.err(n.loc, "Uso de variable no declarada: '" + n.target.name + "'")
                lhs_t = T_UNKNOWN()
            else:
                if lhs_sym.kind == "const":
                    self.err(
                        n.loc, "No se puede asignar a const '" + lhs_sym.name + "'"
                    )
                lhs_t = lhs_sym.typ if lhs_sym.typ is not None else T_UNKNOWN()
        elif tn == "MemberAccess":
            # LHS es acceso a campo: obj.name
            # Resolvemos tipo del campo mirando la clase del objeto y el símbolo del miembro
            obj_t = self.visit(n.target.obj)
            if not is_class(obj_t):
                self.err(
                    n.loc, "Asignación a miembro sobre un valor no-clase: " + str(obj_t)
                )
                lhs_t = T_UNKNOWN()
            else:
                class_sym, _ = self.env.resolve(obj_t.info)
                if class_sym is None or class_sym.kind != "class":
                    self.err(n.loc, "Clase no declarada: " + obj_t.info)
                    lhs_t = T_UNKNOWN()
                else:
                    mem = self.env.class_lookup_member(class_sym, n.target.name)
                    if mem is None:
                        self.err(
                            n.loc,
                            "Miembro '"
                            + n.target.name
                            + "' no existe en clase "
                            + obj_t.info,
                        )
                        lhs_t = T_UNKNOWN()
                    else:
                        lhs_t = mem.typ if mem.typ is not None else T_UNKNOWN()
        elif tn == "IndexAccess":
            lhs_t = self.visit(n.target)
        else:
            self.err(n.loc, "Lado izquierdo de asignación inválido")
            lhs_t = T_UNKNOWN()

        rhs_t = self.visit(n.value)

        if lhs_sym is not None:
            if lhs_sym.typ is None or is_unknown(lhs_sym.typ):
                lhs_sym.typ = rhs_t
                lhs_sym.inited = True
            else:
                if not assignable(rhs_t, lhs_sym.typ):
                    self.err(
                        n.loc,
                        "Asignación incompatible: "
                        + str(rhs_t)
                        + " → "
                        + str(lhs_sym.typ),
                    )
                else:
                    lhs_sym.inited = True

        if lhs_sym is None and not is_unknown(lhs_t):
            # Si el RHS queda 'unknown', no disparemos un falso positivo aquí;
            # ya habría otros errores de contexto si realmente hay problema.
            if not is_unknown(rhs_t) and not assignable(rhs_t, lhs_t):
                self.err(
                    n.loc, "Asignación incompatible: " + str(rhs_t) + " → " + str(lhs_t)
                )
        return None

    # valida un if con condición booleana
    def visit_If(self, n):
        ct = self.visit(n.cond)
        if not is_bool(ct):
            self.err(n.loc, "Condición de if debe ser boolean")
        self.visit(n.then_blk)
        if getattr(n, "else_blk", None) is not None:
            self.visit(n.else_blk)
        return None

    # valida un while y su cuerpo
    def visit_While(self, n):
        ct = self.visit(n.cond)
        if not is_bool(ct):
            self.err(n.loc, "Condición de while debe ser boolean")
        self.loop_depth += 1
        self.visit(n.body)
        self.loop_depth -= 1
        return None

    # valida return contra el tipo esperado y marca código muerto
    def visit_Return(self, n):
        funsym = self.env.current_function_symbol()
        if funsym is None:
            self.err(n.loc, "return fuera de una función")
            self._dead_mark()
            return None
        rt = T_VOID()
        if getattr(n, "value", None) is not None:
            rt = self.visit(n.value)
        exp = funsym.return_type if funsym.return_type is not None else T_VOID()
        if not assignable(rt, exp):
            self.err(
                n.loc, "Tipo de return incompatible: " + str(rt) + " → " + str(exp)
            )
        self._dead_mark()
        return None

    # valida uso de break dentro de bucles
    def visit_Break(self, n):
        if self.loop_depth <= 0:
            self.err(n.loc, "break sólo puede usarse dentro de bucles")
        self._dead_mark()
        return None

    # valida uso de continue dentro de bucles
    def visit_Continue(self, n):
        if self.loop_depth <= 0:
            self.err(n.loc, "continue sólo puede usarse dentro de bucles")
        self._dead_mark()
        return None

    # evalúa una expresión independiente efectos laterales
    def visit_ExprStmt(self, n):
        self.visit(n.expr)
        return None

    # expresiones
    # resuelve un identificador y devuelve su tipo
    def visit_Identifier(self, n):
        sym, def_scope = self.env.resolve(n.name)
        if sym is None:
            self.err(n.loc, "Uso de variable no declarada: '" + n.name + "'")
            return T_UNKNOWN()
        self.env.note_capture_if_needed(def_scope, sym)
        return sym.typ if sym.typ is not None else T_UNKNOWN()

    #  mapea literales a tipos del sistema
    def visit_Literal(self, n):
        if n.kind == "int":
            return T_INT()
        if n.kind == "string":
            return T_STRING()
        if n.kind == "boolean":
            return T_BOOL()
        if n.kind == "null":
            return T_NULL()
        return T_UNKNOWN()

    # valida operador unario contra el tipo del operando
    def visit_Unary(self, n):
        t = self.visit(n.expr)
        r = unary_result(n.op, t)
        if r is None:
            if n.op == "!":
                self.err(n.loc, "Operador '!' requiere boolean")
            elif n.op == "-":
                self.err(n.loc, "Operador '-' requiere numérico")
            else:
                self.err(n.loc, "Operador unario no soportado: " + n.op)
            return T_UNKNOWN()
        return r

    # valida operador binario y compatibilidad de operandos
    def visit_Binary(self, n):
        lt = self.visit(n.left)
        rt = self.visit(n.right)
        r = binary_result(n.op, lt, rt)
        if r is None:
            if n.op in ["&&", "||"]:
                self.err(n.loc, "Operadores '&&' y '||' requieren boolean")
            elif n.op in ["+", "-", "*", "/", "%"]:
                if n.op == "+":
                    self.err(
                        n.loc,
                        "Operación aritmética requiere numéricos (o string+any para '+')",
                    )
                elif n.op == "%":
                    self.err(n.loc, "Operación '%' requiere integer")
                else:
                    self.err(n.loc, "Operación aritmética requiere numéricos")
            else:
                self.err(
                    n.loc,
                    "Comparación incompatible: " + str(lt) + " " + n.op + " " + str(rt),
                )
            return T_UNKNOWN()
        return r

    # valida el operador ternario y unifica tipos de ramas
    def visit_Ternary(self, n):
        ct = self.visit(n.cond)
        if not is_bool(ct):
            self.err(n.loc, "Condición del operador ternario debe ser boolean")
        tt = self.visit(n.then_expr)
        et = self.visit(n.else_expr)
        u = ternary_unify(tt, et)
        if u is None:
            self.err(
                n.loc,
                "Ramas del ternario de tipo incompatible: "
                + str(tt)
                + " vs "
                + str(et),
            )
            return T_UNKNOWN()
        return u

    # valida acceso por índice a arreglos
    def visit_IndexAccess(self, n):
        arr_t = self.visit(n.obj)
        idx_t = self.visit(n.index)
        res = index_result(arr_t, idx_t)
        if res is None:
            if not is_array(arr_t):
                self.err(
                    n.loc, "Índice sobre un valor que no es arreglo: " + str(arr_t)
                )
            elif not is_int(idx_t):
                self.err(n.loc, "Índice de arreglo debe ser integer")
            return T_UNKNOWN()
        return res

    # construye el tipo de arreglo a partir de elementos
    def visit_ArrayLiteral(self, n):
        ts = []
        i = 0
        while i < len(n.elements):
            ts.append(self.visit(n.elements[i]))
            i += 1
        elem_t = array_literal_element_type(ts)
        if is_unknown(elem_t) and len(ts) > 1:
            self.err(n.loc, "Arreglo con elementos de tipo incompatible")
        return T_ARRAY(elem_t)

    # resuelve acceso a miembro: campos y métodos
    def visit_MemberAccess(self, n):
        obj_t = self.visit(n.obj)
        if is_class(obj_t):
            class_sym, _ = self.env.resolve(obj_t.info)
            if class_sym is None or class_sym.kind != "class":
                self.err(n.loc, "Clase no declarada: " + obj_t.info)
                return T_UNKNOWN()
            mem = self.env.class_lookup_member(class_sym, n.name)
            if mem is None:
                self.err(
                    n.loc, "Miembro '" + n.name + "' no existe en clase " + obj_t.info
                )
                return T_UNKNOWN()
            if mem.kind == "func":
                return mem.typ if mem.typ is not None else T_FUNC([], T_VOID())
            return mem.typ if mem.typ is not None else T_UNKNOWN()
        self.err(n.loc, "Acceso a miembro sobre un valor no-clase: " + str(obj_t))
        return T_UNKNOWN()

    # valida llamadas a funciones, métodos y constructores
    def visit_Call(self, n):
        args = []
        i = 0
        while i < len(n.args):
            args.append(self.visit(n.args[i]))
            i += 1

        cn = n.callee.__class__.__name__
        if cn == "Identifier":
            sym, _ = self.env.resolve(n.callee.name)
            if sym is None:
                self.err(
                    n.loc,
                    "Llamada a identificador no declarado: '" + n.callee.name + "'",
                )
                return T_UNKNOWN()
            if sym.kind == "func":
                ok, bad = call_compatible(sym.typ, args)
                if not ok:
                    self.err(
                        n.loc,
                        "Llamada a '" + sym.name + "' con argumentos incompatibles",
                    )
                return sym.return_type if sym.return_type is not None else T_VOID()
            if sym.kind == "class":
                ctor = sym.ctor
                if ctor is None:
                    if len(args) != 0:
                        self.err(
                            n.loc,
                            "Constructor de '"
                            + sym.name
                            + "' no declarado; se esperaba 0 argumentos",
                        )
                else:
                    ok, bad = call_compatible(ctor.typ, args)
                    if not ok:
                        self.err(
                            n.loc,
                            "Llamada al constructor de '"
                            + sym.name
                            + "' con argumentos incompatibles",
                        )
                return T_CLASS(sym.name)
            self.err(n.loc, "Identificador no invocable: '" + sym.name + "'")
            return T_UNKNOWN()

        if cn == "MemberAccess":
            obj_t = self.visit(n.callee.obj)
            if not is_class(obj_t):
                self.err(n.loc, "Llamada a método sobre valor no-clase: " + str(obj_t))
                return T_UNKNOWN()
            class_sym, _ = self.env.resolve(obj_t.info)
            if class_sym is None:
                self.err(n.loc, "Clase no declarada: " + obj_t.info)
                return T_UNKNOWN()
            mem = self.env.class_lookup_member(class_sym, n.callee.name)
            if mem is None or mem.kind != "func":
                self.err(
                    n.loc,
                    "Método '" + n.callee.name + "' no existe en clase " + obj_t.info,
                )
                return T_UNKNOWN()
            ok, bad = call_compatible(mem.typ, args)
            if not ok:
                self.err(
                    n.loc,
                    "Llamada a método '"
                    + n.callee.name
                    + "' con argumentos incompatibles",
                )
            return mem.return_type if mem.return_type is not None else T_VOID()

        self.err(n.loc, "Intento de llamar a un valor no-invocable")
        return T_UNKNOWN()

    # valida el uso de 'this' dentro de métodos de clase
    def visit_This(self, n):
        cls = self.env.current_class_symbol()
        fun = self.env.current_function_symbol()
        if cls is None or fun is None or not fun.is_method:
            self.err(n.loc, "Uso de 'this' fuera de un método de clase")
            return T_UNKNOWN()
        return T_CLASS(cls.name)

    # maneja el for con sus tres componentes y ámbito propio
    def visit_For(self, n):
        self.env.push_block()
        if n.init is not None:
            self.visit(n.init)
        if n.cond is not None:
            tcond = self.visit(n.cond)
            if not is_bool(tcond):
                self.err(
                    n.loc, "La condición del 'for' debe ser boolean, no " + str(tcond)
                )
        self.loop_depth += 1
        self.visit(n.body)
        self.loop_depth -= 1
        if n.update is not None:
            self.visit(n.update)
        self.env.pop()
        return None

    # --- foreach (Identifier in expression) ---

    def visit_Foreach(self, n):
        arr_t = self.visit(n.iterable)
        elem_t = T_UNKNOWN()
        if is_array(arr_t):
            elem_t = arr_t.info
        else:
            self.err(n.loc, "foreach espera un arreglo, no " + str(arr_t))
        self.env.push_block()
        try:
            vsym = self.env.declare_var(n.var_name, elem_t)
            vsym.inited = True
        except Exception as e:
            self.err(n.loc, str(e))
        self.loop_depth += 1
        self.visit(n.body)
        self.loop_depth -= 1
        self.env.pop()
        return None

    # valida un switch y que cada case sea compatible con el discriminante

    def visit_Switch(self, n):
        discr_t = self.visit(n.expr)
        self.env.push_block()
        # cada case debe ser tipo compatible con discr_t
        i = 0
        while i < len(n.cases):
            c = n.cases[i]
            ct = self.visit(c.expr)
            if not (assignable(ct, discr_t) and assignable(discr_t, ct)):
                self.err(
                    c.loc,
                    "Tipo de 'case' "
                    + str(ct)
                    + " no compatible con 'switch' "
                    + str(discr_t),
                )
            self.visit(c.block)
            i += 1
        if n.default_block is not None:
            self.visit(n.default_block)
        self.env.pop()
        return None

    # valida bloque try/catch con variable de error agnóstica
    def visit_TryCatch(self, n):
        self.env.push_block()
        self.visit(n.try_block)
        self.env.pop()
        self.env.push_block()
        try:
            esym = self.env.declare_var(n.err_name, T_UNKNOWN())
            esym.inited = True
        except Exception as e:
            self.err(n.loc, str(e))
        self.visit(n.catch_block)
        self.env.pop()
        return None

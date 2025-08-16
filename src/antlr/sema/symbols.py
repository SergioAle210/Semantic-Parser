# -------------------------------------------
# Compiscript - Símbolos y Ámbitos (vanilla)
# -------------------------------------------

# Kinds:
#  'var'       variable mutable
#  'const'     constante
#  'param'     parámetro de función
#  'func'      función libre o método (is_method=True)
#  'class'     definición de clase
#  'field'     campo de clase (usamos VarSymbol con .kind='field')


class Symbol:
    def __init__(self, name, kind, typ):
        self.name = name  # str
        self.kind = kind  # 'var','const','param','func','class','field'
        self.typ = typ  # Type (de types.py) o None
        self.inited = False  # para vars/consts
        # Para funciones:
        self.params = []  # lista de ParamSymbol (si func)
        self.return_type = None
        self.is_method = False
        self.captures = []  # lista de Symbol capturados (si func)
        # Para clases:
        self.members = {}  # nombre -> Symbol (campos/métodos/ctor) si class
        self.ctor = None  # FunctionSymbol del constructor si existe

    def add_param(self, psym):
        # psym: ParamSymbol
        i = 0
        while i < len(self.params):
            if self.params[i].name == psym.name:
                raise Exception("Parámetro duplicado: " + psym.name)
            i = i + 1
        self.params.append(psym)

    def add_member(self, msym):
        # msym: field o func (método) o 'constructor'
        if msym.name in self.members:
            raise Exception("Miembro duplicado en clase: " + msym.name)
        self.members[msym.name] = msym

    def set_constructor(self, funsym):
        # único constructor por ahora (sin sobrecarga)
        if self.ctor is not None:
            raise Exception("Múltiples constructores no soportados")
        self.ctor = funsym

    def add_capture(self, sym):
        # evita repetir en la lista de capturas
        i = 0
        while i < len(self.captures):
            if self.captures[i] is sym:
                return
            i = i + 1
        self.captures.append(sym)


class VarSymbol(Symbol):
    def __init__(self, name, typ):
        Symbol.__init__(self, name, "var", typ)


class ConstSymbol(Symbol):
    def __init__(self, name, typ):
        Symbol.__init__(self, name, "const", typ)
        self.inited = False  # se marcará True al validar init


class ParamSymbol(Symbol):
    def __init__(self, name, typ):
        Symbol.__init__(self, name, "param", typ)
        self.inited = True  # parámetros nacen inicializados


class FunctionSymbol(Symbol):
    def __init__(self, name, return_type):
        Symbol.__init__(self, name, "func", None)
        self.return_type = return_type
        self.is_method = False  # el checker la pondrá True si pertenece a clase


class ClassSymbol(Symbol):
    def __init__(self, name, base_name=None):
        Symbol.__init__(self, name, "class", None)
        self.members = {}
        self.ctor = None
        self.base_name = base_name


# -----------------------
# Scopes y entorno (stack)
# -----------------------


class Scope:
    def __init__(self, parent=None, owner_kind="block", owner_symbol=None):
        # owner_kind: 'block' | 'function' | 'class'
        self.parent = parent
        self.table = {}  # name -> Symbol
        self.owner_kind = owner_kind
        self.owner_symbol = owner_symbol

    def declare(self, sym):
        # prohíbe redeclaración en el MISMO scope
        if sym.name in self.table:
            raise Exception("Redeclaración en el mismo ámbito: " + sym.name)
        # prohibir sobrecarga simple de funciones en mismo scope
        if sym.kind == "func" and sym.name in self.table:
            raise Exception("Función duplicada: " + sym.name)
        self.table[sym.name] = sym
        return sym

    def lookup_here(self, name):
        if name in self.table:
            return self.table[name]
        return None

    def lookup(self, name):
        s = self
        while s is not None:
            v = s.lookup_here(name)
            if v is not None:
                return v, s
            s = s.parent
        return None, None

    def is_function_scope(self):
        return self.owner_kind == "function"

    def is_class_scope(self):
        return self.owner_kind == "class"


class Env:
    def __init__(self):
        self.global_scope = Scope(None, "block", None)
        self.scope = self.global_scope

    # --- push/pop ---
    def push_block(self):
        self.scope = Scope(self.scope, "block", None)
        return self.scope

    def push_function(self, funsym):
        self.scope = Scope(self.scope, "function", funsym)
        return self.scope

    def push_class(self, classsym):
        self.scope = Scope(self.scope, "class", classsym)
        return self.scope

    def pop(self):
        if self.scope.parent is not None:
            self.scope = self.scope.parent
        return self.scope

    # --- declarar símbolos en el scope actual ---
    def declare_var(self, name, typ):
        v = VarSymbol(name, typ)
        return self.scope.declare(v)

    def declare_const(self, name, typ):
        c = ConstSymbol(name, typ)
        return self.scope.declare(c)

    def declare_param(self, name, typ):
        p = ParamSymbol(name, typ)
        return self.scope.declare(p)

    def declare_func(self, name, return_type):
        f = FunctionSymbol(name, return_type)
        return self.scope.declare(f)

    def declare_class(self, name):
        c = ClassSymbol(name)
        return self.scope.declare(c)

    # --- resolución de nombres ---
    def resolve(self, name):
        # Devuelve (symbol, defining_scope) o (None, None)
        return self.scope.lookup(name)

    # --- apoyo a closures ---
    def note_capture_if_needed(self, defining_scope, sym):
        # Si hay una función activa y el símbolo definido está *fuera* de esa función, se captura.
        # Encontrar la función más cercana "activa" en la cadena desde el scope actual hacia arriba.
        cur = self.scope
        nearest_fun_scope = None
        while cur is not None and nearest_fun_scope is None:
            if cur.is_function_scope():
                nearest_fun_scope = cur
                break
            cur = cur.parent

        if nearest_fun_scope is None:
            return  # no estás dentro de una función: no hay captura

        # si el símbolo fue declarado en un scope que no es el de esa función (ni más interno),
        # entonces es una captura
        # i.e., defining_scope está *por encima* del nearest_fun_scope
        s = nearest_fun_scope
        above = False
        t = defining_scope
        while t is not None:
            if t is s:
                above = False
                break
            # si llegamos al tope sin encontrar s → t está por encima
            if t.parent is None:
                above = True
                break
            t = t.parent

        if above:
            funsym = nearest_fun_scope.owner_symbol
            if funsym is not None and funsym.kind == "func":
                funsym.add_capture(sym)

    # --- utilidades de clase ---
    def class_add_field(self, classsym, name, typ):
        fld = VarSymbol(name, typ)
        fld.kind = "field"
        classsym.add_member(fld)
        return fld

    def class_add_method(self, classsym, name, return_type):
        m = FunctionSymbol(name, return_type)
        m.is_method = True
        classsym.add_member(m)
        return m

    def class_set_ctor(self, classsym, return_type_void):
        # constructor no devuelve valor en el lenguaje; guardamos su firma sin retorno útil
        ctor = FunctionSymbol("constructor", return_type_void)
        ctor.is_method = True
        classsym.set_constructor(ctor)
        return ctor

    def resolve_class(self, name):
        sym, _ = self.resolve(name)
        if sym is not None and sym.kind == "class":
            return sym
        return None

    def class_lookup_member(self, classsym, name):
        # Busca en la clase y recorre la cadena de herencia
        cur = classsym
        visited = set()
        while cur is not None:
            if name in cur.members:
                return cur.members[name]
            bname = getattr(cur, "base_name", None)
            if not bname or bname in visited:
                break
            visited.add(bname)
            cur = self.resolve_class(bname)
        return None

    # --- helpers para saber contexto ---
    def current_function_symbol(self):
        # sube buscando el scope de función
        cur = self.scope
        while cur is not None:
            if cur.is_function_scope():
                return cur.owner_symbol
            cur = cur.parent
        return None

    def current_class_symbol(self):
        cur = self.scope
        while cur is not None:
            if cur.is_class_scope():
                return cur.owner_symbol
            cur = cur.parent
        return None

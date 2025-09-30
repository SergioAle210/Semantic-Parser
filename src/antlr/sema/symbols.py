# Compiscript - símbolos y ámbitos
# --------------------------------
# Define los símbolos (var/const/param/func/class/field) y la
# administración de scopes usada por el checker y el IRGen/x86.

# Símbolos
class Symbol:
    def __init__(self, name, kind, typ):
        self.name = name           # nombre visible en el código
        self.kind = kind           # 'var' | 'const' | 'param' | 'func' | 'class' | 'field'
        self.typ = typ             # objeto de tipo del sistema (puede ser None/Unknown)
        self.inited = False        # inicializada (para var/const)
        # Funciones / métodos
        self.params = []           # lista de símbolos de parámetros (FunctionSymbol)
        self.return_type = None    # tipo de retorno (FunctionSymbol)
        self.is_method = False     # true si es método de clase (FunctionSymbol)
        self.captures = []         # símbolos capturados (closures)
        # Clases
        self.members = {}          # tabla de miembros (ClassSymbol)
        self.ctor = None           # constructor (FunctionSymbol) si aplica

    def add_param(self, psym):
        # evita duplicados por nombre
        for p in self.params:
            if p.name == psym.name:
                raise Exception("Parámetro duplicado: " + psym.name)
        self.params.append(psym)

    def add_member(self, msym):
        # añade campo o método a la clase
        if msym.name in self.members:
            raise Exception("Miembro duplicado en clase: " + msym.name)
        self.members[msym.name] = msym

    def set_constructor(self, funsym):
        if self.ctor is not None:
            raise Exception("Múltiples constructores no soportados")
        self.ctor = funsym

    def add_capture(self, sym):
        # registra símbolo capturado (sin duplicar)
        for c in self.captures:
            if c is sym:
                return
        self.captures.append(sym)


class VarSymbol(Symbol):
    def __init__(self, name, typ=None):
        super().__init__(name, kind="var", typ=typ)
        # --- metadatos para codegen ---
        self.offset = None     # desplazamiento en el frame (si aplica)
        self.storage = "stack" # "stack", "global", etc.
        self.is_param = False  # true si proviene de parámetro


class ConstSymbol(Symbol):
    # símbolo para constante
    def __init__(self, name, typ):
        super().__init__(name, kind="const", typ=typ)
        self.inited = False


class ParamSymbol(VarSymbol):
    # tratamos el parámetro como una var con storage/flag específicos
    def __init__(self, name, typ):
        super().__init__(name, typ)
        self.kind = "param"
        self.is_param = True
        self.storage = "param"


class FunctionSymbol(Symbol):
    def __init__(self, name, ret_typ=None):
        super().__init__(name, kind="func", typ=None)  # typ se usa para la firma T_FUNC aparte
        self.return_type = ret_typ
        self.params = []       # lista de ParamSymbol
        # Metadatos de backend
        self.frame = None      # frame del backend (llena IR/x86)
        self.label = None      # etiqueta ASM (p.ej. 'main' o '_f_nombre')
        self.is_builtin = False


class ClassSymbol(Symbol):
    def __init__(self, name, base_name=None):
        super().__init__(name, kind="class", typ=None)
        self.members = {}      # nombre -> Symbol (field/method)
        self.ctor = None       # FunctionSymbol constructor
        self.base_name = base_name  # nombre de clase base (herencia simple)


# -----------------------------
# Scopes (ámbitos)
# -----------------------------
class Scope:
    def __init__(self, parent=None, owner_kind="block", owner_symbol=None):
        self.parent = parent
        self.table = {}              # nombre -> Symbol
        self.owner_kind = owner_kind # "block" | "function" | "class"
        self.owner_symbol = owner_symbol

    def declare(self, sym):
        # valida redeclaración en el mismo ámbito
        if sym.name in self.table:
            raise Exception("Redeclaración en el mismo ámbito: " + sym.name)
        self.table[sym.name] = sym
        return sym

    def lookup_here(self, name):
        return self.table.get(name, None)

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


# Entorno (pila de scopes)
class Env:
    """ Entorno con pila de scopes y utilidades de declaración/resolución. """
    def __init__(self):
        self.global_scope = Scope(None, "block", None)
        self.scope = self.global_scope

    # --- manejo de scopes ---
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

    # --- declaraciones ---
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

    def declare_class(self, name, base_name=None):
        c = ClassSymbol(name, base_name)
        return self.scope.declare(c)

    # --- resolución ---
    def resolve(self, name):
        """Devuelve (symbol, defining_scope) o (None, None)"""
        return self.scope.lookup(name)

    # --- capturas (closures) ---
    def note_capture_if_needed(self, defining_scope, sym):
        """
        Si estamos dentro de una función y 'sym' proviene de un scope por encima
        de dicha función, registra la captura en el símbolo de la función activa.
        """
        # localizar scope de función más cercano
        cur = self.scope
        nearest_fun_scope = None
        while cur is not None and nearest_fun_scope is None:
            if cur.is_function_scope():
                nearest_fun_scope = cur
                break
            cur = cur.parent
        if nearest_fun_scope is None:
            return

        # ¿'defining_scope' está por encima del scope de función?
        s_fun = nearest_fun_scope
        above = False
        t = defining_scope
        while t is not None:
            if t is s_fun:
                above = False
                break
            if t.parent is None:
                above = True
                break
            t = t.parent

        if above:
            funsym = nearest_fun_scope.owner_symbol
            if funsym is not None and funsym.kind == "func":
                funsym.add_capture(sym)

    # --- utilidades para clases ---
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
        """
        Busca un miembro en la clase, subiendo por la cadena de herencia si es necesario.
        """
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

    # --- contexto actual ---
    def current_function_symbol(self):
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

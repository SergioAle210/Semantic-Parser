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


# símbolo base con metadatos comunes
class Symbol:
    def __init__(self, name, kind, typ):
        self.name = name
        self.kind = kind
        self.typ = typ
        self.inited = False
        self.params = []
        self.return_type = None
        self.is_method = False
        self.captures = []
        self.members = {}
        self.ctor = None

    # añade un parámetro, evitando duplicados por nombre
    def add_param(self, psym):
        i = 0
        while i < len(self.params):
            if self.params[i].name == psym.name:
                raise Exception("Parámetro duplicado: " + psym.name)
            i = i + 1
        self.params.append(psym)

    # añade un miembro de clase (campo o método), evitando duplicados
    def add_member(self, msym):
        if msym.name in self.members:
            raise Exception("Miembro duplicado en clase: " + msym.name)
        self.members[msym.name] = msym

    # registra el constructor (único por ahora)
    def set_constructor(self, funsym):
        if self.ctor is not None:
            raise Exception("Múltiples constructores no soportados")
        self.ctor = funsym

    # registra una captura evitando repetir el mismo símbolo
    def add_capture(self, sym):
        i = 0
        while i < len(self.captures):
            if self.captures[i] is sym:
                return
            i = i + 1
        self.captures.append(sym)


class VarSymbol(Symbol):
    def __init__(self, name, typ):
        Symbol.__init__(self, name, "var", typ)


# símbolo para variable mutable
class ConstSymbol(Symbol):
    def __init__(self, name, typ):
        Symbol.__init__(self, name, "const", typ)
        self.inited = False


# símbolo para constante
class ParamSymbol(Symbol):
    def __init__(self, name, typ):
        Symbol.__init__(self, name, "param", typ)
        self.inited = True


# símbolo para parámetro de función
class FunctionSymbol(Symbol):
    def __init__(self, name, return_type):
        Symbol.__init__(self, name, "func", None)
        self.return_type = return_type
        self.is_method = False


# símbolo de clase con tabla de miembros y herencia simple
class ClassSymbol(Symbol):
    def __init__(self, name, base_name=None):
        Symbol.__init__(self, name, "class", None)
        self.members = {}
        self.ctor = None
        self.base_name = base_name


# representa un ámbito con su tabla y referencia al propietario
class Scope:
    def __init__(self, parent=None, owner_kind="block", owner_symbol=None):
        self.parent = parent
        self.table = {}
        self.owner_kind = owner_kind
        self.owner_symbol = owner_symbol

    # declara un símbolo en el ámbito actual con validaciones básicas
    def declare(self, sym):
        if sym.name in self.table:
            raise Exception("Redeclaración en el mismo ámbito: " + sym.name)
        if sym.kind == "func" and sym.name in self.table:
            raise Exception("Función duplicada: " + sym.name)
        self.table[sym.name] = sym
        return sym

    # busca solo en este ámbito
    def lookup_here(self, name):
        if name in self.table:
            return self.table[name]
        return None

    # busca recursivamente hacia los padres
    def lookup(self, name):
        s = self
        while s is not None:
            v = s.lookup_here(name)
            if v is not None:
                return v, s
            s = s.parent
        return None, None

    # indica si este scope pertenece a una función
    def is_function_scope(self):
        return self.owner_kind == "function"

    # indica si este scope pertenece a una clase
    def is_class_scope(self):
        return self.owner_kind == "class"

    # entorno con pila de scopes y utilidades de declaración/resoluciónclass Env:
    def __init__(self):
        self.global_scope = Scope(None, "block", None)
        self.scope = self.global_scope

    # abre un nuevo scope de bloque
    def push_block(self):
        self.scope = Scope(self.scope, "block", None)
        return self.scope

    # abre un scope de función asociado a un símbolo de función
    def push_function(self, funsym):
        self.scope = Scope(self.scope, "function", funsym)
        return self.scope

    # abre un scope de clase asociado a un símbolo de clase
    def push_class(self, classsym):
        self.scope = Scope(self.scope, "class", classsym)
        return self.scope

    # cierra el scope actual y vuelve al padre
    def pop(self):
        if self.scope.parent is not None:
            self.scope = self.scope.parent
        return self.scope

    # declara una variable
    def declare_var(self, name, typ):
        v = VarSymbol(name, typ)
        return self.scope.declare(v)

    # declara una constante
    def declare_const(self, name, typ):
        c = ConstSymbol(name, typ)
        return self.scope.declare(c)

    # declara un parámetro
    def declare_param(self, name, typ):
        p = ParamSymbol(name, typ)
        return self.scope.declare(p)

    # declara una función
    def declare_func(self, name, return_type):
        f = FunctionSymbol(name, return_type)
        return self.scope.declare(f)

    # declara una clase
    def declare_class(self, name):
        c = ClassSymbol(name)
        return self.scope.declare(c)

    # devuelve (symbol, defining_scope) o (none, none)
    def resolve(self, name):
        return self.scope.lookup(name)

    # si hay función activa y el símbolo viene de fuera, regístralo como captura
    def note_capture_if_needed(self, defining_scope, sym):
        cur = self.scope
        nearest_fun_scope = None
        while cur is not None and nearest_fun_scope is None:
            if cur.is_function_scope():
                nearest_fun_scope = cur
                break
            cur = cur.parent

        if nearest_fun_scope is None:
            return

        s = nearest_fun_scope
        above = False
        t = defining_scope
        while t is not None:
            if t is s:
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

    # añade un campo a la clase
    def class_add_field(self, classsym, name, typ):
        fld = VarSymbol(name, typ)
        fld.kind = "field"
        classsym.add_member(fld)
        return fld

    # añade un método a la clase
    def class_add_method(self, classsym, name, return_type):
        m = FunctionSymbol(name, return_type)
        m.is_method = True
        classsym.add_member(m)
        return m

    # define el constructor de la clase
    def class_set_ctor(self, classsym, return_type_void):
        ctor = FunctionSymbol("constructor", return_type_void)
        ctor.is_method = True
        classsym.set_constructor(ctor)
        return ctor

    # resuelve y devuelve una clase por nombre o none
    def resolve_class(self, name):
        sym, _ = self.resolve(name)
        if sym is not None and sym.kind == "class":
            return sym
        return None

    # busca un miembro en la clase recorriendo la cadena de herencia
    def class_lookup_member(self, classsym, name):
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

    # obtiene el símbolo de la función actual si existe
    def current_function_symbol(self):
        cur = self.scope
        while cur is not None:
            if cur.is_function_scope():
                return cur.owner_symbol
            cur = cur.parent
        return None

    # obtiene el símbolo de la clase actual si existe
    def current_class_symbol(self):
        cur = self.scope
        while cur is not None:
            if cur.is_class_scope():
                return cur.owner_symbol
            cur = cur.parent
        return None

class Type:
    def __init__(self, kind, info=None):
        # kind: 'int','float','bool','string','void','null','array','class','func','unknown'
        # info: para array -> Type elem
        #       para class -> nombre (str)
        #       para func  -> ( [param_types], return_type )
        self.kind = kind
        self.info = info

    def __eq__(self, other):
        if other is None:
            return False
        if self.kind != other.kind:
            return False
        if self.kind == "array":
            return self.info == other.info
        if self.kind == "class":
            return self.info == other.info
        if self.kind == "func":
            p1, r1 = self.info
            p2, r2 = other.info
            if len(p1) != len(p2):
                return False
            i = 0
            while i < len(p1):
                if p1[i] != p2[i]:
                    return False
                i = i + 1
            return r1 == r2
        return True

    def __str__(self):
        if self.kind == "array":
            return "array(" + str(self.info) + ")"
        if self.kind == "class":
            return "class(" + str(self.info) + ")"
        if self.kind == "func":
            ps, r = self.info
            s = "func("
            i = 0
            while i < len(ps):
                if i > 0:
                    s = s + ","
                s = s + str(ps[i])
                i = i + 1
            s = s + ")->" + str(r)
            return s
        return self.kind


# Constructores rápidos
def T_INT():
    return Type("int")


def T_FLOAT():
    return Type("float")


def T_BOOL():
    return Type("bool")


def T_STRING():
    return Type("string")


def T_VOID():
    return Type("void")


def T_NULL():
    return Type("null")


def T_UNKNOWN():
    return Type("unknown")


def T_ARRAY(elem):
    return Type("array", elem)


def T_CLASS(name):
    return Type("class", name)


def T_FUNC(params, ret):
    return Type("func", (params, ret))


# Predicados de tipo
def is_numeric(t):
    return t is not None and (t.kind == "int" or t.kind == "float")


def is_int(t):
    return t is not None and t.kind == "int"


def is_float(t):
    return t is not None and t.kind == "float"


def is_bool(t):
    return t is not None and t.kind == "bool"


def is_string(t):
    return t is not None and t.kind == "string"


def is_array(t):
    return t is not None and t.kind == "array"


def is_class(t):
    return t is not None and t.kind == "class"


def is_func(t):
    return t is not None and t.kind == "func"


def is_void(t):
    return t is not None and t.kind == "void"


def is_null(t):
    return t is not None and t.kind == "null"


def is_unknown(t):
    return t is not None and t.kind == "unknown"


def is_reference_like(t):
    # Para políticas de null: consideramos "referencia" a class/array/string
    return is_class(t) or is_array(t) or is_string(t)


# Reglas de conversión / asignabilidad
def can_widen(src, dst):
    # widening implícita: int -> float
    return is_int(src) and is_float(dst)


def assignable(src, dst):
    # ¿puede un valor de tipo 'src' asignarse a una variable de tipo 'dst'?
    if src is None or dst is None:
        return False
    if src == dst:
        return True
    if can_widen(src, dst):
        return True
    # null a tipos de referencia (array/class/string)
    if is_null(src) and is_reference_like(dst):
        return True
    # arrays estrictos (no permitimos int[] -> float[] automáticamente)
    if is_array(src) and is_array(dst):
        return assignable(src.info, dst.info) and (src.info == dst.info)
    # funciones/clases: solo exactamente iguales
    return False


# Operaciones sobre numéricos (promoción)
def unify_numeric(a, b):
    if not (is_numeric(a) and is_numeric(b)):
        return None
    if is_float(a) or is_float(b):
        return T_FLOAT()
    return T_INT()


# Comparaciones y compatibilidad
def compare_compatible(a, b, op):
    # < <= > >=  → numéricos
    if op == "<" or op == "<=" or op == ">" or op == ">=":
        return is_numeric(a) and is_numeric(b)
    # == != → mismo tipo, o numéricos entre sí, o referencias con null
    if a == b:
        return True
    if is_numeric(a) and is_numeric(b):
        return True
    if (is_reference_like(a) and is_null(b)) or (is_reference_like(b) and is_null(a)):
        return True
    return False


# Resultado de unario
def unary_result(op, t):
    # '!' → bool   ;   '-' → numérico
    if op == "!":
        if is_bool(t):
            return T_BOOL()
        return None
    if op == "-":
        if is_numeric(t):
            return t
        return None
    return None


# Resultado de binario (sin efectos de casting más allá de int->float)
def binary_result(op, lt, rt):
    # Lógicos
    if op == "&&" or op == "||":
        if is_bool(lt) and is_bool(rt):
            return T_BOOL()
        return None

    # Aritméticos
    if op == "+" or op == "-" or op == "*" or op == "/":
        # Soporte string + string -> string (opcional; el resto, no permitido)
        if op == "+" and is_string(lt) and is_string(rt):
            return T_STRING()
        u = unify_numeric(lt, rt)
        if u is None:
            return None
        return u

    # Comparaciones
    if op == "==" or op == "!=" or op == "<" or op == "<=" or op == ">" or op == ">=":
        if compare_compatible(lt, rt, op):
            return T_BOOL()
        return None

    # Otros: no soportado
    return None


# Unión para operador ternario cond ? a : b
def ternary_unify(a, b):
    if a == b:
        return a
    u = unify_numeric(a, b)
    if u is not None:
        return u
    # null con referencia → referencia
    if is_null(a) and is_reference_like(b):
        return b
    if is_null(b) and is_reference_like(a):
        return a
    return None


# Arrays / Índices / Literales
def index_result(arr_t, idx_t):
    if not is_array(arr_t):
        return None
    if not is_int(idx_t):
        return None
    return arr_t.info


def array_literal_element_type(elem_types):
    # elem_types: lista de Type
    if elem_types is None or len(elem_types) == 0:
        return T_UNKNOWN()
    t0 = elem_types[0]
    i = 1
    while i < len(elem_types):
        ti = elem_types[i]
        if t0 == ti:
            pass
        elif is_numeric(t0) and is_numeric(ti):
            t0 = unify_numeric(t0, ti)
        else:
            return T_UNKNOWN()  # heterogéneo
        i = i + 1
    return t0


# Funciones / llamadas
def call_compatible(fun_t, arg_types):
    # Devuelve (ok, bad_index) -- bad_index = -1 si ok
    if not is_func(fun_t):
        return (False, -1)
    params, ret = fun_t.info
    if len(params) != len(arg_types):
        return (False, -1)
    i = 0
    while i < len(params):
        # Si el parámetro es unknown, lo aceptamos como comodín
        if is_unknown(params[i]):
            i = i + 1
            continue
        if not assignable(arg_types[i], params[i]):
            return (False, i)
        i = i + 1
    return (True, -1)


def func_of(param_types, ret_type):
    return T_FUNC(param_types, ret_type)


# Parsing de anotaciones: "integer", "float", "boolean", "string", "Id", con '[]'
def parse_type_text(txt):
    # base
    i = 0
    base = ""
    while i < len(txt) and txt[i] != "[":
        base = base + txt[i]
        i = i + 1

    # normaliza algunos alias por si aparecen en ejemplos
    if base == "integer" or base == "int":
        cur = T_INT()
    elif base == "float":
        cur = T_FLOAT()
    elif base == "boolean" or base == "bool":
        cur = T_BOOL()
    elif base == "string":
        cur = T_STRING()
    elif base == "void":
        cur = T_VOID()
    else:
        # identificador de clase
        cur = T_CLASS(base)

    # sufijos []
    while i < len(txt):
        if i + 1 < len(txt) and txt[i] == "[" and txt[i + 1] == "]":
            cur = T_ARRAY(cur)
            i = i + 2
        else:
            break
    return cur

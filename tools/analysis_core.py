# tools/analysis_core.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- Asegura que podamos importar src/antlr/... --
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener

from antlr.parser.generated.CompiscriptLexer import CompiscriptLexer
from antlr.parser.generated.CompiscriptParser import CompiscriptParser

from antlr.sema.ast_builder import ASTBuilder
from antlr.sema.astviz import DotBuilder
from antlr.sema.checker import Checker
from antlr.sema.types import Type, T_INT, T_STRING, is_func, is_void, is_string, is_int


# Utilidades SIN re/strip
def _is_space(ch: str) -> bool:
    return ch == " " or ch == "\t" or ch == "\r" or ch == "\n"


# quita espacios al inicio y final sin usar strip()
def _trim_manual(s: str) -> str:
    n = len(s)
    i = 0
    while i < n and _is_space(s[i]):
        i += 1
    j = n - 1
    while j >= i and _is_space(s[j]):
        j -= 1
    # evita s[i:j+1] si j < i (cadena vacía)
    if j < i:
        return ""
    return s[i : j + 1]


# divide cadena en líneas sin usar splitlines()
def _split_lines_manual(s: str) -> List[str]:
    out: List[str] = []
    cur_chars: List[str] = []
    for ch in s:
        if ch == "\n" or ch == "\r":
            out.append("".join(cur_chars))
            cur_chars = []
            # no intentamos detectar \r\n en particular; ambas separan
        else:
            cur_chars.append(ch)
    out.append("".join(cur_chars))
    return out


#   cuenta ocurrencias de un carácter sin usar count()
def _count_char(s: str, ch: str) -> int:
    c = 0
    for x in s:
        if x == ch:
            c += 1
    return c


#  busca subcadena sin usar find() o index()
def _index_of(s: str, sub: str, start: int = 0) -> int:
    n = len(s)
    m = len(sub)
    i = start
    while i <= n - m:
        k = 0
        ok = True
        while k < m:
            if s[i + k] != sub[k]:
                ok = False
                break
            k += 1
        if ok:
            return i
        i += 1
    return -1


# busca subcadena sin usar find() o index()
def _contains(s: str, sub: str) -> bool:
    return _index_of(s, sub, 0) >= 0


# extrae texto entre dos subcadenas sin usar re
def _extract_between(s: str, after: str, before: str) -> str:
    i = _index_of(s, after, 0)
    if i < 0:
        return ""
    i = i + len(after)
    j = _index_of(s, before, i)
    if j < 0:
        return ""
    return s[i:j]


# is dígitos sin usar re
def _is_digits(s: str) -> bool:
    if len(s) == 0:
        return False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch < "0" or ch > "9":
            return False
        i += 1
    return True


# is cadena entre comillas sin usar re
def _is_quoted_string(s: str) -> bool:
    return (len(s) >= 2) and (s[0] == '"') and (s[len(s) - 1] == '"')


# Infra de errores léx/sintax (ANTLR)
class CollectingErrorListener(ErrorListener):
    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.errors: List[Dict[str, Any]] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(
            {"kind": self.kind, "line": int(line), "col": int(column), "message": msg}
        )


# Serialización (símbolos/func/clase)
def _type_str(t: Optional[Type]) -> Optional[str]:
    return str(t) if t is not None else None


# serialize función a dict
def _serialize_function(fsym) -> Dict[str, Any]:
    params = []
    i = 0
    while i < len(fsym.params):
        p = fsym.params[i]
        params.append({"name": p.name, "type": _type_str(p.typ)})
        i += 1
    caps = []
    j = 0
    while j < len(fsym.captures):
        caps.append(fsym.captures[j].name)
        j += 1
    return {
        "name": fsym.name,
        "return": _type_str(fsym.return_type),
        "params": params,
        "isMethod": bool(getattr(fsym, "is_method", False)),
        "captures": caps,
        "builtin": bool(getattr(fsym, "is_builtin", False)),
    }


# serialize clase a dict
def _serialize_class(env, csym) -> Dict[str, Any]:
    fields = []
    methods = []
    for mname, msym in csym.members.items():
        if msym.kind == "field":
            fields.append({"name": mname, "type": _type_str(msym.typ)})
        elif msym.kind == "func":
            methods.append(_serialize_function(msym))

    # heredados
    inherited: List[Dict[str, Any]] = []
    visited = {}
    bname = getattr(csym, "base_name", None)
    while bname and (bname not in visited):
        visited[bname] = True
        base = env.resolve_class(bname)
        if base is None:
            break
        for mname, msym in base.members.items():
            if mname not in csym.members:
                inherited.append(
                    {
                        "from": base.name,
                        "member": mname,
                        "kind": msym.kind,
                        "type": _type_str(
                            msym.typ if msym.kind == "field" else msym.return_type
                        ),
                    }
                )
        bname = getattr(base, "base_name", None)

    return {
        "name": csym.name,
        "base": getattr(csym, "base_name", None),
        "fields": fields,
        "methods": methods,
        "ctor": _serialize_function(csym.ctor) if csym.ctor else None,
        "inherited": inherited,
    }


# snapshot de símbolos globales a dict
def snapshot_symbols(checker: Checker) -> Dict[str, Any]:
    env = checker.env
    g = env.global_scope.table
    gl_vars, gl_consts, gl_funcs, gl_classes = [], [], [], []

    for name, sym in g.items():
        if sym.kind == "var":
            gl_vars.append({"name": name, "type": _type_str(sym.typ)})
        elif sym.kind == "const":
            gl_consts.append(
                {"name": name, "type": _type_str(sym.typ), "initialized": sym.inited}
            )
        elif sym.kind == "func":
            gl_funcs.append(_serialize_function(sym))
        elif sym.kind == "class":
            gl_classes.append(_serialize_class(env, sym))

    return {
        "globals": {
            "vars": gl_vars,
            "consts": gl_consts,
            "functions": gl_funcs,
            "classes": gl_classes,
        }
    }


# Tokens / Hover
def collect_tokens(ts: CommonTokenStream) -> List[Dict[str, Any]]:
    toks = []
    if ts.tokens is None:
        return toks
    i = 0
    while i < len(ts.tokens):
        t = ts.tokens[i]
        if t.type != -1:
            toks.append(
                {
                    "text": t.text,
                    "line": t.line,
                    "col": t.column,
                    "start": t.start,
                    "stop": t.stop,
                    "type": t.type,
                }
            )
        i += 1
    return toks


# busca token en posición (línea, columna)
def find_token_at(ts: CommonTokenStream, line: int, col: int):
    if ts.tokens is None:
        return None
    i = 0
    while i < len(ts.tokens):
        t = ts.tokens[i]
        if t.line == line:
            # longitud segura
            length = 0
            if t.start is not None and t.stop is not None:
                length = t.stop - t.start + 1
            elif t.text is not None:
                length = len(t.text)
            if length < 1:
                length = 1
            if col >= t.column and col < (t.column + length):
                return t
        i += 1
    return None


# hover en posición (línea, columna)
def hover_at(code: str, line: int, col: int) -> Dict[str, Any]:
    # prepara lexer/parser para tokens
    input_stream = InputStream(code)
    lex = CompiscriptLexer(input_stream)
    ts = CommonTokenStream(lex)
    parser = CompiscriptParser(ts)
    tree = parser.program()

    # checker para symbols globales
    ast = ASTBuilder().visit(tree)
    checker = Checker()
    checker.run(ast)

    tok = find_token_at(ts, line, col)
    if tok is None or tok.text is None:
        return {"token": None, "kind": None, "type": None}

    text = tok.text
    if _is_digits(text):
        return {"token": text, "kind": "Literal", "type": str(T_INT())}
    if _is_quoted_string(text):
        return {"token": text, "kind": "Literal", "type": str(T_STRING())}

    sym, _ = checker.env.resolve(text)
    if sym is not None:
        if sym.kind == "var" or sym.kind == "const" or sym.kind == "param":
            return {"token": text, "kind": sym.kind, "type": _type_str(sym.typ)}
        if sym.kind == "func":
            return {
                "token": text,
                "kind": "function",
                "type": _type_str(sym.return_type),
            }
        if sym.kind == "class":
            return {"token": text, "kind": "class", "type": "class"}
    return {"token": text, "kind": "identifier", "type": None}


# Análisis principal
def analyze_internal(
    code: str,
    include_ast: bool = True,
    include_symbols: bool = True,
    include_tokens: bool = False,
) -> Dict[str, Any]:
    input_stream = InputStream(code)
    lex = CompiscriptLexer(input_stream)
    lex_err = CollectingErrorListener("lexer")
    lex.removeErrorListeners()
    lex.addErrorListener(lex_err)

    ts = CommonTokenStream(lex)
    parser = CompiscriptParser(ts)
    parse_err = CollectingErrorListener("parser")
    parser.removeErrorListeners()
    parser.addErrorListener(parse_err)

    tree = parser.program()

    ast = ASTBuilder().visit(tree)
    checker = Checker()
    checker.run(ast)

    dot = DotBuilder().build(ast) if include_ast else None

    out: Dict[str, Any] = {
        "syntaxErrors": lex_err.errors + parse_err.errors,
        "semanticErrors": checker.errors,
        "astDot": dot if include_ast else None,
        "symbols": snapshot_symbols(checker) if include_symbols else None,
        "tokens": collect_tokens(ts) if include_tokens else None,
    }
    return out


# Quick-Fixes sin regex
def _class_members_from_symbols(symbols: Dict[str, Any], cls_name: str) -> List[str]:
    gl = symbols.get("globals", {})
    classes = gl.get("classes", []) if isinstance(gl, dict) else []
    i = 0
    while i < len(classes):
        c = classes[i]
        if c.get("name", "") == cls_name:
            names: List[str] = []
            f = c.get("fields", [])
            j = 0
            while j < len(f):
                names.append(f[j].get("name", ""))
                j += 1
            m = c.get("methods", [])
            j = 0
            while j < len(m):
                names.append(m[j].get("name", ""))
                j += 1
            inh = c.get("inherited", [])
            j = 0
            while j < len(inh):
                names.append(inh[j].get("member", ""))
                j += 1
            # eliminar duplicados conservando orden
            out: List[str] = []
            seen = {}
            k = 0
            while k < len(names):
                nm = names[k]
                if nm not in seen:
                    out.append(nm)
                    seen[nm] = True
                k += 1
            return out
        i += 1
    return []


# Quick-Fixes sin regex
def suggest_fixes(
    code: str, sem_errors: List[str], symbols: Dict[str, Any]
) -> List[Dict[str, Any]]:
    fixes: List[Dict[str, Any]] = []

    def _add_info(
        title: str, detail: str, line: Optional[int] = None, col: Optional[int] = None
    ):
        fixes.append(
            {"kind": "info", "title": title, "detail": detail, "line": line, "col": col}
        )

    def _parse_loc_prefix(msg: str):
        # Espera: "[l:c] resto..." → devuelve (l, c, resto)
        if (len(msg) >= 4) and (msg[0] == "["):
            # busca ":" y "]"
            i = 1
            # leer número línea
            lnum = 0
            while i < len(msg) and msg[i] >= "0" and msg[i] <= "9":
                lnum = lnum * 10 + (ord(msg[i]) - ord("0"))
                i += 1
            if i < len(msg) and msg[i] == ":":
                i += 1
                cnum = 0
                while i < len(msg) and msg[i] >= "0" and msg[i] <= "9":
                    cnum = cnum * 10 + (ord(msg[i]) - ord("0"))
                    i += 1
                if i < len(msg) and msg[i] == "]":
                    i += 1
                    # salta espacio si hay
                    if i < len(msg) and msg[i] == " ":
                        i += 1
                    rest = msg[i:] if i < len(msg) else ""
                    return lnum, cnum, rest
        return None, None, msg

    i = 0
    while i < len(sem_errors):
        e = sem_errors[i]
        line, col, msg = _parse_loc_prefix(e)

        if _contains(msg, "Uso de variable no declarada: '"):
            var = _extract_between(msg, "Uso de variable no declarada: '", "'")
            _add_info(
                "Variable no declarada",
                "Sugerencia: declara `let " + var + " = /* valor */;` antes de su uso.",
                line,
                col,
            )

        if _contains(msg, "Const '") and _contains(msg, "requiere inicialización"):
            cname = _extract_between(msg, "Const '", "'")
            _add_info(
                "Const sin inicializar",
                "Sugerencia: agrega `const " + cname + " : T = /* valor */;`.",
                line,
                col,
            )

        if _contains(msg, "Operación '%'"):
            _add_info(
                "Uso de '%'", "El operador '%' requiere `integer % integer`.", line, col
            )

        if _contains(msg, "Operación aritmética requiere numéricos"):
            _add_info(
                "Aritmética inválida",
                "Verifica numéricos en ambos operandos (o `string+any` para '+').",
                line,
                col,
            )

        if _contains(msg, "Comparación incompatible"):
            _add_info(
                "Comparación incompatible",
                "Compara tipos compatibles (numérico-numérico, mismo tipo o referencia vs null).",
                line,
                col,
            )

        if _contains(msg, "debe ser boolean"):
            _add_info(
                "Condición no booleana",
                "Convierte la condición a boolean, p. ej. `expr != 0` o `expr == true`.",
                line,
                col,
            )

        if _contains(msg, "Miembro '") and _contains(msg, "' no existe en clase "):
            mem = _extract_between(msg, "Miembro '", "'")
            pos = _index_of(msg, " no existe en clase ", 0)
            cls = msg[pos + len(" no existe en clase ") :] if pos >= 0 else ""
            cand = _class_members_from_symbols(symbols, cls)
            if len(cand) > 0:
                _add_info(
                    "Miembro inexistente",
                    "En '"
                    + cls
                    + "' no existe '"
                    + mem
                    + "'. Disponibles: "
                    + ", ".join(cand)
                    + ".",
                    line,
                    col,
                )
            else:
                _add_info(
                    "Miembro inexistente",
                    "En '"
                    + cls
                    + "' no existe '"
                    + mem
                    + "'. Revisa definición o herencia.",
                    line,
                    col,
                )

        if _contains(msg, "Constructor de '"):
            cls = _extract_between(msg, "Constructor de '", "'")
            _add_info(
                "Constructor",
                "Define `function constructor(...) { ... }` en la clase '"
                + cls
                + "' o ajusta argumentos.",
                line,
                col,
            )

        if _contains(msg, "Llamada a '") and _contains(
            msg, "con argumentos incompatibles"
        ):
            fname = _extract_between(msg, "Llamada a '", "'")
            _add_info(
                "Llamada incompatible",
                "Ajusta tipos/número de argumentos de '" + fname + "' o su firma.",
                line,
                col,
            )

        if _contains(msg, "Tipo de return incompatible"):
            _add_info(
                "Return incompatible",
                "Devuelve un valor del tipo declarado o cambia el tipo de retorno.",
                line,
                col,
            )

        if _contains(msg, "Uso de 'this' fuera de un método de clase"):
            _add_info(
                "this inválido",
                "Usa `this` solo en métodos/constructor de clase.",
                line,
                col,
            )

        i += 1

    return fixes


# Formateador sin strip/regex
def format_code(code: str) -> str:
    lines = _split_lines_manual(code)
    IND = "  "  # 2 espacios
    indent = 0
    out: List[str] = []

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = _trim_manual(raw)
        # si la línea empieza con '}', dedenta antes
        starts_close = len(line) > 0 and line[0] == "}"
        if starts_close and indent > 0:
            indent -= 1

        # emite línea con indent
        buf = []
        j = 0
        while j < indent:
            buf.append(IND)
            j += 1
        buf.append(line)
        out.append("".join(buf))

        # ajusta indent con cuenta de llaves
        opens = _count_char(line, "{")
        closes = _count_char(line, "}")
        indent = indent + opens - closes
        if indent < 0:
            indent = 0

        i += 1

    # Unir con '\n' (no es strip)
    return "\n".join(out)

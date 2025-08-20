# app.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
import time

# -----------------------------
# Detección robusta del ROOT
# -----------------------------
def _find_project_root() -> Path:
    p = Path(__file__).resolve().parent
    steps = 0
    while steps < 5:
        has_src = (p / "src").exists()
        has_tests = (p / "tests").exists()
        has_examples = (p / "examples").exists()
        has_tools = (p / "tools").exists()
        if has_src or has_tests or has_examples or has_tools:
            return p
        p = p.parent
        steps += 1
    return Path(__file__).resolve().parent

ROOT = _find_project_root()
SRC = ROOT / "src"
TOOLS = ROOT / "tools"

# Solo importa si NO está en sys.path (no revisamos sys.argv)
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from analysis_core import analyze_internal, suggest_fixes, hover_at  # noqa
# Para mostrar nombres de tokens:
from antlr.parser.generated.CompiscriptLexer import CompiscriptLexer  # noqa

# -----------------------------
# Estilos y estado base
# -----------------------------
st.set_page_config(page_title="VSCompi+", layout="wide")

if "editor_nonce" not in st.session_state:
    st.session_state.editor_nonce = 0
if "code" not in st.session_state:
    st.session_state.code = 'function main(): integer { print("Hola"); return 0; }'
if "last_sample" not in st.session_state:
    st.session_state.last_sample = "(ninguno)"

st.markdown(
    """
    <style>
      :root {
        --bg:#0f172a; --panel:#111827; --muted:#1f2937;
        --acc:#22c55e; --acc2:#06b6d4; --warn:#f59e0b; --err:#ef4444;
        --txt:#e5e7eb; --sub:#9ca3af;
      }
      .main > div { background: var(--bg); }
      header, .st-emotion-cache-18ni7ap { background: var(--panel) !important; }
      .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5 { color: var(--txt); }
      .title { padding:8px 14px; border-radius:10px;
               background: linear-gradient(90deg, var(--acc), var(--acc2));
               color:#0b1220; font-weight:800; display:inline-block; letter-spacing:.3px; }
      .panel { background:var(--panel); border:1px solid var(--muted);
               border-radius:14px; padding:14px; box-shadow:0 1px 12px rgba(0,0,0,.18); }
      .ok   { background: rgba(34,197,94,.15); border-left:4px solid var(--acc); padding:10px; border-radius:8px; }
      .warn { background: rgba(245,158,11,.15); border-left:4px solid var(--warn); padding:10px; border-radius:8px; }
      .err  { background: rgba(239,68,68,.15); border-left:4px solid var(--err);  padding:10px; border-radius:8px; }
      .metric-box { background:linear-gradient(180deg, rgba(31,41,55,.6), rgba(17,24,39,.6));
                    border:1px solid var(--muted); border-radius:12px; padding:12px; text-align:center; }
      .metric-val { font-size:22px; font-weight:800; color:var(--txt); }
      .metric-lbl { font-size:12px; color:var(--sub); letter-spacing:.3px; }
      .stTabs [data-baseweb="tab"] { color:var(--txt); }
      .stTabs [data-baseweb="tab-highlight"] { background: linear-gradient(90deg, rgba(34,197,94,.25), rgba(6,182,212,.25)); }
      .stDataFrame { border-radius:12px; overflow:hidden; }
      .stTextArea textarea { background:#0b1220 !important; color:var(--txt) !important; border-radius:12px !important; }
      .stButton > button { background: linear-gradient(180deg, #1f2937, #111827);
                           border:1px solid #243244; color:var(--txt); border-radius:10px; padding:.45rem .9rem; }
      .stButton > button:hover { border-color:#2f415a; }
      .statusbar { margin-top:6px; display:flex; gap:16px; align-items:center; justify-content:flex-end;
                   background:var(--panel); border:1px solid var(--muted); border-radius:10px; padding:6px 10px; }
      .statusitem { color:var(--sub); font-size:12px; }
      .statusitem .val { color:var(--txt); font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title">VSCompi+</div>', unsafe_allow_html=True)
st.caption("IDE ligera para Compiscript — diagnósticos, AST, símbolos, quick-fixes y hover")

# -----------------------------
# Sidebar: selector de .cps + toggles
# -----------------------------
tests_dir = ROOT / "tests"
examples_dir = ROOT / "examples"

def _list_cps() -> List[str]:
    items: List[str] = []
    if tests_dir.exists():
        for p in sorted(tests_dir.rglob("*.cps")):
            if p.is_file():
                items.append(str(p.relative_to(ROOT)).replace("\\", "/"))
    if examples_dir.exists():
        for p in sorted(examples_dir.rglob("*.cps")):
            if p.is_file():
                rel = str(p.relative_to(ROOT)).replace("\\", "/")
                # evita duplicados
                exists = False
                for s in items:
                    if s == rel:
                        exists = True
                        break
                if not exists:
                    items.append(rel)
    return items

samples = ["(ninguno)"] + _list_cps()
st.sidebar.subheader("Abrir archivo de pruebas")
sel_sample = st.sidebar.selectbox("Archivo (.cps):", samples, index=0)

auto_analyze = st.sidebar.checkbox("Analizar automáticamente", value=True)
show_tokens  = st.sidebar.checkbox("Mostrar tokens", value=False)
show_ast     = st.sidebar.checkbox("Mostrar AST (Graphviz)", value=True)
show_symbols = st.sidebar.checkbox("Mostrar Tabla de Símbolos", value=True)
show_quickfix= st.sidebar.checkbox("Mostrar Quick-fixes", value=True)
hide_builtins= st.sidebar.checkbox("Ocultar funciones built-in", value=True)

# Selección de archivo → cargar
if sel_sample != st.session_state.last_sample:
    try:
        if sel_sample != "(ninguno)":
            st.session_state.code = (ROOT / sel_sample).read_text(encoding="utf-8")
        st.session_state.last_sample = sel_sample
        st.session_state.editor_nonce += 1
        if sel_sample != "(ninguno)":
            st.success("Cargado: " + sel_sample)
    except Exception as ex:
        st.sidebar.error("No se pudo cargar: " + str(ex))

# -----------------------------
# Helpers mini (sin regex/strip)
# -----------------------------
def _parse_sem_line(msg: str):
    if (len(msg) >= 4) and (msg[0] == "["):
        i = 1; lnum = 0
        while i < len(msg) and msg[i].isdigit():
            lnum = lnum * 10 + (ord(msg[i]) - 48); i += 1
        if i < len(msg) and msg[i] == ":":
            i += 1; cnum = 0
            while i < len(msg) and msg[i].isdigit():
                cnum = cnum * 10 + (ord(msg[i]) - 48); i += 1
            if i < len(msg) and msg[i] == "]":
                i += 1
                if i < len(msg) and msg[i] == " ": i += 1
                return {"line": lnum, "col": cnum, "message": msg[i:] if i < len(msg) else ""}
    return {"line": None, "col": None, "message": msg}

def _to_int(x: Any, default_val: int) -> int:
    if isinstance(x, (int, float)): return int(x)
    if isinstance(x, str):
        i, n, seen = 0, 0, False
        while i < len(x) and x[i].isdigit():
            n = n*10 + (ord(x[i]) - 48); i += 1; seen = True
        if seen: return n
    return default_val

def _tolower(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        out.append(chr(o+32) if 65 <= o <= 90 else ch)
    return "".join(out)

def _is_semantic_label(lbl: str) -> bool:
    t = _tolower(lbl)
    return ("sem" in t) or ("type" in t) or ("typing" in t) or ("name" in t) or ("symbol" in t)

def _is_syntax_label(lbl: str) -> bool:
    t = _tolower(lbl)
    return ("lex" in t) or ("parse" in t) or ("syntax" in t) or ("lexer" in t) or ("parser" in t)

def _norm_diag_from_dict(e: Dict[str, Any], default_kind: str) -> Dict[str, Any]:
    line, col, msg, kind = 1, 0, "", default_kind
    for k in ("kind","category","type","phase"):
        v = e.get(k);  kind = v if isinstance(v,str) and v else kind
    for k in ("message","msg","text","detail","description","reason"):
        v = e.get(k);  msg = v if isinstance(v,str) else msg
    for k in ("line","lineno","row","l","startLine"):
        v = e.get(k)
        if v is not None: line = _to_int(v, line); break
    for k in ("col","column","character","ch","startCol","startColumn"):
        v = e.get(k)
        if v is not None: col = _to_int(v, col); break
    for pk in ("pos","loc","position","start"):
        p = e.get(pk)
        if isinstance(p, dict):
            line = _to_int(p.get("line", p.get("row", line)), line)
            col  = _to_int(p.get("col", p.get("column", col)), col)
    rng = e.get("range")
    if isinstance(rng, dict):
        stt = rng.get("start")
        if isinstance(stt, dict):
            line = _to_int(stt.get("line", line), line)
            col  = _to_int(stt.get("column", col), col)
    return {"kind": kind, "line": int(line), "col": int(col), "message": msg}

def _norm_diag(e: Any, default_kind: str) -> Dict[str, Any]:
    if isinstance(e, dict): return _norm_diag_from_dict(e, default_kind)
    if isinstance(e, str):
        tmp = _parse_sem_line(e); l = tmp.get("line", None)
        if l is not None:
            return {"kind": default_kind, "line": int(tmp["line"]), "col": int(tmp["col"]), "message": tmp["message"]}
        return {"kind": default_kind, "line": 1, "col": 0, "message": e}
    return {"kind": default_kind, "line": 1, "col": 0, "message": ""}

def _collect_diagnostics(res: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    lexsyn: List[Dict[str, Any]] = []; sem: List[Dict[str, Any]] = []
    if not isinstance(res, dict): return {"lexsyn": lexsyn, "sem": sem}
    syntax_keys = ["syntaxErrors","parseErrors","parserErrors","lexErrors","lexerErrors","lexicalErrors","syntaxDiagnostics"]
    sem_keys    = ["semanticErrors","semErrors","semanticDiagnostics","typeErrors","nameErrors","analysisErrors"]
    for k in syntax_keys:
        v = res.get(k)
        if isinstance(v, list):
            j=0
            while j < len(v):
                lexsyn.append(_norm_diag(v[j], k)); j+=1
        elif isinstance(v,(dict,str)):
            lexsyn.append(_norm_diag(v, k))
    for k in sem_keys:
        v = res.get(k)
        if isinstance(v, list):
            j=0
            while j < len(v):
                sem.append(_norm_diag(v[j], k)); j+=1
        elif isinstance(v,(dict,str)):
            sem.append(_norm_diag(v, k))
    for dk in ("diagnostics","errors"):
        dlst = res.get(dk)
        if isinstance(dlst, list):
            for e in dlst:
                if isinstance(e, dict):
                    picked = None
                    for name in ("kind","category","type","phase"):
                        v = e.get(name)
                        if isinstance(v,str) and v: picked = v; break
                    picked = picked or "diagnostic"
                    if _is_semantic_label(picked):
                        sem.append(_norm_diag(e, picked))
                    elif _is_syntax_label(picked):
                        lexsyn.append(_norm_diag(e, picked))
                    else:
                        lexsyn.append(_norm_diag(e, picked))
                elif isinstance(e, str):
                    lexsyn.append(_norm_diag(e, "diagnostic"))
    return {"lexsyn": lexsyn, "sem": sem}

def _count_list(lst) -> int:
    c = 0
    for _ in lst: c += 1
    return c

def _join_params(plist: List[Dict[str, Any]]) -> str:
    if plist is None: return ""
    parts: List[str] = []
    i = 0
    while i < len(plist):
        p = plist[i]
        nm = p.get("name",""); tp = p.get("type","unknown") or "unknown"
        parts.append(nm + ":" + tp)
        i += 1
    # join manual (sin .join podría ser demasiado)
    out = ""
    i = 0
    while i < len(parts):
        if i > 0: out = out + ", "
        out = out + parts[i]
        i += 1
    return out

def _tok_type_name(tid: int) -> str:
    names = getattr(CompiscriptLexer, "symbolicNames", None)
    if isinstance(names, list) and (tid is not None) and (tid >= 0) and (tid < len(names)):
        nm = names[tid]
        if isinstance(nm, str) and len(nm) > 0:
            return nm
    return str(tid)

# -----------------------------
# Layout: Editor + Panel
# -----------------------------
left, right = st.columns([1.1, 0.9])

with left:
    st.subheader("Código")
    # Editor básico: cada cambio hace rerun → si 'Analizar automáticamente' está ON, reanaliza
    st.text_area("Fuente Compiscript", key="code", height=380, label_visibility="collapsed")

    # Barra de estado (líneas y caracteres)
    num_lines = st.session_state.code.count("\n") + 1 if st.session_state.code else 1
    num_chars = len(st.session_state.code or "")
    st.markdown(
        f'<div class="statusbar">'
        f'<span class="statusitem">Editor: <span class="val">básico</span></span>'
        f'<span class="statusitem">Líneas: <span class="val">{num_lines}</span></span>'
        f'<span class="statusitem">Caracteres: <span class="val">{num_chars}</span></span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    # Solo botón "Analizar ahora" + leyenda
    c1, c2 = st.columns([1, 2])
    with c1:
        run_click = st.button("Analizar ahora")
    with c2:
        st.caption("Auto: si está activado en la barra lateral, analiza al teclear.")

with right:
    st.subheader("Panel")
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.write("Opciones rápidas")
    st.checkbox("Analizar automáticamente", value=auto_analyze, key="__aa",
                help="Si lo activas, cada edición re-analiza el código.")
    st.checkbox("Ocultar built-ins", value=hide_builtins, key="__hb",
                help="No mostrar funciones built-in (ej. print) en la tabla de símbolos.")
    st.markdown("</div>", unsafe_allow_html=True)

use_auto_flag = st.session_state.get("__aa", auto_analyze)
hide_builtins = st.session_state.get("__hb", hide_builtins)

# -----------------------------
# Análisis
# -----------------------------
result: Optional[Dict[str, Any]] = None
do_analyze = bool(run_click) or bool(use_auto_flag)

if do_analyze:
    try:
        result = analyze_internal(
            st.session_state.code,
            include_ast=show_ast,
            include_symbols=show_symbols,
            include_tokens=True,          # siempre recogemos tokens; los mostramos si el toggle está on
        )
    except Exception as ex:
        st.error("Error de análisis: " + str(ex))

# -----------------------------
# Resultados
# -----------------------------
lexsyn: List[Dict[str, Any]] = []
sem: List[Dict[str, Any]] = []
symbols: Dict[str, Any] = {}
gl: Dict[str, Any] = {}
tokens: List[Dict[str, Any]] = []

if result is not None:
    diags = _collect_diagnostics(result)
    lexsyn = diags["lexsyn"];  sem = diags["sem"]
    symbols = result.get("symbols", {}) or {}
    gl = symbols.get("globals", {}) if isinstance(symbols, dict) else {}
    tokens = result.get("tokens", []) or []

    # ---- MÉTRICAS (6 columnas) ----
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.markdown(
            f'<div class="metric-box"><div class="metric-val">{_count_list(lexsyn)}</div><div class="metric-lbl">Errores Léx/Sint</div></div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="metric-box"><div class="metric-val">{_count_list(sem)}</div><div class="metric-lbl">Errores Semánticos</div></div>',
            unsafe_allow_html=True,
        )
    with m3:
        vars_ = gl.get("vars", []) or []
        st.markdown(
            f'<div class="metric-box"><div class="metric-val">{_count_list(vars_)}</div><div class="metric-lbl">Variables</div></div>',
            unsafe_allow_html=True,
        )
    with m4:
        consts_ = gl.get("consts", []) or []
        st.markdown(
            f'<div class="metric-box"><div class="metric-val">{_count_list(consts_)}</div><div class="metric-lbl">Constantes</div></div>',
            unsafe_allow_html=True,
        )
    with m5:
        fns = (gl.get("functions", []) or [])
        if hide_builtins:
            tmp = []
            i = 0
            while i < len(fns):
                if not bool(fns[i].get("builtin", False)):
                    tmp.append(fns[i])
                i += 1
            fns = tmp
        st.markdown(
            f'<div class="metric-box"><div class="metric-val">{_count_list(fns)}</div><div class="metric-lbl">Funciones</div></div>',
            unsafe_allow_html=True,
        )
    with m6:
        clz = gl.get("classes", []) or []
        st.markdown(
            f'<div class="metric-box"><div class="metric-val">{_count_list(clz)}</div><div class="metric-lbl">Clases</div></div>',
            unsafe_allow_html=True,
        )

    tabs_labels = ["Diagnósticos"]
    if show_symbols: tabs_labels.append("Tabla de símbolos")
    if show_ast:     tabs_labels.append("AST")
    if show_quickfix: tabs_labels.append("Quick-fixes")
    if show_tokens:   tabs_labels.append("Tokens")
    tabs = st.tabs(tabs_labels)

    # ---- Diagnósticos + Hover práctico ----
    t = 0
    with tabs[t]:
        st.subheader("Errores léxicos/sintácticos")
        if _count_list(lexsyn) == 0:
            st.markdown('<div class="ok">Sin errores léxicos/sintácticos.</div>', unsafe_allow_html=True)
        else:
            st.dataframe(lexsyn, use_container_width=True)

        st.subheader("Errores semánticos")
        if _count_list(sem) == 0:
            st.markdown('<div class="ok">Sin errores semánticos.</div>', unsafe_allow_html=True)
        else:
            st.dataframe(sem, use_container_width=True)

        st.subheader("Hover")
        c1, c2 = st.columns(2)

        # A) Por línea/columna
        with c1:
            st.markdown("**Por línea/columna**")
            h_line = st.number_input("Línea (1-based)", min_value=1, value=1, step=1, key="hover_line")
            h_col  = st.number_input("Columna (0-based)", min_value=0, value=0, step=1, key="hover_col")
            if st.button("Consultar (línea/columna)"):
                try:
                    h = hover_at(st.session_state.code, int(h_line), int(h_col))
                    st.json(h)
                except Exception as ex:
                    st.error("Hover falló: " + str(ex))

        # B) RÁPIDO: por token
        with c2:
            st.markdown("**Rápido por token**")
            if len(tokens) == 0:
                st.info("No hay tokens disponibles (¿hay código?).")
            else:
                # Construir opciones legibles
                token_opts: List[str] = []
                i = 0
                while i < len(tokens):
                    tkn = tokens[i]
                    txt = tkn.get("text","")
                    ln  = tkn.get("line",1)
                    cl  = tkn.get("col",0)
                    tn  = _tok_type_name(int(tkn.get("type", -1)))
                    token_opts.append("#"+str(i)+"  '"+str(txt)+"'  - "+str(ln)+":"+str(cl)+"  ("+tn+")")
                    i += 1
                idx = st.selectbox(
                    "Selecciona un token",
                    options=list(range(len(token_opts))),
                    format_func=lambda k: token_opts[k] if k < len(token_opts) else "(n/a)"
                )
                if st.button("Consultar (token seleccionado)"):
                    if 0 <= idx < len(tokens):
                        ln = int(tokens[idx].get("line", 1)); cl = int(tokens[idx].get("col", 0))
                        try:
                            h = hover_at(st.session_state.code, ln, cl)
                            st.json(h)
                        except Exception as ex:
                            st.error("Hover falló: " + str(ex))

            # C) Por texto exacto (primera coincidencia)
            st.markdown("**Buscar por texto**")
            q = st.text_input("Texto del token (exacto)", value="")
            if st.button("Consultar (por texto)"):
                found = None
                i = 0
                while i < len(tokens):
                    if tokens[i].get("text","") == q:
                        found = tokens[i]; break
                    i += 1
                if found is None:
                    st.warning("No se encontró ese token.")
                else:
                    ln = int(found.get("line", 1)); cl = int(found.get("col", 0))
                    try:
                        h = hover_at(st.session_state.code, ln, cl)
                        st.json(h)
                    except Exception as ex:
                        st.error("Hover falló: " + str(ex))
    t += 1

    # ---- Tabla de símbolos ----
    if show_symbols:
        with tabs[t]:
            st.subheader("Tabla de Símbolos (global)")
            st.markdown("**Variables**")
            st.dataframe(gl.get("vars", []) or [], use_container_width=True)

            st.markdown("**Constantes**")
            st.dataframe(gl.get("consts", []) or [], use_container_width=True)

            st.markdown("**Funciones**")
            funs = gl.get("functions", []) or []
            rows: List[Dict[str, Any]] = []
            i = 0
            while i < len(funs):
                f = funs[i]
                if hide_builtins and bool(f.get("builtin", False)):
                    i += 1; continue
                rows.append({
                    "name": f.get("name",""),
                    "return": f.get("return",""),
                    "params": _join_params(f.get("params", [])),
                    "captures": ", ".join(f.get("captures", [])),
                    "method?": "yes" if f.get("isMethod", False) else "no",
                    "builtin?": "yes" if f.get("builtin", False) else "no",
                })
                i += 1
            st.dataframe(rows, use_container_width=True)

            st.markdown("**Clases**")
            clzs = gl.get("classes", []) or []
            crows: List[Dict[str, Any]] = []
            i = 0
            while i < len(clzs):
                c = clzs[i]
                fields = c.get("fields", []) or []
                methods = c.get("methods", []) or []
                crows.append({"name": c.get("name",""), "base": c.get("base", None),
                              "#fields": _count_list(fields), "#methods": _count_list(methods)})
                i += 1
            st.dataframe(crows, use_container_width=True)

            st.markdown("**Detalle por clase**")
            i = 0
            while i < len(clzs):
                c = clzs[i]
                with st.expander("Clase " + c.get("name", "(sin nombre)")):
                    st.markdown("*Base*: " + (c.get("base","—") or "—"))
                    st.markdown("**Campos**");  st.dataframe(c.get("fields", []) or [], use_container_width=True)
                    st.markdown("**Métodos**")
                    mrows: List[Dict[str, Any]] = []
                    ms = c.get("methods", []) or []
                    j=0
                    while j < len(ms):
                        m = ms[j]
                        mrows.append({"name": m.get("name",""), "return": m.get("return",""),
                                      "params": _join_params(m.get("params", [])),
                                      "captures": ", ".join(m.get("captures", []))})
                        j+=1
                    st.dataframe(mrows, use_container_width=True)
                    if c.get("inherited", []):
                        st.markdown("**Miembros heredados**")
                        st.dataframe(c.get("inherited", []), use_container_width=True)
                i += 1
    t += 1 if show_symbols else 0

    # ---- AST ----
    if show_ast:
        with tabs[t]:
            st.subheader("Árbol sintáctico (AST)")
            dot = result.get("astDot")
            if dot:
                try:
                    st.graphviz_chart(dot)
                except Exception:
                    st.code(dot, language="dot")
                st.download_button("Descargar DOT", data=dot, file_name="ast.dot", mime="text/vnd.graphviz")
            else:
                st.info("AST no solicitado / vacío.")
    t += 1 if show_ast else 0

    # ---- Quick-fixes ----
    if show_quickfix:
        with tabs[t]:
            st.subheader("Sugerencias (quick-fixes)")
            # Pasamos los errores semánticos normalizados al formato que espera suggest_fixes
            sem_msgs: List[str] = []
            i = 0
            while i < len(sem):
                d = sem[i]; ln = d.get("line", 1); cl = d.get("col", 0); ms = d.get("message", "")
                sem_msgs.append("[" + str(int(ln)) + ":" + str(int(cl)) + "] " + (ms or ""))
                i += 1
            fixes = suggest_fixes(st.session_state.code, sem_msgs, result.get("symbols", {}) or {})
            if _count_list(fixes) == 0:
                st.markdown('<div class="ok">No hay sugerencias.</div>', unsafe_allow_html=True)
            else:
                st.dataframe(fixes, use_container_width=True)
    t += 1 if show_quickfix else 0

    # ---- Tokens ----
    if show_tokens:
        with tabs[t]:
            st.subheader("Tokens (depuración)")
            # Enriquecemos con el nombre simbólico del tipo
            rows: List[Dict[str, Any]] = []
            i = 0
            while i < len(tokens):
                tkn = tokens[i]
                rows.append({
                    "text": tkn.get("text",""),
                    "line": tkn.get("line",1),
                    "col":  tkn.get("col",0),
                    "start": tkn.get("start", None),
                    "stop":  tkn.get("stop",  None),
                    "type":  tkn.get("type",  None),
                    "typeName": _tok_type_name(int(tkn.get("type", -1))),
                })
                i += 1
            st.dataframe(rows, use_container_width=True)

st.caption("VSCompi+ — Compiscript • Streamlit UI")

# app.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
import time

# --- Rutas ---
ROOT = Path(__file__).resolve().parents[0]
SRC = ROOT / "src"
if str(SRC) not in sys.argv and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.argv and str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from analysis_core import analyze_internal, suggest_fixes, hover_at, format_code  # noqa

# -----------------------------
# Estilos y estado base
# -----------------------------
st.set_page_config(page_title="VSCompi+", layout="wide")

if "editor_nonce" not in st.session_state:
    st.session_state.editor_nonce = 0  # por si futuras acciones quieren re‑montar el editor
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

      .title {
        padding:8px 14px; border-radius:10px;
        background: linear-gradient(90deg, var(--acc), var(--acc2));
        color:#0b1220; font-weight:800; display:inline-block; letter-spacing:.3px;
      }

      .panel {
        background:var(--panel); border:1px solid var(--muted);
        border-radius:14px; padding:14px; box-shadow:0 1px 12px rgba(0,0,0,.18);
      }

      .ok   { background: rgba(34,197,94,.15); border-left:4px solid var(--acc); padding:10px; border-radius:8px; }
      .warn { background: rgba(245,158,11,.15); border-left:4px solid var(--warn); padding:10px; border-radius:8px; }
      .err  { background: rgba(239,68,68,.15); border-left:4px solid var(--err);  padding:10px; border-radius:8px; }

      .metric-box {
        background:linear-gradient(180deg, rgba(31,41,55,.6), rgba(17,24,39,.6));
        border:1px solid var(--muted); border-radius:12px; padding:12px; text-align:center;
      }
      .metric-val { font-size:22px; font-weight:800; color:var(--txt); }
      .metric-lbl { font-size:12px; color:var(--sub); letter-spacing:.3px; }

      .stTabs [data-baseweb="tab"] { color:var(--txt); }
      .stTabs [data-baseweb="tab-highlight"] {
        background: linear-gradient(90deg, rgba(34,197,94,.25), rgba(6,182,212,.25));
      }
      .stDataFrame { border-radius:12px; overflow:hidden; }
      .stTextArea textarea { background:#0b1220 !important; color:var(--txt) !important; border-radius:12px !important; }
      .stButton > button {
        background: linear-gradient(180deg, #1f2937, #111827);
        border:1px solid #243244; color:var(--txt); border-radius:10px; padding:.45rem .9rem;
      }
      .stButton > button:hover { border-color:#2f415a; }
      .statusbar {
        margin-top:6px; display:flex; gap:16px; align-items:center; justify-content:flex-end;
        background:var(--panel); border:1px solid var(--muted); border-radius:10px; padding:6px 10px;
      }
      .statusitem { color:var(--sub); font-size:12px; }
      .statusitem .val { color:var(--txt); font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title">VSCompi+</div>', unsafe_allow_html=True)
st.caption("IDE ligera para Compiscript — diagnósticos, AST, símbolos, quick‑fixes y hover")

# -----------------------------
# Sidebar: selector de archivos (tests/ y examples/) + toggles
# -----------------------------
tests_dir = ROOT / "tests"
examples_dir = ROOT / "examples"

def _list_cps() -> List[str]:
    """Devuelve rutas relativas a ROOT de todos los .cps en tests/ y examples/ (recursivo)."""
    items: List[str] = []
    if tests_dir.exists():
        for p in sorted(tests_dir.rglob("*.cps")):
            if p.is_file():
                items.append(str(p.relative_to(ROOT)).replace("\\", "/"))
    if examples_dir.exists():
        for p in sorted(examples_dir.rglob("*.cps")):
            if p.is_file():
                rel = str(p.relative_to(ROOT)).replace("\\", "/")
                if rel not in items:
                    items.append(rel)
    return items

samples = ["(ninguno)"] + _list_cps()

st.sidebar.subheader("Abrir archivo de pruebas")
sel_sample = st.sidebar.selectbox("Archivo (.cps):", samples, index=0)

auto_analyze = st.sidebar.checkbox("Analizar automáticamente", value=True)
show_tokens = st.sidebar.checkbox("Mostrar tokens", value=False)
show_ast = st.sidebar.checkbox("Mostrar AST (Graphviz)", value=True)
show_symbols = st.sidebar.checkbox("Mostrar Tabla de Símbolos", value=True)
show_quickfix = st.sidebar.checkbox("Mostrar Quick‑fixes", value=True)
hide_builtins = st.sidebar.checkbox("Ocultar funciones built‑in", value=True)

# Cambió el archivo seleccionado → cargarlo
if sel_sample != st.session_state.last_sample:
    try:
        if sel_sample != "(ninguno)":
            st.session_state.code = (ROOT / sel_sample).read_text(encoding="utf-8")
        st.session_state.last_sample = sel_sample
        st.session_state.editor_nonce += 1
        st.success(f"Cargado: {sel_sample}") if sel_sample != "(ninguno)" else None
    except Exception as ex:
        st.sidebar.error("No se pudo cargar: " + str(ex))

# -----------------------------
# Helpers mínimos
# -----------------------------
def _parse_sem_line(msg: str):
    if (len(msg) >= 4) and (msg[0] == "["):
        i = 1
        lnum = 0
        while i < len(msg) and msg[i].isdigit():
            lnum = lnum * 10 + (ord(msg[i]) - ord("0"))
            i += 1
        if i < len(msg) and msg[i] == ":":
            i += 1
            cnum = 0
            while i < len(msg) and msg[i].isdigit():
                cnum = cnum * 10 + (ord(msg[i]) - ord("0"))
                i += 1
            if i < len(msg) and msg[i] == "]":
                i += 1
                if i < len(msg) and msg[i] == " ":
                    i += 1
                txt = msg[i:] if i < len(msg) else ""
                return {"line": lnum, "col": cnum, "message": txt}
    return {"line": None, "col": None, "message": msg}

def _to_int(x: Any, default_val: int) -> int:
    if isinstance(x, (int, float)): return int(x)
    if isinstance(x, str):
        i, n, seen = 0, 0, False
        while i < len(x) and x[i].isdigit():
            n = n*10 + (ord(x[i])-48); i += 1; seen = True
        if seen: return n
    return default_val

def _tolower(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        out.append(chr(o + 32) if 65 <= o <= 90 else ch)
    return "".join(out)

def _norm_diag_from_dict(e: Dict[str, Any], default_kind: str) -> Dict[str, Any]:
    line, col, msg, kind = 1, 0, "", default_kind
    for k in ("kind","category","type","phase"):
        v = e.get(k);  kind = v if isinstance(v,str) and v else kind
    for k in ("message","msg","text","detail","description","reason"):
        v = e.get(k);  msg = v if isinstance(v,str) else msg
    for k in ("line","lineno","row","l","startLine"):
        v = e.get(k);  line = _to_int(v, line) if v is not None else line
        if v is not None: break
    for k in ("col","column","character","ch","startCol","startColumn"):
        v = e.get(k);  col = _to_int(v, col) if v is not None else col
        if v is not None: break
    for pk in ("pos","loc","position","start"):
        p = e.get(pk)
        if isinstance(p, dict):
            line = _to_int(p.get("line", p.get("row", line)), line)
            col  = _to_int(p.get("col",  p.get("column", col)), col)
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

def _is_semantic_label(lbl: str) -> bool:
    t = _tolower(lbl)
    return ("sem" in t) or ("type" in t) or ("typing" in t) or ("name" in t) or ("symbol" in t)

def _is_syntax_label(lbl: str) -> bool:
    t = _tolower(lbl)
    return ("lex" in t) or ("parse" in t) or ("syntax" in t) or ("lexer" in t) or ("parser" in t)

def _collect_diagnostics(res: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    lexsyn: List[Dict[str, Any]] = [];  sem: List[Dict[str, Any]] = []
    if not isinstance(res, dict): return {"lexsyn": lexsyn, "sem": sem}
    syntax_keys = ["syntaxErrors","parseErrors","parserErrors","lexErrors","lexerErrors","lexicalErrors","syntaxDiagnostics"]
    sem_keys    = ["semanticErrors","semErrors","semanticDiagnostics","typeErrors","nameErrors","analysisErrors"]
    for k in syntax_keys:
        v = res.get(k)
        if isinstance(v, list):   lexsyn.extend([_norm_diag(x, k) for x in v])
        elif isinstance(v,(dict,str)): lexsyn.append(_norm_diag(v, k))
    for k in sem_keys:
        v = res.get(k)
        if isinstance(v, list):   sem.extend([_norm_diag(x, k) for x in v])
        elif isinstance(v,(dict,str)): sem.append(_norm_diag(v, k))
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
                    (sem if _is_semantic_label(picked) else lexsyn).append(_norm_diag(e, picked))
                elif isinstance(e, str):
                    lexsyn.append(_norm_diag(e, "diagnostic"))
    return {"lexsyn": lexsyn, "sem": sem}

def _count_list(lst) -> int:
    c = 0
    for _ in lst: c += 1
    return c

def _join_params(plist: List[Dict[str, Any]]) -> str:
    if plist is None: return ""
    parts = []
    for p in plist:
        nm = p.get("name",""); tp = p.get("type","unknown") or "unknown"
        parts.append(f"{nm}:{tp}")
    return ", ".join(parts)

# -----------------------------
# Layout superior: Editor + Panel
# -----------------------------
left, right = st.columns([1.1, 0.9])

with left:
    st.subheader("Código")

    # Editor básico (sin librerías externas)
    st.text_area("Fuente Compiscript", key="code", height=380, label_visibility="collapsed")

    # Barra de estado (no hay cursor: mostramos líneas y caracteres)
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

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("Formatear"):
            try:
                st.session_state.code = format_code(st.session_state.code)
                st.success("Código formateado.")
            except Exception as ex:
                st.error("Error de formateo: " + str(ex))
    with c2:
        run_click = st.button("Analizar ahora")
    with c3:
        st.caption("Auto: si está activado en la barra lateral, analiza al teclear.")

with right:
    st.subheader("Panel")
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.write("Opciones rápidas")
    st.checkbox("Analizar automáticamente", value=auto_analyze, key="__aa", help="Refleja el estado de la barra lateral")
    st.checkbox("Ocultar built‑ins", value=hide_builtins, key="__hb", help="No mostrar funciones built‑in como 'print'")
    st.markdown("</div>", unsafe_allow_html=True)

# Usar SIEMPRE lo del panel derecho si existe
use_auto_flag = st.session_state.get("__aa", auto_analyze)
hide_builtins = st.session_state.get("__hb", hide_builtins)

# -----------------------------
# Análisis (AST / símbolos / etc.)
# -----------------------------
result: Optional[Dict[str, Any]] = None
do_analyze = bool(run_click) or bool(use_auto_flag)

if do_analyze:
    try:
        result = analyze_internal(
            st.session_state.code,
            include_ast=show_ast,
            include_symbols=show_symbols,
            include_tokens=show_tokens,
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

if result is not None:
    # Normaliza y separa diagnósticos
    diags = _collect_diagnostics(result)
    lexsyn = diags["lexsyn"];  sem = diags["sem"]

    symbols = result.get("symbols", {}) or {}
    gl = symbols.get("globals", {}) if isinstance(symbols, dict) else {}

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f'<div class="metric-box"><div class="metric-val">{_count_list(lexsyn)}</div><div class="metric-lbl">Léx/Sint</div></div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="metric-box"><div class="metric-val">{_count_list(sem)}</div><div class="metric-lbl">Semánticos</div></div>',
            unsafe_allow_html=True,
        )
    with m3:
        fns = (gl.get("functions", []) or [])
        if hide_builtins:
            fns = [f for f in fns if not bool(f.get("builtin", False))]
        st.markdown(
            f'<div class="metric-box"><div class="metric-val">{_count_list(fns)}</div><div class="metric-lbl">Funciones</div></div>',
            unsafe_allow_html=True,
        )
    with m4:
        clz = gl.get("classes", []) or []
        st.markdown(
            f'<div class="metric-box"><div class="metric-val">{_count_list(clz)}</div><div class="metric-lbl">Clases</div></div>',
            unsafe_allow_html=True,
        )

    tabs_labels = ["Diagnósticos"]
    if show_symbols: tabs_labels.append("Tabla de símbolos")
    if show_ast:     tabs_labels.append("AST")
    if show_quickfix: tabs_labels.append("Quick‑fixes")
    if show_tokens:   tabs_labels.append("Tokens")
    tabs = st.tabs(tabs_labels)

    # --- Diagnósticos ---
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

        st.subheader("Hover (línea/columna)")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            h_line = st.number_input("Línea (1‑based)", min_value=1, value=1, step=1)
        with c2:
            h_col = st.number_input("Columna (0‑based)", min_value=0, value=0, step=1)
        with c3:
            if st.button("Consultar Hover"):
                try:
                    h = hover_at(st.session_state.code, int(h_line), int(h_col))
                    st.json(h)
                except Exception as ex:
                    st.error("Hover falló: " + str(ex))
    t += 1

    # --- Tabla de símbolos ---
    if show_symbols:
        with tabs[t]:
            st.subheader("Tabla de Símbolos (global)")
            st.markdown("**Variables**")
            st.dataframe(gl.get("vars", []) or [], use_container_width=True)

            st.markdown("**Constantes**")
            st.dataframe(gl.get("consts", []) or [], use_container_width=True)

            st.markdown("**Funciones**")
            funs = gl.get("functions", []) or []
            rows = []
            for f in funs:
                if hide_builtins and bool(f.get("builtin", False)):  # ocultar built‑ins
                    continue
                rows.append(
                    {
                        "name": f.get("name", ""),
                        "return": f.get("return", ""),
                        "params": _join_params(f.get("params", [])),
                        "captures": ", ".join(f.get("captures", [])),
                        "method?": "yes" if f.get("isMethod", False) else "no",
                        "builtin?": "yes" if f.get("builtin", False) else "no",
                    }
                )
            st.dataframe(rows, use_container_width=True)

            st.markdown("**Clases**")
            clzs = gl.get("classes", []) or []
            crows = []
            for c in clzs:
                fields = c.get("fields", []) or []
                methods = c.get("methods", []) or []
                crows.append(
                    {
                        "name": c.get("name", ""),
                        "base": c.get("base", None),
                        "#fields": _count_list(fields),
                        "#methods": _count_list(methods),
                    }
                )
            st.dataframe(crows, use_container_width=True)

            st.markdown("**Detalle por clase**")
            for c in clzs:
                with st.expander("Clase " + c.get("name", "(sin nombre)")):
                    st.markdown("*Base*: " + (c.get("base", "—") or "—"))
                    st.markdown("**Campos**")
                    st.dataframe(c.get("fields", []) or [], use_container_width=True)
                    st.markdown("**Métodos**")
                    mrows = []
                    for m in (c.get("methods", []) or []):
                        mrows.append(
                            {
                                "name": m.get("name", ""),
                                "return": m.get("return", ""),
                                "params": _join_params(m.get("params", [])),
                                "captures": ", ".join(m.get("captures", [])),
                            }
                        )
                    st.dataframe(mrows, use_container_width=True)
                    if c.get("inherited", []):
                        st.markdown("**Miembros heredados**")
                        st.dataframe(c.get("inherited", []), use_container_width=True)
    t += 1 if show_symbols else 0

    # --- AST ---
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

    # --- Quick‑fixes ---
    if show_quickfix:
        with tabs[t]:
            st.subheader("Sugerencias (quick‑fixes)")
            sem_msgs: List[str] = []
            for d in sem:
                ln = d.get("line", 1); cl = d.get("col", 0); ms = d.get("message", "")
                sem_msgs.append(f"[{int(ln)}:{int(cl)}] {ms or ''}")
            fixes = suggest_fixes(st.session_state.code, sem_msgs, result.get("symbols", {}) or {})
            if _count_list(fixes) == 0:
                st.markdown('<div class="ok">No hay sugerencias.</div>', unsafe_allow_html=True)
            else:
                st.dataframe(fixes, use_container_width=True)
    t += 1 if show_quickfix else 0

    # --- Tokens ---
    if show_tokens:
        with tabs[t]:
            st.subheader("Tokens (depuración)")
            st.json(result.get("tokens", []) or [])

st.caption("VSCompi+ — Compiscript • Streamlit UI")

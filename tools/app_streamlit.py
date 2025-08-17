# tools/app_streamlit.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# --- Rutas ---
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from analysis_core import analyze_internal, suggest_fixes, hover_at, format_code

# -------------------------------------------------
# Intentar usar un editor con eventos (caret/gutter)
# -------------------------------------------------
try:
    # Paquete: streamlit-code-editor  -> módulo: code_editor
    from code_editor import code_editor

    HAS_CODE_EDITOR = True
    CODE_EDITOR_FLAVOR = "code_editor"
except Exception:
    try:
        # Algunos forks/alias publican este nombre
        from streamlit_code_editor import code_editor

        HAS_CODE_EDITOR = True
        CODE_EDITOR_FLAVOR = "streamlit_code_editor"
    except Exception:
        HAS_CODE_EDITOR = False
        CODE_EDITOR_FLAVOR = None

# -----------------------------
# Estilos (sin libs externas)
# -----------------------------
st.set_page_config(page_title="VSCompi+", layout="wide")

st.markdown(
    """
    <style>
      :root {
        --bg: #0f172a;          /* slate-900 */
        --panel: #111827;       /* gray-900 */
        --muted: #1f2937;       /* gray-800 */
        --acc: #22c55e;         /* green-500 */
        --acc2: #06b6d4;        /* cyan-500 */
        --warn: #f59e0b;        /* amber-500 */
        --err: #ef4444;         /* red-500 */
        --txt: #e5e7eb;         /* gray-200 */
        --sub: #9ca3af;         /* gray-400 */
      }
      .main > div { background: var(--bg); }
      header, .st-emotion-cache-18ni7ap { background: var(--panel) !important; }
      .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5 { color: var(--txt); }
      .title { padding: 8px 14px; border-radius: 8px;
        background: linear-gradient(90deg, var(--acc), var(--acc2));
        color: black; font-weight: 700; display: inline-block; }
      .panel { background: var(--panel); border: 1px solid var(--muted); border-radius: 12px; padding: 12px; }
      .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px;
        background: var(--muted); color: var(--txt); margin-left: 6px; }
      .ok { background: rgba(34,197,94,0.2); border-left: 4px solid var(--acc); padding: 8px; border-radius: 6px; }
      .warn { background: rgba(245,158,11,0.15); border-left: 4px solid var(--warn); padding: 8px; border-radius: 6px; }
      .err { background: rgba(239,68,68,0.15); border-left: 4px solid var(--err); padding: 8px; border-radius: 6px; }
      .micro { color: var(--sub); font-size: 12px; }
      .metric-box { background: var(--muted); border-radius: 8px; padding: 10px; text-align: center; }
      .metric-val { font-size: 22px; font-weight: 800; color: var(--txt); }
      .metric-lbl { font-size: 12px; color: var(--sub); }
      .stTabs [data-baseweb="tab"] { color: var(--txt); }
      .stTextArea textarea { background: #0b1220 !important; color: var(--txt) !important; }
      /* marcador visual para líneas con error (editor externo) */
      .ace_error-marker { position: absolute; background: rgba(239,68,68,0.15); z-index: 5; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title">VSCompi+</div>', unsafe_allow_html=True)
st.caption(
    "IDE ligera para Compiscript — diagnósticos, AST, símbolos, quick‑fixes y hover"
)

# -----------------------------
# Sidebar: ejemplos y opciones
# -----------------------------
examples_dir = ROOT / "examples"
example_files: List[str] = []
if examples_dir.exists():
    for p in sorted(examples_dir.iterdir()):
        if p.is_file() and p.suffix == ".cps":
            example_files.append(p.name)

st.sidebar.subheader("Archivos de ejemplo")
sel_example = st.sidebar.selectbox(
    "Abrir ejemplo:", ["(ninguno)"] + example_files, index=0
)

auto_analyze = st.sidebar.checkbox("Analizar automáticamente", value=True)
show_tokens = st.sidebar.checkbox("Mostrar tokens", value=False)
show_ast = st.sidebar.checkbox("Mostrar AST (Graphviz)", value=True)
show_symbols = st.sidebar.checkbox("Mostrar Tabla de Símbolos", value=True)
show_quickfix = st.sidebar.checkbox("Mostrar Quick‑fixes", value=True)
hide_builtins = st.sidebar.checkbox("Ocultar funciones built‑in", value=True)

# -----------------------------
# Estado editor (una sola key)
# -----------------------------
if "code" not in st.session_state:
    st.session_state.code = 'function main(): integer { print("Hola"); return 0; }'
if "last_example" not in st.session_state:
    st.session_state.last_example = "(ninguno)"
if "cursor" not in st.session_state:
    st.session_state.cursor = {"row": 0, "column": 0}  # 0‑based internamente

# cargar ejemplo solo si cambió
if sel_example != st.session_state.last_example:
    try:
        if sel_example != "(ninguno)":
            st.session_state.code = (examples_dir / sel_example).read_text(
                encoding="utf-8"
            )
        st.session_state.last_example = sel_example
    except Exception as ex:
        st.sidebar.error("No se pudo cargar el ejemplo: " + str(ex))


# -----------------------------
# Helpers locales sin regex/strip
# -----------------------------
def _parse_sem_line(msg: str):
    # "[l:c] texto..."
    if (len(msg) >= 4) and (msg[0] == "["):
        i = 1
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
                if i < len(msg) and msg[i] == " ":
                    i += 1
                txt = msg[i:] if i < len(msg) else ""
                return {"line": lnum, "col": cnum, "message": txt}
    return {"line": None, "col": None, "message": msg}


def _count_list(lst):
    c, i = 0, 0
    while i < len(lst):
        c += 1
        i += 1
    return c


def _join_params(plist: List[Dict[str, Any]]) -> str:
    if plist is None:
        return ""
    parts, i = [], 0
    while i < len(plist):
        nm = plist[i].get("name", "")
        tp = plist[i].get("type", "unknown") or "unknown"
        parts.append(nm + ":" + tp)
        i += 1
    s, j = "", 0
    while j < len(parts):
        if j > 0:
            s = s + ", "
        s = s + parts[j]
        j += 1
    return s


def _ace_annotations(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Ace usa filas 0‑based
    anns: List[Dict[str, Any]] = []
    if res is None:
        return anns
    se = res.get("syntaxErrors", []) or []
    i = 0
    while i < len(se):
        e = se[i]
        anns.append(
            {
                "row": int(e.get("line", 1)) - 1,
                "column": int(e.get("col", 0)),
                "type": "error",
                "text": "[parser] " + (e.get("message") or ""),
            }
        )
        i += 1
    s2 = res.get("semanticErrors", []) or []
    i = 0
    while i < len(s2):
        l, c, msg = None, None, s2[i]
        if (len(msg) >= 4) and (msg[0] == "["):
            tmp = _parse_sem_line(msg)
            l, c, msg = tmp["line"], tmp["col"], tmp["message"]
        if l is None:
            l, c = 1, 0
        anns.append({"row": int(l) - 1, "column": int(c), "type": "error", "text": msg})
        i += 1
    return anns


def _cursor_from_response(resp: Dict[str, Any]) -> Optional[Dict[str, int]]:
    # Varios wrappers devuelven la posición en claves distintas: intentamos varias
    # Preferimos resp["cursor"] -> {"row":..,"column":..}
    cur = resp.get("cursor", None)
    if isinstance(cur, dict) and ("row" in cur) and ("column" in cur):
        return {"row": int(cur["row"]), "column": int(cur["column"])}
    # Algunos devuelven resp["selection"]["cursor"]
    sel = resp.get("selection", None)
    if isinstance(sel, dict):
        c = sel.get("cursor", None)
        if isinstance(c, dict) and ("row" in c) and ("column" in c):
            return {"row": int(c["row"]), "column": int(c["column"])}
    # Otros devuelven "selections": [ { "cursor": {...} } ]
    sels = resp.get("selections", None)
    if isinstance(sels, list) and len(sels) > 0 and isinstance(sels[0], dict):
        c = sels[0].get("cursor", None)
        if isinstance(c, dict) and ("row" in c) and ("column" in c):
            return {"row": int(c["row"]), "column": int(c["column"])}
    return None


# -----------------------------
# Layout superior: editor + métricas
# -----------------------------
left, right = st.columns([1.1, 0.9])

with left:
    st.subheader("Código")

    # -- Bloque de análisis previo a editor para anotar errores
    pending_result: Optional[Dict[str, Any]] = None

    # Si analizamos "al tipear", primero ejecutamos análisis rápido con el texto actual
    if auto_analyze:
        try:
            pending_result = analyze_internal(
                st.session_state.code,
                include_ast=False,
                include_symbols=False,
                include_tokens=False,
            )
        except Exception:
            pending_result = None

    annotations = _ace_annotations(pending_result) if pending_result else []

    # ---------- EDITOR ----------
    ce_resp = None
    if HAS_CODE_EDITOR:
        # Intento con anotaciones; si la firma no acepta, caemos sin anotaciones
        try:
            ce_resp = code_editor(
                st.session_state.code,
                lang="text",
                height=380,
                theme="material-one-dark",
                focus=True,
                key="code_editor",
                options={
                    "wrap": True,
                    "showGutter": True,
                    "showLineNumbers": True,
                    "highlightActiveLine": True,
                    "tabSize": 2,
                    "useSoftTabs": True,
                    "minLines": 18,
                },
                annotations=annotations,  # subraya errores
            )
        except TypeError:
            # Algunas versiones no soportan 'annotations' como arg separado
            ce_resp = code_editor(
                st.session_state.code,
                lang="text",
                height=380,
                theme="material-one-dark",
                focus=True,
                key="code_editor",
                options={
                    "wrap": True,
                    "showGutter": True,
                    "showLineNumbers": True,
                    "highlightActiveLine": True,
                    "tabSize": 2,
                    "useSoftTabs": True,
                    "minLines": 18,
                },
            )

        if isinstance(ce_resp, dict):
            # Actualizar código y cursor (dinámico)
            new_code = ce_resp.get("text", st.session_state.code)
            if new_code is not None:
                st.session_state.code = new_code
            cur = _cursor_from_response(ce_resp)
            if cur is not None:
                st.session_state.cursor = cur
    else:
        # Fallback: text_area (sin gutter/cursor en vivo)
        st.text_area(
            "Fuente Compiscript", key="code", height=360, label_visibility="collapsed"
        )

    # Barra de estado con Lín./col. (1‑based al mostrar)
    row = st.session_state.cursor.get("row", 0)
    col = st.session_state.cursor.get("column", 0)
    st.caption("**Lín. " + str(int(row) + 1) + ", col. " + str(int(col)) + "**")

    # Acciones
    a1, a2, a3 = st.columns([1, 1, 2])
    with a1:
        if st.button("Formatear"):
            try:
                st.session_state.code = format_code(st.session_state.code)
                st.success("Código formateado.")
            except Exception as ex:
                st.error("Error de formateo: " + str(ex))
    with a2:
        run_click = st.button("Analizar ahora")
    with a3:
        st.markdown(
            '<span class="micro">Auto: analiza al teclear si está activado.</span>',
            unsafe_allow_html=True,
        )

with right:
    st.subheader("Panel")
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.write("Opciones rápidas")
    st.checkbox(
        "Analizar automáticamente",
        value=auto_analyze,
        key="__aa",
        help="Refleja el estado de la barra lateral",
    )
    st.checkbox(
        "Ocultar built‑ins",
        value=hide_builtins,
        key="__hb",
        help="No mostrar funciones built‑in como 'print'",
    )
    if not HAS_CODE_EDITOR:
        st.warning(
            "Instala 'streamlit-code-editor' para ver **números de línea** y **posición de cursor**.\n\n`pip install streamlit-code-editor`"
        )
    st.markdown("</div>", unsafe_allow_html=True)

do_analyze = (
    st.session_state.__aa if "__aa" in st.session_state else auto_analyze
) or run_click
hide_builtins = st.session_state.__hb if "__hb" in st.session_state else hide_builtins

# -----------------------------
# Análisis final (según toggle)
# -----------------------------
result: Optional[Dict[str, Any]] = None
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
if result is not None:
    # métricas rápidas
    lexsyn = result.get("syntaxErrors", []) or []
    sem = result.get("semanticErrors", []) or []
    symbols = result.get("symbols", {}) or {}
    gl = symbols.get("globals", {}) if isinstance(symbols, dict) else {}

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            '<div class="metric-box"><div class="metric-val">%d</div><div class="metric-lbl">Léx/Sint</div></div>'
            % _count_list(lexsyn),
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            '<div class="metric-box"><div class="metric-val">%d</div><div class="metric-lbl">Semánticos</div></div>'
            % _count_list(sem),
            unsafe_allow_html=True,
        )
    with m3:
        fns = gl.get("functions", []) or []
        if hide_builtins:
            tmp = []
            i = 0
            while i < len(fns):
                if not bool(fns[i].get("builtin", False)):
                    tmp.append(fns[i])
                i += 1
            fns = tmp
        st.markdown(
            '<div class="metric-box"><div class="metric-val">%d</div><div class="metric-lbl">Funciones</div></div>'
            % _count_list(fns),
            unsafe_allow_html=True,
        )
    with m4:
        clz = gl.get("classes", []) or []
        st.markdown(
            '<div class="metric-box"><div class="metric-val">%d</div><div class="metric-lbl">Clases</div></div>'
            % _count_list(clz),
            unsafe_allow_html=True,
        )

    # Pestañas
    tabs_labels = ["Diagnósticos"]
    if show_symbols:
        tabs_labels.append("Tabla de símbolos")
    if show_ast:
        tabs_labels.append("AST")
    if show_quickfix:
        tabs_labels.append("Quick‑fixes")
    if show_tokens:
        tabs_labels.append("Tokens")
    tabs = st.tabs(tabs_labels)

    # --- Diagnósticos ---
    t = 0
    with tabs[t]:
        st.subheader("Errores léxicos/sintácticos")
        lexsyn_rows = lexsyn  # {kind,line,col,message}
        if _count_list(lexsyn_rows) == 0:
            st.markdown(
                '<div class="ok">Sin errores léxicos/sintácticos.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.dataframe(lexsyn_rows, use_container_width=True)

        st.subheader("Errores semánticos")
        sem_rows: List[Dict[str, Any]] = []
        i = 0
        while i < len(sem):
            sem_rows.append(_parse_sem_line(sem[i]))
            i += 1
        if _count_list(sem_rows) == 0:
            st.markdown(
                '<div class="ok">Sin errores semánticos.</div>', unsafe_allow_html=True
            )
        else:
            st.dataframe(sem_rows, use_container_width=True)

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
            # variables
            st.markdown("**Variables**")
            st.dataframe(gl.get("vars", []) or [], use_container_width=True)
            # consts
            st.markdown("**Constantes**")
            st.dataframe(gl.get("consts", []) or [], use_container_width=True)
            # funciones
            st.markdown("**Funciones**")
            funs = gl.get("functions", []) or []
            rows = []
            i = 0
            while i < len(funs):
                f = funs[i]
                if hide_builtins and bool(f.get("builtin", False)):
                    i += 1
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
                i += 1
            st.dataframe(rows, use_container_width=True)

            # clases
            st.markdown("**Clases**")
            clzs = gl.get("classes", []) or []
            crows = []
            i = 0
            while i < len(clzs):
                c = clzs[i]
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
                i += 1
            st.dataframe(crows, use_container_width=True)

            # detalle por clase
            st.markdown("**Detalle por clase**")
            i = 0
            while i < len(clzs):
                c = clzs[i]
                with st.expander("Clase " + c.get("name", "(sin nombre)")):
                    st.markdown("*Base*: " + (c.get("base", "—") or "—"))
                    st.markdown("**Campos**")
                    st.dataframe(c.get("fields", []) or [], use_container_width=True)
                    st.markdown("**Métodos**")
                    mrows, j = [], 0
                    methods = c.get("methods", []) or []
                    while j < len(methods):
                        m = methods[j]
                        mrows.append(
                            {
                                "name": m.get("name", ""),
                                "return": m.get("return", ""),
                                "params": _join_params(m.get("params", [])),
                                "captures": ", ".join(m.get("captures", [])),
                            }
                        )
                        j += 1
                    st.dataframe(mrows, use_container_width=True)
                    if c.get("inherited", []):
                        st.markdown("**Miembros heredados**")
                        st.dataframe(c.get("inherited", []), use_container_width=True)
                i += 1
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
                st.download_button(
                    "Descargar DOT",
                    data=dot,
                    file_name="ast.dot",
                    mime="text/vnd.graphviz",
                )
            else:
                st.info("AST no solicitado / vacío.")
    t += 1 if show_ast else 0

    # --- Quick‑fixes ---
    if show_quickfix:
        with tabs[t]:
            st.subheader("Sugerencias (quick‑fixes)")
            fixes = suggest_fixes(
                st.session_state.code,
                result.get("semanticErrors", []) or [],
                result.get("symbols", {}) or {},
            )
            if _count_list(fixes) == 0:
                st.markdown(
                    '<div class="ok">No hay sugerencias.</div>', unsafe_allow_html=True
                )
            else:
                st.dataframe(fixes, use_container_width=True)
    t += 1 if show_quickfix else 0

    # --- Tokens ---
    if show_tokens:
        with tabs[t]:
            st.subheader("Tokens (depuración)")
            st.json(result.get("tokens", []) or [])

st.caption("VSCompi+ — Compiscript • Streamlit UI")

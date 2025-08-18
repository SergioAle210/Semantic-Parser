from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import time

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
# Editor Ace vía streamlit-code-editor (dos sabores)
# -------------------------------------------------
HAS_CODE_EDITOR = False
CODE_EDITOR_FLAVOR = None
try:
    from code_editor import code_editor  # pip install streamlit-code-editor

    HAS_CODE_EDITOR = True
    CODE_EDITOR_FLAVOR = "code_editor"
except Exception:
    try:
        from streamlit_code_editor import code_editor

        HAS_CODE_EDITOR = True
        CODE_EDITOR_FLAVOR = "streamlit_code_editor"
    except Exception:
        HAS_CODE_EDITOR = False
        CODE_EDITOR_FLAVOR = None

# -----------------------------
# Estilos y estado base
# -----------------------------
st.set_page_config(page_title="VSCompi+", layout="wide")

# Estado UI inicial
if "live_cursor" not in st.session_state:
    st.session_state.live_cursor = False  # OFF por defecto para no interferir
if "editor_nonce" not in st.session_state:
    st.session_state.editor_nonce = 0

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

      .ace_error-marker { position:absolute; background: rgba(239,68,68,.15); z-index:5; }

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
st.caption(
    "IDE ligera para Compiscript — diagnósticos, AST, símbolos, quick‑fixes y hover"
)

# -----------------------------
# Sidebar: ejemplos y toggles
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

auto_analyze_sidebar = st.sidebar.checkbox("Analizar automáticamente", value=True)
show_tokens = st.sidebar.checkbox("Mostrar tokens", value=False)
show_ast = st.sidebar.checkbox("Mostrar AST (Graphviz)", value=True)
show_symbols = st.sidebar.checkbox("Mostrar Tabla de Símbolos", value=True)
show_quickfix = st.sidebar.checkbox("Mostrar Quick‑fixes", value=True)
hide_builtins_sidebar = st.sidebar.checkbox("Ocultar funciones built‑in", value=True)
editor_event_debug = st.sidebar.checkbox(
    "Depurar evento del editor (mostrar dict)", value=False
)

# -----------------------------
# Estado editor
# -----------------------------
if "code" not in st.session_state:
    st.session_state.code = 'function main(): integer { print("Hola"); return 0; }'
if "last_example" not in st.session_state:
    st.session_state.last_example = "(ninguno)"
if "cursor" not in st.session_state:
    st.session_state.cursor = {"row": 0, "column": 0}

# Al cambiar de ejemplo → re‑monta editor y resetea cursor
if sel_example != st.session_state.last_example:
    try:
        if sel_example != "(ninguno)":
            st.session_state.code = (examples_dir / sel_example).read_text(
                encoding="utf-8"
            )
        st.session_state.last_example = sel_example
        st.session_state.cursor = {"row": 0, "column": 0}
        st.session_state.editor_nonce += 1
    except Exception as ex:
        st.sidebar.error("No se pudo cargar el ejemplo: " + str(ex))


# -----------------------------
# Helpers (sin regex/strip)
# -----------------------------
def _parse_sem_line(msg: str):
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


# --------- utilidades de normalización (sin regex/strip) ----------
def _tolower(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        o = ord(ch)
        if o >= 65 and o <= 90:
            out.append(chr(o + 32))
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _to_int(x: Any, default_val: int) -> int:
    if isinstance(x, int):
        return int(x)
    if isinstance(x, float):
        return int(x)
    if isinstance(x, str):
        i, n, seen = 0, 0, False
        while i < len(x) and x[i] >= "0" and x[i] <= "9":
            n = n * 10 + (ord(x[i]) - ord("0"))
            seen = True
            i += 1
        if seen:
            return n
    return default_val


def _norm_diag_from_dict(e: Dict[str, Any], default_kind: str) -> Dict[str, Any]:
    line = 1
    col = 0
    msg = ""
    kind = default_kind

    # kind-like
    for k in ("kind", "category", "type", "phase"):
        v = e.get(k, None)
        if isinstance(v, str) and len(v) > 0:
            kind = v

    # message-like
    for k in ("message", "msg", "text", "detail", "description", "reason"):
        v = e.get(k, None)
        if isinstance(v, str):
            msg = v

    # line/col direct
    for k in ("line", "lineno", "row", "l", "startLine"):
        v = e.get(k, None)
        if v is not None:
            line = _to_int(v, line)
            break
    for k in ("col", "column", "character", "ch", "startCol", "startColumn"):
        v = e.get(k, None)
        if v is not None:
            col = _to_int(v, col)
            break

    # nested pos
    for pk in ("pos", "loc", "position", "start"):
        p = e.get(pk, None)
        if isinstance(p, dict):
            if ("line" in p) or ("row" in p):
                line = _to_int(p.get("line", p.get("row", line)), line)
            if ("col" in p) or ("column" in p):
                col = _to_int(p.get("col", p.get("column", col)), col)

    # range.start
    rng = e.get("range", None)
    if isinstance(rng, dict):
        stt = rng.get("start", None)
        if isinstance(stt, dict):
            line = _to_int(stt.get("line", line), line)
            col = _to_int(stt.get("column", col), col)

    return {"kind": kind, "line": int(line), "col": int(col), "message": msg}


def _norm_diag(e: Any, default_kind: str) -> Dict[str, Any]:
    if isinstance(e, dict):
        return _norm_diag_from_dict(e, default_kind)
    if isinstance(e, str):
        tmp = _parse_sem_line(e)
        l = tmp.get("line", None)
        if l is not None:
            return {
                "kind": default_kind,
                "line": int(tmp["line"]),
                "col": int(tmp["col"]),
                "message": tmp["message"],
            }
        return {"kind": default_kind, "line": 1, "col": 0, "message": e}
    # num/otro
    return {"kind": default_kind, "line": 1, "col": 0, "message": ""}


def _is_semantic_label(lbl: str) -> bool:
    t = _tolower(lbl)
    return (
        ("sem" in t)
        or ("type" in t)
        or ("typing" in t)
        or ("name" in t)
        or ("symbol" in t)
    )


def _is_syntax_label(lbl: str) -> bool:
    t = _tolower(lbl)
    return (
        ("lex" in t)
        or ("parse" in t)
        or ("syntax" in t)
        or ("lexer" in t)
        or ("parser" in t)
    )


def _collect_diagnostics(
    res: Optional[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Devuelve {"lexsyn":[{kind,line,col,message},...], "sem":[...]},
    unificando múltiples esquemas posibles del análisis.
    """
    lexsyn: List[Dict[str, Any]] = []
    sem: List[Dict[str, Any]] = []
    if not isinstance(res, dict):
        return {"lexsyn": lexsyn, "sem": sem}

    # 1) Claves conocidas por separado
    syntax_keys = [
        "syntaxErrors",
        "parseErrors",
        "parserErrors",
        "lexErrors",
        "lexerErrors",
        "lexicalErrors",
        "syntaxDiagnostics",
    ]
    sem_keys = [
        "semanticErrors",
        "semErrors",
        "semanticDiagnostics",
        "typeErrors",
        "nameErrors",
        "analysisErrors",
    ]

    i = 0
    while i < len(syntax_keys):
        k = syntax_keys[i]
        v = res.get(k, None)
        if isinstance(v, list):
            j = 0
            while j < len(v):
                lexsyn.append(_norm_diag(v[j], k))
                j += 1
        elif isinstance(v, dict) or isinstance(v, str):
            lexsyn.append(_norm_diag(v, k))
        i += 1

    i = 0
    while i < len(sem_keys):
        k = sem_keys[i]
        v = res.get(k, None)
        if isinstance(v, list):
            j = 0
            while j < len(v):
                sem.append(_norm_diag(v[j], k))
                j += 1
        elif isinstance(v, dict) or isinstance(v, str):
            sem.append(_norm_diag(v, k))
        i += 1

    # 2) Lista unificada 'diagnostics' o 'errors'
    for dk in ("diagnostics", "errors"):
        dlst = res.get(dk, None)
        if isinstance(dlst, list):
            j = 0
            while j < len(dlst):
                e = dlst[j]
                if isinstance(e, dict):
                    # decidir bucket
                    picked = None
                    for name in ("kind", "category", "type", "phase"):
                        v = e.get(name, None)
                        if isinstance(v, str) and len(v) > 0:
                            picked = v
                            break
                    if picked is None:
                        picked = "diagnostic"
                    if _is_semantic_label(picked):
                        sem.append(_norm_diag(e, picked))
                    elif _is_syntax_label(picked):
                        lexsyn.append(_norm_diag(e, picked))
                    else:
                        # si no sabemos, por defecto a léx/sint
                        lexsyn.append(_norm_diag(e, picked))
                elif isinstance(e, str):
                    # sin metadatos → por defecto léx/sint
                    lexsyn.append(_norm_diag(e, "diagnostic"))
                j += 1

    return {"lexsyn": lexsyn, "sem": sem}


def _ace_annotations_from_diags(
    lexsyn: List[Dict[str, Any]], sem: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    anns: List[Dict[str, Any]] = []
    i = 0
    while i < len(lexsyn):
        e = lexsyn[i]
        anns.append(
            {
                "row": int(e.get("line", 1)) - 1,
                "column": int(e.get("col", 0)),
                "type": "error",
                "text": "[syntax] " + (e.get("message") or ""),
            }
        )
        i += 1
    i = 0
    while i < len(sem):
        e = sem[i]
        anns.append(
            {
                "row": int(e.get("line", 1)) - 1,
                "column": int(e.get("col", 0)),
                "type": "error",
                "text": "[semantic] " + (e.get("message") or ""),
            }
        )
        i += 1
    return anns


def _cursor_from_response(resp: Dict[str, Any]) -> Optional[Dict[str, int]]:
    cur = resp.get("cursor", None)
    if isinstance(cur, dict) and ("row" in cur) and ("column" in cur):
        return {"row": int(cur["row"]), "column": int(cur["column"])}

    pos = resp.get("position", None)
    if isinstance(pos, dict) and ("row" in pos) and ("column" in pos):
        return {"row": int(pos["row"]), "column": int(pos["column"])}

    sel = resp.get("selection", None)
    if isinstance(sel, dict):
        c = sel.get("cursor", None)
        if isinstance(c, dict) and ("row" in c) and ("column" in c):
            return {"row": int(c["row"]), "column": int(c["column"])}
        stt = sel.get("start", None)
        if isinstance(stt, dict) and ("row" in stt) and ("column" in stt):
            return {"row": int(stt["row"]), "column": int(stt["column"])}
        end = sel.get("end", None)
        if isinstance(end, dict) and ("row" in end) and ("column" in end):
            return {"row": int(end["row"]), "column": int(end["column"])}

    sels = resp.get("selections", None)
    if isinstance(sels, list) and len(sels) > 0 and isinstance(sels[0], dict):
        c = sels[0].get("cursor", None)
        if isinstance(c, dict) and ("row" in c) and ("column" in c):
            return {"row": int(c["row"]), "column": int(c["column"])}
        stt = sels[0].get("start", None)
        if isinstance(stt, dict) and ("row" in stt) and ("column" in stt):
            return {"row": int(stt["row"]), "column": int(stt["column"])}
        end = sels[0].get("end", None)
        if isinstance(end, dict) and ("row" in end) and ("column" in end):
            return {"row": int(end["row"]), "column": int(end["column"])}

    r = resp.get("row", None)
    c = resp.get("column", None)
    if (r is not None) and (c is not None):
        return {"row": int(r), "column": int(c)}
    return None


def _extract_editor_text(resp: Dict[str, Any], default_text: str) -> str:
    keys = ["text", "content", "value", "code"]
    i = 0
    while i < len(keys):
        k = keys[i]
        if (k in resp) and isinstance(resp[k], str):
            return resp[k]
        i += 1
    return default_text


def _is_empty_event(resp: Dict[str, Any]) -> bool:
    textlike = ["text", "content", "value", "code"]
    i = 0
    while i < len(textlike):
        v = resp.get(textlike[i], None)
        if isinstance(v, str) and len(v) > 0:
            return False
        i += 1
    if resp.get("type", "") not in ("", None):
        return False
    for k in ("cursor", "position", "selection", "selections"):
        v = resp.get(k, None)
        if v not in (None, "", {}, []):
            return False
    return True


# -----------------------------
# Layout superior: editor + métricas
# -----------------------------
left, right = st.columns([1.1, 0.9])

run_click = False

with left:
    st.subheader("Código")

    # Pre‑análisis para anotaciones en el editor (cuando auto)
    pending_result: Optional[Dict[str, Any]] = None
    if auto_analyze_sidebar:
        try:
            pending_result = analyze_internal(
                st.session_state.code,
                include_ast=False,
                include_symbols=False,
                include_tokens=False,
            )
        except Exception:
            pending_result = None

    # Crear anotaciones desde el colector robusto
    _prev_diags = _collect_diagnostics(pending_result)
    annotations = _ace_annotations_from_diags(_prev_diags["lexsyn"], _prev_diags["sem"])

    # -------- EDITOR --------
    ce_resp: Optional[Dict[str, Any]] = None
    editor_key = f"code_editor_{st.session_state.editor_nonce}"

    if HAS_CODE_EDITOR:
        editor_options = {
            "wrap": True,
            "showGutter": True,
            "showLineNumbers": True,
            "highlightActiveLine": True,
            "tabSize": 2,
            "useSoftTabs": True,
            "minLines": 18,
            "showPrintMargin": False,
            "annotations": annotations,
            "errors": annotations,
        }
        try:
            ce_resp = code_editor(
                st.session_state.code,
                lang="text",
                height=380,
                theme="material-one-dark",
                focus=True,
                key=editor_key,
                options=editor_options,
                annotations=annotations,
            )
        except TypeError:
            ce_resp = code_editor(
                st.session_state.code,
                lang="text",
                height=380,
                theme="material-one-dark",
                focus=True,
                key=editor_key,
                options=editor_options,
            )

        if isinstance(ce_resp, dict) and (not _is_empty_event(ce_resp)):
            # 1) Buffer
            new_code = _extract_editor_text(ce_resp, st.session_state.code)
            if (new_code is not None) and (new_code != st.session_state.code):
                st.session_state.code = new_code
            # 2) Cursor
            cur = _cursor_from_response(ce_resp)
            if cur is not None:
                st.session_state.cursor = cur
            # 3) Debug opcional
            if editor_event_debug:
                with st.expander("Evento crudo del editor"):
                    st.write(ce_resp)
    else:
        st.text_area(
            "Fuente Compiscript", key="code", height=360, label_visibility="collapsed"
        )

    # Barra de estado
    row = st.session_state.cursor.get("row", 0)
    col = st.session_state.cursor.get("column", 0)
    st.markdown(
        f'<div class="statusbar">'
        f'<span class="statusitem">Editor: <span class="val">{CODE_EDITOR_FLAVOR or "fallback"}</span></span>'
        f'<span class="statusitem">Lín.: <span class="val">{int(row)+1}</span></span>'
        f'<span class="statusitem">Col.: <span class="val">{int(col)}</span></span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    st.checkbox(
        "Cursor en vivo (auto‑refresh ~200 ms)",
        value=st.session_state.live_cursor,
        key="live_cursor",
        help="Úsalo sólo si tu build del editor no emite eventos al mover el cursor.",
    )

    # Acciones
    a1, a2, a3 = st.columns([1, 1, 2])
    with a1:
        if st.button("Formatear"):
            try:
                st.session_state.code = format_code(st.session_state.code)
                st.session_state.editor_nonce += 1  # re‑montar tras formatear
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

    # Re‑montaje manual del editor (si ves desincronía)
    r1, r2, r3 = st.columns([1, 3, 3])
    with r1:
        if st.button(
            "🔄 Refrescar editor",
            key="refresh_editor",
            help="Fuerza re‑montar el componente del editor",
        ):
            st.session_state.editor_nonce += 1
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()

with right:
    st.subheader("Panel")
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.write("Opciones rápidas")
    st.checkbox(
        "Analizar automáticamente",
        value=auto_analyze_sidebar,
        key="__aa",
        help="Refleja el estado de la barra lateral",
    )
    st.checkbox(
        "Ocultar built‑ins",
        value=hide_builtins_sidebar,
        key="__hb",
        help="No mostrar funciones built‑in como 'print'",
    )
    if not HAS_CODE_EDITOR:
        st.warning(
            "Instala 'streamlit-code-editor' para ver **números de línea** y **posición de cursor**.\n\n`pip install streamlit-code-editor`"
        )
    st.markdown("</div>", unsafe_allow_html=True)

# Flags consolidados (usar SIEMPRE el estado del panel derecho si existe)
use_auto_flag = st.session_state.get("__aa", auto_analyze_sidebar)
hide_builtins = st.session_state.get("__hb", hide_builtins_sidebar)

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
    # Unificar diagnósticos aquí también
    diags = _collect_diagnostics(result)
    lexsyn = diags["lexsyn"]
    sem = diags["sem"]

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
        if _count_list(lexsyn) == 0:
            st.markdown(
                '<div class="ok">Sin errores léxicos/sintácticos.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.dataframe(lexsyn, use_container_width=True)

        st.subheader("Errores semánticos")
        if _count_list(sem) == 0:
            st.markdown(
                '<div class="ok">Sin errores semánticos.</div>', unsafe_allow_html=True
            )
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
            # Alimentar suggest_fixes con mensajes "[l:c] msg" a partir de los semánticos normalizados
            sem_msgs: List[str] = []
            i = 0
            while i < len(sem):
                d = sem[i]
                ln = d.get("line", 1)
                cl = d.get("col", 0)
                ms = d.get("message", "")
                sem_msgs.append(
                    "[" + str(int(ln)) + ":" + str(int(cl)) + "] " + (ms or "")
                )
                i += 1

            fixes = suggest_fixes(
                st.session_state.code,
                sem_msgs,
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

# -----------------------------
# Auto‑refresh del cursor (AL FINAL)
# -----------------------------
if st.session_state.live_cursor and HAS_CODE_EDITOR and (not run_click):
    time.sleep(0.2)
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()

st.caption("VSCompi+ — Compiscript • Streamlit UI")

# VSCompi+ — IDE

[![Video explicativo](https://img.shields.io/badge/YouTube-Video%20explicativo-red)](https://youtu.be/Kav2WP6vfyQ)

VSCompi+ es una interfaz en **Streamlit** para analizar código del lenguaje _Compiscript_.
Incluye **diagnósticos léxicos/sintácticos**, **chequeo semántico**, **tabla de símbolos**, **AST con Graphviz**, **hover** por posición/token y **quick-fixes** sugeridos. También muestra **métricas**: conteo de errores, **variables**, **constantes**, **funciones** y **clases**.

> ✅ Proyecto académico: pensado para visualizar rápidamente los resultados del compilador (lexer/parser/semántica) y depurar con ayuda visual.

---

## 👥 Integrantes

- Sergio Orellana — 221122
- Rodrigo Mansilla — 22611
- Andre Marroquin — 22266

---

## Tabla de contenido

- [Arquitectura](#arquitectura)
- [Instalación](#instalación)
- [Ejecutar la app](#ejecutar-la-app)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Cómo funciona cada módulo](#cómo-funciona-cada-módulo)
- [Tabla de símbolos](#tabla-de-símbolos)
- [Árbol de Sintaxis Abstracta (AST)](#árbol-de-sintaxis-abstracta-ast)
- [Reglas semánticas principales](#reglas-semánticas-principales)
- [Pruebas sugeridas](#pruebas-sugeridas)
- [Solución de problemas](#solución-de-problemas)
- [Roadmap](#roadmap)
- [Licencia](#licencia)

---

## Arquitectura

Flujo general:

1. **Entrada de código** en la UI (editor básico de Streamlit).
2. Llamada a `analysis_core.analyze_internal(...)` que:
   - Ejecuta **lexer/parser** para producir **tokens** y el **AST** (vía _builder_).
   - Ejecuta el **checker semántico** (pase de colección + pase de validación).
   - Construye la **tabla de símbolos** a partir del entorno (`Env`).
   - Genera el DOT del **AST** (para Graphviz).
3. La UI muestra en pestañas: **Diagnósticos**, **Símbolos**, **AST**, **Quick-fixes** y **Tokens**.

> La app detecta la raíz del proyecto y añade `src/` y `tools/` a `sys.path` para que los imports funcionen sin configurar PYTHONPATH manualmente.

---

## Instalación

Requisitos:

- Python 3.10+
- Paquetes: `streamlit`, `antlr4-python3-runtime`, `graphviz`
- **Graphviz** instalado en el sistema para renderizar DOT (CLI `dot`)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

pip install streamlit antlr4-python3-runtime graphviz

# Instalar Graphviz del sistema si falta:
# Debian/Ubuntu: sudo apt-get install graphviz
# macOS (Homebrew): brew install graphviz
```

---

## Ejecutar la app

Desde la raíz del proyecto:

```bash
streamlit run app.py
```

En la barra lateral puedes:

- Abrir archivos de **tests** o **examples**.
- Activar/desactivar: análisis automático, AST, tokens, quick-fixes, tabla de símbolos.
- Ocultar **built-ins** (p. ej., `print`) en la tabla de símbolos.

---

## Estructura del proyecto

```
.
├── app.py                  # UI de Streamlit (VSCompi+)
├── src/
│   ├── analysis_core.py    # Orquestación del pipeline de análisis
│   └── antlr/
│       ├── parser/         # Lexer/Parser (generados) y utilidades
│       └── sema/           # Semántica & AST
│           ├── ast.py
│           ├── ast_builder.py
│           ├── astviz.py
│           ├── checker.py
│           ├── symbols.py
│           └── types.py
├── tests/                  # Archivos .cps de prueba
└── examples/               # Ejemplos .cps
```

> Los nombres exactos pueden variar; la detección de raíz evita problemas de importación.

---

## Cómo funciona cada módulo

### `app.py` (Streamlit)

- Monta la UI, estilos y toggles.
- Gestiona el editor de código, carga de ejemplos y estado.
- Invoca `analyze_internal(...)` y muestra:
  - **Métricas** (errores léx/sint, semánticos, **variables**, **constantes**, **funciones**, **clases**).
  - Pestañas: **Diagnósticos**, **Tabla de símbolos**, **AST** (Graphviz), **Quick-fixes**, **Tokens**.
- Herramientas de **hover**: por línea/columna y por token.

### `analysis_core.py`

- Función central `analyze_internal(code, ...)` que:
  - Llama al **lexer/parser** y recolecta **tokens**.
  - Convierte ParseTree → **AST** (con `ast_builder`).
  - Ejecuta `checker` para validaciones semánticas (dos pases).
  - Extrae la **tabla de símbolos** desde `Env`.
  - Genera **DOT** del AST (con `astviz`).
- Devuelve un `dict` con: `tokens`, `astDot`, `symbols`, `diagnostics`.

### `ast.py`

- Define las **clases de nodos AST** (p. ej. `Program`, `Block`, `VarDecl`, `ConstDecl`, `FunctionDecl`, `If`, `While`, `Return`, `Binary`, `Call`, `ClassDecl`, etc.).
- Cada nodo incluye `loc` (línea/columna) para reportes precisos.

### `ast_builder.py`

- Transforma el **ParseTree** del parser en el **AST** del proyecto.
- Se asegura de poblar `loc`, nombres, operadores, listas de `statements`, etc.

### `astviz.py`

- `DotBuilder` genera **Graphviz DOT** a partir del AST.
- Escapa caracteres especiales y etiqueta nodos/aristas de forma legible.
- La UI usa `st.graphviz_chart(dot)` para visualizar y permite **descargar** el `.dot`.

### `checker.py`

- **Verificador semántico**:
  - Pase **\_collect(...)**: declara funciones/clases/miembros para armar **firmas** antes de validar.
  - Pase **visit(...)**: valida **tipos**, **alcances**, **retornos**, **llamadas**, **asignaciones**, **índices**, **this**, etc.
- Detección de **código muerto** tras `return`, control de **ámbitos** (global, bloque, función, clase) y regla de **“todas las rutas retornan”** para funciones/métodos no-`void`.

### `symbols.py`

- Implementa la **tabla de símbolos**: `Env` (pila de scopes), `Symbol`, `VarSymbol`, `ConstSymbol`, `FunctionSymbol`, `ClassSymbol`.
- Soporta **shadowing**, búsqueda jerárquica, captura de variables para funciones anidadas y utilidades de clases (campos/métodos/ctor).

### `types.py`

- Sistema de **tipos** de Compiscript: `T_INT`, `T_STRING`, `T_BOOL`, `T_ARRAY(elem)`, `T_CLASS(name)`, `T_FUNC(params, ret)`, `T_VOID`, `T_NULL`, `T_UNKNOWN`…
- Operaciones: `assignable(a, b)`, `binary_result(op, a, b)`, `unary_result(op, t)`, `call_compatible(sig, args)`, `array_literal_element_type`, etc.
- `parse_type_text("integer") → T_INT`, etc.

---

## Tabla de símbolos

- **Scopes** apilados: global → función/clase → bloque.
- Cada **símbolo** tiene: `name`, `kind` (`var`, `const`, `func`, `class`), `typ`, y flags (`is_builtin`, `is_method`, `inited`).
- Para **clases**: `fields`, `methods` y `ctor`. Los métodos tienen `return_type` y firma `T_FUNC`.
- La UI muestra:
  - Variables/constantes globales.
  - Funciones (con opción para ocultar _built-ins_ como `print`).
  - Clases con **#fields** y **#methods** y un **detalle por clase** (campos/métodos/heredados).

---

## Árbol de Sintaxis Abstracta (AST)

- El AST simplifica el ParseTree a nodos semánticos.
- `astviz.DotBuilder` genera un grafo **DOT** con etiquetas por tipo de nodo y propiedades relevantes (p. ej., `Function\nmain : integer`).
- Puedes **descargar** el DOT para renderizarlo externamente con `dot -Tpng ast.dot -o ast.png`.

---

## Reglas semánticas principales

- **Declaración y uso**:
  - Variables/constantes deben existir en el alcance; no se puede asignar a `const`.
- **Tipado**:
  - Asignaciones compatibles (`assignable(rhs, lhs)`).
  - Operadores unarios/binarios con tipos válidos (`+ - * / %`, `&& ||`, comparaciones).
  - Índices: sólo sobre `array[int]`.
  - Literales: `int`, `string`, `boolean`, `null`.
- **Funciones y métodos**:
  - Firma recolectada antes de validar el cuerpo.
  - **Todas las rutas retornan** cuando el retorno no es `void` (incluye `if` con `else`, `switch` con `default`, etc.).
  - Llamadas compatibles en número y tipo de argumentos.
- **Clases**:
  - Existencia de miembros, tipos compatibles en inicializaciones.
  - `this` sólo dentro de métodos.
- **Control de flujo**:
  - `if/while/for`: condición booleana.
  - Detección de **código muerto** después de `return`, `break`, `continue`.

---

## Pruebas sugeridas

1. **Funciones sin `return`** con retorno anotado (`integer`, `string`, etc.).
2. **Condicionales**: `if` con/ sin `else` asegurando retorno en ambos lados.
3. **Switch** con/ sin `default` y casos que retornan.
4. **Asignaciones** incompatibles (e.g., `integer` ← `string`).
5. **Const** sin inicializar y reasignaciones a `const`.
6. **Arrays**: índice no-`integer` y mezcla de tipos en literales.
7. **Clases**: acceso a miembros inexistentes, llamadas a métodos con tipos erróneos, `this` fuera de método.
8. **Sombras de nombre** (shadowing) en bloques y funciones anidadas.
9. **Código muerto** tras `return`.
10. **Built-ins**: llamada a `print` con argumentos y ver conteo de funciones ocultando/mostrando built-ins.

---

## Solución de problemas

- **No se renderiza el AST**: instala Graphviz del sistema y reinicia la app.
- **ImportError**: verifica que `src/` exista; la app añade rutas pero requiere estructura mínima.
- **Tokens vacíos**: revisa errores léxicos/sintácticos; el parser puede haber fallado.

---

## Roadmap

- Editor enriquecido (resaltado, atajos, saltos a definición).
- Más reglas semánticas (promociones numéricas, inferencia avanzada en arrays).
- Exportar reporte de diagnósticos a JSON.
- Soporte para paquetes y módulos.

---

## Licencia

Uso académico. Puedes adaptar a tus necesidades (añade la licencia que corresponda para tu curso/proyecto).

---

### 📺 Video

Explicación completa del código y la arquitectura: https://youtu.be/Kav2WP6vfyQ

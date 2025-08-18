# ▶️ Guía de Ejecución — Compiscript

Esta guía cubre instalación, ejecución por CLI, uso del IDE en Streamlit, regeneración de ANTLR y pruebas.

## ✅ Requisitos
- Python 3.10+ recomendado
- Java 8+ (para regenerar ANTLR si lo necesitas)
- Graphviz (opcional, para exportar AST a PNG desde la CLI)
  - Windows: instala Graphviz y agrega `dot.exe` al PATH o define `DOT_EXE=C:\ruta\a\dot.exe`.

## 📦 Instalación
```bash
# 1) Crear y activar un entorno virtual (opcional pero recomendado)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
# source .venv/bin/activate

# 2) Instalar dependencias
pip install -r requirements.txt

```
## 🧪 Ejecutar análisis por CLI

El CLI analiza un archivo 
.cps
, genera AST (DOT y opcionalmente PNG) y valida reglas semánticas.
```bash
 # desde la raíz del repo
python -m compiscript.cli examples/ok/ok.cps
```

Salida típica:

- En build/ast/ se guardan:
  - <archivo>.txt con el DOT del AST.
  - <archivo>.png si Graphviz dot está disponible.
- Mensajes de error:
  - Léx/sint: se reportan con [línea:col] ....
  - Semántica: lista de errores semánticos.
- Éxito:
  - “AST (DOT) guardado en: ...”
  - “✓ Análisis semántico: OK”



## 🖥️ IDE (Streamlit)

El IDE VSCompi+ permite editar código Compiscript y ver diagnósticos, AST, símbolos, hover y quick-fixes.

```bash
# desde la raíz del repo
streamlit run tools/app_streamlit.py
```

Características:

- Panel izquierdo: editor (con o sin componente Ace según instalación).
- Barra lateral: abrir ejemplos (examples/), toggles (AST, símbolos, tokens, quick‑fixes).
- Panel derecho: métricas + pestañas (Diagnósticos, Símbolos, AST, Quick‑fixes, Tokens).
- Hover: ingresa (línea/columna) para ver tipo o clase de símbolo.
- Formateo: botón “Formatear”.

***Recomendado:***
```bash
pip install streamlit-code-editor
```


## 🔁 Regenerar Lexer/Parser (ANTLR)
El repo ya incluye código generado en src/antlr/parser/generated/.

Opción A: usando el JAR incluido
```bash
java -jar antlr-4.13.1-complete.jar -Dlanguage=Python3 -visitor -listener -o src/antlr/parser/generated grammar/Compiscript.g4
```

Opción B: usando el JAR incluido
```bash
java -jar antlr-4.13.1-complete.jar -Dlanguage=Python3 -visitor -listener -o src/antlr/parser/generated grammar/Compiscript.g4
```

Luego, asegúrate que los imports en Python apunten a:

- `from antlr.parser.generated.CompiscriptLexer import CompiscriptLexer`

- `from antlr.parser.generated.CompiscriptParser import CompiscriptParser`

## 🧷 Pruebas
Ejecuta la suite de pruebas (pytest):
```bash
pytest -q
```


# 🧪 Compiscript — Analizador Sintáctico y Semántico con IDE

Un compilador educativo para el lenguaje Compiscript (subset de TypeScript), construido con ANTLR4 y Python. Incluye:
- Lexer/Parser generados a partir de [grammar/Compiscript.g4](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/grammar/Compiscript.g4:0:0-0:0).
- Construcción de AST, verificación semántica y tabla de símbolos.
- Visualización de AST (Graphviz DOT/PNG).
- IDE ligera en Streamlit con diagnósticos, AST, símbolos, hover y quick-fixes.

## 👥 Integrantes
- Sergio Orellana — 221122
- Rodrigo Mansilla — 22611
- Andre Marroquin — 22266

## 🚀 Funcionalidades Principales
- Análisis léxico y sintáctico con ANTLR4.
- Construcción de AST: [src/antlr/sema/ast.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/ast.py:0:0-0:0), [ast_builder.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/ast_builder.py:0:0-0:0).
- Análisis semántico: verificación de tipos, ámbitos, funciones, clases, control de flujo — [src/antlr/sema/checker.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/checker.py:0:0-0:0), [symbols.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/symbols.py:0:0-0:0), [types.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/types.py:0:0-0:0).
- Tabla de símbolos con entornos anidados y snapshot serializable.
- Visualización de AST (DOT/PNG): [src/antlr/sema/astviz.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/astviz.py:0:0-0:0).
- IDE Streamlit: edición, diagnósticos, AST, tabla de símbolos, hover y quick-fixes — [tools/app_streamlit.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/tools/app_streamlit.py:0:0-0:0) (usa [tools/analysis_core.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/tools/analysis_core.py:0:0-0:0)).
- CLI para analizar archivos [.cps](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/examples/ast1.cps:0:0-0:0) y exportar AST: [src/compiscript/cli.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/compiscript/cli.py:0:0-0:0).
- Suite de pruebas con pytest.

## 📁 Estructura del Proyecto
- [grammar/Compiscript.g4](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/grammar/Compiscript.g4:0:0-0:0): Gramática ANTLR del lenguaje.
- `src/`
  - `antlr/parser/generated/`: Código generado por ANTLR (lexer/parser).
  - `antlr/sema/`:
    - [ast.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/ast.py:0:0-0:0): Nodos del AST.
    - [ast_builder.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/ast_builder.py:0:0-0:0): Visitor desde ParseTree a AST.
    - [checker.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/checker.py:0:0-0:0): Reglas semánticas y sistema de tipos.
    - [symbols.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/symbols.py:0:0-0:0): Tabla de símbolos y entornos.
    - [types.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/types.py:0:0-0:0): Tipos (`integer`, `string`, `boolean`, arreglos, funciones, clases, `null`, etc.).
    - [astviz.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/astviz.py:0:0-0:0): Generador DOT del AST.
  - [compiscript/cli.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/compiscript/cli.py:0:0-0:0): Entrada CLI para analizar archivos [.cps](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/examples/ast1.cps:0:0-0:0) y generar AST.
- `tools/`
  - [analysis_core.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/tools/analysis_core.py:0:0-0:0): Orquestación de pipeline (lexer+parser+AST+semántica+símbolos+tokens+hover+quick-fixes).
  - [app_streamlit.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/tools/app_streamlit.py:0:0-0:0): IDE VSCompi+ (UI en Streamlit).
- `examples/`: Programas de ejemplo [.cps](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/examples/ast1.cps:0:0-0:0) (ok/err, demos de IDE).
- `tests/`: Pruebas automatizadas (pytest).
- [requirements.txt](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/requirements.txt:0:0-0:0): Dependencias Python.
- `build/ast/`: Salida de AST (DOT/PNG) al usar la CLI.

## 🧩 Lenguaje (resumen)
- Tipos base: `integer`, `string`, `boolean`, `null`, arreglos `T[]`, clases.
- Variables (`let`/`var`), constantes (`const` con inicialización obligatoria).
- Funciones con parámetros y tipo de retorno, anidadas, closures y recursión.
- Clases con métodos, `constructor`, herencia simple y `this`.
- Expresiones, llamadas, indexación, acceso a propiedades.
- Control de flujo: `if/else`, `while`, `do-while`, `for`, `foreach`, `switch`, `try/catch`, `break/continue`, `return`.
- Verificaciones semánticas:
  - Tipado en operadores aritméticos/lógicos/comparaciones.
  - Asignaciones, inicialización de `const`.
  - Ámbitos, declaraciones duplicadas, uso de no declarados.
  - Llamadas a funciones (número/tipo de args), tipo de retorno.
  - Reglas de flujo (`return` en función, `break/continue` en bucles).
  - Clases/miembros, `this`, constructores.
  - Listas e índices.
  - Detección de miembros inexistentes, sugerencias y hover en IDE.

## 🧠 Arquitectura de análisis
1. Lexer/Parser: [Compiscript.g4](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/grammar/Compiscript.g4:0:0-0:0) → ANTLR genera Python en `src/antlr/parser/generated/`.
2. AST: `ASTBuilder` convierte ParseTree a nodos [ast.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/ast.py:0:0-0:0).
3. Semántica: `Checker` recorre AST, mantiene tabla de símbolos ([symbols.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/symbols.py:0:0-0:0)) y usa [types.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/src/antlr/sema/types.py:0:0-0:0).
4. Visualización: `DotBuilder` produce DOT; la CLI intenta convertir a PNG (Graphviz).
5. IDE: [tools/app_streamlit.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/tools/app_streamlit.py:0:0-0:0) usa [analysis_core.py](cci:7://file:///c:/Users/rodri/Documents/Compiladores/Semantic-Parser/tools/analysis_core.py:0:0-0:0) para analizar texto en vivo y mostrar resultados.


Hecho con ❤️ para el curso de Compiladores.
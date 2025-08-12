import sys, os, shutil, subprocess
from antlr4 import FileStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener

BASE = os.path.dirname(os.path.dirname(__file__))  # .../src
sys.path.append(BASE)

from antlr.parser.generated.CompiscriptLexer import CompiscriptLexer
from antlr.parser.generated.CompiscriptParser import CompiscriptParser
from antlr.sema.ast_builder import ASTBuilder
from antlr.sema.astviz import DotBuilder
from antlr.sema.checker import Checker

class SyntaxErrorListener(ErrorListener):
    def __init__(self):
        self.errors = []
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append("[" + str(line) + ":" + str(column) + "] " + msg)

def main():
    if len(sys.argv) < 2:
        print("Uso: python -m compiscript.cli <archivo.cps>")
        sys.exit(2)

    src_path = sys.argv[1]
    inp = FileStream(src_path, encoding="utf-8")

    lexer = CompiscriptLexer(inp)
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)

    listener = SyntaxErrorListener()
    parser.removeErrorListeners()
    parser.addErrorListener(listener)

    tree = parser.program()
    if len(listener.errors) > 0:
        i = 0
        while i < len(listener.errors):
            print(listener.errors[i]); i = i + 1
        sys.exit(1)

    # ParseTree -> AST
    ast = ASTBuilder().visit(tree)

    # Guardar DOT (.txt) y PNG con nombre del archivo fuente
    repo_root = os.path.dirname(BASE)
    out_dir = os.path.join(repo_root, "build", "ast")
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    base = os.path.splitext(os.path.basename(src_path))[0]
    txt_path = os.path.join(out_dir, base + ".txt")
    png_path = os.path.join(out_dir, base + ".png")

    dot_text = DotBuilder().build(ast)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(dot_text)
    print("AST (DOT) guardado en:", txt_path)

    dot_exe = os.environ.get("DOT_EXE") or shutil.which("dot")
    if dot_exe:
        try:
            subprocess.run([dot_exe, "-Tpng", "-o", png_path],
                           input=dot_text.encode("utf-8"),
                           check=True)
            print("AST (PNG) guardado en:", png_path)
        except Exception:
            print("Advertencia: no se pudo generar el PNG con Graphviz (se guardó solo el .txt).")
    else:
        print("Advertencia: Graphviz 'dot' no encontrado; se guardó solo el .txt.")

    # Análisis semántico (Fase 2)
    checker = Checker()
    checker.run(ast)

    if len(checker.errors) > 0:
        i = 0
        while i < len(checker.errors):
            print(checker.errors[i]); i = i + 1
        sys.exit(1)

    print("✓ Análisis semántico: OK")

if __name__ == "__main__":
    main()

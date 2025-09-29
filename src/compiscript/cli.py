# compiscript/cli.py
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

from compiscript.codegen.irgen import IRGen
from compiscript.ir.pretty import format_ir
from compiscript.codegen.x86_naive import X86Naive


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
        for e in listener.errors:
            print(e)
        sys.exit(1)

    # ParseTree -> AST
    ast = ASTBuilder().visit(tree)

    # Guardar DOT (.txt) y PNG con nombre del archivo fuente
    repo_root = os.path.dirname(BASE)
    out_ast_dir = os.path.join(repo_root, "build", "ast")
    os.makedirs(out_ast_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(src_path))[0]
    dot_text = DotBuilder().build(ast)
    txt_path = os.path.join(out_ast_dir, base + ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(dot_text)
    print("AST (DOT) guardado en:", txt_path)

    dot_exe = os.environ.get("DOT_EXE") or shutil.which("dot")
    png_path = os.path.join(out_ast_dir, base + ".png")
    if dot_exe:
        try:
            subprocess.run(
                [dot_exe, "-Tpng", "-o", png_path],
                input=dot_text.encode("utf-8"),
                check=True,
            )
            print("AST (PNG) guardado en:", png_path)
        except Exception:
            print(
                "Advertencia: no se pudo generar el PNG con Graphviz (se guardó solo el .txt)."
            )
    else:
        print("Advertencia: Graphviz 'dot' no encontrado; se guardó solo el .txt.")

    # Análisis semántico
    checker = Checker()
    checker.run(ast)
    if len(checker.errors) > 0:
        for e in checker.errors:
            print(e)
        sys.exit(1)
    print("✓ Análisis semántico: OK")

    # IR
    ir = IRGen().build(ast)
    ir_dir = os.path.join(repo_root, "build", "ir")
    os.makedirs(ir_dir, exist_ok=True)
    ir_path = os.path.join(ir_dir, base + ".ir.txt")
    with open(ir_path, "w", encoding="utf-8") as f:
        f.write(format_ir(ir))
    print("IR guardado en:", ir_path)

    # x86
    asm = X86Naive().compile(ir)
    asm_dir = os.path.join(repo_root, "build", "asm")
    os.makedirs(asm_dir, exist_ok=True)
    asm_path = os.path.join(asm_dir, base + ".asm")
    with open(asm_path, "w", encoding="utf-8") as f:
        f.write(asm)
    print("ASM (x86) guardado en:", asm_path)


if __name__ == "__main__":
    main()

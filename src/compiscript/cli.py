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
from compiscript.ir.optimize import optimize_program
from compiscript.codegen.x86_naive import X86Naive
from compiscript.codegen.ass_mips import MIPSNaive


class SyntaxErrorListener(ErrorListener):
    def __init__(self):
        self.errors = []
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(f"[{line}:{column}] {msg}")


def _mk_out_dirs(repo_root: str, src_path: str):
    base = os.path.splitext(os.path.basename(src_path))[0]
    out_root = os.path.join(repo_root, "build", base)
    ast_dir = os.path.join(out_root, "ast")
    ir_dir  = os.path.join(out_root, "ir")
    asm_dir = os.path.join(out_root, "asm")
    os.makedirs(ast_dir, exist_ok=True)
    os.makedirs(ir_dir,  exist_ok=True)
    os.makedirs(asm_dir, exist_ok=True)
    return out_root, ast_dir, ir_dir, asm_dir, base


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

    # Dirs de salida por archivo
    repo_root = os.path.dirname(BASE)
    out_root, ast_dir, ir_dir, asm_dir, base = _mk_out_dirs(repo_root, src_path)

    # AST → DOT (+ opcional PNG)
    dot_text = DotBuilder().build(ast)
    ast_txt = os.path.join(ast_dir, "ast.dot.txt")
    with open(ast_txt, "w", encoding="utf-8") as f:
        f.write(dot_text)
    print("AST (DOT) guardado en:", ast_txt)

    dot_exe = os.environ.get("DOT_EXE") or shutil.which("dot")
    ast_png = os.path.join(ast_dir, "ast.png")
    if dot_exe:
        try:
            subprocess.run([dot_exe, "-Tpng", "-o", ast_png],
                           input=dot_text.encode("utf-8"), check=True)
            print("AST (PNG) guardado en:", ast_png)
        except Exception:
            print("Advertencia: no se pudo generar el PNG con Graphviz (se guardó solo el .txt).")
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
    ir_prog = IRGen().build(ast)
    # 1) Guardar IR "tal cual" (sin optimizar)
    ir_txt = os.path.join(ir_dir, "program.ir.txt")
    with open(ir_txt, "w", encoding="utf-8") as f:
        f.write(format_ir(ir_prog))
    print("IR (sin optimizar) guardado en:", ir_txt)

    # 2) Optimizar y guardar IR optimizado
    ir_prog_opt = optimize_program(ir_prog)   # nota: modifica en sitio y retorna prog
    ir_txt_op = os.path.join(ir_dir, "program_op.ir.txt")
    with open(ir_txt_op, "w", encoding="utf-8") as f:
        f.write(format_ir(ir_prog_opt))
    print("IR optimizado guardado en:", ir_txt_op)

    # x86 ASM (.asm)
    asm_text_x86 = X86Naive().compile(ir_prog_opt)
    asm_path_x86 = os.path.join(asm_dir, f"{base}.asm")
    with open(asm_path_x86, "w", encoding="utf-8") as f:
        f.write(asm_text_x86)
    print("ASM (x86) guardado en:", asm_path_x86)

    # MIPS ASM (.s)  ← NUEVO
    mips_text = MIPSNaive().compile(ir_prog_opt)
    mips_path = os.path.join(asm_dir, f"{base}.s")
    with open(mips_path, "w", encoding="utf-8") as f:
        f.write(mips_text)
    print("ASM (MIPS) guardado en:", mips_path)


if __name__ == "__main__":
    main()

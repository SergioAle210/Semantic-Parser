import sys, os
from antlr4 import FileStream, CommonTokenStream
from antlr.sema.errors import ErrorReporter
from antlr.sema.checker import Semantics
BASE = os.path.dirname(os.path.dirname(__file__)) 
sys.path.append(BASE)

from antlr.parser.generated.CompiscriptLexer import CompiscriptLexer
from antlr.parser.generated.CompiscriptParser import CompiscriptParser
from antlr4.error.ErrorListener import ErrorListener

class SyntaxErrorListener(ErrorListener):
    def __init__(self): self.errors=[]
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(f"[{line}:{column}] {msg}")

def main():
        if len(sys.argv) < 2:
            print("Uso: python -m compiscript.cli <archivo.cps>")
            sys.exit(2)
        inp = FileStream(sys.argv[1], encoding="utf-8")
        lex = CompiscriptLexer(inp)
        tokens = CommonTokenStream(lex)
        par = CompiscriptParser(tokens)
        el = SyntaxErrorListener(); par.removeErrorListeners(); par.addErrorListener(el)
        _ = par.program()
        if el.errors:
            print("\n".join(el.errors)); sys.exit(1)
        # Silencioso si parsea bien
        el = SyntaxErrorListener(); par.removeErrorListeners(); par.addErrorListener(el)
        tree = par.program()
        if el.errors:
            print("\n".join(el.errors)); sys.exit(1)

        # semántica (por ahora, solo scopes/definiciones)
        rep = ErrorReporter()
        Semantics(rep).visit(tree)
        if rep.has():
            rep.dump(); sys.exit(1)

if __name__ == "__main__":
    main()

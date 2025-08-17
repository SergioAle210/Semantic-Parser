from antlr4 import InputStream, CommonTokenStream
from antlr.parser.generated.CompiscriptLexer import CompiscriptLexer
from antlr.parser.generated.CompiscriptParser import CompiscriptParser
from antlr.sema.ast_builder import ASTBuilder
from antlr.sema.checker import Checker


def analyze_source(src: str):
    input_stream = InputStream(src)
    lexer = CompiscriptLexer(input_stream)
    tokens = CommonTokenStream(lexer)
    parser = CompiscriptParser(tokens)
    tree = parser.program()
    ast = ASTBuilder().visit(tree)
    checker = Checker()
    checker.run(ast)
    return ast, checker


def errors_of(src: str):
    return analyze_source(src)[1].errors

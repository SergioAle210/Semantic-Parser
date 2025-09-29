# compiscript/tests/examples.py
from compiscript.codegen.irgen import IRGen, Program, Block, Assign, Identifier, Literal, Binary, While, If, Return, ExprStmt, Unary
from compiscript.ir.pretty import pretty
from compiscript.codegen.x86_naive import X86Naive

def ex_sum_loop():
    # int s=0; int i=1; while (i <= 5) { s = s + i; i = i + 1; } return s;
    ast = Program([
        Assign(Identifier("s"), Literal("int", 0)),
        Assign(Identifier("i"), Literal("int", 1)),
        While(Binary("<=", Identifier("i"), Literal("int", 5)),
              Block([
                  Assign(Identifier("s"), Binary("+", Identifier("s"), Identifier("i"))),
                  Assign(Identifier("i"), Binary("+", Identifier("i"), Literal("int", 1))),
              ])),
        Return(Identifier("s"))
    ])
    ir = IRGen().gen(ast)
    print("=== TAC ===")
    print(pretty(ir))
    x86 = X86Naive().lower(ir, func_name="main")
    print("\n=== x86 (cdecl, 32-bit) ===")
    print(x86)

def ex_if_short_circuit():
    # if ((a < 10 || b > 3) && !(c == 0)) { a = a + 1; } return a;
    ast = Program([
        If(
            Binary("&&",
                Binary("||",
                    Binary("<", Identifier("a"), Literal("int", 10)),
                    Binary(">", Identifier("b"), Literal("int", 3))
                ),
                Unary("!", Binary("==", Identifier("c"), Literal("int", 0)))
            ),
            Block([ Assign(Identifier("a"), Binary("+", Identifier("a"), Literal("int", 1))) ])
        ),
        Return(Identifier("a"))
    ])
    ir = IRGen().gen(ast)
    print("=== TAC ===")
    print(pretty(ir))
    x86 = X86Naive().lower(ir, func_name="main")
    print("\n=== x86 (cdecl, 32-bit) ===")
    print(x86)

if __name__ == "__main__":
    ex_sum_loop()
    print("\n" + "="*60 + "\n")
    ex_if_short_circuit()

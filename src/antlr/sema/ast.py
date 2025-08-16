class Loc:
    def __init__(self, line, col):
        self.line = int(line)
        self.col = int(col)


class Node:
    def __init__(self, loc):
        self.loc = loc


class Program(Node):
    def __init__(self, loc, statements=None):
        Node.__init__(self, loc)
        self.statements = statements if statements is not None else []


class Block(Node):
    def __init__(self, loc, statements=None):
        Node.__init__(self, loc)
        self.statements = statements if statements is not None else []


class VarDecl(Node):
    def __init__(self, loc, name, type_ann, init):
        Node.__init__(self, loc)
        self.name = name
        self.type_ann = type_ann
        self.init = init


class ConstDecl(Node):
    def __init__(self, loc, name, type_ann, init):
        Node.__init__(self, loc)
        self.name = name
        self.type_ann = type_ann
        self.init = init


class Assign(Node):
    def __init__(self, loc, target, value):
        Node.__init__(self, loc)
        self.target = target
        self.value = value


class If(Node):
    def __init__(self, loc, cond, then_blk, else_blk):
        Node.__init__(self, loc)
        self.cond = cond
        self.then_blk = then_blk
        self.else_blk = else_blk


class While(Node):
    def __init__(self, loc, cond, body):
        Node.__init__(self, loc)
        self.cond = cond
        self.body = body


class Return(Node):
    def __init__(self, loc, value):
        Node.__init__(self, loc)
        self.value = value


class Break(Node):
    def __init__(self, loc):
        Node.__init__(self, loc)


class Continue(Node):
    def __init__(self, loc):
        Node.__init__(self, loc)


class ExprStmt(Node):
    def __init__(self, loc, expr):
        Node.__init__(self, loc)
        self.expr = expr


class Identifier(Node):
    def __init__(self, loc, name):
        Node.__init__(self, loc)
        self.name = name


class Literal(Node):
    def __init__(self, loc, value, kind):
        Node.__init__(self, loc)
        self.value = value
        self.kind = kind


class Unary(Node):
    def __init__(self, loc, op, expr):
        Node.__init__(self, loc)
        self.op = op
        self.expr = expr


class Binary(Node):
    def __init__(self, loc, op, left, right):
        Node.__init__(self, loc)
        self.op = op
        self.left = left
        self.right = right


class Ternary(Node):
    def __init__(self, loc, cond, then_expr, else_expr):
        Node.__init__(self, loc)
        self.cond = cond
        self.then_expr = then_expr
        self.else_expr = else_expr


class Call(Node):
    def __init__(self, loc, callee, args=None):
        Node.__init__(self, loc)
        self.callee = callee
        self.args = args if args is not None else []


class MemberAccess(Node):
    def __init__(self, loc, obj, name):
        Node.__init__(self, loc)
        self.obj = obj
        self.name = name


class IndexAccess(Node):
    def __init__(self, loc, obj, index):
        Node.__init__(self, loc)
        self.obj = obj
        self.index = index


class ArrayLiteral(Node):
    def __init__(self, loc, elements=None):
        Node.__init__(self, loc)
        self.elements = elements if elements is not None else []


class This(Node):
    def __init__(self, loc):
        Node.__init__(self, loc)


class Param(Node):
    def __init__(self, loc, name, type_ann):
        Node.__init__(self, loc)
        self.name = name
        self.type_ann = type_ann  # str o None


class FunctionDecl(Node):
    def __init__(self, loc, name, params, ret_ann, body):
        Node.__init__(self, loc)
        self.name = name  # str
        self.params = params  # lista de Param
        self.ret_ann = ret_ann  # str o None (p.ej. "integer")
        self.body = body  # Block


class For(Node):
    def __init__(self, loc, init, cond, update, body):
        Node.__init__(self, loc)
        self.init = init  # VarDecl | Assign | ExprStmt | None
        self.cond = cond  # expr | None (equivale a true)
        self.update = update  # expr | None
        self.body = body  # Block


class Foreach(Node):
    def __init__(self, loc, var_name, iterable, body):
        Node.__init__(self, loc)
        self.var_name = var_name  # str
        self.iterable = iterable  # expr
        self.body = body  # Block


class SwitchCase(Node):
    def __init__(self, loc, expr, block):
        Node.__init__(self, loc)
        self.expr = expr  # expr del "case"
        self.block = block  # Block (statements del case)


class Switch(Node):
    def __init__(self, loc, expr, cases, default_block):
        Node.__init__(self, loc)
        self.expr = expr  # expr del switch(...)
        self.cases = cases or []  # [SwitchCase]
        self.default_block = default_block  # Block | None


class TryCatch(Node):
    def __init__(self, loc, try_block, err_name, catch_block):
        Node.__init__(self, loc)
        self.try_block = try_block  # Block
        self.err_name = err_name  # str
        self.catch_block = catch_block  # Block


class ClassDecl(Node):
    def __init__(self, loc, name, base_name, members):
        Node.__init__(self, loc)
        self.name = name  # str
        self.base_name = base_name  # str | None (ident después de ":")
        self.members = members or []  # [VarDecl|ConstDecl|FunctionDecl]

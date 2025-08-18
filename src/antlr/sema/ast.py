# clase que representa una ubicación en el código fuente (línea y columna)
class Loc:
    def __init__(self, line, col):
        self.line = int(line)
        self.col = int(col)


# clase base para todos los nodos del ast; todos tienen una loc
class Node:
    def __init__(self, loc):
        self.loc = loc


# programa raíz; agrupa una lista de sentencias
class Program(Node):
    def __init__(self, loc, statements=None):
        Node.__init__(self, loc)
        self.statements = statements if statements is not None else []


# bloque de sentencias (nuevo ámbito)
class Block(Node):
    def __init__(self, loc, statements=None):
        Node.__init__(self, loc)
        self.statements = statements if statements is not None else []


# declaración de variable mutable con tipo opcional e inicializador opcional
class VarDecl(Node):
    def __init__(self, loc, name, type_ann, init):
        Node.__init__(self, loc)
        self.name = name
        self.type_ann = type_ann
        self.init = init


# declaración de constante con tipo e inicializador requerido por semántica
class ConstDecl(Node):
    def __init__(self, loc, name, type_ann, init):
        Node.__init__(self, loc)
        self.name = name
        self.type_ann = type_ann
        self.init = init


# asignación: target = value
class Assign(Node):
    def __init__(self, loc, target, value):
        Node.__init__(self, loc)
        self.target = target
        self.value = value


# sentencia condicional if/else
class If(Node):
    def __init__(self, loc, cond, then_blk, else_blk):
        Node.__init__(self, loc)
        self.cond = cond
        self.then_blk = then_blk
        self.else_blk = else_blk


# bucle while(cond)
class While(Node):
    def __init__(self, loc, cond, body):
        Node.__init__(self, loc)
        self.cond = cond
        self.body = body


# return expr?; marca salida de función
class Return(Node):
    def __init__(self, loc, value):
        Node.__init__(self, loc)
        self.value = value


# break; sale del bucle actual
class Break(Node):
    def __init__(self, loc):
        Node.__init__(self, loc)


# continue; salta a la siguiente iteración del bucle
class Continue(Node):
    def __init__(self, loc):
        Node.__init__(self, loc)


# sentencia de expresión evaluar por efectos
class ExprStmt(Node):
    def __init__(self, loc, expr):
        Node.__init__(self, loc)
        self.expr = expr


# identificador simple nombre
class Identifier(Node):
    def __init__(self, loc, name):
        Node.__init__(self, loc)
        self.name = name


# literal int, string, bool, null con su clase de literal
class Literal(Node):
    def __init__(self, loc, value, kind):
        Node.__init__(self, loc)
        self.value = value
        self.kind = kind


# operador unario, p. ej. -x o !x
class Unary(Node):
    def __init__(self, loc, op, expr):
        Node.__init__(self, loc)
        self.op = op
        self.expr = expr


# operador binario, p. ej. a + b
class Binary(Node):
    def __init__(self, loc, op, left, right):
        Node.__init__(self, loc)
        self.op = op
        self.left = left
        self.right = right


# operador ternario cond ? then : else
class Ternary(Node):
    def __init__(self, loc, cond, then_expr, else_expr):
        Node.__init__(self, loc)
        self.cond = cond
        self.then_expr = then_expr
        self.else_expr = else_expr


# llamada a función o método
class Call(Node):
    def __init__(self, loc, callee, args=None):
        Node.__init__(self, loc)
        self.callee = callee
        self.args = args if args is not None else []


# acceso a miembro: obj.name
class MemberAccess(Node):
    def __init__(self, loc, obj, name):
        Node.__init__(self, loc)
        self.obj = obj
        self.name = name


# acceso indexado: obj[index]
class IndexAccess(Node):
    def __init__(self, loc, obj, index):
        Node.__init__(self, loc)
        self.obj = obj
        self.index = index


# literal de arreglo: [e1, e2, ...]
class ArrayLiteral(Node):
    def __init__(self, loc, elements=None):
        Node.__init__(self, loc)
        self.elements = elements if elements is not None else []


# referencia al receptor de método dentro de clases
class This(Node):
    def __init__(self, loc):
        Node.__init__(self, loc)


# parámetro de función con nombre y anotación de tipo opcional
class Param(Node):
    def __init__(self, loc, name, type_ann):
        Node.__init__(self, loc)
        self.name = name
        self.type_ann = type_ann


# declaración de función con parámetros, retorno opcional y cuerpo
class FunctionDecl(Node):
    def __init__(self, loc, name, params, ret_ann, body):
        Node.__init__(self, loc)
        self.name = name
        self.params = params
        self.ret_ann = ret_ann
        self.body = body


# bucle for clásico con init, cond, update y cuerpo
class For(Node):
    def __init__(self, loc, init, cond, update, body):
        Node.__init__(self, loc)
        self.init = init
        self.cond = cond
        self.update = update
        self.body = body


# bucle foreach for var_name in iterable)
class Foreach(Node):
    def __init__(self, loc, var_name, iterable, body):
        Node.__init__(self, loc)
        self.var_name = var_name
        self.iterable = iterable
        self.body = body  #


# caso individual de switch con su expresión y bloque
class SwitchCase(Node):
    def __init__(self, loc, expr, block):
        Node.__init__(self, loc)
        self.expr = expr
        self.block = block


# sentencia switch con casos y bloque default opcional
class Switch(Node):
    def __init__(self, loc, expr, cases, default_block):
        Node.__init__(self, loc)
        self.expr = expr
        self.cases = cases or []
        self.default_block = default_block


# manejo de errores
class TryCatch(Node):
    def __init__(self, loc, try_block, err_name, catch_block):
        Node.__init__(self, loc)
        self.try_block = try_block
        self.err_name = err_name
        self.catch_block = catch_block


# declaración de clase con herencia opcional y miembros
class ClassDecl(Node):
    def __init__(self, loc, name, base_name, members):
        Node.__init__(self, loc)
        self.name = name
        self.base_name = base_name
        self.members = members or []

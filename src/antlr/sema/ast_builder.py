# src/antlr/ast_builder.py
from antlr.parser.generated.CompiscriptVisitor import CompiscriptVisitor
from antlr.parser.generated.CompiscriptParser import CompiscriptParser
from antlr4 import ParserRuleContext

from antlr.sema.ast import (
    Loc, Program, Block, VarDecl, ConstDecl, Assign, If, While, Return,
    Break, Continue, ExprStmt, Identifier, Literal, Unary, Binary, Ternary,
    Call, MemberAccess, IndexAccess, ArrayLiteral, This,
    Param, FunctionDecl   # <-- añade esto
)
def loc_of(ctx):
    t = ctx.start
    return Loc(t.line, t.column)

class ASTBuilder(CompiscriptVisitor):
    # --- Programa / Bloques ---
    def visitProgram(self, ctx):
        stmts = []
        items = ctx.statement()
        i = 0
        while i < len(items):
            stmts.append(self.visit(items[i]))
            i = i + 1
        return Program(loc_of(ctx), stmts)

    def visitBlock(self, ctx):
        stmts = []
        items = ctx.statement()
        i = 0
        while i < len(items):
            stmts.append(self.visit(items[i]))
            i = i + 1
        return Block(loc_of(ctx), stmts)

    # --- Sentencias ---
    def visitVariableDeclaration(self, ctx):
        name = ctx.Identifier().getText()
        t_ann = None
        if ctx.typeAnnotation() is not None:
            txt = ctx.typeAnnotation().getText()
            t_ann = txt[1:len(txt)]
        init = None
        if ctx.initializer() is not None:
            init = self.visit(ctx.initializer().expression())
        return VarDecl(loc_of(ctx), name, t_ann, init)

    def visitConstantDeclaration(self, ctx):
        name = ctx.Identifier().getText()
        t_ann = None
        if ctx.typeAnnotation() is not None:
            txt = ctx.typeAnnotation().getText()
            t_ann = txt[1:len(txt)]
        init = self.visit(ctx.expression())
        return ConstDecl(loc_of(ctx), name, t_ann, init)

    def visitAssignment(self, ctx):
        # Caso: Identifier '=' expression ';'
        if ctx.Identifier() is not None:
            target = Identifier(loc_of(ctx), ctx.Identifier().getText())
            # En esta regla, expression() puede devolver lista (por la otra alternativa).
            # Tomamos la primera expresión de forma robusta.
            exprs = ctx.expression()
            if isinstance(exprs, list):
                value = self.visit(exprs[0])
            else:
                value = self.visit(exprs)
            return Assign(loc_of(ctx), target, value)

        # Caso: expression '.' Identifier '=' expression ';'
        lhs = self.visit(ctx.expression(0))
        name = ctx.Identifier().getText()
        rhs  = self.visit(ctx.expression(1))
        return Assign(loc_of(ctx), MemberAccess(loc_of(ctx), lhs, name), rhs)

    def visitExpressionStatement(self, ctx):
        return ExprStmt(loc_of(ctx), self.visit(ctx.expression()))

    def visitPrintStatement(self, ctx):
        callee = Identifier(loc_of(ctx), "print")
        args = [ self.visit(ctx.expression()) ]
        return ExprStmt(loc_of(ctx), Call(loc_of(ctx), callee, args))

    def visitIfStatement(self, ctx):
        cond = self.visit(ctx.expression())
        then_blk = self.visit(ctx.block(0))
        else_blk = None
        if ctx.block(1) is not None:
            else_blk = self.visit(ctx.block(1))
        return If(loc_of(ctx), cond, then_blk, else_blk)

    def visitWhileStatement(self, ctx):
        cond = self.visit(ctx.expression())
        body = self.visit(ctx.block())
        return While(loc_of(ctx), cond, body)

    def visitDoWhileStatement(self, ctx):
        body = self.visit(ctx.block())
        cond = self.visit(ctx.expression())
        return While(loc_of(ctx), cond, body)

    def visitReturnStatement(self, ctx):
        expr = None
        if ctx.expression() is not None:
            expr = self.visit(ctx.expression())
        return Return(loc_of(ctx), expr)

    def visitBreakStatement(self, ctx):
        return Break(loc_of(ctx))

    def visitContinueStatement(self, ctx):
        return Continue(loc_of(ctx))

    # --- Expresiones / Precedencia ---
    def visitExpression(self, ctx):
        return self.visit(ctx.assignmentExpr())

    def visitAssignExpr(self, ctx):
        lhs = self.visit(ctx.lhs)
        rhs = self.visit(ctx.assignmentExpr())
        return Assign(loc_of(ctx), lhs, rhs)

    def visitPropertyAssignExpr(self, ctx):
        obj = self.visit(ctx.lhs)
        name = ctx.Identifier().getText()
        rhs = self.visit(ctx.assignmentExpr())
        return Assign(loc_of(ctx), MemberAccess(loc_of(ctx), obj, name), rhs)

    def visitExprNoAssign(self, ctx):
        return self.visit(ctx.conditionalExpr())

    def visitTernaryExpr(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.logicalOrExpr())
        cond = self.visit(ctx.logicalOrExpr())
        then_e = self.visit(ctx.expression(0))
        else_e = self.visit(ctx.expression(1))
        return Ternary(loc_of(ctx), cond, then_e, else_e)

    def visitLogicalOrExpr(self, ctx):
        left = self.visit(ctx.logicalAndExpr(0))
        i = 1
        while i < len(ctx.logicalAndExpr()):
            right = self.visit(ctx.logicalAndExpr(i))
            left = Binary(loc_of(ctx), "||", left, right)
            i = i + 1
        return left

    def visitLogicalAndExpr(self, ctx):
        left = self.visit(ctx.equalityExpr(0))
        i = 1
        while i < len(ctx.equalityExpr()):
            right = self.visit(ctx.equalityExpr(i))
            left = Binary(loc_of(ctx), "&&", left, right)
            i = i + 1
        return left

    def visitEqualityExpr(self, ctx):
        left = self.visit(ctx.relationalExpr(0))
        i = 1
        while i < len(ctx.relationalExpr()):
            op = ctx.getChild(i*2 - 1).getText()
            right = self.visit(ctx.relationalExpr(i))
            left = Binary(loc_of(ctx), op, left, right)
            i = i + 1
        return left

    def visitRelationalExpr(self, ctx):
        left = self.visit(ctx.additiveExpr(0))
        i = 1
        while i < len(ctx.additiveExpr()):
            op = ctx.getChild(i*2 - 1).getText()
            right = self.visit(ctx.additiveExpr(i))
            left = Binary(loc_of(ctx), op, left, right)
            i = i + 1
        return left

    def visitAdditiveExpr(self, ctx):
        left = self.visit(ctx.multiplicativeExpr(0))
        i = 1
        while i < len(ctx.multiplicativeExpr()):
            op = ctx.getChild(i*2 - 1).getText()  
            right = self.visit(ctx.multiplicativeExpr(i))
            left = Binary(loc_of(ctx), op, left, right)
            i = i + 1
        return left

    def visitMultiplicativeExpr(self, ctx):
        left = self.visit(ctx.unaryExpr(0))
        i = 1
        while i < len(ctx.unaryExpr()):
            op = ctx.getChild(i*2 - 1).getText()    
            right = self.visit(ctx.unaryExpr(i))
            left = Binary(loc_of(ctx), op, left, right)
            i = i + 1
        return left

    def visitUnaryExpr(self, ctx):
        if ctx.getChildCount() == 2:
            op = ctx.getChild(0).getText()
            expr = self.visit(ctx.unaryExpr())
            return Unary(loc_of(ctx), op, expr)
        return self.visit(ctx.primaryExpr())

    def visitPrimaryExpr(self, ctx):
        if ctx.getChild(0).getText() == "(":
            return self.visit(ctx.expression())
        if ctx.literalExpr() is not None:
            return self.visit(ctx.literalExpr())
        return self.visit(ctx.leftHandSide())

    def visitLiteralExpr(self, ctx):
        if ctx.arrayLiteral() is not None:
            arr = ctx.arrayLiteral()
            elems = []
            exprs = arr.expression()
            i = 0
            while i < len(exprs):
                elems.append(self.visit(exprs[i]))
                i = i + 1
            return ArrayLiteral(loc_of(ctx), elems)

        txt = ctx.getText()
        if txt == "true":  return Literal(loc_of(ctx), True, "boolean")
        if txt == "false": return Literal(loc_of(ctx), False, "boolean")
        if txt == "null":  return Literal(loc_of(ctx), None, "null")

        if len(txt) >= 2 and txt[0] == '"' and txt[len(txt)-1] == '"':
            inner = txt[1:len(txt)-1]
            return Literal(loc_of(ctx), inner, "string")

        j = 0
        ok = True
        while j < len(txt):
            ch = txt[j]
            if ch < '0' or ch > '9':
                ok = False; break
            j = j + 1
        if ok:
            return Literal(loc_of(ctx), int(txt), "int")

        return Literal(loc_of(ctx), txt, "unknown")

    def visitLeftHandSide(self, ctx):
        node = self.visit(ctx.primaryAtom())
        ops = ctx.suffixOp()
        i = 0
        while i < len(ops):
            node = self.visit_with_receiver(ops[i], node)
            i = i + 1
        return node

    def visit_with_receiver(self, op_ctx, recv):
        # CallExpr | IndexExpr | PropertyAccessExpr
        if getattr(op_ctx, "arguments", None) is not None or op_ctx.getChild(0).getText() == "(":
            args = []
            if op_ctx.arguments() is not None:
                exprs = op_ctx.arguments().expression()
                k = 0
                while k < len(exprs):
                    args.append(self.visit(exprs[k]))
                    k = k + 1
            return Call(loc_of(op_ctx), recv, args)

        if op_ctx.getChild(0).getText() == "[":
            return IndexAccess(loc_of(op_ctx), recv, self.visit(op_ctx.expression()))

        # PropertyAccessExpr: '.' Identifier
        name = op_ctx.Identifier().getText()
        return MemberAccess(loc_of(op_ctx), recv, name)

    def visitIdentifierExpr(self, ctx):
        return Identifier(loc_of(ctx), ctx.Identifier().getText())

    def visitNewExpr(self, ctx):
        ctor = Identifier(loc_of(ctx), ctx.Identifier().getText())
        args = []
        if ctx.arguments() is not None:
            exprs = ctx.arguments().expression()
            i = 0
            while i < len(exprs):
                args.append(self.visit(exprs[i]))
                i = i + 1
        return Call(loc_of(ctx), ctor, args)

    def visitThisExpr(self, ctx):
        return This(loc_of(ctx))

    def visitFunctionDeclaration(self, ctx):
        # function Identifier '(' parameters? ')' (':' type)? block
        name = ctx.Identifier().getText()

        # parámetros
        params = []
        if ctx.parameters() is not None:
            ps = ctx.parameters().parameter()
            i = 0
            while i < len(ps):
                pctx = ps[i]
                pname = pctx.Identifier().getText()
                tann = None
                if pctx.type_() is not None:          
                    tann = pctx.type_().getText()
                params.append(Param(loc_of(pctx), pname, tann))
                i += 1

        # tipo de retorno
        ret_ann = None
        if ctx.type_() is not None:                   
            ret_ann = ctx.type_().getText()

        # cuerpo
        body = self.visit(ctx.block())

        return FunctionDecl(loc_of(ctx), name, params, ret_ann, body)

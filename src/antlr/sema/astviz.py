class DotBuilder:
    def __init__(self):
        self.lines = []
        self.counter = 0

    def nid(self):
        s = "n" + str(self.counter)
        self.counter = self.counter + 1
        return s

    def add(self, s):
        self.lines.append(s)

    def escape(self, s):
        res = ""
        i = 0
        while i < len(s):
            ch = s[i]
            if ch == '"':
                res = res + '\\"'
            elif ch == "\\":
                res = res + "\\\\"
            elif ch == "\n":
                res = res + "\\n"
            else:
                res = res + ch
            i = i + 1
        return res

    def build(self, root):
        self.lines = []
        self.add("digraph AST {")
        self.add("node [shape=box, fontsize=10];")
        self._emit(root)
        self.add("}")
        return "\n".join(self.lines)

    def _label_of(self, node):
        name = node.__class__.__name__
        # Etiquetas especiales primero
        if name == "FunctionDecl":
            ret = node.ret_ann if node.ret_ann is not None else "void"
            return "Function\\n" + node.name + " : " + ret
        if name == "Param":
            return (
                "Param\\n"
                + (node.name or "")
                + ((" : " + node.type_ann) if node.type_ann else "")
            )
        if name == "ClassDecl":
            if getattr(node, "base_name", None):
                return "Class\\n" + node.name + " : " + node.base_name
            return "Class\\n" + node.name
        if name == "Foreach":
            return "Foreach\\n" + node.var_name

        # genérico
        if hasattr(node, "op"):
            return name + "\\n" + node.op
        if hasattr(node, "name"):
            return name + "\\n" + node.name
        if hasattr(node, "kind"):
            return name + "\\n" + node.kind
        return name

    def _children_of(self, node):
        out = []
        n = node.__class__.__name__
        if n == "Program" or n == "Block":
            i = 0
            arr = node.statements
            while i < len(arr):
                out.append(("stmt", arr[i]))
                i = i + 1
        elif n == "VarDecl":
            if node.init is not None:
                out.append(("init", node.init))
        elif n == "ConstDecl":
            out.append(("init", node.init))
        elif n == "Assign":
            out.append(("target", node.target))
            out.append(("value", node.value))
        elif n == "If":
            out.append(("cond", node.cond))
            out.append(("then", node.then_blk))
            if node.else_blk is not None:
                out.append(("else", node.else_blk))
        elif n == "While":
            out.append(("cond", node.cond))
            out.append(("body", node.body))
        elif n == "Return":
            if node.value is not None:
                out.append(("value", node.value))
        elif n == "ExprStmt":
            out.append(("expr", node.expr))
        elif n == "Unary":
            out.append(("expr", node.expr))
        elif n == "Binary":
            out.append(("L", node.left))
            out.append(("R", node.right))
        elif n == "Ternary":
            out.append(("cond", node.cond))
            out.append(("then", node.then_expr))
            out.append(("else", node.else_expr))
        elif n == "Call":
            out.append(("callee", node.callee))
            i = 0
            while i < len(node.args):
                out.append(("arg", node.args[i]))
                i = i + 1
        elif n == "MemberAccess":
            out.append(("obj", node.obj))
            # el nombre del miembro ya aparece en la etiqueta via _label_of
        elif n == "IndexAccess":
            out.append(("obj", node.obj))
            out.append(("idx", node.index))
        elif n == "ArrayLiteral":
            i = 0
            while i < len(node.elements):
                out.append(("elt", node.elements[i]))
                i = i + 1
        elif n == "FunctionDecl":
            # cuerpo
            out.append(("body", node.body))
            # params
            i = 0
            while i < len(node.params):
                out.append(("param", node.params[i]))
                i = i + 1
        elif n == "For":
            if node.init is not None:
                out.append(("init", node.init))
            if node.cond is not None:
                out.append(("cond", node.cond))
            if node.update is not None:
                out.append(("update", node.update))
            out.append(("body", node.body))
        elif n == "Foreach":
            out.append(("iterable", node.iterable))
            out.append(("body", node.body))
        elif n == "Switch":
            out.append(("expr", node.expr))
            i = 0
            while i < len(node.cases):
                out.append(("case", node.cases[i]))
                i += 1
            if node.default_block is not None:
                out.append(("default", node.default_block))
        elif n == "SwitchCase":
            out.append(("expr", node.expr))
            out.append(("block", node.block))
        elif n == "TryCatch":
            out.append(("try", node.try_block))
            out.append(("catch", node.catch_block))
        elif n == "ClassDecl":
            i = 0
            while i < len(node.members):
                out.append(("member", node.members[i]))
                i += 1
        return out

    def _emit(self, node):
        my = self.nid()
        self.add(my + ' [label="' + self.escape(self._label_of(node)) + '"];')
        kids = self._children_of(node)
        i = 0
        while i < len(kids):
            edge_lbl, ch = kids[i]
            child_id = self._emit(ch)
            self.add(
                my + " -> " + child_id + ' [label="' + self.escape(edge_lbl) + '"];'
            )
            i = i + 1
        return my

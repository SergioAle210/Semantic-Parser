# compiscript/ir/optimize.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional

from compiscript.ir.tac import (
    IRProgram, IRFunction, Instr, Operand,
    Label, Jump, CJump, Move, BinOp, UnaryOp, Cmp, Call, Return,
    Temp, Local, Param, ConstInt, ConstStr,
    Load, Store, LoadI, StoreI
)

# Utilidades de operandos/constantes

def _is_const_int(op: Operand) -> bool:
    return isinstance(op, ConstInt)

def _const_val(op: Operand) -> int:
    assert isinstance(op, ConstInt)
    return op.value

def _op_key(op: Operand) -> str:
    if isinstance(op, ConstInt): return f"CI:{op.value}"
    if isinstance(op, ConstStr): return f"CS:{op.label}"
    if isinstance(op, Temp):     return f"T:{op.name}"
    if isinstance(op, Local):    return f"L:{op.name}"
    if isinstance(op, Param):    return f"P:{op.name}"
    return f"?:{op}"

def _normalize_commutative(op: str, akey: str, bkey: str) -> Tuple[str,str,str]:
    # Para +, *, ==, != normalizamos (conmutativas) para CSE local.
    if op in ("+", "*", "==", "!="):
        akey, bkey = sorted((akey, bkey))
    return (op, akey, bkey)

def _compute_binop_const(op: str, av: int, bv: int) -> Tuple[bool, Optional[int]]:
    if op == "+":  return True, av + bv
    if op == "-":  return True, av - bv
    if op == "*":  return True, av * bv
    if op == "/":  return True, (av // bv) if bv != 0 else None
    if op == "%":  return True, (av %  bv) if bv != 0 else None
    return False, None

def _compute_unary_const(op: str, av: int) -> Tuple[bool, Optional[int]]:
    if op == "neg": return True, -av
    if op == "not": return True, 0 if av else 1
    return False, None

def _compute_cmp_const(op: str, av: int, bv: int) -> Tuple[bool, Optional[int]]:
    if op == "==": return True, 1 if av == bv else 0
    if op == "!=": return True, 1 if av != bv else 0
    if op == "<":  return True, 1 if av <  bv else 0
    if op == "<=": return True, 1 if av <= bv else 0
    if op == ">":  return True, 1 if av >  bv else 0
    if op == ">=": return True, 1 if av >= bv else 0
    return False, None

def _instr_uses(ins: Instr) -> List[Operand]:
    uses: List[Operand] = []
    if isinstance(ins, Move):    uses = [ins.src]
    elif isinstance(ins, BinOp): uses = [ins.a, ins.b]
    elif isinstance(ins, UnaryOp): uses = [ins.a]
    elif isinstance(ins, Cmp):   uses = [ins.a, ins.b]
    elif isinstance(ins, Call):  uses = list(ins.args)
    elif isinstance(ins, CJump): uses = [ins.a, ins.b]
    elif isinstance(ins, Load):  uses = [ins.base]
    elif isinstance(ins, Store): uses = [ins.base, ins.src]
    elif isinstance(ins, LoadI): uses = [ins.base, ins.index]
    elif isinstance(ins, StoreI): uses = [ins.base, ins.index, ins.src]
    elif isinstance(ins, Return) and ins.value is not None:
        uses = [ins.value]
    return uses

def _instr_def_temp(ins: Instr) -> Optional[str]:
    dst = None
    if isinstance(ins, (Move, BinOp, UnaryOp, Cmp, Load, LoadI)):
        dst = ins.dst
    elif isinstance(ins, Call):
        dst = ins.dst
    if isinstance(dst, Temp):
        return dst.name
    return None

def _safe_side_effect(ins: Instr) -> bool:
    # Barreras: no borrar ni reordenar
    if isinstance(ins, (Store, StoreI, Return, Jump, CJump, Label)):
        return True
    if isinstance(ins, Call):
        return True
    return False

def _replace_operand(op: Operand, copy_map: Dict[str, Operand]) -> Operand:
    if isinstance(op, (Temp, Local, Param)):
        k = _op_key(op)
        if k in copy_map:
            return copy_map[k]
    return op

def _kill_var_in_maps(v: Operand, copy_map: Dict[str, Operand], expr_map: Dict[Tuple[str,str,str], Operand]) -> None:
    if not isinstance(v, (Temp, Local, Param)):
        return
    vkey = _op_key(v)
    if vkey in copy_map:
        del copy_map[vkey]
    # También invalida copias que usen v como valor
    todel = [k for k, val in copy_map.items() if _op_key(val) == vkey]
    for k in todel:
        del copy_map[k]
    # Invalida expresiones que mencionen v
    todel2 = [ek for ek in expr_map.keys() if ek[1] == vkey or ek[2] == vkey]
    for ek in todel2:
        del expr_map[ek]

# PASO A: Simplificación local + CSE + copy‑prop por bloque

def _simplify_and_cse_blockwise(fn: IRFunction) -> None:
    new_body: List[Instr] = []
    copy_map: Dict[str, Operand] = {}
    expr_map: Dict[Tuple[str,str,str], Operand] = {}

    def flush_maps():
        copy_map.clear()
        expr_map.clear()

    for ins in fn.body:
        # Un Label inicia bloque: reinicia mapas (líder de bloque)
        if isinstance(ins, Label):
            flush_maps()
            new_body.append(ins)
            continue

        # ---------- Sustitución/reescritura seguras (ANTES de posibles flush) ----------

        if isinstance(ins, Move):
            src = _replace_operand(ins.src, copy_map)
            dst = ins.dst
            # Eliminar x = x
            if isinstance(dst, (Temp, Local, Param)) and _op_key(dst) == _op_key(src):
                continue
            _kill_var_in_maps(dst, copy_map, expr_map)
            if isinstance(dst, (Temp, Local, Param)):
                copy_map[_op_key(dst)] = src
            new_body.append(Move(dst=dst, src=src))
            # Move no es barrera
            continue

        if isinstance(ins, UnaryOp):
            a = _replace_operand(ins.a, copy_map)
            if _is_const_int(a):
                ok, val = _compute_unary_const(ins.op, _const_val(a))
                if ok:
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=ConstInt(val)))
                    continue
            _kill_var_in_maps(ins.dst, copy_map, expr_map)
            new_body.append(UnaryOp(op=ins.op, dst=ins.dst, a=a))
            continue

        if isinstance(ins, Cmp):
            a = _replace_operand(ins.a, copy_map)
            b = _replace_operand(ins.b, copy_map)
            # x ? x  => constante
            if _op_key(a) == _op_key(b):
                truth = None
                if ins.op == "==": truth = 1
                elif ins.op == "!=": truth = 0
                elif ins.op in ("<", ">"): truth = 0
                elif ins.op in ("<=", ">="): truth = 1
                if truth is not None:
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=ConstInt(truth)))
                    continue
            # plegado si ambos constantes
            if _is_const_int(a) and _is_const_int(b):
                ok, val = _compute_cmp_const(ins.op, _const_val(a), _const_val(b))
                if ok:
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=ConstInt(val)))
                    continue
            _kill_var_in_maps(ins.dst, copy_map, expr_map)
            new_body.append(Cmp(op=ins.op, dst=ins.dst, a=a, b=b))
            continue

        if isinstance(ins, BinOp):
            a = _replace_operand(ins.a, copy_map)
            b = _replace_operand(ins.b, copy_map)

            # Álgebra segura
            if ins.op == "+":
                if _is_const_int(a) and _const_val(a) == 0:
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=b)); continue
                if _is_const_int(b) and _const_val(b) == 0:
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=a)); continue
            if ins.op == "-":
                # x - x -> 0
                if _op_key(a) == _op_key(b):
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=ConstInt(0))); continue
                if _is_const_int(b) and _const_val(b) == 0:
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=a)); continue
            if ins.op == "*":
                if (_is_const_int(a) and _const_val(a) == 1) or (_is_const_int(b) and _const_val(b) == 1):
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=(b if _is_const_int(a) else a))); continue
                if (_is_const_int(a) and _const_val(a) == 0) or (_is_const_int(b) and _const_val(b) == 0):
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=ConstInt(0))); continue
            if ins.op == "/":
                if _is_const_int(b) and _const_val(b) == 1:
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=a)); continue
            if ins.op == "%":
                if _is_const_int(b) and _const_val(b) == 1:
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=ConstInt(0))); continue

            # Folding binario
            if _is_const_int(a) and _is_const_int(b):
                ok, val = _compute_binop_const(ins.op, _const_val(a), _const_val(b))
                if ok and val is not None:
                    _kill_var_in_maps(ins.dst, copy_map, expr_map)
                    new_body.append(Move(dst=ins.dst, src=ConstInt(val)))
                    continue

            # CSE local por bloque
            akey, bkey = _op_key(a), _op_key(b)
            ekey = _normalize_commutative(ins.op, akey, bkey)
            if ekey in expr_map and isinstance(ins.dst, (Temp, Local, Param)):
                _kill_var_in_maps(ins.dst, copy_map, expr_map)
                new_body.append(Move(dst=ins.dst, src=expr_map[ekey]))
                continue

            _kill_var_in_maps(ins.dst, copy_map, expr_map)
            if isinstance(ins.dst, (Temp, Local, Param)):
                expr_map[ekey] = ins.dst
            new_body.append(BinOp(op=ins.op, dst=ins.dst, a=a, b=b))
            continue

        if isinstance(ins, Load):
            base = _replace_operand(ins.base, copy_map)
            _kill_var_in_maps(ins.dst, copy_map, expr_map)
            new_body.append(Load(dst=ins.dst, base=base, offset=ins.offset))
            # Load no es barrera: conservadoramente NO invalidamos expr_map/copy_map
            continue

        if isinstance(ins, LoadI):
            base = _replace_operand(ins.base, copy_map)
            idx  = _replace_operand(ins.index, copy_map)
            _kill_var_in_maps(ins.dst, copy_map, expr_map)
            new_body.append(LoadI(dst=ins.dst, base=base, index=idx))
            continue

        if isinstance(ins, Store):
            base = _replace_operand(ins.base, copy_map)
            src  = _replace_operand(ins.src, copy_map)
            new_body.append(Store(base=base, offset=ins.offset, src=src))
            # Store = barrera: invalidar mapas
            flush_maps()
            continue

        if isinstance(ins, StoreI):
            base = _replace_operand(ins.base, copy_map)
            idx  = _replace_operand(ins.index, copy_map)
            src  = _replace_operand(ins.src, copy_map)
            new_body.append(StoreI(base=base, index=idx, src=src))
            flush_maps()
            continue

        if isinstance(ins, CJump):
            a = _replace_operand(ins.a, copy_map)
            b = _replace_operand(ins.b, copy_map)
            # x ? x -> salto directo
            if _op_key(a) == _op_key(b):
                always_true = ins.op in ("==", "<=", ">=")
                always_false = ins.op in ("!=", "<", ">")
                if always_true or always_false:
                    new_body.append(Jump(target=ins.if_true if always_true else ins.if_false))
                    flush_maps()
                    continue
            # Si ambos son constantes, resolvemos a salto directo
            if _is_const_int(a) and _is_const_int(b):
                ok, val = _compute_cmp_const(ins.op, _const_val(a), _const_val(b))
                if ok:
                    new_body.append(Jump(target=ins.if_true if val else ins.if_false))
                    flush_maps()
                    continue
            new_body.append(CJump(op=ins.op, a=a, b=b, if_true=ins.if_true, if_false=ins.if_false))
            flush_maps()
            continue

        if isinstance(ins, Call):
            # Sustituye args con copy-prop antes del flush
            args = tuple(_replace_operand(a, copy_map) for a in ins.args)
            dst  = ins.dst
            if dst is not None:
                _kill_var_in_maps(dst, copy_map, expr_map)
            new_body.append(Call(func=ins.func, dst=dst, args=args))
            flush_maps()
            continue

        if isinstance(ins, Return):
            val = _replace_operand(ins.value, copy_map) if ins.value is not None else None
            new_body.append(Return(value=val))
            flush_maps()
            continue

        if isinstance(ins, Jump):
            new_body.append(ins)
            flush_maps()
            continue

        # fallback
        new_body.append(ins)

    fn.body = new_body


# PASO B: Eliminación de temps muertos (DCE por función)

def _dce_temps_function(fn: IRFunction) -> None:
    changed = True
    while changed:
        changed = False
        uses: Dict[str, int] = {}
        for ins in fn.body:
            for op in _instr_uses(ins):
                if isinstance(op, Temp):
                    uses[op.name] = uses.get(op.name, 0) + 1

        new_body: List[Instr] = []
        for ins in reversed(fn.body):
            tdef = _instr_def_temp(ins)
            if tdef is not None and not _safe_side_effect(ins):
                if uses.get(tdef, 0) == 0:
                    changed = True
                    continue
            new_body.append(ins)
        new_body.reverse()
        fn.body = new_body


# PASO C: Eliminar inalcanzable lineal (entre Jump/Return y siguiente Label)

def _remove_unreachable(fn: IRFunction) -> None:
    new_body: List[Instr] = []
    reachable = True
    for ins in fn.body:
        if isinstance(ins, Label):
            reachable = True
            new_body.append(ins)
            continue
        if not reachable:
            continue
        new_body.append(ins)
        if isinstance(ins, (Jump, Return)):
            reachable = False
    fn.body = new_body

# PASO D: Limpiar saltos triviales y etiquetas muertas
#  - goto L justo antes de 'L:' se elimina
#  - etiquetas sin referencias se eliminan

def _remove_trivial_jumps_and_dead_labels(fn: IRFunction) -> None:
    body = fn.body

    # 1) Remove jumps to the very next label
    i = 0
    out: List[Instr] = []
    while i < len(body):
        ins = body[i]
        if isinstance(ins, Jump) and (i + 1) < len(body) and isinstance(body[i+1], Label) and body[i+1].name == ins.target:
            # quitar el Jump trivial
            i += 1  # saltamos el jump; el label siguiente se conserva
            continue
        out.append(ins)
        i += 1
    body = out

    # 2) Remove labels that are never targeted
    targets = set()
    for ins in body:
        if isinstance(ins, Jump):
            targets.add(ins.target)
        elif isinstance(ins, CJump):
            targets.add(ins.if_true); targets.add(ins.if_false)

    out2: List[Instr] = []
    for ins in body:
        if isinstance(ins, Label):
            if ins.name in targets:
                out2.append(ins)
            else:
                continue  # etiqueta sin referencias: eliminarla
        else:
            out2.append(ins)
    fn.body = out2

# Orquestador

# Helpers: reescritura de operandos / instrucciones

def _rewrite_operands(ins: Instr,
                      map_temp: Optional[callable] = None,
                      map_str: Optional[callable] = None) -> Instr:
    """
    Devuelve una nueva instrucción con Temp/ConstStr reescritos via map_temp/map_str.
    Si no hay cambios, devuelve un objeto equivalente.
    """
    def mop(op: Operand) -> Operand:
        if map_temp and isinstance(op, Temp):
            return map_temp(op)
        if map_str and isinstance(op, ConstStr):
            newlab = map_str(op.label)
            if newlab != op.label:
                return ConstStr(newlab)
        return op

    # Clases de instrucción con sus campos
    if isinstance(ins, Label):
        return ins
    if isinstance(ins, Jump):
        return Jump(target=ins.target)
    if isinstance(ins, CJump):
        return CJump(op=ins.op, a=mop(ins.a), b=mop(ins.b),
                     if_true=ins.if_true, if_false=ins.if_false)
    if isinstance(ins, Move):
        return Move(dst=mop(ins.dst), src=mop(ins.src))
    if isinstance(ins, BinOp):
        return BinOp(op=ins.op, dst=mop(ins.dst), a=mop(ins.a), b=mop(ins.b))
    if isinstance(ins, UnaryOp):
        return UnaryOp(op=ins.op, dst=mop(ins.dst), a=mop(ins.a))
    if isinstance(ins, Cmp):
        return Cmp(op=ins.op, dst=mop(ins.dst), a=mop(ins.a), b=mop(ins.b))
    if isinstance(ins, Call):
        new_dst = mop(ins.dst) if ins.dst is not None else None
        new_args = tuple(mop(a) for a in ins.args)
        return Call(func=ins.func, dst=new_dst, args=new_args)
    if isinstance(ins, Return):
        return Return(value=mop(ins.value) if ins.value is not None else None)
    if isinstance(ins, Load):
        return Load(dst=mop(ins.dst), base=mop(ins.base), offset=ins.offset)
    if isinstance(ins, Store):
        return Store(base=mop(ins.base), offset=ins.offset, src=mop(ins.src))
    if isinstance(ins, LoadI):
        return LoadI(dst=mop(ins.dst), base=mop(ins.base), index=mop(ins.index))
    if isinstance(ins, StoreI):
        return StoreI(base=mop(ins.base), index=mop(ins.index), src=mop(ins.src))
    # fallback
    return ins


# PASO S1: Pooling/Deduplicación de strings a nivel de programa

def _pool_strings(prog: IRProgram) -> None:
    """
    - Unifica labels de strings por contenido (mismo payload de bytes).
    - Reescribe todos los ConstStr(...) del IR para que apunten al label canónico.
    - Elimina de prog.strings los labels no referenciados.
    Idempotente y semantics-preserving.
    """
    # 1) Elegir canónico por contenido
    content2label: Dict[Tuple[int, ...], str] = {}
    alias: Dict[str, str] = {}
    # Mantener orden de inserción tal como viene en prog.strings
    for lab, bs in prog.strings.items():
        sig = tuple(bs)  # robusto si bs es bytes/list/iterable
        if sig in content2label:
            alias[lab] = content2label[sig]  # duplicado -> apuntar al canónico
        else:
            content2label[sig] = lab
            alias[lab] = lab  # canónico

    # 2) Reescribir todas las ocurrencias de ConstStr en el IR
    def map_str(label: str) -> str:
        return alias.get(label, label)

    for fn in prog.functions.values():
        fn.body = [_rewrite_operands(ins, map_temp=None, map_str=map_str) for ins in fn.body]

    # 3) Recolectar labels de string realmente usados tras la reescritura
    used: set[str] = set()
    for fn in prog.functions.values():
        for ins in fn.body:
            # recorrer operandos con el mismo helper:
            def collect(op: Operand):
                if isinstance(op, ConstStr):
                    used.add(op.label)
            if isinstance(ins, Move):
                collect(ins.src); collect(ins.dst)
            elif isinstance(ins, BinOp):
                collect(ins.dst); collect(ins.a); collect(ins.b)
            elif isinstance(ins, UnaryOp):
                collect(ins.dst); collect(ins.a)
            elif isinstance(ins, Cmp):
                collect(ins.dst); collect(ins.a); collect(ins.b)
            elif isinstance(ins, Call):
                if ins.dst is not None: collect(ins.dst)
                for a in ins.args: collect(a)
            elif isinstance(ins, Return):
                if ins.value is not None: collect(ins.value)
            elif isinstance(ins, Load):
                collect(ins.dst); collect(ins.base)
            elif isinstance(ins, Store):
                collect(ins.base); collect(ins.src)
            elif isinstance(ins, LoadI):
                collect(ins.dst); collect(ins.base); collect(ins.index)
            elif isinstance(ins, StoreI):
                collect(ins.base); collect(ins.index); collect(ins.src)
            # Label, Jump, CJump no tienen ConstStr

    # 4) Filtrar prog.strings: conservamos sólo labels canónicos en uso
    if used:
        new_strings: Dict[str, bytes] = {}
        for lab, bs in prog.strings.items():
            if lab in used:
                new_strings[lab] = bytes(bs)
        prog.strings = new_strings
    else:
        # En programas sin strings, vaciar (por si venía algo huérfano).
        prog.strings = {}


# PASO S2: Renumeración de temporales por función (t0, t1, ...) estable

def _renumber_temps_per_function(prog: IRProgram, prefix: str = "t") -> None:
    """
    Renumera todos los Temp dentro de cada función en orden de primera aparición:
      t0, t1, ...
    No toca Local/Param. Idempotente: si ya están t0..tn, se mantienen.
    """
    for fn in prog.functions.values():
        # Orden estable por primera aparición
        mapping: Dict[str, Temp] = {}
        counter = 0

        def map_temp(op: Operand) -> Operand:
            nonlocal counter
            if not isinstance(op, Temp):
                return op
            old = op.name
            dst = mapping.get(old)
            if dst is None:
                dst = Temp(f"{prefix}{counter}")
                mapping[old] = dst
                counter += 1
            return dst

        fn.body = [_rewrite_operands(ins, map_temp=map_temp, map_str=None) for ins in fn.body]


# Orquestador

def optimize_program(prog: IRProgram, *, max_iter: int = 2) -> IRProgram:
    """
    Optimiza el IR de forma segura (semantics-preserving).
    Pases:
      - S1: pooling/dedup de strings (global)
      - A:  CSE/propagación/folding (por bloque)
      - B:  DCE de temps
      - C:  poda de inalcanzable
      - D:  limpieza de saltos/etiquetas
      - S2: renumeración de temporales por función (t0..tn)
    Varias vueltas A–D para estabilizar. S1 y S2 son idempotentes.
    """
    # Deduplicar strings antes, para que toda la optimización los vea ya canónicos
    _pool_strings(prog)

    for _ in range(max_iter):
        for fn in prog.functions.values():
            _simplify_and_cse_blockwise(fn)    # CSE local + copy-prop + folding
            _dce_temps_function(fn)            # dead temps
            _remove_unreachable(fn)            # inalcanzable lineal
            _remove_trivial_jumps_and_dead_labels(fn)

    # Limpiar strings otra vez por si DCE u otras pases quitaron uses
    _pool_strings(prog)

    # Renumerar temps por función al final (legibilidad; backends ya compactan slots)
    _renumber_temps_per_function(prog)

    return prog


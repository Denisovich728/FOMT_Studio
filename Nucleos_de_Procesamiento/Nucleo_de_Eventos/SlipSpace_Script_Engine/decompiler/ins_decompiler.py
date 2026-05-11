# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.0.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
from typing import List, Dict, Tuple, Optional, Any
from ..ir import *
from ..ast import *

from .error import DecompileError

class DecompileToken:
    pass

class TokenExpr(DecompileToken):
    def __init__(self, expr: Expr): self.expr = expr

class TokenFunctionCall(DecompileToken):
    def __init__(self, invoke: Invoke): self.invoke = invoke

class TokenPushVar(DecompileToken):
    def __init__(self, var_id: VarId): self.var_id = var_id

class TokenPushInt(DecompileToken):
    def __init__(self, value: IntValue): self.value = value

class TokenAssignExpr(DecompileToken):
    def __init__(self, var_id: VarId, op: AssignOperation, expr: Expr):
        self.var_id = var_id
        self.op = op
        self.expr = expr

class TokenStmts(DecompileToken):
    def __init__(self, stmts: List[Stmt]): self.stmts = stmts

class TokenJump(DecompileToken):
    def __init__(self, jump_id: JumpId): self.jump_id = jump_id

class TokenBeq(DecompileToken):
    def __init__(self, jump_id: JumpId): self.jump_id = jump_id

class TokenBne(DecompileToken):
    def __init__(self, jump_id: JumpId): self.jump_id = jump_id

class TokenLabel(DecompileToken):
    def __init__(self, jump_id: JumpId): self.jump_id = jump_id

class TokenCase(DecompileToken):
    def __init__(self, switch_id: SwitchId, case_enum: CaseEnum):
        self.switch_id = switch_id
        self.case_enum = case_enum

class TokenSwitchCases(DecompileToken):
    def __init__(self, switch_id: SwitchId, cases: List[Tuple['SwitchCase', Optional[JumpId]]]):
        self.switch_id = switch_id
        self.cases = cases

class ASTOptimizer:
    """Optimiza la lista de sentencias antes del formateo final."""
    def __init__(self, refcounts: Dict[JumpId, int], label_order: Dict[JumpId, int]):
        self.refcounts = refcounts.copy()
        self.label_order = label_order
        self.alias_map: Dict[JumpId, JumpId] = {}

    def optimize(self, stmts: List[Stmt]) -> List[Stmt]:
        # 1. Identificar alias (etiquetas consecutivas)
        self._find_aliases(stmts)
        # 2. Re-enrutar todos los saltos
        self._remap_jumps(stmts)
        # 3. Estructuración de bloques if-else implícitos
        stmts = self._structure_if_else(stmts)
        # 4. Resolver breaks implícitos (goto al final del switch)
        stmts = self._resolve_breaks(stmts)
        # 5. Eliminar saltos redundantes (Phantom Jumps)
        stmts = self._remove_phantom_jumps(stmts)
        # 6. Eliminar etiquetas inútiles y huérfanas
        return self._cleanup(stmts)

    def _structure_if_else(self, stmts: List[Stmt]) -> List[Stmt]:
        """Detecta el patrón: if(cond){...; goto LBL;} else_stmts; LBL: 
        y lo convierte en StmtIfElse."""
        i = 0
        while i < len(stmts):
            s = stmts[i]
            
            # Recursión en bloques internos primero (bottom-up)
            if isinstance(s, StmtIf):
                s.stmts = self._structure_if_else(s.stmts)
            elif isinstance(s, StmtIfElse):
                s.true_stmts = self._structure_if_else(s.true_stmts)
                s.false_stmts = self._structure_if_else(s.false_stmts)
            elif isinstance(s, StmtSwitch):
                for case in s.cases:
                    case.stmts = self._structure_if_else(case.stmts)

            # Detectar patrón If-Else
            if isinstance(s, StmtIf) and s.stmts and isinstance(s.stmts[-1], StmtGoto):
                target_id = s.stmts[-1].jump_id
                
                # Buscar la etiqueta de destino más adelante en la misma lista
                found_label_idx = -1
                for j in range(i + 1, len(stmts)):
                    if isinstance(stmts[j], StmtLabel) and stmts[j].jump_id == target_id:
                        found_label_idx = j
                        break
                
                if found_label_idx != -1:
                    # ¡PATRÓN DETECTADO!
                    # 1. Extraer sentencias del bloque ELSE
                    else_stmts = stmts[i + 1 : found_label_idx]
                    # 2. El bloque TRUE es el actual menos el goto final
                    true_stmts = s.stmts[:-1]
                    # 3. Crear el nuevo IfElse
                    new_if_else = StmtIfElse(s.condition, true_stmts, else_stmts)
                    # 4. Actualizar conteo de referencias (el goto desaparece)
                    if target_id in self.refcounts:
                        self.refcounts[target_id] -= 1
                    
                    # 5. Reemplazar y limpiar la lista
                    stmts[i] = new_if_else
                    del stmts[i + 1 : found_label_idx + 1]
                    
                    # Re-analizar este mismo índice por si el nuevo IfElse es parte de otro bloque
                    continue
            
            i += 1
        return stmts

    def _resolve_breaks(self, stmts: List[Stmt], exit_label: Optional[JumpId] = None) -> List[Stmt]:
        """Regla: El Break Implícito.
        Si estamos dentro de un switch y encontramos un goto que salta al final del switch,
        lo convertimos en un break."""
        for i in range(len(stmts)):
            s = stmts[i]
            if isinstance(s, StmtIf):
                s.stmts = self._resolve_breaks(s.stmts, exit_label)
            elif isinstance(s, StmtIfElse):
                s.true_stmts = self._resolve_breaks(s.true_stmts, exit_label)
                s.false_stmts = self._resolve_breaks(s.false_stmts, exit_label)
            elif isinstance(s, StmtSwitch):
                for case in s.cases:
                    case.stmts = self._resolve_breaks(case.stmts, s.exit_label)
            elif isinstance(s, StmtDoWhile):
                s.body = self._resolve_breaks(s.body, exit_label)
            elif isinstance(s, StmtGoto) and exit_label:
                # Heurística: es un break si apunta exactamente al final o más allá (salto de salida)
                target_order = self.label_order.get(s.jump_id, -1)
                exit_order = self.label_order.get(exit_label, -1)
                if s.jump_id == exit_label or (target_order != -1 and exit_order != -1 and target_order >= exit_order):
                    stmts[i] = StmtBreak()
        return stmts

    def _remove_phantom_jumps(self, stmts: List[Stmt], next_stmt: Optional[Stmt] = None) -> List[Stmt]:
        """Regla: El Salto Redundante (Phantom Jump).
        Si un goto salta a la siguiente línea lógica de ejecución, es redundante."""
        i = 0
        while i < len(stmts):
            s = stmts[i]
            # Siguiente lógico: la siguiente sentencia en la lista o la del padre
            logical_next = stmts[i+1] if i + 1 < len(stmts) else next_stmt
            
            if isinstance(s, StmtIf):
                s.stmts = self._remove_phantom_jumps(s.stmts, logical_next)
            elif isinstance(s, StmtIfElse):
                s.true_stmts = self._remove_phantom_jumps(s.true_stmts, logical_next)
                s.false_stmts = self._remove_phantom_jumps(s.false_stmts, logical_next)
            elif isinstance(s, StmtSwitch):
                for case in s.cases:
                    case.stmts = self._remove_phantom_jumps(case.stmts, logical_next)
            elif isinstance(s, StmtDoWhile):
                s.body = self._remove_phantom_jumps(s.body, s)

            if isinstance(s, StmtGoto) and isinstance(logical_next, StmtLabel):
                if s.jump_id == logical_next.jump_id:
                    stmts.pop(i)
                    continue
            i += 1
        return stmts

    def _find_aliases(self, stmts: List[Stmt]):
        i = 0
        while i < len(stmts) - 1:
            curr = stmts[i]
            next_s = stmts[i+1]
            
            # Caso A: Etiqueta -> Etiqueta
            if isinstance(curr, StmtLabel) and isinstance(next_s, StmtLabel):
                self.alias_map[curr.jump_id] = next_s.jump_id
                # El refcount de la primera pasa a la segunda
                self.refcounts[next_s.jump_id] = self.refcounts.get(next_s.jump_id, 0) + self.refcounts.get(curr.jump_id, 0)
                self.refcounts[curr.jump_id] = 0
                stmts.pop(i)
                continue
            
            # Caso B: Etiqueta -> Goto (Redirección directa)
            if isinstance(curr, StmtLabel) and isinstance(next_s, StmtGoto):
                self.alias_map[curr.jump_id] = next_s.jump_id
                self.refcounts[next_s.jump_id] = self.refcounts.get(next_s.jump_id, 0) + self.refcounts.get(curr.jump_id, 0)
                self.refcounts[curr.jump_id] = 0
                # No podemos borrar el goto, pero sí la etiqueta
                stmts.pop(i)
                continue
                
            i += 1

    def _remap_jumps(self, stmts: List[Stmt]):
        def remap_id(jid: JumpId) -> JumpId:
            root = jid
            visited = {root}
            while root in self.alias_map:
                root = self.alias_map[root]
                if root in visited: break # Evitar bucles infinitos
                visited.add(root)
            return root

        def visit(s):
            if isinstance(s, StmtGoto):
                s.jump_id = remap_id(s.jump_id)
            elif isinstance(s, StmtLabel):
                s.jump_id = remap_id(s.jump_id)
            elif isinstance(s, StmtIf):
                if s.exit_jump: s.exit_jump = remap_id(s.exit_jump)
                for sub in s.stmts: visit(sub)
            elif isinstance(s, StmtIfElse):
                for sub in s.true_stmts: visit(sub)
                for sub in s.false_stmts: visit(sub)
            elif isinstance(s, StmtSwitch):
                if s.exit_label: s.exit_label = remap_id(s.exit_label)
                for case in s.cases:
                    for sub in case.stmts: visit(sub)

        for s in stmts:
            visit(s)

    def _cleanup(self, stmts: List[Stmt]) -> List[Stmt]:
        # Fase A: Escaneo de etiquetas realmente utilizadas en el AST final
        used_labels = set()
        def find_used(s_list):
            for s in s_list:
                if isinstance(s, StmtGoto):
                    used_labels.add(s.jump_id)
                elif isinstance(s, StmtIf):
                    find_used(s.stmts)
                elif isinstance(s, StmtIfElse):
                    find_used(s.true_stmts)
                    find_used(s.false_stmts)
                elif isinstance(s, StmtSwitch):
                    for case in s.cases:
                        find_used(case.stmts)
        find_used(stmts)

        # Fase B: Filtrado
        def filter_stmts(s_list):
            new_list = []
            for s in s_list:
                if isinstance(s, StmtLabel):
                    if s.jump_id in used_labels:
                        new_list.append(s)
                elif isinstance(s, StmtIf):
                    s.stmts = filter_stmts(s.stmts)
                    new_list.append(s)
                elif isinstance(s, StmtIfElse):
                    s.true_stmts = filter_stmts(s.true_stmts)
                    s.false_stmts = filter_stmts(s.false_stmts)
                    new_list.append(s)
                elif isinstance(s, StmtSwitch):
                    for case in s.cases:
                        case.stmts = filter_stmts(case.stmts)
                    new_list.append(s)
                else:
                    new_list.append(s)
            return new_list

        return filter_stmts(stmts)

class DecompileState:
    def __init__(self, instructions: List[Ins]):
        self.input = instructions[:]
        self.stack: List[DecompileToken] = []

class InsDecompiler:
    def __init__(self, instructions: List[Ins], known_callables: Dict[CallId, Tuple[str, CallableShape]]):
        self.state = DecompileState(instructions)
        self.variables: Dict[VarId, str] = {}
        self.jump_to_idx = {
            ins.jump_id: idx 
            for idx, ins in enumerate((i for i in instructions if not isinstance(i, Case))) 
            if isinstance(ins, Label)
        }
        # Mapa de orden secuencial de Labels: JumpId -> posición ordinal
        self.label_order: Dict[JumpId, int] = {}
        order = 0
        for ins in instructions:
            if isinstance(ins, Label):
                self.label_order[ins.jump_id] = order
                order += 1
        
        # Cuenta de referencias JMP para cada Label: JumpId -> conteo de JMPs apuntando aquí.
        # Un Label con refcount > 1 es un punto de convergencia compartido (goto compartido).
        self.jmp_refcount: Dict[JumpId, int] = {}
        for ins in instructions:
            target = ins.branch_target()
            if target:
                self.jmp_refcount[target] = self.jmp_refcount.get(target, 0) + 1
        
        self.known_callables = known_callables

    def remaining(self) -> int:
        return len(self.state.input)

    def at_end(self) -> bool:
        return self.remaining() == 0

    def back(self) -> List[DecompileToken]:
        return self.state.stack

    def is_expr(self, tok) -> bool:
        tname = type(tok).__name__
        return tname in ("TokenExpr", "TokenAssignExpr", "TokenFunctionCall", "TokenPushVar", "TokenPushInt")

    def token_to_expr(self, tok) -> Expr:
        tname = type(tok).__name__
        if tname == "TokenExpr":
            return tok.expr
        if tname == "TokenAssignExpr":
            return ExprCmpEq(ExprName(self.variable_name(tok.var_id)), tok.expr)
        if tname == "TokenFunctionCall":
            return ExprCall(tok.invoke)
        if tname == "TokenPushVar":
            return ExprName(self.variable_name(tok.var_id))
        if tname == "TokenPushInt":
            return ExprInt(tok.value)
        raise DecompileError(f"Token {tok} is not an expression")

    def variable_name(self, var_id: VarId) -> str:
        if var_id not in self.variables:
            self.variables[var_id] = f"var_{var_id.id}"
        return self.variables[var_id]

    def pop_expr(self) -> Expr:
        if not self.state.stack:
            return ExprInt(IntValue(0))
        token = self.state.stack.pop()
        if isinstance(token, TokenExpr): return token.expr
        elif isinstance(token, TokenFunctionCall): return ExprCall(token.invoke)
        elif isinstance(token, TokenPushVar): return ExprName(self.variable_name(token.var_id))
        elif isinstance(token, TokenPushInt): return ExprInt(token.value)
        
        # Fallback
        self.state.stack.append(token)
        return ExprInt(IntValue(0))

    def pop_assign_params(self) -> Tuple[VarId, Expr]:
        rhs = self.pop_expr()
        if not self.state.stack:
             return VarId(0), rhs
        lhs = self.state.stack.pop()
        if isinstance(lhs, TokenPushInt):
            return VarId(lhs.value), rhs
        return VarId(0), rhs

    def pop_binop_params(self) -> Tuple[Expr, Expr]:
        rhs = self.pop_expr()
        lhs = self.pop_expr()
        return lhs, rhs

    def push_stmt(self, stmt: Stmt):
        if self.state.stack and isinstance(self.state.stack[-1], TokenStmts):
            self.state.stack[-1].stmts.append(stmt)
        else:
            self.state.stack.append(TokenStmts([stmt]))

    def match_at_assign(self):
        stack = self.state.stack
        
        # Necesitamos al menos 1 item (la expresión) para intentar algo
        if len(stack) < 1:
            self.state.input.pop(0)  # consumir el Assign
            return
        
        # Si el top no es una expresión, consumir el Assign y seguir
        if not self.is_expr(stack[-1]):
            self.state.input.pop(0)
            return

        # Buscamos el ID de la variable (TokenPushInt) saltando Stmts/Labels
        var_idx = -2
        found_var = False
        while abs(var_idx) <= len(stack):
            if isinstance(stack[var_idx], TokenPushInt):
                found_var = True
                break
            elif isinstance(stack[var_idx], (TokenStmts, TokenLabel, TokenJump)):
                var_idx -= 1
            else:
                break
        
        if found_var:
            # Caso normal: hay un PushInt con el ID de la variable
            input_head = self.state.input.pop(0)
            op = AssignOperation.NONE
            if isinstance(input_head, AssignAdd): op = AssignOperation.ADD
            elif isinstance(input_head, AssignSub): op = AssignOperation.SUB
            elif isinstance(input_head, AssignMul): op = AssignOperation.MUL
            elif isinstance(input_head, AssignDiv): op = AssignOperation.DIV
            elif isinstance(input_head, AssignMod): op = AssignOperation.MOD
            
            expr = self.pop_expr()
            # Sacamos los tokens intermedios (labels, stmts) para guardarlos
            intermediates = []
            while not isinstance(self.state.stack[-1], TokenPushInt):
                intermediates.append(self.state.stack.pop())
            
            var_token = self.state.stack.pop()
            # Restauramos los intermedios
            while intermediates:
                self.state.stack.append(intermediates.pop())
                
            self.state.stack.append(TokenAssignExpr(VarId(var_token.value), op, expr))
            return
        
        # Fallback: No hay PushInt -> la función es un proc "suelto" o una expresión descartada
        self.state.input.pop(0)  # consumir el Assign
        expr = self.pop_expr()
        if type(expr).__name__ not in ("ExprInt", "ExprName"):
            self.push_stmt(StmtExpr(expr))

    def match_at_binop(self):
        if len(self.back()) >= 2 and self.is_expr(self.back()[-2]) and self.is_expr(self.back()[-1]):
            input_head = self.state.input.pop(0)
            lhs, rhs = self.pop_binop_params()
            
            if isinstance(input_head, Add): expr = ExprOpAdd(lhs, rhs)
            elif isinstance(input_head, Sub): expr = ExprOpSub(lhs, rhs)
            elif isinstance(input_head, Mul): expr = ExprOpMul(lhs, rhs)
            elif isinstance(input_head, Div): expr = ExprOpDiv(lhs, rhs)
            elif isinstance(input_head, Mod): expr = ExprOpMod(lhs, rhs)
            elif isinstance(input_head, LogicalAnd): expr = ExprOpAnd(lhs, rhs)
            elif isinstance(input_head, LogicalOr): expr = ExprOpOr(lhs, rhs)
            else: raise DecompileError("Invalid binop")
            self.state.stack.append(TokenExpr(expr))
            return
        raise DecompileError("Could not reduce binop")

    def match_at_unop(self):
        if len(self.back()) >= 1 and self.is_expr(self.back()[-1]):
            input_head = self.state.input.pop(0)
            inner = self.pop_expr()
            
            if isinstance(input_head, Neg): expr = ExprOpNeg(inner)
            elif isinstance(input_head, LogicalNot): expr = ExprOpNot(inner)
            else: raise DecompileError("Invalid unop")
            self.state.stack.append(TokenExpr(expr))
            return
        raise DecompileError("Could not reduce unop")

    def match_at_cmp(self):
        if len(self.back()) >= 1 and self.is_expr(self.back()[-1]):
            if len(self.state.input) >= 7:
                p0, p1, p2, p3, p4, p5, p6 = self.state.input[:7]
                if isinstance(p0, Cmp) and isinstance(p1, BranchIns) and isinstance(p2, PushInt) and p2.value == 0 \
                   and isinstance(p3, Jmp) and isinstance(p4, Label) and isinstance(p5, PushInt) and p5.value == 1 and isinstance(p6, Label):
                    target_branch = p1.branch_target()
                    if target_branch == p4.jump_id and p3.jump_id == p6.jump_id:
                        self.state.input = self.state.input[7:]
                        lhs, rhs = self.pop_binop_params()
                        
                        if isinstance(p1, Blt): ex = ExprCmpLt(lhs, rhs)
                        elif isinstance(p1, Ble): ex = ExprCmpLe(lhs, rhs)
                        elif isinstance(p1, Beq): ex = ExprCmpEq(lhs, rhs)
                        elif isinstance(p1, Bne): ex = ExprCmpNe(lhs, rhs)
                        elif isinstance(p1, Bge): ex = ExprCmpGe(lhs, rhs)
                        elif isinstance(p1, Bgt): ex = ExprCmpGt(lhs, rhs)
                        else: raise DecompileError("Invalid cmp branch")
                        
                        self.state.stack.append(TokenExpr(ex))
                        return
        raise DecompileError("Could not reduce cmp")

    def match_at_discard(self):
        # El DISCARD es una escoba: limpia el stack de expresiones pendientes
        while self.state.stack and self.is_expr(self.state.stack[-1]):
            top = self.state.stack.pop()
            tname = type(top).__name__
            
            # Si lo que descartamos es una asignación, queremos que se guarde como sentencia
            if tname == "TokenAssignExpr":
                self.push_stmt(StmtAssign(top.op, self.variable_name(top.var_id), top.expr))
            # Si es una llamada a función que devuelve valor, la guardamos como sentencia Call
            elif tname == "TokenFunctionCall":
                self.push_stmt(StmtCall(top.invoke))
            
        if self.state.input:
            self.state.input.pop(0)
        return

    def match_at_dupe_inc(self):
        if len(self.back()) >= 1 and isinstance(self.back()[-1], TokenPushVar):
            pushed_var_id = self.back()[-1].var_id
            if len(self.state.input) >= 3:
                i0, i1, i2 = self.state.input[:3]
                if isinstance(i0, Dupe) and isinstance(i1, Inc) and isinstance(i2, PopVar) and i2.var_id == pushed_var_id:
                    self.state.input = self.state.input[3:]
                    self.state.stack.pop()
                    self.state.stack.append(TokenExpr(ExprPostIncrement(self.variable_name(pushed_var_id))))
                    return
                elif isinstance(i0, Dupe) and isinstance(i1, Dec) and isinstance(i2, PopVar) and i2.var_id == pushed_var_id:
                    self.state.input = self.state.input[3:]
                    self.state.stack.pop()
                    self.state.stack.append(TokenExpr(ExprPostDecrement(self.variable_name(pushed_var_id))))
                    return
                elif isinstance(i0, Inc) and isinstance(i1, Dupe) and isinstance(i2, PopVar) and i2.var_id == pushed_var_id:
                    self.state.input = self.state.input[3:]
                    self.state.stack.pop()
                    self.state.stack.append(TokenExpr(ExprPreIncrement(self.variable_name(pushed_var_id))))
                    return
                elif isinstance(i0, Dec) and isinstance(i1, Dupe) and isinstance(i2, PopVar) and i2.var_id == pushed_var_id:
                    self.state.input = self.state.input[3:]
                    self.state.stack.pop()
                    self.state.stack.append(TokenExpr(ExprPreDecrement(self.variable_name(pushed_var_id))))
                    return
        raise DecompileError("Could not reduce dupe inc")

    def _collect_body_stmts(self, tokens: list) -> List[Stmt]:
        """Convierte una lista de tokens intermedios en sentencias para el cuerpo de un if.
        
        Reconoce patrones de if no reducidos: [Expr] [Beq] [Stmts] -> StmtIf
        """
        body = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            
            # Patrón: [Expr] [Beq(X)] [Stmts] -> StmtIf(expr, stmts)
            # Esto ocurre cuando un else-if interno no fue reducido por match_at_label
            if self.is_expr(tok) and i + 2 < len(tokens):
                next_tok = tokens[i + 1]
                body_tok = tokens[i + 2]
                if isinstance(next_tok, TokenBeq) and isinstance(body_tok, TokenStmts):
                    cond = self.token_to_expr(tok)
                    body.append(StmtIf(cond, body_tok.stmts))
                    i += 3
                    continue
                elif isinstance(next_tok, TokenBeq):
                    # Beq sin body (if vacío)
                    cond = self.token_to_expr(tok)
                    body.append(StmtIf(cond, []))
                    i += 2
                    continue
            
            if isinstance(tok, TokenStmts):
                body.extend(tok.stmts)
            elif isinstance(tok, TokenLabel):
                # Emitimos la etiqueta si es un punto de convergencia (refcount > 0)
                # o si es necesaria para la legibilidad.
                body.append(StmtLabel(tok.jump_id))
            elif isinstance(tok, (TokenBeq, TokenBne)):
                # Si un salto condicional llega aquí, es un "Conditional Goto"
                is_bne = isinstance(tok, TokenBne)
                cond = self.token_to_expr(self.state.stack[i-1])
                # Nota: El expr ya fue consumido por el detector de i-1 arriba?
                # No, en este bucle 'i' avanza manualmente.
                # Pero en _collect_body_stmts, i avanza de 1 en 1.
                # Tenemos que ser cuidadosos con el stack.
                body.append(StmtIf(cond, [StmtGoto(tok.jump_id)]))
            elif isinstance(tok, TokenJump):
                # Un salto incondicional huérfano es un GOTO
                body.append(StmtGoto(tok.jump_id))
            elif isinstance(tok, TokenAssignExpr):
                body.append(StmtAssign(tok.op, self.variable_name(tok.var_id), tok.expr))
            elif self.is_expr(tok):
                expr = self.token_to_expr(tok)
                ename = type(expr).__name__
                # SKIP: No permitimos que constantes o variables solas se vuelvan StmtExpr (ej: "0;" o "var_1;")
                if ename not in ("ExprInt", "ExprName"):
                    body.append(StmtExpr(expr))
            elif isinstance(tok, TokenFunctionCall):
                body.append(StmtCall(tok.invoke))
            i += 1
        return body

    def match_at_label(self, label_jump_id: JumpId):
        stack = self.back()
        if not stack: return
        
        # Sensores de Stack
        s1 = stack[-1] if len(stack) >= 1 else None
        s2 = stack[-2] if len(stack) >= 2 else None
        s3 = stack[-3] if len(stack) >= 3 else None
        s4 = stack[-4] if len(stack) >= 4 else None
        
        n1 = type(s1).__name__ if s1 else None
        n2 = type(s2).__name__ if s2 else None
        n3 = type(s3).__name__ if s3 else None
        n4 = type(s4).__name__ if s4 else None

        # ── Patrón A: if/else completo (MÁXIMA PRIORIDAD) ──
        if len(stack) >= 2:
            # Buscamos si el label actual L cierra un bloque que empezó con un IF
            found_if_idx = -1
            for i in range(len(self.state.stack) - 1, -1, -1):
                tok = self.state.stack[i]
                if type(tok).__name__ == "TokenStmts" and len(tok.stmts) >= 1:
                    last_s = tok.stmts[-1]
                    if type(last_s).__name__ in ("StmtIf", "StmtIfElse"):
                        if hasattr(last_s, 'exit_jump') and last_s.exit_jump == label_jump_id:
                            found_if_idx = i
                            break
            
            if found_if_idx != -1:
                self.state.input.pop(0) # label l
                
                else_body = []
                while len(self.state.stack) > found_if_idx + 1:
                    tok = self.state.stack.pop()
                    if hasattr(tok, 'stmts'):
                        else_body = tok.stmts + else_body
                    elif hasattr(tok, 'stmt'):
                        else_body = [tok.stmt] + else_body
                
                prev_stmts_token = self.state.stack.pop()
                prev_if = prev_stmts_token.stmts.pop()
                
                if type(prev_if).__name__ == "StmtIf":
                    new_if_else = StmtIfElse(
                        condition=prev_if.condition, 
                        true_stmts=prev_if.stmts, 
                        false_stmts=else_body
                    )
                else:
                    new_if_else = StmtIfElse(
                        condition=prev_if.condition,
                        true_stmts=prev_if.true_stmts,
                        false_stmts=else_body
                    )

                if prev_stmts_token.stmts:
                    prev_stmts_token.stmts.append(new_if_else)
                    self.state.stack.append(prev_stmts_token)
                else:
                    self.push_stmt(new_if_else)
                return

        # ── Patrón 1: if simple ──
        if len(stack) >= 3:
            s1, s2, s3 = stack[-1], stack[-2], stack[-3]
            if type(s2).__name__ == "TokenBeq" and s2.jump_id == label_jump_id and type(s1).__name__ == "TokenStmts" and self.is_expr(s3):
                self.state.input.pop(0)
                stmts = self.state.stack.pop().stmts
                self.state.stack.pop() # beq
                cond = self.pop_expr()
                self.push_stmt(StmtIf(cond, stmts))
                return
            
        # ── Patrón 2: if vacío ──
        if len(stack) >= 2:
            s1, s2 = stack[-1], stack[-2]
            if type(s1).__name__ == "TokenBeq" and s1.jump_id == label_jump_id and self.is_expr(s2):
                self.state.input.pop(0)
                self.state.stack.pop()
                cond = self.pop_expr()
                self.push_stmt(StmtIf(cond, []))
                return
                
            # Patrón clásico: [Expr] [Beq(K)] [Stmts] [Jmp(L)] [Label(K)] [Stmts]
            if len(stack) >= 6:
                s5, s6 = stack[-5], stack[-6]
                n5 = type(s5).__name__
                if n1 == "TokenStmts" and n2 == "TokenLabel" and n3 == "TokenJump" and s3.jump_id == label_jump_id \
                   and n5 == "TokenBeq" and getattr(s5, 'jump_id', None) == getattr(s2, 'jump_id', None) and self.is_expr(s6):
                    self.state.input.pop(0) # label l
                    
                    # ASPIRADORA: Recolectar todo hasta TokenLabel(K)
                    else_body = []
                    while self.state.stack:
                        tok = self.state.stack.pop()
                        if type(tok).__name__ == "TokenLabel" and tok.jump_id == s2.jump_id:
                            break # Encontramos label k
                        if type(tok).__name__ == "TokenStmts":
                            else_body = tok.stmts + else_body

                    self.state.stack.pop() # jmp l
                    true_stmts = self.state.stack.pop().stmts
                    self.state.stack.pop() # beq
                    cond = self.pop_expr()
                    self.push_stmt(StmtIfElse(cond, true_stmts, else_body))
                    return

        # ── Patrón 4: if con JMP en el body (busca Beq enterrado) ──
        # [Expr] [Beq(L)] [body...] [posible Jmp(X)] ... Label(L)
        # Cuando Label(L) llega y el Beq(L) está enterrado en la pila
        # porque hay tokens intermedios (body + posible JMP al final).
        #
        # Regla clave para distinguir if/else vs goto:
        # - Si el JMP apunta a un Label cuyo label_order es ADYACENTE (label_order del JMP target 
        #   == label_order de L + 1), es un if/else real.
        # - Si el JMP apunta MUCHO MÁS LEJOS (shared jump target / goto CLEANUP), 
        #   es un bloque if independiente con un goto al final de su body.
        if len(stack) >= 3:
            beq_idx = None
            for i in range(len(stack) - 1, -1, -1):
                if isinstance(stack[i], TokenBeq) and stack[i].jump_id == label_jump_id:
                    beq_idx = i
                    break
                if isinstance(stack[i], (TokenBeq, TokenBne)) and stack[i].jump_id != label_jump_id:
                    break
            
            if beq_idx is not None and beq_idx > 0 and self.is_expr(stack[beq_idx - 1]):
                body_tokens = stack[beq_idx + 1:]
                
                # Verificar si el último token del body es un Jump
                jmp_end_id = None
                is_local_else_jmp = False
                if body_tokens and isinstance(body_tokens[-1], TokenJump):
                    jmp_end_id = body_tokens[-1].jump_id
                    
                    # ¿Es un JMP local (if/else) o un JMP lejano (goto compartido)?
                    # Regla: Si el destino (jmp_end_id) tiene refcount > 1, es un punto
                    # de convergencia compartido. Debemos dejar el JMP como un GOTO explícito.
                    refcount = self.jmp_refcount.get(jmp_end_id, 0)
                    beq_label_order = self.label_order.get(label_jump_id, -1)
                    jmp_label_order = self.label_order.get(jmp_end_id, -1)
                    
                    # Es un else local SOLO si el refcount es 1 y apunta hacia adelante
                    is_local_else_jmp = (refcount == 1 and jmp_label_order > beq_label_order)
                    
                    if is_local_else_jmp:
                        # Es parte de un if/else real
                        body_tokens = body_tokens[:-1]
                    else:
                        # El JMP es un goto dentro del body del if
                        jmp_end_id = None
                
                body_stmts = self._collect_body_stmts(body_tokens)
                cond_expr = self.token_to_expr(stack[beq_idx - 1])
                del self.state.stack[beq_idx - 1:]
                
                if is_local_else_jmp and jmp_end_id is not None:
                    # if/else-if real: guardamos como StmtIf temporal + marcadores
                    # para reducir cuando Label(END) llegue
                    self.push_stmt(StmtIf(cond_expr, body_stmts, exit_jump=jmp_end_id))
                    self.state.stack.append(TokenJump(jmp_end_id))
                    self.state.stack.append(TokenLabel(label_jump_id))
                    self.state.input.pop(0)
                    return
                else:
                    # if simple (posiblemente con goto en el body)
                    self.push_stmt(StmtIf(cond_expr, body_stmts))
                    self.state.input.pop(0)
                    return
        
        raise DecompileError("Could not reduce at label")

    def match_at_backward_branch(self, jump_id: JumpId, is_bne: bool):
        stack = self.back()
        
        # We need a condition expression at the top of the stack
        if len(stack) < 2 or not self.is_expr(stack[-1]):
            raise DecompileError("Backward branch without condition")
            
        # Scan backward to find TokenLabel(jump_id)
        label_idx = -1
        for i in range(len(stack) - 2, -1, -1):
            if isinstance(stack[i], TokenLabel) and stack[i].jump_id == jump_id:
                label_idx = i
                break
                
        if label_idx == -1:
            raise DecompileError("No matching backward label found")
            
        # Found backward label. Collect statements between label and condition
        block_stmts = []
        for i in range(label_idx + 1, len(stack) - 1):
            tok = stack[i]
            if isinstance(tok, TokenStmts):
                block_stmts.extend(tok.stmts)
            elif isinstance(tok, TokenLabel):
                pass # ignore internal labels
            else:
                # Unreduced token, try to convert to statement
                if self.is_expr(tok):
                    block_stmts.append(StmtExpr(self.token_to_expr(tok)))
                else:
                    raise DecompileError(f"Unexpected token in backward loop body: {tok}")
                    
        cond_expr = self.pop_expr()
        if not is_bne:
            # If it's Beq (Branch if Equal to Zero), the loop continues when condition is FALSE.
            # So the do-while condition is the negated expression.
            cond_expr = ExprOpNot(cond_expr)
            
        stmt_loop = StmtDoWhile(cond_expr, block_stmts)
        
        # Clean stack from label onwards
        del self.state.stack[label_idx:]
        self.push_stmt(stmt_loop)
        self.state.input.pop(0) # consume Beq/Bne

    def match_at_switch(self, switch_id: SwitchId):
        stack = self.back()
        
        if not isinstance(stack[-1], TokenLabel):
            raise DecompileError("Switch must be preceded by a Label")
            
        switch_label_id = stack[-1].jump_id
        
        cases = []
        idx = len(stack) - 2
        
        while idx >= 0:
            token = stack[idx]
            
            if isinstance(token, TokenJump) and token.jump_id == switch_label_id:
                break
                
            block_stmts = []
            
            while idx >= 0:
                tok = stack[idx]
                if isinstance(tok, TokenCase) and tok.switch_id == switch_id:
                    break
                if isinstance(tok, TokenJump) and tok.jump_id == switch_label_id:
                    break
                    
                if isinstance(tok, TokenStmts):
                    block_stmts = tok.stmts + block_stmts
                elif isinstance(tok, TokenJump):
                    # Un JMP dentro de un switch es un break si apunta al final del switch
                    # o si es un salto hacia adelante que sale del contexto del caso.
                    # Usamos una heurística más permisiva para evitar el fall-through.
                    is_break = (tok.jump_id == switch_label_id)
                    
                    # Si no es el switch_label_id exacto, pero apunta a un label lejano,
                    # también es un break (común en optimizaciones de compilador).
                    if not is_break:
                        target_order = self.label_order.get(tok.jump_id, -1)
                        exit_order = self.label_order.get(switch_label_id, -1)
                        if target_order >= exit_order:
                            is_break = True
                            
                    if is_break:
                        if not block_stmts or not isinstance(block_stmts[0], StmtBreak):
                            block_stmts.insert(0, StmtBreak())
                elif isinstance(tok, TokenLabel):
                    pass # Ignore internal dead labels
                else:
                    if self.is_expr(tok):
                        expr = self.token_to_expr(tok)
                        if type(expr).__name__ not in ("ExprInt", "ExprName"):
                            block_stmts.insert(0, StmtExpr(expr))
                idx -= 1
                
            if idx < 0:
                break
                
            if isinstance(stack[idx], TokenJump) and stack[idx].jump_id == switch_label_id:
                break

            case_exprs = []
            is_default = False
            
            while idx >= 0 and isinstance(stack[idx], TokenCase) and stack[idx].switch_id == switch_id:
                c = stack[idx]
                if isinstance(c.case_enum, CaseDefault):
                    is_default = True
                elif isinstance(c.case_enum, CaseVal):
                    case_exprs.append(ExprInt(c.case_enum.val))
                idx -= 1
                
            case_exprs.reverse()
            if is_default:
                cases.insert(0, SwitchCaseDefault(block_stmts))
            else:
                cases.insert(0, SwitchCaseCase(case_exprs, block_stmts))
                
        else:
            raise DecompileError("Could not find Switch entry Jump")
            
        cond_idx = idx - 1
        cond_expr = None
        delete_from = cond_idx + 1
        
        if cond_idx >= 0:
            if self.is_expr(stack[cond_idx]):
                cond_expr = self.token_to_expr(stack[cond_idx])
                delete_from = cond_idx
            elif isinstance(stack[cond_idx], TokenStmts) and len(stack[cond_idx].stmts) > 0:
                last_stmt = stack[cond_idx].stmts[-1]
                if isinstance(last_stmt, StmtCall):
                    cond_expr = ExprCall(last_stmt.invoke)
                    stack[cond_idx].stmts.pop()
                    if not stack[cond_idx].stmts:
                        delete_from = cond_idx
        
        if cond_expr is None:
            # Fallback if no valid condition is found
            cond_expr = ExprInt(-1)
            
        stmt_switch = StmtSwitch(cond_expr, cases, switch_id, exit_label=switch_label_id)
        
        self.state.input.pop(0)
        del self.state.stack[delete_from:]
        self.push_stmt(stmt_switch)

    def advance(self):
        ins = self.state.input[0]
        
        # Single if/elif chain to prevent double-popping and ensure every instruction is handled once
        try:
            if isinstance(ins, (Assign, AssignAdd, AssignSub, AssignMul, AssignDiv, AssignMod)):
                self.match_at_assign()
            elif isinstance(ins, (Add, Sub, Mul, Div, Mod, LogicalAnd, LogicalOr)):
                self.match_at_binop()
            elif isinstance(ins, (Neg, LogicalNot)):
                self.match_at_unop()
            elif isinstance(ins, Cmp):
                self.match_at_cmp()
            elif isinstance(ins, (Dupe, Inc, Dec)):
                self.match_at_dupe_inc()
            elif isinstance(ins, PushVar):
                self.state.stack.append(TokenPushVar(ins.var_id))
                self.state.input.pop(0)
            elif isinstance(ins, PushInt):
                self.state.stack.append(TokenPushInt(ins.value))
                self.state.input.pop(0)
            elif isinstance(ins, PopVar):
                if len(self.back()) >= 1 and self.is_expr(self.back()[-1]):
                    expr = self.pop_expr()
                    self.push_stmt(StmtAssign(AssignOperation.NONE, self.variable_name(ins.var_id.id), expr))
                    self.state.input.pop(0)
                else:
                    raise DecompileError(f"Could not reduce PopVar. Stack tail: {[str(t) for t in self.back()[-3:]]}")
            elif isinstance(ins, Discard):
                self.match_at_discard()
            elif isinstance(ins, Jmp):
                self.state.stack.append(TokenJump(ins.jump_id))
                self.state.input.pop(0)
            elif isinstance(ins, Beq):
                try:
                    self.match_at_backward_branch(ins.jump_id, is_bne=False)
                except DecompileError:
                    self.state.stack.append(TokenBeq(ins.jump_id))
                    self.state.input.pop(0)
            elif isinstance(ins, Bne):
                try:
                    self.match_at_backward_branch(ins.jump_id, is_bne=True)
                except DecompileError:
                    self.state.stack.append(TokenBne(ins.jump_id))
                    self.state.input.pop(0)
            elif isinstance(ins, Call):
                name, shape = self.known_callables.get(ins.call_id, (f"OpcodeUnknw_{ins.call_id.id:03X}", CallableShape.new_proc([])))
                args = []
                for _ in range(shape.num_parameters()):
                    args.append(self.pop_expr())
                args.reverse()
                invoke = Invoke(name, args)
                self.state.input.pop(0)
                if shape.is_func():
                    self.state.stack.append(TokenFunctionCall(invoke))
                else:
                    self.push_stmt(StmtCall(invoke))
            elif isinstance(ins, Switch):
                self.match_at_switch(ins.switch_id)
            elif isinstance(ins, Case):
                self.state.stack.append(TokenCase(ins.switch_id, ins.case_enum))
                self.state.input.pop(0)
            elif isinstance(ins, Exit):
                self.push_stmt(StmtExit())
                self.state.input.pop(0)
            elif isinstance(ins, Label):
                try:
                    self.match_at_label(ins.jump_id)
                except DecompileError:
                    self.state.stack.append(TokenLabel(ins.jump_id))
                    self.state.input.pop(0)
            else:
                # Catch-all for unknown opcodes
                self.state.input.pop(0)
        except DecompileError as e:
            import traceback; traceback.print_exc()
            print(f"Advance failed: {e}")
            # If a reduction fails, we must at least consume the instruction to avoid infinite loops
            self.state.input.pop(0)

def decompile_instructions(instructions: List[Ins], known_callables: Dict[CallId, Tuple[str, CallableShape]]) -> List[Stmt]:
    decompiler = InsDecompiler(instructions, known_callables)
    while not decompiler.at_end():
        decompiler.advance()
    
    # Recolectar sentencias del stack final usando la lógica unificada
    stmts = decompiler._collect_body_stmts(decompiler.state.stack)
    
    # PASE 2: Optimización del AST (Graph Reduction)
    optimizer = ASTOptimizer(decompiler.jmp_refcount, decompiler.label_order)
    stmts = optimizer.optimize(stmts)
    
    # Añadir declaraciones de variables al inicio del script
    if decompiler.variables:
        var_decls = []
        # Ordenar variables por ID para una salida secuencial
        used_ids = sorted(decompiler.variables.keys(), key=lambda v: v.id)
        for vid in used_ids:
            var_decls.append((decompiler.variables[vid], None))
            
        if var_decls:
            stmts.insert(0, StmtVars(var_decls))
            
    return stmts

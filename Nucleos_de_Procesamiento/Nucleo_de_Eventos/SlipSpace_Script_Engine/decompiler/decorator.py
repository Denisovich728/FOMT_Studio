from typing import List, Dict
from ..ast import *
from ..ir import ValueTypeEnum

from .error import DecompileError

class StringDecorateVisitor:
    def __init__(self, num_strings: int, known_callables: Dict):
        self.num_strings = num_strings
        self.known_callables = known_callables
        self.callables_by_name = {name: shape for cid, (name, shape) in known_callables.items()}
        
    def stringify_expr(self, expr_container: list, idx: int):
        # El descompilador ya pone el ID como ExprInt. 
        # No necesitamos cambiarlo a ExprStr porque el usuario quiere ver el ID numérico en la llamada.
        pass

    def visit_invoke(self, invoke: Invoke):
        shape = self.callables_by_name.get(invoke.func)
        if not shape:
            return

        if len(shape.parameter_types) != len(invoke.args):
            return
            
        for i, param_type in enumerate(shape.parameter_types):
            if param_type.type_enum == ValueTypeEnum.STRING:
                self.stringify_expr(invoke.args, i)
            else:
                self.visit_expr(invoke.args[i])

    def visit_expr(self, expr: Expr):
        if type(expr) in (ExprName, ExprInt, ExprStr, ExprPostIncrement, ExprPreIncrement, ExprPostDecrement, ExprPreDecrement):
            pass
        elif isinstance(expr, (ExprOpAdd, ExprOpSub, ExprOpMul, ExprOpDiv, ExprOpMod, ExprOpOr, ExprOpAnd, ExprCmpEq, ExprCmpNe, ExprCmpLt, ExprCmpLe, ExprCmpGt, ExprCmpGe)):
            self.visit_expr(expr.lhs)
            self.visit_expr(expr.rhs)
        elif isinstance(expr, (ExprOpNeg, ExprOpNot)):
            self.visit_expr(expr.inner)
        elif isinstance(expr, ExprCall):
            self.visit_invoke(expr.invoke)

    def visit_stmt(self, stmt: Stmt):
        if isinstance(stmt, StmtVars):
            for i, (name, exp) in enumerate(stmt.vars):
                if exp: self.visit_expr(exp)
        elif isinstance(stmt, StmtConsts):
            for i, (name, exp) in enumerate(stmt.consts):
                self.visit_expr(exp)
        elif isinstance(stmt, StmtAssign):
            self.visit_expr(stmt.expr)
        elif isinstance(stmt, StmtExpr):
            self.visit_expr(stmt.expr)
        elif isinstance(stmt, StmtCall):
            self.visit_invoke(stmt.invoke)
        elif isinstance(stmt, StmtIf):
            self.visit_expr(stmt.condition)
            self.visit_stmts(stmt.stmts)
        elif isinstance(stmt, StmtIfElse):
            self.visit_expr(stmt.condition)
            self.visit_stmts(stmt.true_stmts)
            self.visit_stmts(stmt.false_stmts)
        elif isinstance(stmt, StmtFor):
            self.visit_stmt(stmt.head)
            self.visit_expr(stmt.condition)
            self.visit_stmt(stmt.tail)
            self.visit_stmts(stmt.body)
        elif isinstance(stmt, StmtDoWhile):
            self.visit_expr(stmt.condition)
            self.visit_stmts(stmt.body)
        elif isinstance(stmt, StmtSwitch):
            self.visit_expr(stmt.condition)
            for case in stmt.cases:
                self.visit_stmts(case.stmts)

    def visit_stmts(self, stmts: List[Stmt]):
        for stmt in stmts:
            self.visit_stmt(stmt)

def decorate_stmts_with_strings(stmts: List[Stmt], strings: List[bytes], known_callables: Dict):
    if not strings:
        return
        
    message_stmts = []
    for i, s in enumerate(strings):
        message_stmts.append(StmtMessage(i, s))
        
    visitor = StringDecorateVisitor(len(strings), known_callables)
    visitor.visit_stmts(stmts)
    
    # Inyectamos los CONST_MESSAGE_X al principio
    stmts[:] = message_stmts + stmts

class ItemDecorateVisitor(StringDecorateVisitor):
    def __init__(self, item_names: Dict[int, str], known_callables: Dict):
        super().__init__([], known_callables)
        self.item_names = item_names

    def visit_invoke(self, invoke: Invoke):
        # Lógica especial: si es Give_Item, forzamos decoración del primer argumento
        if invoke.func == "Give_Item" and len(invoke.args) >= 1:
            self.stringify_expr(invoke.args, 0)
        else:
            # Para otros comandos, solo si están en el CSV como STRING
            super().visit_invoke(invoke)

    def stringify_expr(self, expr_container: list, idx: int):
        expr = expr_container[idx]
        if isinstance(expr, ExprInt):
            val = expr.value
            if val in self.item_names:
                # Convertimos el ID numérico en un literal de string con el nombre del ítem
                name_bytes = self.item_names[val].encode('windows-1252', errors='replace')
                expr_container[idx] = ExprStr(name_bytes)

def decorate_stmts_with_items(stmts: List[Stmt], item_names: Dict[int, str], known_callables: Dict):
    if not item_names:
        return
    visitor = ItemDecorateVisitor(item_names, known_callables)
    visitor.visit_stmts(stmts)

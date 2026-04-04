from typing import List, Dict
from ..ast import *
from ..ir import ValueTypeEnum

from .error import DecompileError

class StringDecorateVisitor:
    def __init__(self, constant_names: List[str], known_callables: Dict):
        self.constant_names = constant_names
        self.known_callables = known_callables
        self.callables_by_name = {name: shape for cid, (name, shape) in known_callables.items()}
        self.next_to_place = 0
        
    def stringify_expr(self, expr_container: list, idx: int):
        expr = expr_container[idx]
        if isinstance(expr, ExprInt):
            val = expr.value
            if val == self.next_to_place:
                self.next_to_place += 1
            elif val > self.next_to_place:
                raise DecompileError("String decoration order mismatch")
                
            expr_container[idx] = ExprName(self.constant_names[val])
        else:
            raise DecompileError("Expected integer ID for string parameter")

    def visit_invoke(self, invoke: Invoke):
        shape = self.callables_by_name.get(invoke.func)
        if not shape:
            return # Unmapped library. We cannot safely decorate strings dynamically here without heuristics.

        if len(shape.parameter_types) != len(invoke.args):
            return # Args mismatch.
            
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
        
    string_constants = []
    string_constant_stmts = []
    
    for i, s in enumerate(strings):
        name = f"MESSAGE_{i}"
        string_constants.append(name)
        string_constant_stmts.append(StmtConsts([(name, ExprStr(s))]))
        
    visitor = StringDecorateVisitor(string_constants, known_callables)
    visitor.visit_stmts(stmts)
    
    # Prepend consts to the AST block
    stmts[:] = string_constant_stmts + stmts

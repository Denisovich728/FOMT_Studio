# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from dataclasses import dataclass
from typing import List, Tuple, Optional, Union
from enum import Enum, auto

from .ir import CallId, IntValue, StrValue, SwitchId, VarId, CallableShape

@dataclass
class Invoke:
    func: str
    args: List['Expr']

class Expr: pass

@dataclass
class ExprName(Expr): name: str
@dataclass
class ExprInt(Expr):
    value: IntValue
    comment: Optional[str] = None
    force_decimal: bool = False
@dataclass
class ExprStr(Expr): value: bytes
@dataclass
class ExprOpAdd(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprOpSub(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprOpMul(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprOpDiv(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprOpMod(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprOpOr(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprOpAnd(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprOpNeg(Expr): inner: Expr
@dataclass
class ExprOpNot(Expr): inner: Expr
@dataclass
class ExprPostIncrement(Expr): name: str
@dataclass
class ExprPreIncrement(Expr): name: str
@dataclass
class ExprPostDecrement(Expr): name: str
@dataclass
class ExprPreDecrement(Expr): name: str
@dataclass
class ExprCmpEq(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprCmpNe(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprCmpLt(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprCmpLe(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprCmpGe(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprCmpGt(Expr): lhs: Expr; rhs: Expr
@dataclass
class ExprCall(Expr): invoke: Invoke

class AssignOperation(Enum):
    NONE = auto()
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()

class Stmt: pass

@dataclass
class StmtVars(Stmt): vars: List[Tuple[str, Optional[Expr]]]
@dataclass
class StmtConsts(Stmt): consts: List[Tuple[str, Expr]]
@dataclass
class StmtAssign(Stmt): op: AssignOperation; name: str; expr: Expr
@dataclass
class StmtExpr(Stmt): expr: Expr
@dataclass
class StmtCall(Stmt): invoke: Invoke
@dataclass
class StmtMessage(Stmt): index: int; text: bytes
@dataclass
class StmtIf(Stmt): condition: Expr; stmts: List[Stmt]; exit_jump: Optional[JumpId] = None
@dataclass
class StmtIfElse(Stmt): condition: Expr; true_stmts: List[Stmt]; false_stmts: List[Stmt]
@dataclass
class StmtFor(Stmt): condition: Expr; head: Stmt; tail: Stmt; body: List[Stmt]
@dataclass
class StmtDoWhile(Stmt): condition: Expr; body: List[Stmt]
@dataclass
class StmtSwitch(Stmt): condition: Expr; cases: List['SwitchCase']; switch_id: SwitchId; exit_label: Optional[JumpId] = None
class StmtExit(Stmt): pass
class StmtBreak(Stmt): pass
class StmtEmpty(Stmt): pass

@dataclass
class StmtLabel(Stmt): jump_id: JumpId
@dataclass
class StmtGoto(Stmt): jump_id: JumpId

class SwitchCase: pass

@dataclass
class SwitchCaseCase(SwitchCase): exprs: List[Expr]; stmts: List[Stmt]
@dataclass
class SwitchCaseDefault(SwitchCase): stmts: List[Stmt]

class ConstVal: pass
@dataclass
class ConstValInt(ConstVal): value: IntValue
@dataclass
class ConstValStr(ConstVal): value: StrValue

class NameRef: pass
@dataclass
class NameRefConst(NameRef): val: ConstVal
@dataclass
class NameRefFunc(NameRef): call_id: CallId; shape: CallableShape
@dataclass
class NameRefProc(NameRef): call_id: CallId; shape: CallableShape
@dataclass
class NameRefVar(NameRef): var_id: VarId

class ConstAccess:
    def lookup_const(self, name: str) -> Optional[ConstVal]:
        raise NotImplementedError()

class NameAccess(ConstAccess):
    def lookup_name(self, name: str) -> Optional[NameRef]:
        raise NotImplementedError()

    def lookup_const(self, name: str) -> Optional[ConstVal]:
        ref = self.lookup_name(name)
        if isinstance(ref, NameRefConst):
            return ref.val
        return None

def eval_expr(expr: Expr, const_access: ConstAccess) -> Optional[ConstVal]:
    """Evaluates constant expressions at compile time."""
    if isinstance(expr, ExprName):
        return const_access.lookup_const(expr.name)
    elif isinstance(expr, ExprInt):
        return ConstValInt(expr.value)
    elif isinstance(expr, ExprStr):
        return ConstValStr(expr.value)
    
    # Binary Ops Helper
    def binop(lhs, rhs, op_func):
        l = eval_expr(lhs, const_access)
        r = eval_expr(rhs, const_access)
        if isinstance(l, ConstValInt) and isinstance(r, ConstValInt):
            return ConstValInt(op_func(l.value, r.value))
        return None

    if isinstance(expr, ExprOpAdd): return binop(expr.lhs, expr.rhs, lambda a, b: a + b)
    elif isinstance(expr, ExprOpSub): return binop(expr.lhs, expr.rhs, lambda a, b: a - b)
    elif isinstance(expr, ExprOpMul): return binop(expr.lhs, expr.rhs, lambda a, b: a * b)
    elif isinstance(expr, ExprOpDiv): return binop(expr.lhs, expr.rhs, lambda a, b: a // b)
    elif isinstance(expr, ExprOpMod): return binop(expr.lhs, expr.rhs, lambda a, b: a % b)
    elif isinstance(expr, ExprOpOr): return binop(expr.lhs, expr.rhs, lambda a, b: 1 if a != 0 or b != 0 else 0)
    elif isinstance(expr, ExprOpAnd): return binop(expr.lhs, expr.rhs, lambda a, b: 1 if a != 0 and b != 0 else 0)
    elif isinstance(expr, ExprOpNeg):
        v = eval_expr(expr.inner, const_access)
        return ConstValInt(-v.value) if isinstance(v, ConstValInt) else None
    elif isinstance(expr, ExprOpNot):
        v = eval_expr(expr.inner, const_access)
        return ConstValInt(1 if v.value == 0 else 0) if isinstance(v, ConstValInt) else None

    # Error handling for unsupported constant evaluations can return None or raise exceptions
    return None

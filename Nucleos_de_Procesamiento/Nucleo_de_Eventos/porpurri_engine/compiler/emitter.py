from typing import List, Dict, Optional
from ..ir import *
from ..ast import *

class CompileError(Exception):
    pass

class BlockScope:
    def __init__(self, parent=None, var_frame=0):
        self.var_frame = var_frame
        self.names = {}
        self.parent = parent
        
    def next_id(self) -> int:
        return self.var_frame
        
    def define_var(self, name: str) -> Optional[VarId]:
        if name in self.names:
            return None
        vid = VarId(self.var_frame)
        self.var_frame += 1
        self.names[name] = NameRefVar(vid)
        return vid
        
    def define_const(self, name: str, val: ConstVal) -> bool:
        if name in self.names:
            return False
        self.names[name] = NameRefConst(val)
        return True

    def lookup_name(self, name: str) -> Optional[NameRef]:
        if name in self.names:
            return self.names[name]
        if self.parent:
            return self.parent.lookup_name(name)
        return None

    def lookup_const(self, name: str) -> Optional[ConstVal]:
        ref = self.lookup_name(name)
        if isinstance(ref, NameRefConst):
            return ref.val
        return None

class ConstScope(BlockScope):
    def add_const(self, name: str, val: ConstVal):
        self.define_const(name, val)
        
    def add_func(self, name: str, call_id: CallId, shape: CallableShape):
        self.names[name] = NameRefFunc(call_id, shape)
        
    def add_proc(self, name: str, call_id: CallId, shape: CallableShape):
        self.names[name] = NameRefProc(call_id, shape)

class Emitter:
    def __init__(self):
        self.instructions: List[Ins] = []
        self.strings: List[bytes] = []
        self.location_counter = 0
        self.errors = []
        
    def new_label(self) -> JumpId:
        self.location_counter += 1
        return JumpId(self.location_counter)
        
    def emit(self, ins: Ins):
        self.instructions.append(ins)
        
    def emit_str_id(self, string: bytes) -> IntValue:
        if string in self.strings:
            return self.strings.index(string)
        self.strings.append(string)
        return len(self.strings) - 1

    def const_value(self, val: ConstVal):
        if isinstance(val, ConstValInt):
            self.emit(PushInt(val.value))
        elif isinstance(val, ConstValStr):
            id_val = self.emit_str_id(val.value)
            self.emit(PushInt(id_val))

    def expr(self, scope: BlockScope, expr: Expr):
        if isinstance(expr, ExprName):
            ref = scope.lookup_name(expr.name)
            if isinstance(ref, NameRefVar): self.emit(PushVar(ref.var_id))
            elif isinstance(ref, NameRefConst): self.const_value(ref.val)
            else: self.errors.append(f"Name not declared or invalid: {expr.name}")
        elif isinstance(expr, ExprInt):
            self.emit(PushInt(expr.value))
        elif isinstance(expr, ExprStr):
            sid = self.emit_str_id(expr.value)
            self.emit(PushInt(sid))
            
        elif isinstance(expr, ExprOpAdd): self.expr(scope, expr.lhs); self.expr(scope, expr.rhs); self.emit(Add())
        elif isinstance(expr, ExprOpSub): self.expr(scope, expr.lhs); self.expr(scope, expr.rhs); self.emit(Sub())
        elif isinstance(expr, ExprOpMul): self.expr(scope, expr.lhs); self.expr(scope, expr.rhs); self.emit(Mul())
        elif isinstance(expr, ExprOpDiv): self.expr(scope, expr.lhs); self.expr(scope, expr.rhs); self.emit(Div())
        elif isinstance(expr, ExprOpMod): self.expr(scope, expr.lhs); self.expr(scope, expr.rhs); self.emit(Mod())
        elif isinstance(expr, ExprOpOr): self.expr(scope, expr.lhs); self.expr(scope, expr.rhs); self.emit(LogicalOr())
        elif isinstance(expr, ExprOpAnd): self.expr(scope, expr.lhs); self.expr(scope, expr.rhs); self.emit(LogicalAnd())
        elif isinstance(expr, ExprOpNeg): self.expr(scope, expr.inner); self.emit(Neg())
        elif isinstance(expr, ExprOpNot): self.expr(scope, expr.inner); self.emit(LogicalNot())
        
        elif isinstance(expr, ExprPostIncrement):
            ref = scope.lookup_name(expr.name)
            self.emit(PushVar(ref.var_id)); self.emit(Dupe()); self.emit(Inc()); self.emit(PopVar(ref.var_id))
        elif isinstance(expr, ExprPreIncrement):
            ref = scope.lookup_name(expr.name)
            self.emit(PushVar(ref.var_id)); self.emit(Inc()); self.emit(Dupe()); self.emit(PopVar(ref.var_id))
        elif isinstance(expr, ExprPostDecrement):
            ref = scope.lookup_name(expr.name)
            self.emit(PushVar(ref.var_id)); self.emit(Dupe()); self.emit(Dec()); self.emit(PopVar(ref.var_id))
        elif isinstance(expr, ExprPreDecrement):
            ref = scope.lookup_name(expr.name)
            self.emit(PushVar(ref.var_id)); self.emit(Dec()); self.emit(Dupe()); self.emit(PopVar(ref.var_id))
            
        elif isinstance(expr, ExprCmpEq): self.expr_cmp(scope, expr.lhs, expr.rhs, Beq)
        elif isinstance(expr, ExprCmpNe): self.expr_cmp(scope, expr.lhs, expr.rhs, Bne)
        elif isinstance(expr, ExprCmpLt): self.expr_cmp(scope, expr.lhs, expr.rhs, Blt)
        elif isinstance(expr, ExprCmpLe): self.expr_cmp(scope, expr.lhs, expr.rhs, Ble)
        elif isinstance(expr, ExprCmpGe): self.expr_cmp(scope, expr.lhs, expr.rhs, Bge)
        elif isinstance(expr, ExprCmpGt): self.expr_cmp(scope, expr.lhs, expr.rhs, Bgt)
        
        elif isinstance(expr, ExprCall):
            ref = scope.lookup_name(expr.invoke.func)
            for a in expr.invoke.args:
                self.expr(scope, a)
            if isinstance(ref, NameRefFunc):
                self.emit(Call(ref.call_id))
            else:
                self.errors.append(f"Not callable: {expr.invoke.func}")
                
    def expr_cmp(self, scope, lhs, rhs, branch_cls):
        lbl_true = self.new_label()
        lbl_next = self.new_label()
        self.expr(scope, lhs)
        self.expr(scope, rhs)
        self.emit(Cmp())
        self.emit(branch_cls(lbl_true))
        self.emit(PushInt(0))
        self.emit(Jmp(lbl_next))
        self.emit(Label(lbl_true))
        self.emit(PushInt(1))
        self.emit(Label(lbl_next))
        
    def assign(self, scope, var_id, expr, op):
        self.emit(PushInt(var_id.id))
        self.expr(scope, expr)
        if op == AssignOperation.NONE: self.emit(Assign())
        elif op == AssignOperation.ADD: self.emit(AssignAdd())
        elif op == AssignOperation.SUB: self.emit(AssignSub())
        elif op == AssignOperation.MUL: self.emit(AssignMul())
        elif op == AssignOperation.DIV: self.emit(AssignDiv())
        elif op == AssignOperation.MOD: self.emit(AssignMod())
        self.emit(Discard())
        
    def stmts(self, parent_scope: BlockScope, stmts_list: List[Stmt]):
        scope = BlockScope(parent=parent_scope)
        for s in stmts_list:
            if isinstance(s, StmtVars):
                for name, exp in s.vars:
                    vid = scope.define_var(name)
                    if exp:
                        self.assign(scope, vid, exp, AssignOperation.NONE)
                        
            elif isinstance(s, StmtConsts):
                for name, exp in s.consts:
                    val = eval_expr(exp, scope)
                    if val is not None:
                        scope.define_const(name, val)
                        
            elif isinstance(s, StmtAssign):
                ref = scope.lookup_name(s.name)
                self.assign(scope, ref.var_id, s.expr, s.op)
                
            elif isinstance(s, StmtExpr):
                self.expr(scope, s.expr)
                self.emit(Discard())
                
            elif isinstance(s, StmtCall):
                ref = scope.lookup_name(s.invoke.func)
                for arg in s.invoke.args:
                    self.expr(scope, arg)
                self.emit(Call(ref.call_id))
                if isinstance(ref, NameRefFunc):
                    self.emit(Discard()) # Procs do not leave values
                    
            elif isinstance(s, StmtIf):
                nxt = self.new_label()
                self.expr(scope, s.condition)
                self.emit(Beq(nxt))
                self.stmts(scope, s.stmts)
                self.emit(Label(nxt))
                
            elif isinstance(s, StmtIfElse):
                else_lbl = self.new_label()
                nxt_lbl = self.new_label()
                self.expr(scope, s.condition)
                self.emit(Beq(else_lbl))
                self.stmts(scope, s.true_stmts)
                self.emit(Jmp(nxt_lbl))
                self.emit(Label(else_lbl))
                self.stmts(scope, s.false_stmts)
                self.emit(Label(nxt_lbl))
                
            elif isinstance(s, StmtFor):
                for_scope = BlockScope(parent=scope, var_frame=scope.next_id())
                loop_lbl, tail_lbl, body_lbl, nxt_lbl = [self.new_label() for _ in range(4)]
                
                self.stmts(for_scope, [s.head])
                self.emit(Label(loop_lbl))
                self.expr(for_scope, s.condition)
                self.emit(Bne(body_lbl))
                self.emit(Jmp(nxt_lbl))
                self.emit(Label(tail_lbl))
                self.stmts(for_scope, [s.tail])
                self.emit(Jmp(loop_lbl))
                self.emit(Label(body_lbl))
                self.stmts(for_scope, s.body)
                self.emit(Jmp(tail_lbl))
                self.emit(Label(nxt_lbl))
                
            elif isinstance(s, StmtDoWhile):
                loop_lbl = self.new_label()
                self.emit(Label(loop_lbl))
                self.stmts(scope, s.body)
                self.expr(scope, s.condition)
                self.emit(Bne(loop_lbl))
                
            elif isinstance(s, StmtSwitch):
                switch_lbl = self.new_label()
                nxt_lbl = self.new_label()
                self.expr(scope, s.condition)
                self.emit(Jmp(switch_lbl))
                
                for switch_case in s.cases:
                    if isinstance(switch_case, SwitchCaseCase):
                        for c_exp in switch_case.exprs:
                            val = eval_expr(c_exp, scope)
                            if isinstance(val, ConstValInt):
                                self.emit(Case(s.switch_id, CaseVal(val.value)))
                        self.stmts(scope, switch_case.stmts)
                        # omit jump if exit was issued
                        if not switch_case.stmts or not isinstance(switch_case.stmts[-1], StmtExit):
                            self.emit(Jmp(nxt_lbl))
                    elif isinstance(switch_case, SwitchCaseDefault):
                        self.emit(Case(s.switch_id, CaseDefault()))
                        self.stmts(scope, switch_case.stmts)
                        if not switch_case.stmts or not isinstance(switch_case.stmts[-1], StmtExit):
                            self.emit(Jmp(nxt_lbl))
                            
                self.emit(Jmp(nxt_lbl)) # dead code pad
                self.emit(Label(switch_lbl))
                self.emit(Switch(s.switch_id))
                self.emit(Label(nxt_lbl))
                
            elif isinstance(s, StmtExit):
                self.emit(Exit())
                
    def end(self) -> Script:
        if self.errors:
            raise CompileError("\n".join(self.errors))
        return Script(self.instructions, self.strings)

def compile_script(stmts: List[Stmt], const_scope: ConstScope) -> Script:
    # We allocate switch ids
    sid_alloc = 0
    def alloc_switches(stmt_list):
        nonlocal sid_alloc
        for s in stmt_list:
            if isinstance(s, StmtIf): alloc_switches(s.stmts)
            elif isinstance(s, StmtIfElse): alloc_switches(s.true_stmts); alloc_switches(s.false_stmts)
            elif isinstance(s, StmtFor): alloc_switches(s.body)
            elif isinstance(s, StmtDoWhile): alloc_switches(s.body)
            elif isinstance(s, StmtSwitch):
                s.switch_id = SwitchId(sid_alloc)
                sid_alloc += 1
                for sc in s.cases:
                    alloc_switches(sc.stmts)
                    
    alloc_switches(stmts)
    emitter = Emitter()
    emitter.stmts(const_scope, stmts)
    return emitter.end()

def eval_expr(expr: Expr, scope: ConstScope) -> Optional[ConstVal]:
    if isinstance(expr, ExprInt):
        return ConstValInt(expr.value)
    if isinstance(expr, ExprStr):
        return ConstValStr(expr.value)
    if isinstance(expr, ExprName):
        return scope.lookup_const(expr.name)
    return None

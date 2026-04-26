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
        self.known_callables = known_callables

    def remaining(self) -> int:
        return len(self.state.input)

    def at_end(self) -> bool:
        return self.remaining() == 0

    def back(self) -> List[DecompileToken]:
        return self.state.stack

    def is_expr(self, token: DecompileToken) -> bool:
        return isinstance(token, (TokenExpr, TokenFunctionCall, TokenPushVar, TokenPushInt))

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
        if len(self.back()) >= 2 and isinstance(self.back()[-2], TokenPushInt) and self.is_expr(self.back()[-1]):
            input_head = self.state.input.pop(0)
            op = AssignOperation.NONE
            if isinstance(input_head, AssignAdd): op = AssignOperation.ADD
            elif isinstance(input_head, AssignSub): op = AssignOperation.SUB
            elif isinstance(input_head, AssignMul): op = AssignOperation.MUL
            elif isinstance(input_head, AssignDiv): op = AssignOperation.DIV
            elif isinstance(input_head, AssignMod): op = AssignOperation.MOD
            
            var_id, expr = self.pop_assign_params()
            self.state.stack.append(TokenAssignExpr(var_id, op, expr))
            return
        raise DecompileError("Could not reduce assign")

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

    def match_at_discard(self):
        if len(self.back()) >= 1:
            tok = self.back()[-1]
            if isinstance(tok, TokenFunctionCall):
                self.state.input.pop(0)
                invoke = self.state.stack.pop().invoke
                self.push_stmt(StmtCall(invoke))
                return
            elif self.is_expr(tok):
                self.state.input.pop(0)
                expr = self.pop_expr()
                self.push_stmt(StmtExpr(expr))
                return
            elif isinstance(tok, TokenAssignExpr):
                self.state.input.pop(0)
                asg = self.state.stack.pop()
                self.push_stmt(StmtAssign(asg.op, self.variable_name(asg.var_id), asg.expr))
                return
        raise DecompileError("Could not reduce discard")

    def match_at_label(self, label_jump_id: JumpId):
        stack = self.back()
        if len(stack) >= 3 and getattr(stack[-2], 'jump_id', None) == label_jump_id and isinstance(stack[-2], TokenBeq) and isinstance(stack[-1], TokenStmts) and self.is_expr(stack[-3]):
            self.state.input.pop(0)
            stmts = self.state.stack.pop().stmts
            self.state.stack.pop() # beq
            cond = self.pop_expr()
            self.push_stmt(StmtIf(cond, stmts))
            return
            
        if len(stack) >= 2 and getattr(stack[-1], 'jump_id', None) == label_jump_id and isinstance(stack[-1], TokenBeq) and self.is_expr(stack[-2]):
            self.state.input.pop(0)
            self.state.stack.pop()
            cond = self.pop_expr()
            self.push_stmt(StmtIf(cond, []))
            return

        if len(stack) >= 6 and isinstance(stack[-1], TokenStmts) and isinstance(stack[-2], TokenLabel) and isinstance(stack[-3], TokenJump) and isinstance(stack[-4], TokenStmts) and getattr(stack[-5], 'jump_id', None) == getattr(stack[-2], 'jump_id', None) and isinstance(stack[-5], TokenBeq) and self.is_expr(stack[-6]):
            if stack[-3].jump_id == label_jump_id:
                self.state.input.pop(0)
                else_stmts = self.state.stack.pop().stmts
                self.state.stack.pop() # label k
                self.state.stack.pop() # jmp l
                true_stmts = self.state.stack.pop().stmts
                self.state.stack.pop() # beq
                cond = self.pop_expr()
                self.push_stmt(StmtIfElse(cond, true_stmts, else_stmts))
                return
        raise DecompileError("Could not reduce at label")

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
            elif isinstance(ins, Discard):
                self.match_at_discard()
            elif isinstance(ins, Jmp):
                self.state.stack.append(TokenJump(ins.jump_id))
                self.state.input.pop(0)
            elif isinstance(ins, Beq):
                self.state.stack.append(TokenBeq(ins.jump_id))
                self.state.input.pop(0)
            elif isinstance(ins, Bne):
                self.state.stack.append(TokenBne(ins.jump_id))
                self.state.input.pop(0)
            elif isinstance(ins, Call):
                name, shape = self.known_callables.get(ins.call_id, (f"Func{ins.call_id.id:03X}", CallableShape.new_proc([])))
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
        except DecompileError:
            # If a reduction fails, we must at least consume the instruction to avoid infinite loops
            self.state.input.pop(0)

def decompile_instructions(instructions: List[Ins], known_callables: Dict[CallId, Tuple[str, CallableShape]]) -> List[Stmt]:
    decompiler = InsDecompiler(instructions, known_callables)
    while not decompiler.at_end():
        decompiler.advance()
        
    stmts = []
    # FIX: Collect ALL tokens from the stack, not just the first one.
    for token in decompiler.state.stack:
        if isinstance(token, TokenStmts):
            stmts.extend(token.stmts)
        elif isinstance(token, TokenExpr):
            stmts.append(StmtExpr(token.expr))
        elif isinstance(token, TokenFunctionCall):
            stmts.append(StmtCall(token.invoke))
        elif isinstance(token, TokenAssignExpr):
            stmts.append(StmtAssign(token.op, decompiler.variable_name(token.var_id), token.expr))
        elif isinstance(token, TokenPushVar):
            stmts.append(StmtExpr(ExprName(decompiler.variable_name(token.var_id))))
        elif isinstance(token, TokenPushInt):
            stmts.append(StmtExpr(ExprInt(token.value)))
    
    # Prepend variable declarations
    if decompiler.variables:
        var_decls = []
        max_id = max(vid.id for vid in decompiler.variables.keys())
        for i in range(max_id + 1):
            vid = VarId(i)
            if vid in decompiler.variables:
                var_decls.append((decompiler.variables[vid], None))
        if var_decls:
            stmts.insert(0, StmtVars(var_decls))
            
    return stmts

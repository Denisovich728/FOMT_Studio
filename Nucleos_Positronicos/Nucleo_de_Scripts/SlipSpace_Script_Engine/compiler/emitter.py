# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ------------------------------------------------------------
# Revisión del emitter:
#  - switch: los `case` apilados (estilo C) ahora comparten cuerpo
#  - flags sin nombre (Flag_0xNNN) se compilan al ID real
#  - resolución de nombres según el contexto (switch / Check_Flag)
#  - avisos (emitter.warnings) en vez de fallos silenciosos
#  - scopes anidados ya no reinician los IDs de variables
#  - Emitter.listing() para comparar contra el script original
# ============================================================
import re
import logging
from typing import List, Dict, Optional
from ..ir import *
from ..ast import *

log = logging.getLogger("fomt.emitter")

# Nombres sin entrada en el CSV que el descompilador escribe como Flag_0x173, etc.
_UNNAMED_ID_RE = re.compile(
    r"^(?:Flag|Item|Food|Tool|Char|Map|Emote|Anim|Portrait|Candidate)_0x([0-9A-Fa-f]+)$"
)


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
    # Qué tabla de nombres usar según la función que alimenta el switch.
    # (Evita que "Apple" se resuelva con el ID de item cuando el switch es de comida.)
    _SWITCH_CTX = {
        "Search_Food_Gift_Address": "food_resolver",
        "Search_Item_Gift_Address": "item_resolver",
        "GetEntityLocation": "map_resolver",
        "Check_Equped_Tool": "tool_resolver",
    }

    def __init__(self, item_resolver: Dict[str, int] = None, food_resolver: Dict[str, int] = None,
                 tool_resolver: Dict[str, int] = None, char_resolver: Dict[str, int] = None,
                 candidate_resolver: Dict[str, int] = None, portrait_resolver: Dict[str, int] = None,
                 map_resolver: Dict[str, int] = None, emote_resolver: Dict[str, int] = None,
                 anim_resolver: Dict[str, int] = None, flag_resolver: Dict[str, int] = None):
        self.item_resolver = item_resolver or {}
        self.food_resolver = food_resolver or {}
        self.tool_resolver = tool_resolver or {}
        self.char_resolver = char_resolver or {}
        self.candidate_resolver = candidate_resolver or {}
        self.portrait_resolver = portrait_resolver or {}
        self.map_resolver = map_resolver or {}
        self.emote_resolver = emote_resolver or {}
        self.anim_resolver = anim_resolver or {}
        self.flag_resolver = flag_resolver or {}
        self.instructions: List[Ins] = []
        self.strings: List[bytes] = []
        self.location_counter = 0
        self.errors = []
        self.warnings: List[str] = []
        self.break_targets: List[JumpId] = []
        self.user_labels: Dict[str, JumpId] = {}
        self._str_cache: Dict[bytes, int] = {}
        self._call_ctx = None   # (nombre_funcion, indice_arg) para los avisos

    # ---------------------------------------------------------
    # Utilidades
    # ---------------------------------------------------------
    def warn(self, msg: str):
        if msg not in self.warnings:
            self.warnings.append(msg)
            log.warning(msg)

    def new_label(self) -> JumpId:
        self.location_counter += 1
        return JumpId(self.location_counter)

    def get_user_label(self, name: str) -> JumpId:
        if name not in self.user_labels:
            self.user_labels[name] = self.new_label()
        return self.user_labels[name]

    def emit(self, ins: Ins):
        self.instructions.append(ins)

    def emit_str_id(self, string: bytes) -> int:
        idx = self._str_cache.get(string)
        if idx is not None:
            return idx
        self.strings.append(string)
        idx = len(self.strings) - 1
        self._str_cache[string] = idx
        return idx

    @staticmethod
    def _message_index(name: str) -> Optional[int]:
        if not name.startswith("MESSAGE_"):
            return None
        tail = name[len("MESSAGE_"):]
        try:
            return int(tail, 16 if tail.lower().startswith("0x") else 10)
        except ValueError:
            return None

    def _reserve_messages(self, stmts: List[Stmt]):
        """Reserva de antemano la tabla de mensajes para que ningún string
        auxiliar pise un índice MESSAGE_N declarado más abajo."""
        for s in stmts:
            if isinstance(s, StmtConsts):
                for name, _ in s.consts:
                    idx = self._message_index(name)
                    if idx is not None:
                        while len(self.strings) <= idx:
                            self.strings.append(b"")
            elif isinstance(s, StmtMessage):
                while len(self.strings) <= s.index:
                    self.strings.append(b"")
            elif isinstance(s, StmtIf):
                self._reserve_messages(s.stmts)
            elif isinstance(s, StmtIfElse):
                self._reserve_messages(s.true_stmts)
                self._reserve_messages(s.false_stmts)
            elif isinstance(s, (StmtFor, StmtDoWhile)):
                self._reserve_messages(s.body)
            elif isinstance(s, StmtSwitch):
                for sc in s.cases:
                    self._reserve_messages(sc.stmts)

    def const_value(self, val: ConstVal):
        if isinstance(val, ConstValInt):
            self.emit(PushInt(val.value))
        elif isinstance(val, ConstValStr):
            id_val = self.emit_str_id(val.value)
            self.emit(PushInt(id_val))

    # ---------------------------------------------------------
    # Expresiones
    # ---------------------------------------------------------
    def expr(self, scope: BlockScope, expr: Expr):
        if isinstance(expr, ExprName):
            idx = self._message_index(expr.name)
            if idx is not None:
                self.emit(PushInt(idx))
                return

            ref = scope.lookup_name(expr.name)
            if isinstance(ref, NameRefVar): self.emit(PushVar(ref.var_id))
            elif isinstance(ref, NameRefConst): self.const_value(ref.val)
            else: self.errors.append(f"Name not declared or invalid: {expr.name}")
        elif isinstance(expr, ExprInt):
            self.emit(PushInt(expr.value))
        elif isinstance(expr, ExprStr):
            resolved = eval_expr(expr, scope, self)
            if isinstance(resolved, ConstValInt):
                self.emit(PushInt(resolved.value))
            else:
                text = expr.value.decode('windows-1252', errors='replace')
                ctx = f" (en {self._call_ctx[0]}, arg {self._call_ctx[1]})" if self._call_ctx else ""
                self.warn(f"Nombre sin resolver '{text}'{ctx}: se emitió como índice de string, NO como ID")
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
            if isinstance(ref, NameRefFunc):
                self._emit_invoke_args(scope, expr.invoke)
                self.emit(Call(ref.call_id))
            else:
                self.errors.append(f"Not callable: {expr.invoke.func}")

    def _emit_invoke_args(self, scope: BlockScope, invoke: Invoke):
        is_give_item = invoke.func in ("Give_Item", "Get_Item_Sprite_ID", "Add_Item_To_Rucksack_Raw")
        is_give_food = (invoke.func == "Give_Food")
        is_give_tool = invoke.func in (
            "Give_Tool", "Give_Tool_TBox", "Give_Tool_In_ToolBox",
            "Give_Tool_In_Inventory", "Animation_Tool_Give",
            "Anmation_Tool_Give", "Take_Tool"
        )
        is_flag_func = invoke.func in ("Check_Flag", "Set_Flag")

        char_funcs = (
            "Set_Name_Window", "Give_Friendship_Points", "Free_Event_Entity",
            "Set_Entity_Position", "Get_Entity_X", "Get_Entity_Y",
            "Set_Entity_Facing", "Set_Entit_y_Facing", "Get_Entity_Facing",
            "Get_Entity_X_Facing", "Despawn_Entity",
            "Is_NPC_Birthday", "Chek_Friendship_Points", "Has_NPC_Talked_Today",
            "Has_NPC_Talked_Today_2", "Kill_NPC", "Execute_Movement", "SetEntityAnim",
            "Hide_Entity", "GetEntityLocation", "Wait_For_Animation",
            "Set_Vector_X", "Set_Vector_Y", "Has_Met_NPC", "Has_Spoken_To_NPC_Today",
            "SetEntityFacing", "GetEntityFacing"
        )
        is_char_func = invoke.func in char_funcs
        is_routine_override = (invoke.func == "Routine_State_Override")

        is_candidate_func = invoke.func in ("Set_Hearth_Anim", "Give_Love_Points", "Chek_Love_Points")
        is_portrait_func = (invoke.func == "Set_Portrait")
        is_map_func = invoke.func in ("Warp_Player", "Warp_Entity_To_Map")

        for i, arg in enumerate(invoke.args):
            if isinstance(arg, ExprStr):
                name = arg.value.decode('windows-1252', errors='ignore').strip()
                resolved = False

                if i == 0:
                    if is_flag_func:
                        v = eval_expr(arg, scope, self, self.flag_resolver)
                        if isinstance(v, ConstValInt):
                            self.emit(PushInt(v.value)); resolved = True
                    elif is_give_item:
                        if name in self.item_resolver:
                            self.emit(PushInt(self.item_resolver[name])); resolved = True
                    elif is_give_food:
                        if name in self.food_resolver:
                            self.emit(PushInt(self.food_resolver[name])); resolved = True
                    elif is_give_tool:
                        if name in self.tool_resolver:
                            self.emit(PushInt(self.tool_resolver[name])); resolved = True
                        elif name in self.item_resolver:
                            self.emit(PushInt(self.item_resolver[name])); resolved = True
                    elif is_candidate_func:
                        if name in self.candidate_resolver:
                            self.emit(PushInt(self.candidate_resolver[name])); resolved = True
                        elif name in self.char_resolver:
                            self.emit(PushInt(self.char_resolver[name])); resolved = True
                    elif is_portrait_func:
                        if name in self.portrait_resolver:
                            self.emit(PushInt(self.portrait_resolver[name])); resolved = True
                    elif is_char_func:
                        if name == "Player":
                            self.emit(PushInt(0)); resolved = True
                        elif name in self.char_resolver:
                            self.emit(PushInt(self.char_resolver[name])); resolved = True
                    elif is_map_func:
                        if invoke.func == "Warp_Player":
                            if name in self.map_resolver:
                                self.emit(PushInt(self.map_resolver[name])); resolved = True
                        else:  # Warp_Entity_To_Map (Arg 0 es la entidad)
                            if name == "Player":
                                self.emit(PushInt(0)); resolved = True
                            elif name in self.char_resolver:
                                self.emit(PushInt(self.char_resolver[name])); resolved = True

                elif i == 1:
                    if invoke.func == "Show_Emote":
                        if name in self.emote_resolver:
                            self.emit(PushInt(self.emote_resolver[name])); resolved = True
                    elif invoke.func == "SetEntityAnim":
                        if name in self.anim_resolver:
                            self.emit(PushInt(self.anim_resolver[name])); resolved = True
                    elif invoke.func == "Warp_Entity_To_Map":
                        if name in self.map_resolver:
                            self.emit(PushInt(self.map_resolver[name])); resolved = True

                # --- RESOLUCIÓN DE RUTINAS (Nombre_Routine -> ID) ---
                if not resolved and name.endswith("_Routine") and invoke.func == "Routine_State_Override" and i == 1:
                    raw_name = name.replace("_Routine", "")
                    if raw_name in self.char_resolver:
                        self.emit(PushInt(self.char_resolver[raw_name])); resolved = True

                facing_names = {"Down": 0, "Up": 1, "Left": 2, "Right": 3}
                if not resolved and name in facing_names:
                    target_idx = -1
                    if invoke.func in ("SetEntityFacing", "Set_Entity_Facing", "Set_Entit_y_Facing"):
                        target_idx = 1
                    elif invoke.func in ("SetEntityPosition", "Set_Entity_Position"):
                        target_idx = 3
                    if i == target_idx:
                        self.emit(PushInt(facing_names[name])); resolved = True

                if not resolved and (name.startswith("Pos_X:") or name.startswith("Pos_Y:")):
                    try:
                        num_str = name.split(":", 1)[1].strip()
                        self.emit(PushInt(int(num_str, 16 if "0x" in num_str else 10))); resolved = True
                    except ValueError:
                        pass

                if resolved:
                    continue

            self._call_ctx = (invoke.func, i)
            try:
                self.expr(scope, arg)
            finally:
                self._call_ctx = None

    def expr_cmp(self, scope, lhs, rhs, branch_cls):
        lbl_true = self.new_label()
        lbl_next = self.new_label()
        self.expr(scope, lhs); self.expr(scope, rhs); self.emit(Cmp()); self.emit(branch_cls(lbl_true))
        self.emit(PushInt(0)); self.emit(Jmp(lbl_next)); self.emit(Label(lbl_true)); self.emit(PushInt(1)); self.emit(Label(lbl_next))

    def assign(self, scope, var_id, expr, op):
        self.emit(PushInt(var_id.id)); self.expr(scope, expr)
        if op == AssignOperation.NONE: self.emit(Assign())
        elif op == AssignOperation.ADD: self.emit(AssignAdd())
        elif op == AssignOperation.SUB: self.emit(AssignSub())
        elif op == AssignOperation.MUL: self.emit(AssignMul())
        elif op == AssignOperation.DIV: self.emit(AssignDiv())
        elif op == AssignOperation.MOD: self.emit(AssignMod())
        self.emit(Discard())

    # ---------------------------------------------------------
    # switch
    # ---------------------------------------------------------
    def _switch_resolver(self, cond: Expr) -> Optional[Dict[str, int]]:
        if isinstance(cond, ExprCall):
            attr = self._SWITCH_CTX.get(cond.invoke.func)
            if attr:
                return getattr(self, attr)
        return None

    @staticmethod
    def _expr_text(e: Expr) -> str:
        if isinstance(e, ExprStr):
            return e.value.decode('windows-1252', errors='replace')
        if isinstance(e, ExprInt):
            return hex(e.value)
        return type(e).__name__

    def _emit_switch(self, scope: BlockScope, s: StmtSwitch):
        prefer = self._switch_resolver(s.condition)
        switch_logic_lbl, nxt_lbl = self.new_label(), self.new_label()
        self.break_targets.append(nxt_lbl)
        self.expr(scope, s.condition)
        self.emit(Jmp(switch_logic_lbl))

        seen = set()
        pending: List[Expr] = []   # `case` apilados sin cuerpo (fall-through estilo C)
        n_cases = len(s.cases)

        for n, sc in enumerate(s.cases):
            is_last = (n == n_cases - 1)

            if isinstance(sc, SwitchCaseCase):
                if not sc.stmts and not is_last:
                    # case "A": case "B": cuerpo  ->  A y B comparten el cuerpo
                    pending.extend(sc.exprs)
                    continue
                exprs = pending + list(sc.exprs)
                is_default = False
            else:
                exprs = pending
                is_default = True
            pending = []

            body_lbl = self.new_label()
            self.emit(Label(body_lbl))

            for c_exp in exprs:
                val = eval_expr(c_exp, scope, self, prefer)
                if isinstance(val, ConstValInt):
                    if val.value in seen:
                        self.warn(f"switch: valor duplicado {hex(val.value)} ('{self._expr_text(c_exp)}'); "
                                  f"dos nombres del CSV comparten el mismo ID")
                        continue
                    seen.add(val.value)
                    self.emit(Case(s.switch_id, CaseVal(val.value)))
                else:
                    self.warn(f"switch: case '{self._expr_text(c_exp)}' no se pudo resolver y se DESCARTÓ")

            if is_default:
                self.emit(Case(s.switch_id, CaseDefault()))

            self.stmts(scope, sc.stmts)
            if not sc.stmts or not isinstance(sc.stmts[-1], (StmtExit, StmtBreak)):
                self.emit(Jmp(nxt_lbl))

        self.emit(Label(switch_logic_lbl))
        self.emit(Switch(s.switch_id))
        self.emit(Label(nxt_lbl))
        self.break_targets.pop()

    # ---------------------------------------------------------
    # Sentencias
    # ---------------------------------------------------------
    def stmts(self, parent_scope: BlockScope, stmts_list: List[Stmt]):
        # El scope hijo continúa la numeración de variables del padre
        scope = BlockScope(parent=parent_scope, var_frame=parent_scope.next_id())
        for s in stmts_list:
            if isinstance(s, StmtVars):
                for name, exp in s.vars:
                    vid = scope.define_var(name)
                    if exp: self.assign(scope, vid, exp, AssignOperation.NONE)
            elif isinstance(s, StmtMessage):
                while len(self.strings) <= s.index: self.strings.append(b"")
                self.strings[s.index] = s.text
            elif isinstance(s, StmtConsts):
                for name, exp in s.consts:
                    val = eval_expr(exp, scope)
                    if val is not None:
                        scope.define_const(name, val)
                        if isinstance(val, ConstValStr):
                            idx = self._message_index(name)
                            if idx is not None:
                                while len(self.strings) <= idx: self.strings.append(b"")
                                self.strings[idx] = val.value
                            else:
                                self.emit_str_id(val.value)
            elif isinstance(s, StmtAssign):
                ref = scope.lookup_name(s.name)
                self.assign(scope, ref.var_id, s.expr, s.op)
            elif isinstance(s, StmtExpr):
                self.expr(scope, s.expr); self.emit(Discard())
            elif isinstance(s, StmtCall):
                ref = scope.lookup_name(s.invoke.func)
                if ref:
                    self._emit_invoke_args(scope, s.invoke)
                    self.emit(Call(ref.call_id))
                    if isinstance(ref, NameRefFunc): self.emit(Discard())
                else: self.errors.append(f"Undefined function/procedure: {s.invoke.func}")
            elif isinstance(s, StmtIf):
                nxt = self.new_label(); self.expr(scope, s.condition); self.emit(Beq(nxt)); self.stmts(scope, s.stmts); self.emit(Label(nxt))
            elif isinstance(s, StmtIfElse):
                else_lbl, nxt_lbl = self.new_label(), self.new_label()
                self.expr(scope, s.condition); self.emit(Beq(else_lbl)); self.stmts(scope, s.true_stmts); self.emit(Jmp(nxt_lbl)); self.emit(Label(else_lbl)); self.stmts(scope, s.false_stmts); self.emit(Label(nxt_lbl))
            elif isinstance(s, StmtFor):
                for_scope = BlockScope(parent=scope, var_frame=scope.next_id())
                loop_lbl, tail_lbl, body_lbl, nxt_lbl = [self.new_label() for _ in range(4)]
                self.stmts(for_scope, [s.head]); self.emit(Label(loop_lbl)); self.expr(for_scope, s.condition); self.emit(Bne(body_lbl)); self.emit(Jmp(nxt_lbl)); self.emit(Label(tail_lbl)); self.stmts(for_scope, [s.tail]); self.emit(Jmp(loop_lbl)); self.emit(Label(body_lbl)); self.break_targets.append(nxt_lbl); self.stmts(for_scope, s.body); self.break_targets.pop(); self.emit(Jmp(tail_lbl)); self.emit(Label(nxt_lbl))
            elif isinstance(s, StmtDoWhile):
                loop_lbl, nxt_lbl = self.new_label(), self.new_label(); self.emit(Label(loop_lbl)); self.break_targets.append(nxt_lbl); self.stmts(scope, s.body); self.break_targets.pop(); self.expr(scope, s.condition); self.emit(Bne(loop_lbl)); self.emit(Label(nxt_lbl))
            elif isinstance(s, StmtSwitch):
                self._emit_switch(scope, s)
            elif isinstance(s, StmtExit): self.emit(Exit())
            elif isinstance(s, StmtBreak): self.emit(Jmp(self.break_targets[-1]))
            elif isinstance(s, StmtLabel):
                name = s.jump_id.id if isinstance(s.jump_id, JumpId) else str(s.jump_id)
                self.emit(Label(self.get_user_label(name)))
            elif isinstance(s, StmtGoto):
                name = s.jump_id.id if isinstance(s.jump_id, JumpId) else str(s.jump_id)
                self.emit(Jmp(self.get_user_label(name)))

    # ---------------------------------------------------------
    # Salida / depuración
    # ---------------------------------------------------------
    def end(self) -> Script:
        if self.errors: raise CompileError("\n".join(self.errors))
        return Script(self.instructions, self.strings)

    def listing(self) -> str:
        """Volcado legible de las instrucciones, para comparar con el script original."""
        lines = []
        for i, ins in enumerate(self.instructions):
            try:
                args = ", ".join(f"{k}={v!r}" for k, v in vars(ins).items())
            except TypeError:
                args = repr(ins)
            lines.append(f"{i:05d}  {type(ins).__name__}({args})")
        return "\n".join(lines)


def compile_script(stmts: List[Stmt], const_scope: ConstScope, strict: bool = False, **resolvers) -> Script:
    sid_alloc = 0

    def alloc_switches(stmt_list):
        nonlocal sid_alloc
        for s in stmt_list:
            if isinstance(s, StmtIf): alloc_switches(s.stmts)
            elif isinstance(s, StmtIfElse): alloc_switches(s.true_stmts); alloc_switches(s.false_stmts)
            elif isinstance(s, StmtFor): alloc_switches(s.body)
            elif isinstance(s, StmtDoWhile): alloc_switches(s.body)
            elif isinstance(s, StmtSwitch):
                s.switch_id = SwitchId(sid_alloc); sid_alloc += 1
                for sc in s.cases: alloc_switches(sc.stmts)

    alloc_switches(stmts)
    emitter = Emitter(**resolvers)
    emitter._reserve_messages(stmts)
    emitter.stmts(const_scope, stmts)

    if strict and emitter.warnings:
        raise CompileError("\n".join(emitter.warnings))

    script = emitter.end()
    try:
        script.warnings = list(emitter.warnings)   # revisa esto tras compilar
    except Exception:
        pass
    return script


def eval_expr(expr: Expr, scope: ConstScope, emitter: Emitter = None,
              prefer: Optional[Dict[str, int]] = None) -> Optional[ConstVal]:
    if isinstance(expr, ExprInt): return ConstValInt(expr.value)
    if isinstance(expr, ExprStr):
        name = expr.value.decode('windows-1252', errors='ignore').strip()
        if prefer and name in prefer: return ConstValInt(prefer[name])
        if name == "Player": return ConstValInt(0)
        if emitter:
            for r in [emitter.char_resolver, emitter.item_resolver, emitter.food_resolver, emitter.tool_resolver,
                      emitter.candidate_resolver, emitter.portrait_resolver, emitter.map_resolver,
                      emitter.emote_resolver, emitter.anim_resolver, emitter.flag_resolver]:
                if name in r: return ConstValInt(r[name])
        if name.startswith("Script_"):
            try: return ConstValInt(int(name.replace("Script_", "")))
            except ValueError: pass
        if name.startswith("Pos_X:") or name.startswith("Pos_Y:"):
            try:
                num_str = name.split(":", 1)[1].strip()
                return ConstValInt(int(num_str, 16 if "0x" in num_str else 10))
            except ValueError: pass
        m = _UNNAMED_ID_RE.match(name)     # Flag_0x173 -> 0x173
        if m:
            return ConstValInt(int(m.group(1), 16))
        return ConstValStr(expr.value)
    if isinstance(expr, ExprName): return scope.lookup_const(expr.name)
    return None
from typing import List, Dict, Optional
from ..ast import *
from ..ir import ValueTypeEnum

from .error import DecompileError

def _find_call_in_expr(expr, func_names):
    """Busca recursivamente una ExprCall con nombre en func_names dentro de operadores binarios."""
    if isinstance(expr, ExprCall) and expr.invoke.func in func_names:
        return expr
    # Recorrer operadores binarios (AND, OR, etc.)
    if hasattr(expr, 'lhs'):
        found = _find_call_in_expr(expr.lhs, func_names)
        if found: return found
    if hasattr(expr, 'rhs'):
        found = _find_call_in_expr(expr.rhs, func_names)
        if found: return found
    if hasattr(expr, 'inner'):
        found = _find_call_in_expr(expr.inner, func_names)
        if found: return found
    return None

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
        # Estandarizar índices de mensajes a decimal para coherencia con constantes
        msg_funcs = ("TalkMessage", "TalkMessageSlow", "Print_Message", "Print_TV_Message", "Show_Tre_Option_Menu")
        if invoke.func in msg_funcs:
            for arg in invoke.args:
                if isinstance(arg, ExprInt):
                    arg.force_decimal = True

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
    def __init__(self, item_names: Dict[int, str], food_names: Dict[int, str], tool_names: Dict[int, str], known_callables: Dict):
        super().__init__([], known_callables)
        self.item_names = item_names
        self.food_names = food_names
        self.tool_names = tool_names
        self.force_item_context = False
        self.force_food_context = False

    def visit_invoke(self, invoke: Invoke):
        if invoke.func in ("Give_Item", "Get_Item_Sprite_ID", "Add_Item_To_Rucksack_Raw") and len(invoke.args) >= 1:
            self.stringify_expr(invoke.args, 0, self.item_names)
        elif invoke.func == "Give_Food" and len(invoke.args) >= 1:
            self.stringify_expr(invoke.args, 0, self.food_names)
        elif invoke.func in ("Give_Tool", "Give_Tool_TBox", "Give_Tool_In_ToolBox", "Give_Tool_In_Inventory", "Animation_Tool_Give", "Anmation_Tool_Give", "Take_Tool") and len(invoke.args) >= 1:
            self.stringify_expr(invoke.args, 0, self.tool_names)
            # Fallback para semillas/variados que se usan como herramientas
            if isinstance(invoke.args[0], ExprInt):
                self.stringify_expr(invoke.args, 0, self.item_names)
        else:
            super().visit_invoke(invoke)

    def _peek_search_func(self, stmts: List[Stmt]) -> Optional[str]:
        """Escanea un bloque de código buscando llamadas a funciones de búsqueda de regalos."""
        item_search_funcs = ("Search_Item_Gift_Address", "Search__Item_Gift_Address")
        food_search_funcs = ("Search_Food_Gift_Address", "Search__Food_Gift_Address")
        all_search_funcs = item_search_funcs + food_search_funcs

        for s in stmts:
            if isinstance(s, StmtCall) and s.invoke.func in all_search_funcs:
                return s.invoke.func
            if isinstance(s, StmtExpr) and isinstance(s.expr, ExprCall) and s.expr.invoke.func in all_search_funcs:
                return s.expr.invoke.func
            if isinstance(s, StmtSwitch):
                if isinstance(s.condition, ExprCall) and s.condition.invoke.func in all_search_funcs:
                    return s.condition.invoke.func
            # Búsqueda recursiva simple en bloques condicionales
            if isinstance(s, StmtIf):
                res = self._peek_search_func(s.stmts)
                if res: return res
            elif isinstance(s, StmtIfElse):
                res = self._peek_search_func(s.true_stmts) or self._peek_search_func(s.false_stmts)
                if res: return res
        return None

    def _decorate_case_label(self, case: SwitchCaseCase, label: str):
        """Añade una etiqueta descriptiva al valor del case del switch padre."""
        for i, ex in enumerate(case.exprs):
            if isinstance(ex, ExprInt):
                # Ejemplo: 0 -> "FOOD_GIFT (0)"
                val_str = f"{label} ({ex.value})".encode('windows-1252', errors='replace')
                case.exprs[i] = ExprStr(val_str)

    def visit_expr(self, expr: Expr):
        # Manejar comparaciones complejas en el AST (ExprCmpEq, ExprCmpGe, etc.)
        if isinstance(expr, (ExprCmpEq, ExprCmpNe, ExprCmpLt, ExprCmpLe, ExprCmpGt, ExprCmpGe)):
            if isinstance(expr.lhs, ExprCall) and expr.lhs.invoke.func == "Check_Equped_Tool":
                if isinstance(expr.rhs, ExprInt):
                    val = expr.rhs.value
                    if val in self.tool_names:
                        name_bytes = self.tool_names[val].encode('windows-1252', errors='replace')
                        expr.rhs = ExprStr(name_bytes)
        super().visit_expr(expr)

    def visit_stmt(self, stmt: Stmt):
        if isinstance(stmt, StmtSwitch):
            # Contexto de herramientas en switch
            is_check_tool = False
            if isinstance(stmt.condition, ExprCall) and stmt.condition.invoke.func == "Check_Equped_Tool":
                is_check_tool = True

            if is_check_tool:
                for case in stmt.cases:
                    if isinstance(case, SwitchCaseCase):
                        for i in range(len(case.exprs)):
                            self.stringify_item_expr(case.exprs, i, self.tool_names)

            # Contexto original de búsqueda de regalos
            is_search_item = self.force_item_context
            is_search_food = self.force_food_context
            
            if isinstance(stmt.condition, ExprCall):
                f = stmt.condition.invoke.func
                if f in ("Search_Item_Gift_Address", "Search__Item_Gift_Address"): is_search_item = True
                elif f in ("Search_Food_Gift_Address", "Search__Food_Gift_Address"): is_search_food = True

            if is_search_item:
                for case in stmt.cases:
                    if isinstance(case, SwitchCaseCase):
                        for i in range(len(case.exprs)):
                            self.stringify_item_expr(case.exprs, i, self.item_names)
            elif is_search_food:
                for case in stmt.cases:
                    if isinstance(case, SwitchCaseCase):
                        for i in range(len(case.exprs)):
                            self.stringify_item_expr(case.exprs, i, self.food_names)
            
            # Visitar cuerpo de los casos
            for case in stmt.cases:
                self.visit_stmts(case.stmts)
        else:
            super().visit_stmt(stmt)

    def stringify_item_expr(self, expr_container: list, idx: int, mapping: Dict[int, str]):
        expr = expr_container[idx]
        if isinstance(expr, ExprInt):
            val = expr.value
            if val in mapping:
                name_bytes = mapping[val].encode('windows-1252', errors='replace')
                expr_container[idx] = ExprStr(name_bytes)
            # Limpiamos el comentario si existía de una pasada anterior
            if hasattr(expr, 'comment'):
                expr.comment = None

    def stringify_expr(self, expr_container: list, idx: int, mapping: Dict[int, str]):
        self.stringify_item_expr(expr_container, idx, mapping)

def decorate_stmts_with_items(stmts: List[Stmt], item_names: Dict[int, str], food_names: Dict[int, str], tool_names: Dict[int, str], known_callables: Dict):
    if not item_names and not food_names and not tool_names:
        return
    visitor = ItemDecorateVisitor(item_names, food_names, tool_names, known_callables)
    visitor.visit_stmts(stmts)

class CharacterDecorateVisitor(StringDecorateVisitor):
    def __init__(self, char_names: Dict[int, str], candidate_names: Dict[int, str], portrait_names: Dict[int, str], map_names: Dict[int, str], emote_names: Dict[int, str], anim_names: Dict[int, str], known_callables: Dict):
        super().__init__([], known_callables)
        self.char_names = char_names
        self.candidate_names = candidate_names
        self.portrait_names = portrait_names
        self.map_names = map_names
        self.emote_names = emote_names
        self.anim_names = anim_names

    def visit_invoke(self, invoke: Invoke):
        # Funciones que usan IDs de personajes/entidades en su primer argumento
        char_funcs = (
            "Set_Name_Window", "Give_Friendship_Points", "Free_Event_Entity",
            "Set_Entity_Position", "Get_Entity_X", "Get_Entity_Y",
            "Set_Entity_Facing", "Set_Entit_y_Facing", "Get_Entity_Facing", 
            "Get_Entity_X_Facing", "Despawn_Entity",
            "Is_NPC_Birthday", "Chek_Friendship_Points", "Has_NPC_Talked_Today", 
            "Has_NPC_Talked_Today_2", "Kill_NPC", "Execute_Movement", "SetEntityAnim",
            "Hide_Entity", "GetEntityLocation", "Wait_For_Animation",
            "Set_Vector_X", "Set_Vector_Y", "Has_Met_NPC", "Has_Spoken_To_NPC_Today",
            "Routine_State_Override"
        )
        candidate_funcs = ("Set_Hearth_Anim", "Give_Love_Points", "Chek_Love_Points")

        if invoke.func in char_funcs and len(invoke.args) >= 1:
            self.stringify_expr(invoke.args, 0, self.char_names)
        elif invoke.func in candidate_funcs and len(invoke.args) >= 1:
            self.stringify_expr(invoke.args, 0, self.candidate_names)
        
        # El segundo argumento de Routine_State_Override debe ser decorado con "Script_ID"
        if invoke.func == "Routine_State_Override" and len(invoke.args) >= 2:
            if isinstance(invoke.args[1], ExprInt):
                val = invoke.args[1].value
                script_str = f"Script_{val}".encode('windows-1252', errors='replace')
                invoke.args[1] = ExprStr(script_str)
            
        if invoke.func == "Set_Portrait" and len(invoke.args) >= 1:
            self.stringify_expr(invoke.args, 0, self.portrait_names)
        elif invoke.func in ("Warp_Player", "Warp_Entity_To_Map") and len(invoke.args) >= 1:
            self.stringify_expr(invoke.args, 0, self.map_names)
        elif invoke.func == "Show_Emote" and len(invoke.args) >= 2:
            self.stringify_expr(invoke.args, 0, self.char_names)
            self.stringify_expr(invoke.args, 1, self.emote_names)
        elif invoke.func == "SetEntityAnim" and len(invoke.args) >= 2:
            self.stringify_expr(invoke.args, 0, self.char_names)
            self.stringify_expr(invoke.args, 1, self.anim_names)
        elif invoke.func in ("Take_Money", "Check_Money", "Give_Money") and len(invoke.args) >= 1:
            if isinstance(invoke.args[0], ExprInt):
                invoke.args[0].force_decimal = True
        else:
            super().visit_invoke(invoke)

    def visit_stmt(self, stmt: Stmt):
        if isinstance(stmt, StmtSwitch):
            is_map_switch = False
            if isinstance(stmt.condition, ExprCall):
                f = stmt.condition.invoke.func
                if f in ("GetEntityLocation", "Last_Sleep_Location_Check"):
                    is_map_switch = True
            
            if is_map_switch:
                 for case in stmt.cases:
                    if isinstance(case, SwitchCaseCase):
                        for i in range(len(case.exprs)):
                            self.stringify_expr(case.exprs, i, self.map_names)
            
            for case in stmt.cases:
                self.visit_stmts(case.stmts)
        else:
            super().visit_stmt(stmt)

    def visit_expr(self, expr: Expr):
        # Manejar comparaciones complejas en el AST (ExprCmpEq, ExprCmpGe, etc.)
        if isinstance(expr, (ExprCmpEq, ExprCmpNe, ExprCmpLt, ExprCmpLe, ExprCmpGt, ExprCmpGe)):
            # Caso: GetEntityLocation(...) == MAP_ID o Last_Sleep_Location_Check() == MAP_ID
            if isinstance(expr.lhs, ExprCall) and expr.lhs.invoke.func in ("GetEntityLocation", "Last_Sleep_Location_Check"):
                if isinstance(expr.rhs, ExprInt):
                    val = expr.rhs.value
                    if val in self.map_names:
                        name_bytes = self.map_names[val].encode('windows-1252', errors='replace')
                        expr.rhs = ExprStr(name_bytes)
            
            # Caso: Check_Money() >= AMOUNT
            elif isinstance(expr.lhs, ExprCall) and expr.lhs.invoke.func == "Check_Money":
                if isinstance(expr.rhs, ExprInt):
                    expr.rhs.force_decimal = True
        
        super().visit_expr(expr)

    def stringify_expr(self, expr_container: list, idx: int, mapping: Dict[int, str] = None):
        expr = expr_container[idx]
        if isinstance(expr, ExprInt):
            val = expr.value
            
            # Hardcode: ID 0 siempre es Player en el contexto de personajes
            if val == 0 and mapping is self.char_names:
                expr_container[idx] = ExprStr(b"Player")
                return

            # Si se pasó un mapeo específico, lo usamos.
            if mapping and val in mapping:
                name_bytes = mapping[val].encode('windows-1252', errors='replace')
                expr_container[idx] = ExprStr(name_bytes)
            if hasattr(expr, 'comment'):
                expr.comment = None

def decorate_stmts_with_characters(stmts: List[Stmt], char_names: Dict[int, str], candidate_names: Dict[int, str], portrait_names: Dict[int, str], map_names: Dict[int, str], emote_names: Dict[int, str], anim_names: Dict[int, str], known_callables: Dict):
    if not char_names and not candidate_names and not portrait_names and not map_names and not emote_names and not anim_names:
        return
    visitor = CharacterDecorateVisitor(char_names, candidate_names, portrait_names, map_names, emote_names, anim_names, known_callables)
    visitor.visit_stmts(stmts)

class FlagDecorateVisitor(StringDecorateVisitor):
    def __init__(self, flag_names: Dict[int, str], known_callables: Dict):
        super().__init__([], known_callables)
        self.flag_names = flag_names

    def visit_invoke(self, invoke: Invoke):
        flag_funcs = ("Check_Flag", "Set_Flag")
        if invoke.func in flag_funcs and len(invoke.args) >= 1:
            self.stringify_expr(invoke.args, 0, self.flag_names)
        else:
            super().visit_invoke(invoke)

    def stringify_expr(self, expr_container: list, idx: int, mapping: Dict[int, str]):
        expr = expr_container[idx]
        if isinstance(expr, ExprInt):
            val = expr.value
            if val in mapping:
                name_bytes = mapping[val].encode('windows-1252', errors='replace')
                expr_container[idx] = ExprStr(name_bytes)
            if hasattr(expr, 'comment'):
                expr.comment = None

def decorate_stmts_with_flags(stmts: List[Stmt], flag_names: Dict[int, str], known_callables: Dict):
    if not flag_names:
        return
    visitor = FlagDecorateVisitor(flag_names, known_callables)
    visitor.visit_stmts(stmts)

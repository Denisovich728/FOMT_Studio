# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from typing import List
from ..ast import *
from ..ir import *

class Formatter:
    def __init__(self):
        self.output = []
        self.indent_level = 0
        
    def write(self, text: str):
        self.output.append(text)
        
    def write_line(self, text: str):
        self.output.append("    " * self.indent_level + text + "\n")
        
    def write_indent(self):
        self.output.append("    " * self.indent_level)
        
    def indent(self):
        self.indent_level += 1
        
    def unindent(self):
        self.indent_level -= 1
        
    def format_expr(self, expr: Expr) -> str:
        if isinstance(expr, ExprName): return expr.name
        elif isinstance(expr, ExprInt): 
            if expr.force_decimal:
                base = str(expr.value)
            else:
                base = f"0x{expr.value:X}" if expr.value > 9 or expr.value < 0 else str(expr.value)
            
            if expr.comment:
                return f"{base} /* {expr.comment} */"
            return base
        elif isinstance(expr, ExprStr): 
            # Mapa de Caracteres Especiales de FoMT (USA)
            charmap = {
                0x01: "{PLAYER}",
                0x02: "{VALUE1}",
                0x03: "{VALUE2}",
                0x04: "{VALUE4}",
                0x05: "\\BRK",
                0x06: "{BREAK}",
                0x07: "{BREAK2}",
                0x08: "{VALUE8}",
                0x09: "{VALUE9}",
                0x0C: "\\WAIT_CLICK", 
                0x19: "{HORSE}",
                0x0D: "\\r",
                0x0A: "\\n",
                0x22: '\\"',
                0x5C: "\\\\",
                0xF0: "Á", 0xF1: "É", 0xF2: "Í", 0xF3: "Ó", 0xF4: "Ú",
                0xF5: "á", 0xF6: "é", 0xF7: "í", 0xF8: "ó", 0xF9: "ú",
                0x2B: "Ñ", 0x2D: "ñ"
            }
            
            res = '"'
            for b in expr.value:
                if b in charmap:
                    res += charmap[b]
                elif 0x20 <= b <= 0x7E:
                    res += chr(b)
                elif b == 0:
                    continue # El terminador no se imprime
                else:
                    res += f'\\x{b:02X}'
            res += '"'
            return res
        elif isinstance(expr, ExprCall): 
            args = ", ".join(self.format_expr(a) for a in expr.invoke.args)
            return f"{expr.invoke.func}({args})"
        elif isinstance(expr, ExprPreIncrement): return f"++{expr.name}"
        elif isinstance(expr, ExprPostIncrement): return f"{expr.name}++"
        elif isinstance(expr, ExprPreDecrement): return f"--{expr.name}"
        elif isinstance(expr, ExprPostDecrement): return f"{expr.name}--"
        elif isinstance(expr, ExprOpAdd): return f"({self.format_expr(expr.lhs)} + {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprOpSub): return f"({self.format_expr(expr.lhs)} - {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprOpMul): return f"({self.format_expr(expr.lhs)} * {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprOpDiv): return f"({self.format_expr(expr.lhs)} / {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprOpMod): return f"({self.format_expr(expr.lhs)} % {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprOpAnd): return f"({self.format_expr(expr.lhs)} && {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprOpOr): return f"({self.format_expr(expr.lhs)} || {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprOpNeg): return f"-{self.format_expr(expr.inner)}"
        elif isinstance(expr, ExprOpNot): return f"!{self.format_expr(expr.inner)}"
        elif isinstance(expr, ExprCmpEq): return f"({self.format_expr(expr.lhs)} == {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprCmpNe): return f"({self.format_expr(expr.lhs)} != {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprCmpLt): return f"({self.format_expr(expr.lhs)} < {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprCmpLe): return f"({self.format_expr(expr.lhs)} <= {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprCmpGt): return f"({self.format_expr(expr.lhs)} > {self.format_expr(expr.rhs)})"
        elif isinstance(expr, ExprCmpGe): return f"({self.format_expr(expr.lhs)} >= {self.format_expr(expr.rhs)})"
        return "<unknown_expr>"

    def format_stmt(self, stmt: Stmt):
        if isinstance(stmt, StmtVars):
            for name, exp in stmt.vars:
                if exp:
                    self.write_line(f"var {name} = {self.format_expr(exp)};")
                else:
                    self.write_line(f"var {name};")
                    
        elif isinstance(stmt, StmtConsts):
            for name, exp in stmt.consts:
                self.write_line(f"const {name} = {self.format_expr(exp)};")
                
        elif isinstance(stmt, StmtAssign):
            op_str = {
                AssignOperation.NONE: "=",
                AssignOperation.ADD: "+=",
                AssignOperation.SUB: "-=",
                AssignOperation.MUL: "*=",
                AssignOperation.DIV: "/=",
                AssignOperation.MOD: "%=",
            }[stmt.op]
            self.write_line(f"{stmt.name} {op_str} {self.format_expr(stmt.expr)};")
            
        elif isinstance(stmt, StmtExpr):
            self.write_line(f"{self.format_expr(stmt.expr)};")
            
        elif isinstance(stmt, StmtCall):
            args = ", ".join(self.format_expr(a) for a in stmt.invoke.args)
            self.write_line(f"{stmt.invoke.func}({args});")
            
        elif isinstance(stmt, StmtMessage):
            self.write_line(f"const MESSAGE_{stmt.index} = {self.format_expr(ExprStr(stmt.text))};")
        elif isinstance(stmt, StmtIf):
            self.write_line(f"if ({self.format_expr(stmt.condition)}) {{")
            self.indent()
            for s in stmt.stmts: self.format_stmt(s)
            self.unindent()
            self.write_line("}")
            
        elif isinstance(stmt, StmtIfElse):
            self.write_line(f"if ({self.format_expr(stmt.condition)}) {{")
            self.indent()
            for s in stmt.true_stmts: self.format_stmt(s)
            self.unindent()
            self.write_line("} else {")
            self.indent()
            for s in stmt.false_stmts: self.format_stmt(s)
            self.unindent()
            self.write_line("}")
            
        elif isinstance(stmt, StmtDoWhile):
            self.write_line("do {")
            self.indent()
            for s in stmt.body: self.format_stmt(s)
            self.unindent()
            self.write_line(f"}} while ({self.format_expr(stmt.condition)});")
            
        elif isinstance(stmt, StmtFor):
            # Try to format head and tail inline if they are simple
            head_str = ""
            if isinstance(stmt.head, StmtAssign): head_str = f"{stmt.head.name} = {self.format_expr(stmt.head.expr)}"
            elif isinstance(stmt.head, StmtExpr): head_str = self.format_expr(stmt.head.expr)
            
            tail_str = ""
            if isinstance(stmt.tail, StmtAssign): tail_str = f"{stmt.tail.name} = {self.format_expr(stmt.tail.expr)}"
            elif isinstance(stmt.tail, StmtExpr): tail_str = self.format_expr(stmt.tail.expr)
            
            self.write_line(f"for ({head_str}; {self.format_expr(stmt.condition)}; {tail_str}) {{")
            self.indent()
            for s in stmt.body: self.format_stmt(s)
            self.unindent()
            self.write_line("}")
            
        elif isinstance(stmt, StmtSwitch):
            self.write_line(f"switch ({self.format_expr(stmt.condition)}) {{")
            self.indent()
            for sc in stmt.cases:
                if isinstance(sc, SwitchCaseCase):
                    for ex in sc.exprs:
                        self.write_line(f"case {self.format_expr(ex)}:")
                    self.indent()
                    for s in sc.stmts: self.format_stmt(s)
                    self.unindent()
                elif isinstance(sc, SwitchCaseDefault):
                    self.write_line("default:")
                    self.indent()
                    for s in sc.stmts: self.format_stmt(s)
                    self.unindent()
            self.unindent()
            self.write_line("}")
            
        elif isinstance(stmt, StmtExit):
            self.write_line("exit;")
        elif isinstance(stmt, StmtBreak):
            self.write_line("break;")
        elif isinstance(stmt, StmtLabel):
            # Las etiquetas se imprimen sin indentación para mayor visibilidad
            old_indent = self.indent_level
            self.indent_level = 0
            self.write_line(f"LBL_{stmt.jump_id.id:04X}:")
            self.indent_level = old_indent
        elif isinstance(stmt, StmtGoto):
            self.write_line(f"goto LBL_{stmt.jump_id.id:04X};")

def format_script(stmts: List[Stmt]) -> str:
    f = Formatter()
    
    # Separar constantes/mensajes del resto del código para mejor jerarquía
    msgs = [s for s in stmts if isinstance(s, StmtMessage)]
    consts = [s for s in stmts if isinstance(s, (StmtConsts, StmtVars))]
    others = [s for s in stmts if not isinstance(s, (StmtMessage, StmtConsts, StmtVars))]
    
    for s in msgs: 
        f.format_stmt(s)
    if msgs and (consts or others): 
        f.write("\n")
    
    for s in consts: 
        f.format_stmt(s)
    if consts and others: 
        f.write("\n")
    
    for s in others: 
        f.format_stmt(s)
    
    return "".join(f.output)

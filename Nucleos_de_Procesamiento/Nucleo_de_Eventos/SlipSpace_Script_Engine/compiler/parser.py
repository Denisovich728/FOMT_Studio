# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from typing import List, Optional, Tuple, Dict
from .lexer import Token, TokenType, Lexer, LexerError
from ..ast import *
from ..ir import ValueType, ValueTypeEnum

class ParseError(Exception):
    def __init__(self, message: str, line: int = 0, col: int = 0):
        super().__init__(f"{message} at line {line}:{col}")
        self.line = line
        self.col = col

class Parser:
    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.tokens: List[Token] = []
        self.pos = 0
        self.switch_id_counter = 0
        self._pump()
        
    def _pump(self):
        while True:
            t = self.lexer.next_token()
            self.tokens.append(t)
            if t.type == TokenType.EOF:
                break
                
    def peek(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]
        
    def next_token(self) -> Token:
        t = self.peek()
        if t.type != TokenType.EOF:
            self.pos += 1
        return t
        
    def expect(self, tok_type: TokenType) -> Token:
        t = self.next_token()
        if t.type != tok_type:
            raise ParseError(f"Expected {tok_type}, got {t.type}", t.line, t.column)
        return t
        
    def match(self, tok_type: TokenType) -> bool:
        if self.peek().type == tok_type:
            self.pos += 1
            return True
        return False
        
    def parse_primary_expr(self) -> Expr:
        t = self.next_token()
        if t.type == TokenType.NAME:
            return ExprName(t.value)
        elif t.type == TokenType.INTEGER:
            return ExprInt(t.value)
        elif t.type == TokenType.STRING_LIT:
            return ExprStr(t.value)
        elif t.type == TokenType.LPAREN:
            if self.peek().type == TokenType.PLUSPLUS:
                # preincr
                self.next_token()
                name = self.expect(TokenType.NAME).value
                self.expect(TokenType.RPAREN)
                return ExprPreIncrement(name)
            elif self.peek().type == TokenType.MINUSMINUS:
                self.next_token()
                name = self.expect(TokenType.NAME).value
                self.expect(TokenType.RPAREN)
                return ExprPreDecrement(name)
            elif self.peek().type == TokenType.NAME and self.tokens[self.pos+1].type == TokenType.PLUSPLUS:
                name = self.next_token().value
                self.next_token()
                self.expect(TokenType.RPAREN)
                return ExprPostIncrement(name)
            elif self.peek().type == TokenType.NAME and self.tokens[self.pos+1].type == TokenType.MINUSMINUS:
                name = self.next_token().value
                self.next_token()
                self.expect(TokenType.RPAREN)
                return ExprPostDecrement(name)
            else:
                expr = self.parse_expr()
                self.expect(TokenType.RPAREN)
                return expr
        # try preincr or postincr without parens? Rust grammar requires parens or separate rule
        elif t.type == TokenType.PLUSPLUS:
            # wait, Stmt allows missing parens but expr requires them? 
            name = self.expect(TokenType.NAME).value
            return ExprPreIncrement(name)
        elif t.type == TokenType.MINUSMINUS:
            name = self.expect(TokenType.NAME).value
            return ExprPreDecrement(name)
            
        raise ParseError(f"Unexpected token {t.type} in primary expression")

    def parse_call(self) -> Invoke:
        name = self.expect(TokenType.NAME).value
        self.expect(TokenType.LPAREN)
        args = []
        if not self.match(TokenType.RPAREN):
            while True:
                args.append(self.parse_expr())
                if not self.match(TokenType.COMMA):
                    break
            self.expect(TokenType.RPAREN)
        return Invoke(name, args)

    def parse_call_expr(self) -> Expr:
        if self.peek().type == TokenType.NAME and self.tokens[self.pos+1].type == TokenType.LPAREN:
            return ExprCall(self.parse_call())
        return self.parse_primary_expr()

    def parse_unary_expr(self) -> Expr:
        if self.match(TokenType.MINUS):
            return ExprOpNeg(self.parse_unary_expr())
        if self.match(TokenType.PLUS):
            return self.parse_unary_expr()
        if self.match(TokenType.NEGATE):
            return ExprOpNot(self.parse_unary_expr())
        return self.parse_call_expr()

    def parse_mul_expr(self) -> Expr:
        expr = self.parse_unary_expr()
        while True:
            if self.match(TokenType.TIMES): expr = ExprOpMul(expr, self.parse_unary_expr())
            elif self.match(TokenType.DIVIDE): expr = ExprOpDiv(expr, self.parse_unary_expr())
            elif self.match(TokenType.MODULUS): expr = ExprOpMod(expr, self.parse_unary_expr())
            else: break
        return expr

    def parse_add_expr(self) -> Expr:
        expr = self.parse_mul_expr()
        while True:
            if self.match(TokenType.PLUS): expr = ExprOpAdd(expr, self.parse_mul_expr())
            elif self.match(TokenType.MINUS): expr = ExprOpSub(expr, self.parse_mul_expr())
            else: break
        return expr

    def parse_relation_expr(self) -> Expr:
        expr = self.parse_add_expr()
        while True:
            if self.match(TokenType.COMPARE_LT): expr = ExprCmpLt(expr, self.parse_add_expr())
            elif self.match(TokenType.COMPARE_LE): expr = ExprCmpLe(expr, self.parse_add_expr())
            elif self.match(TokenType.COMPARE_GE): expr = ExprCmpGe(expr, self.parse_add_expr())
            elif self.match(TokenType.COMPARE_GT): expr = ExprCmpGt(expr, self.parse_add_expr())
            else: break
        return expr

    def parse_equality_expr(self) -> Expr:
        expr = self.parse_relation_expr()
        while True:
            if self.match(TokenType.COMPARE_EQ): expr = ExprCmpEq(expr, self.parse_relation_expr())
            elif self.match(TokenType.COMPARE_NE): expr = ExprCmpNe(expr, self.parse_relation_expr())
            else: break
        return expr

    def parse_and_expr(self) -> Expr:
        expr = self.parse_equality_expr()
        while self.match(TokenType.LAND):
            expr = ExprOpAnd(expr, self.parse_equality_expr())
        return expr

    def parse_or_expr(self) -> Expr:
        expr = self.parse_and_expr()
        while self.match(TokenType.LOR):
            expr = ExprOpOr(expr, self.parse_and_expr())
        return expr

    def parse_expr(self) -> Expr:
        # assignment or conditional
        # El AST del motor SlipSpace solo gestiona expresiones condicionales...
        return self.parse_or_expr()

    def parse_stmt_block(self) -> List[Stmt]:
        self.expect(TokenType.LCURLY)
        stmts = []
        while not self.match(TokenType.RCURLY):
            stmts.append(self.parse_stmt())
        return stmts

    def parse_stmt(self) -> Stmt:
        t = self.peek()
        if t.type == TokenType.KW_VAR:
            self.next_token()
            initializers = []
            while True:
                name = self.expect(TokenType.NAME).value
                expr = None
                if self.match(TokenType.EQUAL):
                    expr = self.parse_expr()
                initializers.append((name, expr))
                if not self.match(TokenType.COMMA):
                    break
            self.expect(TokenType.SEMICOLON) # Assuming rust requires semi, or maybe not? 
            # Rust pomelo doesn't seem to enforce semicolons on most stmts.
            return StmtVars(initializers)
            
        elif t.type == TokenType.KW_CONST:
            self.next_token()
            initializers = []
            while True:
                name = self.expect(TokenType.NAME).value
                self.expect(TokenType.EQUAL)
                expr = self.parse_expr()
                initializers.append((name, expr))
                if not self.match(TokenType.COMMA):
                    break
            return StmtConsts(initializers)
            
        elif t.type == TokenType.KW_IF:
            self.next_token()
            cond = self.parse_expr()
            true_stmts = self.parse_stmt_block()
            
            if self.match(TokenType.KW_ELSE):
                if self.peek().type == TokenType.KW_IF:
                    # else if...
                    false_stmts = [self.parse_stmt()] # parse_stmt handles KW_IF
                    return StmtIfElse(cond, true_stmts, false_stmts)
                else:
                    false_stmts = self.parse_stmt_block()
                    return StmtIfElse(cond, true_stmts, false_stmts)
            return StmtIf(cond, true_stmts)
            
        elif t.type == TokenType.KW_DO:
            self.next_token()
            block = self.parse_stmt_block()
            self.expect(TokenType.KW_WHILE)
            cond = self.parse_expr()
            return StmtDoWhile(cond, block)
            
        elif t.type == TokenType.KW_FOR:
            self.next_token()
            head = self.parse_stmt()
            self.expect(TokenType.SEMICOLON)
            cond = self.parse_expr()
            self.expect(TokenType.SEMICOLON)
            tail = self.parse_stmt()
            body = self.parse_stmt_block()
            return StmtFor(cond, head, tail, body)
            
        elif t.type == TokenType.KW_SWITCH:
            self.next_token()
            cond = self.parse_expr()
            self.expect(TokenType.LCURLY)
            cases = []
            while not self.match(TokenType.RCURLY):
                if self.match(TokenType.KW_CASE):
                    exprs = []
                    while True:
                        exprs.append(self.parse_expr())
                        if not self.match(TokenType.COMMA): break
                    
                    # Soporte opcional para ':' (estilo C)
                    self.match(TokenType.COLON)
                    
                    # Si hay una llave, es un bloque. Si no, leemos hasta el próximo case/default/RCURLY
                    if self.peek().type == TokenType.LCURLY:
                        block = self.parse_stmt_block()
                    else:
                        block = []
                        while self.peek().type not in (TokenType.KW_CASE, TokenType.KW_DEFAULT, TokenType.RCURLY, TokenType.EOF):
                            block.append(self.parse_stmt())
                    
                    cases.append(SwitchCaseCase(exprs, block))
                    
                elif self.match(TokenType.KW_DEFAULT):
                    self.match(TokenType.COLON)
                    
                    if self.peek().type == TokenType.LCURLY:
                        block = self.parse_stmt_block()
                    else:
                        block = []
                        while self.peek().type not in (TokenType.KW_CASE, TokenType.KW_DEFAULT, TokenType.RCURLY, TokenType.EOF):
                            block.append(self.parse_stmt())
                    
                    cases.append(SwitchCaseDefault(block))
                else:
                    # En caso de basura o comentarios no detectados entre cases
                    t_err = self.next_token()
                    # Si no es un case o default, lanzamos error
                    raise ParseError(f"Expected case or default in switch, got {t_err.type}", t_err.line, t_err.column)
                    
            sid = self.switch_id_counter
            self.switch_id_counter += 1
            return StmtSwitch(cond, cases, SwitchId(sid))
            
        elif t.type == TokenType.KW_EXIT:
            self.next_token()
            self.expect(TokenType.SEMICOLON)
            return StmtExit()
            
        elif t.type == TokenType.SEMICOLON:
            self.next_token()
            return StmtEmpty()
            
        elif t.type == TokenType.KW_BREAK:
            self.next_token()
            self.expect(TokenType.SEMICOLON)
            return StmtBreak()
        elif t.type == TokenType.PLUSPLUS:
            self.next_token()
            name = self.expect(TokenType.NAME).value
            return StmtExpr(ExprPreIncrement(name))
            
        elif t.type == TokenType.KW_GOTO:
            self.next_token()
            label_name = self.expect(TokenType.NAME).value
            self.match(TokenType.SEMICOLON)
            return StmtGoto(label_name)
            
        elif t.type == TokenType.NAME:
            # Soporte para CONST_MESSAGE_X(...) [Convención de constantes de mensajes]
            if t.value.startswith("CONST_MESSAGE_") or t.value.startswith("MESSAGE_"):
                name = self.next_token().value
                idx_str = name.replace("CONST_MESSAGE_", "").replace("MESSAGE_", "")
                try:
                    idx = int(idx_str, 16 if idx_str.startswith("0x") else 10)
                except:
                    idx = 0
                self.expect(TokenType.LPAREN)
                text = self.expect(TokenType.STRING_LIT).value
                self.expect(TokenType.RPAREN)
                self.match(TokenType.SEMICOLON)
                return StmtMessage(idx, text)

            # Lookahead para comandos, asignaciones o incrementos
            if self.pos + 1 < len(self.tokens):
                n = self.tokens[self.pos+1]
                if n.type == TokenType.LPAREN:
                    call = self.parse_call()
                    self.match(TokenType.SEMICOLON)
                    return StmtCall(call)
                elif n.type in (TokenType.EQUAL, TokenType.ADD_EQUAL, TokenType.SUB_EQUAL, 
                                TokenType.MUL_EQUAL, TokenType.DIV_EQUAL, TokenType.MOD_EQUAL):
                    name = self.expect(TokenType.NAME).value
                    op_tok = self.next_token()
                    exp = self.parse_expr()
                    self.match(TokenType.SEMICOLON)
                    
                    op_map = {
                        TokenType.EQUAL: AssignOperation.NONE,
                        TokenType.ADD_EQUAL: AssignOperation.ADD,
                        TokenType.SUB_EQUAL: AssignOperation.SUB,
                        TokenType.MUL_EQUAL: AssignOperation.MUL,
                        TokenType.DIV_EQUAL: AssignOperation.DIV,
                        TokenType.MOD_EQUAL: AssignOperation.MOD,
                    }
                    return StmtAssign(op_map[op_tok.type], name, exp)
                elif n.type == TokenType.COLON:
                    # Definición de etiqueta LBL_XXX:
                    self.next_token() # consume nombre (t)
                    self.next_token() # consume : (n)
                    return StmtLabel(t.value)
                elif n.type == TokenType.PLUSPLUS:
                    name = self.expect(TokenType.NAME).value
                    self.next_token()
                    self.match(TokenType.SEMICOLON)
                    return StmtExpr(ExprPostIncrement(name))
                elif n.type == TokenType.MINUSMINUS:
                    name = self.expect(TokenType.NAME).value
                    self.next_token()
                    self.match(TokenType.SEMICOLON)
                    return StmtExpr(ExprPostDecrement(name))

            # Fallback: Cualquier otra expresión (incluyendo llamadas a función)
            exp = self.parse_expr()
            self.match(TokenType.SEMICOLON)
            return StmtExpr(exp)

        elif t.type == TokenType.LPAREN:
            # Soporte para expresiones entre paréntesis al inicio de la línea (e.g. comparaciones huérfanas)
            exp = self.parse_expr()
            self.match(TokenType.SEMICOLON)
            return StmtExpr(exp)
        
        raise ParseError(f"Unexpected token {t.type} starting statement", t.line, t.column)

    def parse_program(self, const_scope: 'ConstScope', allow_scripts=True):
        scripts = []
        allow_declarations = True
        
        while self.peek().type != TokenType.EOF:
            t = self.peek()
            
            if t.type == TokenType.KW_CONST:
                if not allow_declarations: raise ParseError("Declarations after script not allowed", t.line, t.column)
                self.next_token() # consume const
                while True:
                    name = self.expect(TokenType.NAME).value
                    # Soporte para const MESSAGE_X = "..."
                    if name.startswith("MESSAGE_"):
                        self.expect(TokenType.EQUAL)
                        expr = self.parse_expr()
                        val = eval_expr(expr, const_scope)
                        if not isinstance(val, ConstValStr):
                            raise ParseError("MESSAGE_X must be a string", t.line, t.column)
                        
                        idx_str = name.replace("MESSAGE_", "")
                        try:
                            idx = int(idx_str, 16 if idx_str.startswith("0x") else 10)
                        except:
                            idx = 0
                        # Devolvemos un StmtMessage envuelto o manejado después.
                        # Pero parse_program espera declaraciones.
                        # Usaremos una lista temporal de statements.
                        # En realidad, StmtMessage es un Stmt.
                        # El parser aquí está dentro de un bucle de KW_CONST.
                        # Vamos a permitir que KW_CONST produzca StmtMessage.
                        # Pero parse_program maneja declaraciones de ConstScope.
                        
                        const_scope.define_const(name, val)
                        # Nota: El emitter lo pillará por el nombre MESSAGE_
                        
                    else:
                        self.expect(TokenType.EQUAL)
                        expr = self.parse_expr()
                        val = eval_expr(expr, const_scope)
                        if val is None: raise ParseError("Failed constant eval", t.line, t.column)
                        const_scope.define_const(name, val)
                    
                    if not self.match(TokenType.COMMA): break
                    
            elif t.type in (TokenType.KW_FUNC, TokenType.KW_PROC):
                is_func = t.type == TokenType.KW_FUNC
                self.next_token()
                if not allow_declarations: raise ParseError("Declarations after script not allowed", t.line, t.column)
                
                cid_expr = self.parse_primary_expr()
                name = self.expect(TokenType.NAME).value
                
                # parse params `()` or `(arg_1, arg_2: string)`
                self.expect(TokenType.LPAREN)
                params: List[ValueType] = []
                if not self.match(TokenType.RPAREN):
                    while True:
                        self.expect(TokenType.NAME)
                        vt = ValueType(ValueTypeEnum.UNDEFINED)
                        if self.match(TokenType.COLON):
                            t_name = self.next_token()
                            if t_name.type == TokenType.KW_STRING: vt = ValueType(ValueTypeEnum.STRING)
                            elif t_name.type == TokenType.KW_INTEGER: vt = ValueType(ValueTypeEnum.INTEGER)
                            elif t_name.type == TokenType.NAME: vt = ValueType(ValueTypeEnum.USER_TYPE, const_scope.add_or_get_user_type(t_name.value) if hasattr(const_scope, 'add_or_get_user_type') else 0)
                            else: raise ParseError("Expected type name", t_name.line, t_name.column)
                        params.append(vt)
                        if not self.match(TokenType.COMMA): break
                    self.expect(TokenType.RPAREN)
                    
                from .emitter import eval_expr
                from ..ir import CallableShape
                
                val = eval_expr(cid_expr, const_scope)
                if not val or not isinstance(val, ConstValInt): raise ParseError("Func/Proc id must be constant int", t.line, t.column)
                
                from ..ir import CallId
                if is_func: const_scope.add_func(name, CallId(val.value), CallableShape.new_func(params))
                else: const_scope.add_proc(name, CallId(val.value), CallableShape.new_proc(params))
                
            elif t.type == TokenType.KW_SCRIPT:
                if not allow_scripts: raise ParseError("Scripts not allowed in this context", t.line, t.column)
                allow_declarations = False
                
                self.next_token()
                id_expr = self.parse_expr()
                name = self.expect(TokenType.NAME).value
                block = self.parse_stmt_block()
                
                from .emitter import eval_expr
                val = eval_expr(id_expr, const_scope)
                if not val or not isinstance(val, ConstValInt): raise ParseError("Script id must be integer", t.line, t.column)
                
                scripts.append((val.value, name, block))
            else:
                raise ParseError(f"Unexpected token {t.type} at program level", t.line, t.column)
                
        return scripts

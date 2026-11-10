# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ------------------------------------------------------------
# Revisión: nombres de script con varias palabras, ';' tras
# const a nivel de programa, imports unificados (sin
# UnboundLocalError) y lookahead seguro.
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

    # ---------------------------------------------------------
    # Utilidades de tokens
    # ---------------------------------------------------------
    def peek(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def peek_at(self, offset: int) -> Token:
        """Lookahead seguro: nunca lanza IndexError (devuelve EOF)."""
        i = self.pos + offset
        if 0 <= i < len(self.tokens):
            return self.tokens[i]
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

    # ---------------------------------------------------------
    # Expresiones
    # ---------------------------------------------------------
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
                self.next_token()
                name = self.expect(TokenType.NAME).value
                self.expect(TokenType.RPAREN)
                return ExprPreIncrement(name)
            elif self.peek().type == TokenType.MINUSMINUS:
                self.next_token()
                name = self.expect(TokenType.NAME).value
                self.expect(TokenType.RPAREN)
                return ExprPreDecrement(name)
            elif self.peek().type == TokenType.NAME and self.peek_at(1).type == TokenType.PLUSPLUS:
                name = self.next_token().value
                self.next_token()
                self.expect(TokenType.RPAREN)
                return ExprPostIncrement(name)
            elif self.peek().type == TokenType.NAME and self.peek_at(1).type == TokenType.MINUSMINUS:
                name = self.next_token().value
                self.next_token()
                self.expect(TokenType.RPAREN)
                return ExprPostDecrement(name)
            else:
                expr = self.parse_expr()
                self.expect(TokenType.RPAREN)
                return expr
        elif t.type == TokenType.PLUSPLUS:
            name = self.expect(TokenType.NAME).value
            return ExprPreIncrement(name)
        elif t.type == TokenType.MINUSMINUS:
            name = self.expect(TokenType.NAME).value
            return ExprPreDecrement(name)

        raise ParseError(f"Unexpected token {t.type} in primary expression", t.line, t.column)

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
        if self.peek().type == TokenType.NAME and self.peek_at(1).type == TokenType.LPAREN:
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
        # El AST del motor SlipSpace solo gestiona expresiones condicionales.
        return self.parse_or_expr()

    # ---------------------------------------------------------
    # Sentencias
    # ---------------------------------------------------------
    def parse_stmt_block(self) -> List[Stmt]:
        self.expect(TokenType.LCURLY)
        stmts = []
        while not self.match(TokenType.RCURLY):
            if self.peek().type == TokenType.EOF:
                t = self.peek()
                raise ParseError("Unexpected end of file, missing '}'", t.line, t.column)
            stmts.append(self.parse_stmt())
        return stmts

    def _parse_case_body(self) -> List[Stmt]:
        """Cuerpo de un case/default: bloque {..} o sentencias hasta el siguiente case/default/}."""
        if self.peek().type == TokenType.LCURLY:
            return self.parse_stmt_block()
        block = []
        while self.peek().type not in (TokenType.KW_CASE, TokenType.KW_DEFAULT,
                                       TokenType.RCURLY, TokenType.EOF):
            block.append(self.parse_stmt())
        return block

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
            self.expect(TokenType.SEMICOLON)
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
            self.match(TokenType.SEMICOLON)
            return StmtConsts(initializers)

        elif t.type == TokenType.KW_IF:
            self.next_token()
            cond = self.parse_expr()
            true_stmts = self.parse_stmt_block()

            if self.match(TokenType.KW_ELSE):
                if self.peek().type == TokenType.KW_IF:
                    false_stmts = [self.parse_stmt()]
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
            self.match(TokenType.SEMICOLON)
            return StmtDoWhile(cond, block)

        elif t.type == TokenType.KW_FOR:
            self.next_token()
            head = self.parse_stmt()
            self.match(TokenType.SEMICOLON)   # head puede haber consumido ya el ';'
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
                        if not self.match(TokenType.COMMA):
                            break
                    self.match(TokenType.COLON)   # ':' opcional (estilo C)
                    cases.append(SwitchCaseCase(exprs, self._parse_case_body()))

                elif self.match(TokenType.KW_DEFAULT):
                    self.match(TokenType.COLON)
                    cases.append(SwitchCaseDefault(self._parse_case_body()))
                else:
                    t_err = self.next_token()
                    raise ParseError(f"Expected case or default in switch, got {t_err.type}",
                                     t_err.line, t_err.column)

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
            self.match(TokenType.SEMICOLON)
            return StmtExpr(ExprPreIncrement(name))

        elif t.type == TokenType.MINUSMINUS:
            self.next_token()
            name = self.expect(TokenType.NAME).value
            self.match(TokenType.SEMICOLON)
            return StmtExpr(ExprPreDecrement(name))

        elif t.type == TokenType.KW_GOTO:
            self.next_token()
            label_name = self.expect(TokenType.NAME).value
            self.match(TokenType.SEMICOLON)
            return StmtGoto(label_name)

        elif t.type == TokenType.NAME:
            # CONST_MESSAGE_X("...") / MESSAGE_X("...")
            if (t.value.startswith("CONST_MESSAGE_") or t.value.startswith("MESSAGE_")) \
                    and self.peek_at(1).type == TokenType.LPAREN:
                name = self.next_token().value
                idx_str = name.replace("CONST_MESSAGE_", "").replace("MESSAGE_", "")
                try:
                    idx = int(idx_str, 16 if idx_str.startswith("0x") else 10)
                except ValueError:
                    idx = 0
                self.expect(TokenType.LPAREN)
                text = self.expect(TokenType.STRING_LIT).value
                self.expect(TokenType.RPAREN)
                self.match(TokenType.SEMICOLON)
                return StmtMessage(idx, text)

            n = self.peek_at(1)
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
                # Etiqueta LBL_XXX:
                self.next_token()
                self.next_token()
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

            # Fallback: cualquier otra expresión
            exp = self.parse_expr()
            self.match(TokenType.SEMICOLON)
            return StmtExpr(exp)

        elif t.type == TokenType.LPAREN:
            exp = self.parse_expr()
            self.match(TokenType.SEMICOLON)
            return StmtExpr(exp)

        raise ParseError(f"Unexpected token {t.type} starting statement", t.line, t.column)

    # ---------------------------------------------------------
    # Nivel de programa
    # ---------------------------------------------------------
    def _parse_script_name(self) -> str:
        """
        Nombre de script: una o más palabras hasta '{'.
        Ej.: `script 993 Personalidad de Popuri {` -> "Personalidad_de_Popuri"
        Acepta nombres, enteros y palabras reservadas usadas como texto.
        """
        first = self.next_token()
        if first.type == TokenType.LCURLY:
            raise ParseError("Expected script name", first.line, first.column)
        parts = [self._token_as_word(first)]
        while self.peek().type not in (TokenType.LCURLY, TokenType.EOF):
            parts.append(self._token_as_word(self.next_token()))
        return "_".join(parts)

    @staticmethod
    def _token_as_word(tok: Token) -> str:
        if tok.type in (TokenType.NAME, TokenType.INTEGER):
            return str(tok.value)
        v = tok.type.value
        if isinstance(v, str) and v.isalpha():   # palabra reservada (string, default, ...)
            return v
        raise ParseError(f"Unexpected token {tok.type} in script name", tok.line, tok.column)

    def parse_program(self, const_scope: 'ConstScope', allow_scripts=True):
        # Imports únicos al inicio: evita UnboundLocalError de eval_expr
        from .emitter import eval_expr
        from ..ir import CallableShape, CallId

        scripts = []
        allow_declarations = True

        while self.peek().type != TokenType.EOF:
            t = self.peek()

            if t.type == TokenType.SEMICOLON:
                self.next_token()   # ';' suelto a nivel de programa

            elif t.type == TokenType.KW_CONST:
                if not allow_declarations:
                    raise ParseError("Declarations after script not allowed", t.line, t.column)
                self.next_token()
                while True:
                    name = self.expect(TokenType.NAME).value
                    self.expect(TokenType.EQUAL)
                    expr = self.parse_expr()
                    val = eval_expr(expr, const_scope)

                    if name.startswith("MESSAGE_") and not isinstance(val, ConstValStr):
                        raise ParseError(f"{name} must be a string", t.line, t.column)
                    if val is None:
                        raise ParseError("Failed constant eval", t.line, t.column)

                    # El emitter reconoce los MESSAGE_ por nombre
                    const_scope.define_const(name, val)

                    if not self.match(TokenType.COMMA):
                        break
                self.match(TokenType.SEMICOLON)   # <- antes faltaba: `const X = "..";` fallaba

            elif t.type in (TokenType.KW_FUNC, TokenType.KW_PROC):
                is_func = t.type == TokenType.KW_FUNC
                self.next_token()
                if not allow_declarations:
                    raise ParseError("Declarations after script not allowed", t.line, t.column)

                cid_expr = self.parse_primary_expr()
                name = self.expect(TokenType.NAME).value

                self.expect(TokenType.LPAREN)
                params: List[ValueType] = []
                if not self.match(TokenType.RPAREN):
                    while True:
                        self.expect(TokenType.NAME)
                        vt = ValueType(ValueTypeEnum.UNDEFINED)
                        if self.match(TokenType.COLON):
                            t_name = self.next_token()
                            if t_name.type == TokenType.KW_STRING:
                                vt = ValueType(ValueTypeEnum.STRING)
                            elif t_name.type == TokenType.KW_INTEGER:
                                vt = ValueType(ValueTypeEnum.INTEGER)
                            elif t_name.type == TokenType.NAME:
                                vt = ValueType(
                                    ValueTypeEnum.USER_TYPE,
                                    const_scope.add_or_get_user_type(t_name.value)
                                    if hasattr(const_scope, 'add_or_get_user_type') else 0)
                            else:
                                raise ParseError("Expected type name", t_name.line, t_name.column)
                        params.append(vt)
                        if not self.match(TokenType.COMMA):
                            break
                    self.expect(TokenType.RPAREN)
                self.match(TokenType.SEMICOLON)

                val = eval_expr(cid_expr, const_scope)
                if not val or not isinstance(val, ConstValInt):
                    raise ParseError("Func/Proc id must be constant int", t.line, t.column)

                if is_func:
                    const_scope.add_func(name, CallId(val.value), CallableShape.new_func(params))
                else:
                    const_scope.add_proc(name, CallId(val.value), CallableShape.new_proc(params))

            elif t.type == TokenType.KW_SCRIPT:
                if not allow_scripts:
                    raise ParseError("Scripts not allowed in this context", t.line, t.column)
                allow_declarations = False

                self.next_token()
                id_expr = self.parse_primary_expr()      # solo el id (993), sin consumir el nombre
                name = self._parse_script_name()         # "Personalidad_de_Popuri"
                block = self.parse_stmt_block()

                val = eval_expr(id_expr, const_scope)
                if not val or not isinstance(val, ConstValInt):
                    raise ParseError("Script id must be integer", t.line, t.column)

                scripts.append((val.value, name, block))
            else:
                raise ParseError(f"Unexpected token {t.type} at program level", t.line, t.column)

        return scripts
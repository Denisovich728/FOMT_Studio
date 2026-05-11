# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import re
from dataclasses import dataclass
from enum import Enum, auto

class TokenType(Enum):
    KW_FUNC = "func"
    KW_PROC = "proc"
    KW_CONST = "const"
    KW_SCRIPT = "script"
    KW_VAR = "var"
    KW_IF = "if"
    KW_ELSE = "else"
    KW_FOR = "for"
    KW_DO = "do"
    KW_WHILE = "while"
    KW_SWITCH = "switch"
    KW_CASE = "case"
    KW_DEFAULT = "default"
    KW_BREAK = "break"
    KW_EXIT = "exit"
    KW_STRING = "string"
    KW_INTEGER = "integer"
    KW_GOTO = "goto"

    LPAREN = "("
    RPAREN = ")"
    LCURLY = "{"
    RCURLY = "}"
    COMMA = ","
    COLON = ":"
    SEMICOLON = ";"

    PLUS = "+"
    MINUS = "-"
    TIMES = "*"
    DIVIDE = "/"
    MODULUS = "%"
    PLUSPLUS = "++"
    MINUSMINUS = "--"
    LAND = "&&"
    LOR = "||"
    NEGATE = "!"
    COMPARE_EQ = "=="
    COMPARE_NE = "!="
    COMPARE_LT = "<"
    COMPARE_LE = "<="
    COMPARE_GE = ">="
    COMPARE_GT = ">"
    EQUAL = "="
    ADD_EQUAL = "+="
    SUB_EQUAL = "-="
    MUL_EQUAL = "*="
    DIV_EQUAL = "/="
    MOD_EQUAL = "%="

    NAME = "name"
    INTEGER = "integer_lit"
    STRING_LIT = "string_lit"
    EOF = "eof"

@dataclass
class Token:
    type: TokenType
    value: any = None
    line: int = 1
    column: int = 1

class LexerError(Exception):
    pass

class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        
    def peek_char(self) -> str:
        if self.pos < len(self.source):
            return self.source[self.pos]
        return ""
        
    def next_char(self) -> str:
        c = self.peek_char()
        if c:
            self.pos += 1
            if c == '\n':
                self.line += 1
                self.col = 1
            else:
                self.col += 1
        return c

    def skip_whitespace_and_comments(self):
        while True:
            c = self.peek_char()
            if c.isspace():
                self.next_char()
            elif c == '/' and self.source.startswith('//', self.pos):
                while self.peek_char() not in ('\n', ''):
                    self.next_char()
            elif c == '/' and self.source.startswith('/*', self.pos):
                self.next_char()
                self.next_char()
                while not self.source.startswith('*/', self.pos) and self.pos < len(self.source):
                    self.next_char()
                if self.pos < len(self.source):
                    self.next_char()
                    self.next_char()
            elif c == '#':  # treat as line comment
                while self.peek_char() not in ('\n', ''):
                    self.next_char()
            else:
                break

    def read_string_literal(self) -> bytes:
        self.next_char() # skip the opening "
        buf = bytearray()
        
        # Mapa Inverso para Compilación (FoMT USA)
        reverse_charmap = {
            "{PLAYER}": 0x01,
            "{VALUE1}": 0x02,
            "{NICKNAME}": 0x02,
            "{VALUE2}": 0x03,
            "{VALUE4}": 0x04,
            "{BREAK}": 0x06,
            "{BREAK2}": 0x07,
            "{VALUE8}": 0x08,
            "{VALUE9}": 0x09,
            "{HORSE}": 0x19
        }

        while True:
            c = self.peek_char()
            
            if not c or c == '"':
                self.next_char() # consume the closing quote
                break
                
            if c == '{':
                # Intentar leer un tag como {PLAYER}
                tag_buf = ""
                peek_pos = self.pos
                while peek_pos < len(self.source) and self.source[peek_pos] != '}':
                    tag_buf += self.source[peek_pos]
                    peek_pos += 1
                
                if peek_pos < len(self.source) and self.source[peek_pos] == '}':
                    tag_buf += '}'
                    if tag_buf in reverse_charmap:
                        buf.append(reverse_charmap[tag_buf])
                        # Avanzar la posición real del lexer
                        for _ in range(len(tag_buf)): self.next_char()
                        continue
                # Si no es un tag válido, se trata como texto normal
                if c == 'Ñ':
                    buf.append(0xB2)
                elif c == 'ñ':
                    buf.append(0xB1)
                else:
                    buf.extend(c.encode('windows-1252'))
                self.next_char()
            elif c == '\\':
                self.next_char() # consume slash
                nc = self.peek_char()
                
                if nc == 'n': 
                    buf.append(0x0A) # \n estándar
                    self.next_char()
                elif self.source.startswith("BRK", self.pos):
                    buf.append(0x05)
                    for _ in range(3): self.next_char()
                elif self.source.startswith("WAIT_CLICK", self.pos):
                    buf.append(0x0C)
                    for _ in range(10): self.next_char()
                elif nc == 'r': 
                    buf.append(0x0D)
                    self.next_char()
                elif nc == 't': 
                    buf.append(0x09)
                    self.next_char()
                elif nc == '"': 
                    buf.append(0x22)
                    self.next_char()
                elif nc == '\\': 
                    buf.append(0x5C)
                    self.next_char()
                elif nc == 'x':
                    self.next_char() # consume x
                    hex_digits = self.next_char() + self.next_char()
                    try:
                        buf.append(int(hex_digits, 16))
                    except ValueError:
                        raise LexerError(f"Valor Hexadecimal Inválido en escape String: \\x{hex_digits}")
                else:
                    buf.append(ord(nc))
                    self.next_char()
            elif c == 'Ñ':
                buf.append(0xB2)
                self.next_char()
            elif c == 'ñ':
                buf.append(0xB1)
                self.next_char()
            else:
                buf.extend(c.encode('windows-1252'))
                self.next_char()
                
        return bytes(buf)
        
    def next_token(self) -> Token:
        self.skip_whitespace_and_comments()
        
        c = self.peek_char()
        if not c:
            return Token(TokenType.EOF, line=self.line, column=self.col)
            
        start_line = self.line
        start_col = self.col
        
        # String Literals
        if c == '"':
            val = self.read_string_literal()
            return Token(TokenType.STRING_LIT, val, start_line, start_col)
            
        # Numbers
        if c.isdigit():
            is_hex = False
            if c == '0' and self.source.startswith('0x', self.pos):
                self.next_char() # 0
                self.next_char() # x
                is_hex = True
                
            num_str = ""
            while True:
                nc = self.peek_char()
                if is_hex and nc in '0123456789abcdefABCDEF':
                    num_str += self.next_char()
                elif not is_hex and nc.isdigit():
                    num_str += self.next_char()
                else:
                    break
                    
            val = int(num_str, 16 if is_hex else 10)
            return Token(TokenType.INTEGER, val, start_line, start_col)
            
        # Names and Keywords
        if c.isalpha() or c == '_':
            name = ""
            while True:
                nc = self.peek_char()
                if nc.isalnum() or nc == '_':
                    name += self.next_char()
                else:
                    break
                    
            try:
                kw_type = TokenType(name)
                return Token(kw_type, line=start_line, column=start_col)
            except ValueError:
                return Token(TokenType.NAME, name, start_line, start_col)
                
        # Operators and Punctuation
        ops_3 = []
        ops_2 = ['++', '--', '&&', '||', '==', '!=', '<=', '>=', '+=', '-=', '*=', '/=', '%=']
        ops_1 = ['(', ')', '{', '}', ',', ':', ';', '+', '-', '*', '/', '%', '!', '<', '>', '=']
        
        for op in ops_2:
            if self.source.startswith(op, self.pos):
                self.next_char(); self.next_char()
                return Token(TokenType(op), line=start_line, column=start_col)
                
        for op in ops_1:
            if self.source.startswith(op, self.pos):
                self.next_char()
                return Token(TokenType(op), line=start_line, column=start_col)
                
        raise LexerError(f"Unexpected character '{c}' at line {self.line}, col {self.col}")
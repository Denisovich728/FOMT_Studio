# Manual Técnico de Referencia: SlipSpace Script Engine
**Harvest Moon: Friends of Mineral Town (Game Boy Advance)**
**Suite de Ingeniería Inversa - FOMT Studio**
*Arquitectura, Especificación Formal del Lenguaje, Bytecode y Guía para Modelos de Lenguaje (LLMs)*

---

## 1. Resumen Ejecutivo y Arquitectura del Motor

El **SlipSpace Script Engine** es el compilador, descompilador y máquina virtual que orquesta la lógica de eventos, diálogos, cinemáticas, máquinas de estado de aldeanos y condiciones de juego en la ROM de *Harvest Moon: Friends of Mineral Town* (GBA).

### 1.1 Modelo de la Máquina Virtual (Stack-based VM)
La VM opera mediante un modelo de pila de 32 bits implementado en código máquina ARM7TDMI:
- **Pila de Operandos:** Las operaciones aritméticas, lógicas y llamadas a funciones empujan (`push`) y extraen (`pop`) valores de la pila de evaluación.
- **Variables Locales:** Se almacenan en ranuras indexadas (`VarId: 0, 1, 2...`) gestionadas por los opcodes `PushVar` y `PopVar`.
- **Estructura de Bloques RIFF:** Los scripts compilados residen en bloques de formato RIFF (`RIFF [longitud] SCR `) compuestos por:
  - Sub-chunk de Código Binario (instrucciones de bytecode GBA).
  - Sub-chunk de Cadenas de Texto (`STR `) con punteros relativos a cadenas de diálogo.

---

## 2. Gramática Formal EBNF (Extended Backus-Naur Form)

```ebnf
Program         ::= ( IncludeDirective | Declaration | ScriptDefinition )* ;

IncludeDirective::= '#include' STRING_LIT ;

Declaration     ::= ConstDecl | FuncDecl | ProcDecl ;
ConstDecl       ::= 'const' IDENTIFIER '=' ( INTEGER_LIT | STRING_LIT ) ';' ;
FuncDecl        ::= 'func' HEX_ID IDENTIFIER '(' ParameterList? ')' ';' ;
ProcDecl        ::= 'proc' HEX_ID IDENTIFIER '(' ParameterList? ')' ';' ;

ParameterList   ::= Type ( ',' Type )* ;
Type            ::= 'integer' | 'string' ;

ScriptDefinition::= 'script' INTEGER_LIT IDENTIFIER '{' StatementList '}' ;

StatementList   ::= Statement* ;

Statement       ::= VarDeclStmt
                  | AssignStmt
                  | CallStmt
                  | IfStmt
                  | SwitchStmt
                  | DoWhileStmt
                  | BreakStmt
                  | ExitStmt
                  | GotoStmt
                  | LabelStmt
                  | BlockStmt ;

VarDeclStmt     ::= 'int' IDENTIFIER ( ',' IDENTIFIER )* ';' ;
AssignStmt      ::= IDENTIFIER AssignOp Expression ';' ;
AssignOp        ::= '=' | '+=' | '-=' | '*=' | '/=' | '%=' ;

CallStmt        ::= IDENTIFIER '(' ArgumentList? ')' ';' ;
ArgumentList    ::= Expression ( ',' Expression )* ;

IfStmt          ::= 'if' '(' Expression ')' Statement ( 'else' Statement )? ;

SwitchStmt      ::= 'switch' '(' Expression ')' '{' SwitchCase* '}' ;
SwitchCase      ::= ( 'case' Expression ':' | 'default' ':' ) StatementList ;

DoWhileStmt     ::= 'do' Statement 'while' '(' Expression ')' ';' ;
BreakStmt       ::= 'break' ';' ;
ExitStmt        ::= 'exit' ';' ;

GotoStmt        ::= 'goto' IDENTIFIER ';' ;
LabelStmt       ::= IDENTIFIER ':' ;
BlockStmt       ::= '{' StatementList '}' ;

Expression      ::= LogicalOrExpr ;
LogicalOrExpr   ::= LogicalAndExpr ( '||' LogicalAndExpr )* ;
LogicalAndExpr  ::= EqualityExpr ( '&&' EqualityExpr )* ;
EqualityExpr    ::= RelationalExpr ( ( '==' | '!=' ) RelationalExpr )* ;
RelationalExpr  ::= AdditiveExpr ( ( '<' | '<=' | '>' | '>=' ) AdditiveExpr )* ;
AdditiveExpr    ::= MultiplicativeExpr ( ( '+' | '-' ) MultiplicativeExpr )* ;
MultiplicativeExpr ::= UnaryExpr ( ( '*' | '/' | '%' ) UnaryExpr )* ;
UnaryExpr       ::= ( '!' | '-' | '++' | '--' ) UnaryExpr | PrimaryExpr ;
PrimaryExpr     ::= IDENTIFIER
                  | INTEGER_LIT
                  | STRING_LIT
                  | CallExpr
                  | '(' Expression ')' ;
CallExpr        ::= IDENTIFIER '(' ArgumentList? ')' ;
```

---

## 3. Tipos de Datos y Variables

1. **Variables de Script:**
   - Declaradas obligatoriamente al inicio del bloque del script con `int`:
     ```c
     int var_0, var_1, var_2;
     ```
   - Representan registros de trabajo de 32 bits de la VM.
2. **Literales Numéricos:**
   - Decimal: `0`, `14`, `100`, `-1`
   - Hexadecimal: `0x00`, `0x4B`, `0x082C7C08`
3. **Cadenas de Texto:**
   - Delimitadas por comillas dobles `"..."`.
   - Utilizadas como argumentos de funciones de diálogo (`TalkMessage`, `Talk`, nombres de flags).

---

## 4. Estructuras de Control y Convenciones de Compilación

### 4.1 Selección Múltiple (`switch / case / break`)
Los switch-case representan dispatch tables nativas de GBA.
- Cada caso termina con `break;` para salir del bloque hacia la siguiente instrucción secuencial.
- Ejemplo canónico:
```c
switch (GetEntityLocation(2)) {
    case 7:
        Set_Portrait(0);
        TalkMessage(14);
        break;
    case 6:
        Set_Portrait(0);
        TalkMessage(47);
        break;
    default:
        break;
}
```

### 4.2 Condicionales Anidados (`if / else`)
El compilador y descompilador soportan anidación arbitraria de condiciones compuestas evaluadas mediante cortocircuito booleano (`&&`, `||`):
```c
if (((Check_Flag("Flag_0x71") == 2) && (Check_Flag("Flag_0x72") == 0))) {
    if ((Has_NPC_Talked_Today(2) == 0)) {
        Set_Portrait(0);
        TalkMessage(18);
    } else {
        Set_Portrait(0);
        TalkMessage(19);
    }
}
```

### 4.3 Terminación de Script (`exit;`)
Instrucción de corte inmediato de la ejecución de la VM de eventos. Cierra el hilo de script y restaura el control al bucle principal de la ROM:
```c
TalkClose();
SetEntityFacing(2, var_2);
exit;
```

---

## 5. Formato de Cadenas y Tokens Especiales de Diálogo

El motor de renderizado de texto de FoMT opera con secuencias de escape consolidadas:

| Token | Byte Hexadecimal | Significado Técnico | Comportamiento en Juego |
| :--- | :--- | :--- | :--- |
| `\n` | `0x0D 0x0A` | Salto de Línea | Pasa a la siguiente línea del cuadro de texto. |
| `\w` | `0x0C` | Wait Click | Detiene el texto hasta que el jugador presiona el botón A. |
| `\b` | `0x05` | Break Box | Limpia el cuadro de diálogo y abre una nueva página de texto. |

### Reglas Críticas del Procesador de Texto:
- Las nuevas líneas en la ROM son estrictamente pares `0x0D 0x0A` (100% verificado empíricamente). No emitir `0x0A` o `0x0D` aislados.
- Los comandos heredados `\WAIT CLICK`, `\WAIT_CLICK` y `\BRK` se normalizan automáticamente a `\w` y `\b`.

---

## 6. API Central y Procedimientos Estándar (Biblioteca FoMT)

Los procedimientos y funciones nativos más comunes se mapean contra `Banco_de_Datos/Cilixes/fomt/Fomt_Lib.csv`:

### 6.1 Diálogos y Retratos
- `TalkMessage(int message_id)`: Imprime el mensaje predeterminado desde la tabla de strings del script.
- `Talk(int character_id, string text)`: Imprime diálogo directo con texto explícito.
- `Set_Portrait(int portrait_variant)`: Asigna la expresión o variante de retrato a mostrar (0 = Neutral, 1 = Feliz, 2 = Enojado, etc.).
- `TalkClose()`: Cierra la caja de diálogo de la interfaz.

### 6.2 Flags y Estado del Mundo
- `Check_Flag(string flag_name | int flag_id) -> int`: Retorna 0 (no activo), 1 (activo) o 2 (completado/avanzado).
- `Set_Flag(string flag_name | int flag_id, int state)`: Actualiza el estado de una bandera global del juego.
- `Has_NPC_Talked_Today(int npc_id) -> int`: Retorna 1 si el jugador ya conversó hoy con el aldeano; 0 en caso contrario.

### 6.3 Entidades y Movimiento
- `GetEntityLocation(int entity_id) -> int`: Retorna el ID del mapa donde reside la entidad.
- `SetEntityFacing(int entity_id, int direction)`: Ajusta la orientación cardinal de la entidad (0=Abajo, 1=Arriba, 2=Izquierda, 3=Derecha).
- `Warp_Entity_To_Map(int map_id)`: Teletransporta a la entidad al mapa indicado.
- `Free_Event_Entity(int entity_id)`: Libera el bloqueo de IA del personaje tras terminar una conversación o evento.

### 6.4 Inventario y Objetos
- `Drop_Held_Item()`: Descarta o remueve el objeto sostenido por el jugador.
- `Give_Item(int item_id, int quantity)`: Entrega herramientas o artículos a la mochila.
- `Check_Equped_Tool() -> int`: Retorna el ID de la herramienta equipada en mano.

---

## 7. Muestra Real Anotada: Máquina de Estados de Aldeano (Evento 992)

```c
#include "Fomt_Lib.csv"

script 992 Rick_Personality {
int var_0, var_1, var_2;
var_2 = GetEntityFacing(2);
SetEntityFacing(2, 0);
var_0 = Check_Held_Item();
var_1 = Check_Gift_Reaction(2, var_0);
if ((var_1 == 3)) {
    Set_Portrait(0);
    TalkMessage(0);
    TalkClose();
    Drop_Held_Item();
} else {
    if ((var_1 == 2)) {
        Set_Portrait(0);
        TalkMessage(2);
        TalkClose();
        Drop_Held_Item();
    } else {
        if ((var_1 == 1)) {
            Set_Portrait(0);
            TalkMessage(4);
            TalkClose();
            Drop_Held_Item();
        } else {
            switch (GetEntityLocation(2)) {
                case 7:
                    if ((Check_Flag("Karen_Marriage_State") == 2)) {
                        if ((Has_NPC_Talked_Today(2) == 0)) {
                            Set_Portrait(0);
                            TalkMessage(14);
                        } else {
                            Set_Portrait(1);
                            TalkMessage(15);
                        }
                    }
                    break;
                case 6:
                    if ((Has_NPC_Talked_Today(2) == 0)) {
                        Set_Portrait(0);
                        TalkMessage(47);
                    } else {
                        Set_Portrait(0);
                        TalkMessage(48);
                    }
                    break;
            }
            Free_Event_Entity(2);
        }
    }
}
TalkClose();
SetEntityFacing(2, var_2);
exit;
}
```

---

## 8. Directrices Obligatorias para LLMs y Compiladores Autónomos

1. **Estructuración Pura sin Gotos Fantasma:**
   - Nunca emitas `goto` o `LBL_XXXX:` para escapes de bloques `if` o salidas de casos de `switch`. Usa `break;` dentro de switch y `exit;` para salidas globales.
2. **Declaración Obligatoria de Variables:**
   - Toda variable `var_X` debe ser declarada al principio del script con `int var_0, var_1;`. No utilices variables no declaradas.
3. **Sintaxis de Include:**
   - La primera línea debe ser siempre `#include "Fomt_Lib.csv"` (o `"MFomt_Lib.csv"` si es More Friends of Mineral Town).
4. **Cierre de Diálogo Seguro:**
   - Toda llamada a `TalkMessage(...)` o `Talk(...)` debe acompañarse de `TalkClose()` antes de teletransportar entidades o llamar a `exit;`.
5. **Escape Sequences en Diálogos:**
   - Usar estrictamente `\n` para saltos de línea, `\w` para pausas/clicks y `\b` para saltos de cuadro.

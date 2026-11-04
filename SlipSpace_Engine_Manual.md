# Manual de Referencia del Lenguaje: SlipSpace Script
**Harvest Moon: Friends of Mineral Town (Game Boy Advance)**
**Suite de Ingeniería Inversa y Modding - FOMT Studio**
*Especificación Formal y Guía de Programación de Alto Nivel para Desarrolladores y Modelos de Lenguaje (LLMs)*

---

## 1. Introducción y Filosofía del Lenguaje

**SlipSpace Script** es un lenguaje imperativo estructurado con sintaxis de estilo C, diseñado específicamente para escribir, editar, descompilar y compilar la totalidad de los eventos, cinemáticas y máquinas de estado de inteligencia artificial de *Harvest Moon: Friends of Mineral Town* (FoMT) y *Harvest Moon: More Friends of Mineral Town* (MFoMT).

### Principios de Diseño:
- **Abstracción Total de Bajo Nivel:** El programador opera exclusivamente con construcciones de alto nivel (`if-else`, `switch-case`, `do-while`, funciones con nombre semántico y cadenas legibles). El compilador se encarga de resolver saltos, tablas de punteros y empaquetado binario.
- **Sintaxis Familiar Estilo C:** Bloques delimitados por llaves `{ }`, sentencias terminadas en punto y coma `;` y operadores estándar (`==`, `!=`, `&&`, `||`, `!`).
- **Determinismo y Tipado Estático:** Variables de trabajo declaradas explícitamente y funciones estándar con firmas semánticas validadas contra la biblioteca oficial (`Fomt_Lib.csv`).

---

## 2. Anatomía de un Script de Evento

Cada archivo o bloque de script sigue una estructura canónica obligatoria:

```c
#include "Fomt_Lib.csv"

script 992 Rick_Personality {
    int var_0, var_1, var_2;

    // Cuerpo de lógica de alto nivel
    var_0 = Check_Held_Item();
    if (var_0 != 0) {
        TalkMessage(1);
        TalkClose();
        Drop_Held_Item();
    }

    exit;
}
```

### Componentes Estructurales:
1. **Directiva `#include`:** Debe figurar al inicio del archivo. Carga el espacio de nombres de procedimientos y funciones (`Fomt_Lib.csv` para FoMT o `MFomt_Lib.csv` para MFoMT).
2. **Definición de Script:** `script <ID> <NombreIdentificador> { ... }`.
   - `<ID>`: Índice numérico del evento dentro de la ROM (1 a 1329 en FoMT).
   - `<NombreIdentificador>`: Nombre alfanumérico que describe la función del evento (ej. `Rick_Personality`, `Event_0001`, `Harvest_Festival`).
3. **Cuerpo del Script:** Encerrado entre llaves `{ }`. Contiene primero la declaración de variables y a continuación las sentencias ejecutables.

---

## 3. Tipos de Datos y Variables

### 3.1 Declaración de Variables Locales
Las variables representan los registros de estado locales del script. Deben declararse **obligatoriamente al principio del script**, antes de cualquier sentencia ejecutable:

```c
int var_0, var_1, var_2;
```

- **Palabra clave:** `int`.
- **Nomenclatura:** `var_N`, donde `N` es un entero mayor o igual a 0 (`var_0`, `var_1`, `var_2`, etc.).
- **Ámbito:** Local al script actual. No conservan valor entre ejecuciones independientes del evento.
- **Capacidad:** Enteros con o sin signo de 32 bits.

### 3.2 Literales
- **Enteros Decimales:** `0`, `1`, `7`, `42`, `-1`.
- **Enteros Hexadecimales:** Prefijados por `0x` o `0X`. Ejemplos: `0x00`, `0x4B`, `0x1F4`, `0x082C7C08`.
- **Cadenas de Texto:** Delimitadas por comillas dobles `"..."`. Se emplean en llamadas directas (`Talk`) y nombres simbólicos de banderas (`Check_Flag("Flag_0x71")`).

---

## 4. Expresiones y Operadores

El lenguaje implementa la precedencia y asociatividad estándar de C:

### 4.1 Operadores Aritméticos
| Operador | Operación | Ejemplo |
| :--- | :--- | :--- |
| `+` | Suma | `var_0 = var_1 + 5;` |
| `-` | Resta | `var_0 = var_1 - 1;` |
| `*` | Multiplicación | `var_0 = var_1 * 2;` |
| `/` | División entera | `var_0 = var_1 / 10;` |
| `%` | Módulo / Residuo | `var_0 = var_1 % 4;` |
| `++` | Pre / Post incremento | `var_0++;` |
| `--` | Pre / Post decremento | `var_0--;` |

### 4.2 Operadores de Asignación
| Operador | Equivalente |
| :--- | :--- |
| `=` | Asignación directa: `var_0 = 10;` |
| `+=` | Suma y asignación: `var_0 += 5;` |
| `-=` | Resta y asignación: `var_0 -= 2;` |
| `*=` | Multiplicación y asignación: `var_0 *= 3;` |
| `/=` | División y asignación: `var_0 /= 2;` |
| `%=` | Módulo y asignación: `var_0 %= 10;` |

### 4.3 Operadores Relacionales
| Operador | Significado |
| :--- | :--- |
| `==` | Igualdad |
| `!=` | Desigualdad |
| `<` | Menor que |
| `<=` | Menor o igual que |
| `>` | Mayor que |
| `>=` | Mayor o igual que |

### 4.4 Operadores Lógicos
- `&&` : Conjunción lógica (AND).
- `||` : Disyunción lógica (OR).
- `!`  : Negación lógica (NOT).

Ejemplo de condición compuesta:
```c
if (((Check_Flag("Flag_0x71") == 2) && (Check_Flag("Flag_0x72") == 0))) {
    // Código si la bandera 0x71 es 2 y la 0x72 es 0
}
```

---

## 5. Estructuras de Control de Alto Nivel

### 5.1 Bifurcación Condicional (`if / else`)
Permite la ejecución selectiva basada en expresiones booleanas. Las sentencias `else` son opcionales y pueden encadenarse:

```c
if (Has_NPC_Talked_Today(2) == 0) {
    Set_Portrait(0);
    TalkMessage(14);
} else {
    Set_Portrait(1);
    TalkMessage(15);
}
```

### 5.2 Selección Múltiple (`switch / case / break`)
Estructura idiomática preferida para evaluar estados finitos, ubicaciones en mapas o tipos de herramientas.

**Regla Mandatoria:** Cada caso debe terminar con `break;` para salir del bloque del switch.

```c
switch (GetEntityLocation(2)) {
    case 6:
        Set_Portrait(0);
        TalkMessage(47);
        break;
    case 7:
        Set_Portrait(0);
        TalkMessage(14);
        break;
    case 0x15:
        Set_Portrait(1);
        TalkMessage(49);
        break;
    default:
        break;
}
```

### 5.3 Bucles Repetitivos (`do / while`)
Ejecuta el bloque subordinado y comprueba la condición al final:

```c
do {
    var_0++;
    TalkMessage(var_0);
} while (var_0 < 3);
```

### 5.4 Terminación de Script (`exit;`)
Detiene inmediatamente el script en ejecución, cerrando el contexto del hilo y devolviendo el control al bucle principal de la ROM de GBA:

```c
TalkClose();
SetEntityFacing(2, var_2);
exit;
```

---

## 6. Sistema de Texto, Diálogos y Formato de Mensajes

El procesador de diálogos de *Friends of Mineral Town* renderiza ventanas de texto mediante códigos de control insertados directamente en las cadenas de texto:

### 6.1 Códigos de Control Oficiales

| Código | Nombre | Comportamiento en Pantalla |
| :--- | :--- | :--- |
| `\n` | **Salto de Línea** | Salta a la línea inferior dentro de la misma caja de diálogo. |
| `\w` | **Pausa / Wait Click** | Detiene el avance del texto y espera a que el jugador presione el botón A. |
| `\b` | **Salto de Cuadro / Break** | Limpia la caja actual y abre una página limpia de texto. |

### Ejemplo Práctico de Formateo de Diálogo:
```c
Talk(2, "¡Hola, Denisovich!\nQué gran día hace hoy en la granja.\w\b¿Has venido a comprar suministros?\w");
```
- `\n` coloca *"Qué gran día..."* en la segunda línea.
- `\w` detiene el diálogo para que el jugador lea la primera caja.
- `\b` limpia la caja por completo y coloca *"¿Has venido a comprar...?"* en una nueva caja.
- El `\w` final espera la confirmación del usuario antes de cerrar o pasar a la siguiente lógica.

### 6.2 Primitivas de Diálogo y Retratos
- `Talk(int npc_id, string mensaje)`: Imprime el texto directamente en pantalla asignado al NPC.
- `TalkMessage(int message_id)`: Muestra el mensaje indexado en la tabla de textos del evento.
- `Set_Portrait(int variante)`: Fija la emoción del retrato (0 = Neutral, 1 = Contento, 2 = Enojado, 3 = Triste, etc.).
- `TalkClose()`: Cierra y desvanece el marco de diálogo en pantalla. **Debe llamarse siempre antes de teletransportar entidades o llamar a `exit;`**.

---

## 7. Catálogo de la API Estándar (`Fomt_Lib.csv`)

Funciones y procedimientos de alto nivel organizados por subsistema:

### 7.1 Gestión de Banderas y Tiempo
- `Check_Flag(string nombre_flag | int flag_id) -> int`: Consulta el valor de una bandera global (0 = inactiva, 1 = activa, 2 = completada).
- `Set_Flag(string nombre_flag | int flag_id, int valor)`: Modifica el estado de una bandera global del juego.
- `Has_NPC_Talked_Today(int npc_id) -> int`: Retorna 1 si el jugador ya habló con el aldeano durante el día actual; 0 si es la primera conversación.
- `Get_Current_Time() -> int`: Retorna la hora del reloj interno de Mineral Town.

### 7.2 Entidades, Orientación y Mapas
- `GetEntityLocation(int npc_id) -> int`: Retorna el ID del mapa donde se encuentra actualmente el NPC.
- `GetEntityFacing(int npc_id) -> int`: Retorna la orientación cardinal actual (0=Abajo, 1=Arriba, 2=Izquierda, 3=Derecha).
- `SetEntityFacing(int npc_id, int direccion)`: Fuerza al personaje a girar hacia la dirección indicada.
- `Warp_Entity_To_Map(int map_id)`: Teletransporta inmediatamente al aldeano al mapa objetivo.
- `Free_Event_Entity(int npc_id)`: Libera a la entidad del bloqueo de cinemática para que retome su rutina diaria.

### 7.3 Inventario, Herramientas y Regalos
- `Check_Held_Item() -> int`: Identifica el objeto que el jugador sostiene sobre su cabeza (0 si tiene las manos vacías).
- `Check_Gift_Reaction(int npc_id, int item_id) -> int`: Evalúa el agrado del aldeano hacia el objeto:
  - `3`: Amor / Favorito (+800 puntos de afecto).
  - `2`: Gusto (+500 puntos de afecto).
  - `1`: Neutral / Indiferente (+100 puntos de afecto).
  - `0`: Disgusto / Odio (-500 puntos de afecto).
- `Drop_Held_Item()`: Consume o remueve el objeto sostenido (entregándolo al NPC).
- `Give_Item(int item_id, int cantidad)`: Añade artículos a la mochila del jugador.
- `Check_Equped_Tool() -> int`: Retorna el ID de la herramienta equipada en la ranura activa.

---

## 8. Muestras Completas de Código de Alto Nivel

### Ejemplo 1: Cinemática Narrativa con Diálogos y Salto de Cuadro
```c
#include "Fomt_Lib.csv"

script 1001 Encuentro_Alcalde {
    int var_0;

    Set_Portrait(0);
    Talk(12, "¡Buenos días, joven!\nBienvenido seas a Mineral Town.\w\bVeo que te estás adaptando rápidamente al trabajo duro.\w");
    
    var_0 = Check_Flag("Town_Reputation");
    if (var_0 >= 10) {
        Set_Portrait(1);
        Talk(12, "Todos en la villa hablan maravillas sobre tu cosecha.\w");
        Give_Item(0x28, 1);
    } else {
        Set_Portrait(0);
        Talk(12, "No olvides regar tus cultivos cada mañana sin falta.\w");
    }

    TalkClose();
    exit;
}
```

### Ejemplo 2: Máquina de Estados de Aldeano (Evento 992 - Rick)
```c
#include "Fomt_Lib.csv"

script 992 Rick_Personality {
    int var_0, var_1, var_2;

    var_2 = GetEntityFacing(2);
    SetEntityFacing(2, 0);

    var_0 = Check_Held_Item();
    var_1 = Check_Gift_Reaction(2, var_0);

    if (var_1 == 3) {
        Set_Portrait(1);
        TalkMessage(0);
        TalkClose();
        Drop_Held_Item();
    } else {
        if (var_1 == 2) {
            Set_Portrait(1);
            TalkMessage(2);
            TalkClose();
            Drop_Held_Item();
        } else {
            switch (GetEntityLocation(2)) {
                case 7:
                    if (Check_Flag("Karen_Marriage_State") == 2) {
                        if (Has_NPC_Talked_Today(2) == 0) {
                            Set_Portrait(0);
                            TalkMessage(14);
                        } else {
                            Set_Portrait(1);
                            TalkMessage(15);
                        }
                    } else {
                        Set_Portrait(0);
                        TalkMessage(16);
                    }
                    break;

                case 6:
                    if (Has_NPC_Talked_Today(2) == 0) {
                        Set_Portrait(0);
                        TalkMessage(47);
                    } else {
                        Set_Portrait(0);
                        TalkMessage(48);
                    }
                    break;

                default:
                    Set_Portrait(0);
                    TalkMessage(30);
                    break;
            }
            Free_Event_Entity(2);
        }
    }

    TalkClose();
    SetEntityFacing(2, var_2);
    exit;
}
```

---

## 9. Reglas Críticas para Modelos de Lenguaje (LLMs) y Desarrolladores

Para garantizar que los scripts compilen limpiamente a la ROM sin errores de sintaxis, deben cumplirse las siguientes directivas:

1. **Declaración en la Primera Línea:** Nunca utilices una variable `var_X` sin haberla declarado previamente en la sentencia inicial `int var_0, var_1;`.
2. **Cero Gotos Innecesarios:** Escribe flujos de control estructurados (`if/else` y `switch/case/break`). No utilices `goto` para simular salidas de bucles o saltos de casos.
3. **Cierre de Diálogos Obligatorio:** Si invocaste `TalkMessage` o `Talk`, debes llamar a `TalkClose()` antes de `exit;` o de realizar un teletransporte de entidad (`Warp_Entity_To_Map`).
4. **Normalización de Cadenas:** Usa exclusivamente `\n` para saltos de renglón, `\w` para pausas con click y `\b` para saltos de cuadro. No utilices secuencias de escape no soportadas.
5. **Comentarios de Código:** Se admiten comentarios de línea única mediante `//` y comentarios de bloque mediante `/* ... */`.

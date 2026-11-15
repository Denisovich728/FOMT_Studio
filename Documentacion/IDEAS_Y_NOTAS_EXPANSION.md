# Ideas y Notas de Expansión — FOMT Studio

Registro de ideas técnicas y consideraciones para futuras implementaciones en FoMT y MFoMT.

## 1. Expansión de ROM hasta 32 MB
- El bus de cartucho de GBA direcciona hasta **32 MB** (`0x08000000` – `0x09FFFFFF`, offset `0x00000000` – `0x01FFFFFF`).
- `fomt virgen.gba` mide **8 MB** (`0x75C243` último byte usado) y `MFOMT VIRGEN.gba` mide **16 MB** (`0x9D98C7` último byte usado, con ~6.26 MB libres `0xFF` desde `0x9E0000`).
- Ambas ROMs pueden expandirse hasta 32 MB rellenando con `0xFF` sin romper punteros nativos.

## 2. Mecánica de Cambio de Ropa (MFoMT -> FoMT)
- En MFoMT el espejo cambia la **paleta de colores** de la protagonista según un ID guardado en WRAM/SRAM.
- **Opción A (Cambio de paletas, estilo oficial MFoMT):**
  - Tabla de N paletas de 16 colores (32 bytes c/u) en espacio libre para Pete/Jack.
  - 1 byte en WRAM/SRAM para guardar `outfit_id`.
  - Hook Thumb en la rutina de carga de paleta del jugador al entrar al mapa o inicializar sprites.
  - Script/trigger del espejo para elegir traje y refrescar paleta.
- **Opción B (Sprites completos distintos):**
  - Requiere además hookear el puntero de tabla de animación/tiles del jugador hacia nuevos bloques de sprites en espacio libre (expandiendo FoMT a 16/32 MB si hace falta).

## 3. Añadir NPCs Nuevos y Rutinas Adicionales
- **Nuevas rutinas en NPC existente (ej. Diosa casada):**
  - Soportado directamente con `+ Nueva Rutina` en `editor_rutinas_npc.py` y `RoutineCodec.reinject_npc_to_project`.
  - Requiere revisar/ajustar la `evaluator_func` del NPC para que devuelva el nuevo `schedule_id` cuando se cumpla la flag de condición (ej. matrimonio).
- **NPC completamente nuevo desde cero (`ID >= 32` en FoMT / `>= 33` en MFoMT):**
  - `RoutineCodec.reinject_npc_to_project` ya repuntea la tabla maestra de rutinas (`0x3D9A4` / `0x3DCA8`), pero el motor GBA requiere además:
    1. Parchear el límite `cmp` en el bucle Thumb del gestor de entidades (`32` en FoMT / `33` en MFoMT).
    2. Expandir/repuntear la tabla de ficha de NPCs (`0x104260` en FoMT / `0x10CF3C` en MFoMT, 8 bytes/fila).
    3. Asignar espacio de estado en WRAM/SRAM (afecto, regalos, etc.).
  - **Atajo práctico sin tocar WRAM:** reutilizar un slot reservado sin uso en juego normal (ej. `ID 34` vacío, o `ID 32/33` Lou/Lu si no se usa conectividad con GameCube).


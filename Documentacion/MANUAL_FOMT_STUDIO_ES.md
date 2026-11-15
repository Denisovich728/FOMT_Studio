# Manual de Usuario de FOMT Studio

Suite de Ingeniería Inversa, Traducción y Modding para *Harvest Moon: Friends of Mineral Town* y *More Friends of Mineral Town* (Game Boy Advance).

---

## 1. Requisitos e Instalación

- **Sistema Operativo:** Windows 10/11 (compatible con Linux y macOS en ejecución desde código fuente).
- **Python:** Python 3.10 o superior.
- **Dependencias principales:** PyQt6, Pillow (PIL), NumPy (según módulos de gráficos/mapas).

### Ejecución desde código fuente
Desde la carpeta raíz `FOMT_Studio`:

```bash
python main.py
```

Si ocurre un error crítico al iniciar, el detalle se registra automáticamente en `fomt_studio_error.log` en la raíz del proyecto.

---

## 2. Estructura del Espacio de Trabajo

El repositorio está organizado por responsabilidades para mantener limpio el entorno de trabajo:

- `main.py`: Punto de entrada de la aplicación gráfica.
- `Consola_de_Comando/`: Interfaz principal (`app.py`), traducción multi-idioma (`i18n.py` / `i18n.json`), temas visuales (`themes.py`), editor de menús, editor de intro y ajustes.
- `Nucleos_Positronicos/`: Motores especializados por dominio:
  - `Nucleo_de_Scripts/`: IDE SlipSpace, motor de compilación/descompilación (`SlipSpace_Script_Engine/`), Teatro de Eventos, Block Puzzle y `memory_extend_engine.py` (expansor de flags).
  - `Nucleo_de_Imagenes/`: Editor extremo de tiles (`tile_editor_extreme.py`), visor de animaciones y extractor.
  - `Nucleo_de_Sprites/`: Visor de sprites y metasprites.
  - `Nucleo_de_Mapas/`: Editor/visor de mapas, tilesets y compresión/descompresión (`decompress_auto`).
  - `Nucleo_de_Aldeanos/`: Editor de NPCs, retratos y rutinas AI.
  - `Nucleo_de_Items/`: Editor individual y masivo de objetos, herramientas y comidas.
  - `Nucleo_de_Sonido/`: Visor de audio Sappy.
  - `Nucleo_de_Rutinas_AI/`: Visor de procedimientos nativos.
- `Banco_de_Datos/`: Modelos de proyecto (`proyecto.py`), parche de fuente española (`parche_font.py`), tablas `Textos_UI/` (`strings_fuera_de_eventos (esp).csv`) y `Utilidades/` de compresión.
- `Herramientas/`: Utilidades CLI autónomas (`inyector_strings_ui.py` para inyección masiva de strings de interfaz, `bin.py` para inspección hexadecimal).
- `Nucleo_Herramientas/`: Utilidades auxiliares (`flagser.py` para expansión de flags por CLI, `config_manager.py`, `visor_parches.py`, `visor_tilesets.py`).
- `Documentacion/`: Manuales del motor SlipSpace, guías de rutinas NPC y manuales de FOMT Studio (ES/EN).
- `Assets_Graficos/` y `Archivos_Trabajo/`: Recursos gráficos, dumps de extracción y respaldos de trabajo.

---

## 3. Primeros Pasos en FOMT Studio

1. **Cargar o Crear Proyecto (`Archivo -> Nuevo Proyecto` / `Cargar Proyecto`):**
   - Selecciona una ROM `.gba` de *Harvest Moon: Friends of Mineral Town* (USA) o *More Friends of Mineral Town* (USA).
   - FOMT Studio detecta automáticamente la cabecera (`HARVESTMOGBA` / `HM MFOM USA`) y crea el árbol de exploración en el panel izquierdo.
2. **Guardar y Compilar (`Ctrl+S` / `Archivo -> Compilar ROM`):**
   - **Guardar Proyecto** almacena los cambios editados en la estructura del proyecto (`.fomt` / archivos locales).
   - **Compilar ROM** genera una ROM `.gba` parcheada con todas las modificaciones aplicadas y actualiza la suma de comprobación de cabecera GBA.
3. **Personalización (`Configuración`):**
   - **Temas:** Light, Dark, Dracula (VS Code), Matrix y Forerunner.
   - **Idiomas:** Español, Inglés, Japonés, Ruso, Alemán, Chino, Hindi y Portugués.
   - **Ajustes del Sistema (`Ctrl+Alt+S`):** Configuración avanzada de rutas y preferencias.

---

## 4. Módulos y Editores Principales

La barra superior y el menú desplegable **Más herramientas** agrupan los editores por categoría:

### 4.1 Scripts y Eventos (SlipSpace)
- **IDE SlipSpace:** Editor de scripts de alto nivel con resaltado de sintaxis, compilación y descompilación directa desde la tabla de eventos (`0x0F89D4` en FoMT). Consulta [SlipSpace_Engine_Manual.md](file:///J:/Laboratorio/FOMT_Studio/Documentacion/SlipSpace_Engine_Manual.md) para la sintaxis completa.
- **Teatro de Eventos:** Previsualización visual de escenas, diálogos y animaciones de eventos.
- **Block Puzzle:** Editor visual basado en bloques lógicos para construir eventos sin escribir código manual.

### 4.2 Editores de Interfaz
- **Textos de UI / Menús:** Edición de cadenas del sistema fuera de eventos (menús de inventario, granja, calendario, pantalla de nombre y confirmación).
- **Textos de Intro:** Edición de la secuencia introductoria del juego.

### 4.3 Gráficos y Audio
- **Visor de Metasprites y Sprites:** Inspección y edición de hojas de sprites y ensamblado de metasprites OAM.
- **Visor y Extractor de Animaciones:** Visualización cuadro por cuadro y extracción de animaciones de personajes/objetos.
- **Editor de Tiles Extremo:** Edición de gráficos 4bpp/8bpp y paletas BGR555.
- **Audio Sappy:** Inspección y reproducción de pistas del motor de sonido Sappy (MP2K).

### 4.4 Datos, Mapas y Base de Datos Interna
- **Editor de Mapas:** Visualización de capas, tilesets y colisiones.
- **Editor Visual de NPCs y Rutinas NPC:** Edición de horarios, ubicaciones y comportamientos diarios de aldeanos.
- **Base de Datos Interna (RAW):** Acceso directo a tablas de NPCs, Objetos, Menús y Editor Maestro de Punteros.
- **Volcado Masivo de Objetos:** Edición por lotes de Herramientas, Comidas/Consumibles y Artículos varios.

---

## 5. Apartado de Herramientas

Accesible directamente desde el menú superior **`Herramientas`** o dentro de **`Más herramientas -> Herramientas`**:

1. **Expansión de Flags y Memoria In-Slot (Editor de Flags):**
   - Permite auditar el rango de flags actual de la ROM y registrar nuevas flags personalizadas (`bit`, `u8`, `u16`, `u32`) usando la cola libre del Slot 1 de guardado (`0x34AC..0x34C3`) sin romper el checksum nativo.
   - Redirige las tablas del despachador de flags hacia espacio libre en ROM (`0x75B000` por defecto).
   - También disponible por CLI ejecutando `python Nucleo_Herramientas/flagser.py <rom.gba>`.
2. **Editor de Partidas (`.sav`):**
   - Carga archivos de guardado SRAM de 64 KB / 128 KB para inspeccionar y modificar dinero, fecha, inventario, afecto y flags activas.
3. **Editor de Tiendas:**
   - Modifica el catálogo, precios y disponibilidad de las tiendas del pueblo.

---

## 6. Parches del Motor y Traducción al Español

En **`Más herramientas -> Parches y Modificaciones`** dispones de parches binarios listos para inyectar:

- **Parche Ñ y Caracteres Latinos:** Instala la tabla de glifos (`ÁÉÍÓÚáéíóúÑñÜü¿¡`) en la fuente del juego y habilita el mapeo `CHARMAP_ES`.
- **Parche Z-Sorting / Escaleras / Piedra de Teletransporte:** Mejoras de motor y calidad de vida para hacks avanzados.

### Inyección masiva de UI desde CSV
Para inyectar o actualizar masivamente los textos de interfaz desde `Banco_de_Datos/Textos_UI/strings_fuera_de_eventos (esp).csv` en una ROM:

```bash
python Herramientas/inyector_strings_ui.py --rom "ruta/a/tu_rom.gba" --out "ruta/a/rom_traducida.gba"
```

---

## 7. Preparación de Parches `.ips` para Producción

Para distribuir una traducción o mod sin distribuir la ROM completa:
1. Toma la ROM limpia original (No-Intro USA, SHA-1 `a2fc3574f0a65a4fcf7682fb274b9d7eebdef963` para FoMT USA).
2. Toma tu ROM compilada final (asegurando el byte de complemento en `0xBD` de la cabecera GBA).
3. Genera el archivo `.ips` comparando ambas ROMs (usando formato `PATCH` + registros de 3 bytes + `EOF`).
4. Verifica siempre el roundtrip aplicando el `.ips` sobre la ROM virgen en memoria o en un archivo temporal y comparando el SHA-1 resultante con tu ROM de producción.


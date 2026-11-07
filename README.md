# ============================================================
# FOMT STUDIO - Suite de Ingenieria Inversa (v4.0.0 "The Greatest Show"-Final Release)
# ============================================================

FOMT Studio es un entorno integral de desarrollo, desensamblado, analisis semantico y modificacion profunda (ROM Hacking) para el ecosistema "Harvest Moon: Friends of Mineral Town" (FoMT) y "More Friends of Mineral Town" (MFoMT) de Game Boy Advance (GBA).

Desarrollado con una arquitectura modular desacoplada en Python 3 y PyQt6, la suite proporciona herramientas especializadas de bajo nivel para editar codigo, graficos, mapas, rutinas de inteligencia artificial, secuencias de audio y datos internos de la ROM sin requerir dependencias externas de 32 bits.

------------------------------------------------------------
NOVEDADES PRINCIPALES DE LA VERSION 4.0.0 "The Greatest Show"-Final Release
------------------------------------------------------------

1. EDITOR DE RUTINAS DIARIAS Y ORQUESTADOR DE MOVIMIENTO (NPC AI ENGINE):
   - Mapeo canonico corregido de los 42 NPCs del juego y 41 nodos espaciales de Mineral Town.
   - Macromapa interactivo con conexion topologica de nodos y navegacion bidireccional entre mapas.
   - Inspeccion y edicion en tiempo real de waypoints horarios (coordenadas X/Y, Map ID, sub-flags y scripts vinculados).
   - Normalizacion de mascaras de bits (0x3FF vs 0xFF) para el manejo de waypoints fuera de mapa (despawn / limbo).
   - Centrado dinamico automatico de camara y asignacion rapida de mapas en el inspector flotante.

2. EDITOR DE MAPAS Y TILESETS CON COMPRESION NATIVA PYTHON (TITAN ENGINE):
   - Motor de compresion y descompresion 100% nativo en Python para formatos GBA:
     * BIOS LZ77 (0x10) con decodificacion y codificacion bit-perfect.
     * Marvelous Arcano LZ (0x70) con escaleras de busqueda de distancias y secuencias literales.
     * RLE (Run-Length Encoding) y conversion de color BGR555 a RGB.
   - Eliminacion total de dependencias de emuladores x86 o binarios externos de 32 bits.
   - Importacion, exportacion e insercion directa de bitmaps (PNG/BMP) de mapas y tilesets en la ROM.
   - Edicion de capas graficas, metatiles, elevaciones, atributos de paso y configuracion de warps.
   - Blitter de estructuras dinamicas y malla de colisiones 100% nativo desde la ROM (0x10692C), sincronizado con el sistema de navegacion A* (TilePathfinder).

3. VISOR Y BASE DE DATOS MAESTRA DE ITEMS:
   - Modo de edicion masiva (Bulk Edit Mode) para herramientas de trabajo, alimentos/consumibles y articulos generales.
   - Sincronizacion directa con las tablas GToolInfo y GFoodInfo de la ROM.
   - Modificacion de nombres, descripciones, precios de compra/venta y banderas de inventario.

4. BASE DE DATOS DE NPCS Y VISOR ACTUALIZADO:
   - Acceso directo integrado en la barra de herramientas principal.
   - Visualizacion tabular de los 42 aldeanos con banderas de estado, identificadores de candidatas a matrimonio y punteros de rutinas.
   - Dialogo de inspeccion profunda con conexion directa al script de evento vinculado y horario de rutina.
   - Enlace directo bidireccional hacia el editor de metasprites y retratos.

5. EDITOR DE RETRATOS Y METASPRITES (MELODY & SYMPHONY ENGINE):
   - Correccion de bugs de decodificacion en RAM y renderizado de paletas GBA de 16 colores.
   - Seleccion automatica por hex_id al transferir desde el detalle del aldeano.
   - Lienzo pixel art interactivo con herramientas de pincel, borrador, gotero, cubeta de relleno e historial (deshacer/rehacer).
   - Inyeccion, exportacion e importacion de retratos con empaquetado bit-perfect en la ROM.

6. MOTOR DE SCRIPTS DE EVENTOS (SLIPSPACE SCRIPT ENGINE v4):
   - Soporte para los 1.328 eventos de la ROM mediante lenguaje estructurado de alto nivel (C-like).
   - Optimizacion de secuencias de escape: consolidacion de retornos de carro (\r\n), pausas (\w) y saltos de linea (\b).
   - Poda de saltos redundantes y eliminacion de etiquetas huerfanas LBL en bucles do-while y bifurcaciones condicionales.
   - Puente de compilacion nativa agbcc 2.9.x (GNU C 2.9 thumb-elf) y GNU Binutils para compilar e inyectar codigo maquina THUMB en la tabla de dispatch (0x03F900).
   - Resolucion optimizada de bifurcaciones de control (goto / lbl) para retornos de funciones padre sin colapso de bytecode.
   - Entorno de desarrollo integrado (IDE) con resaltado de sintaxis dinamico, autocompletado y validacion sintactica.

7. ARQUITECTURA DE RENDIMIENTO Y CARGA ULTRA-RAPIDA:
   - Escaneo grafico inicial reducido de 10.783 ms a 28,5 ms mediante cache persistente en disco indexado por firma SHA-256.
   - Poblacion del arbol de exploracion por lotes (appendRows) con supresion de repintado intermedio.
   - Filtrado de busqueda con debounce de 150 ms para escritura fluida sin congelamiento de interfaz.
   - Tiempo de inicializacion de sesion de ROM reducido de mas de 13 segundos a 1,7 segundos.

8. SISTEMA DE INTERNACIONALIZACION (i18n) DESACOPLADO EN JSON PURO:
   - Base de traducciones modular en Consola_de_Comando/i18n.json (308 claves simetricas por idioma).
   - Soporte para 8 idiomas: Espanol (es), Ingles (en), Japones (jp), Ruso (ru), Aleman (de), Chino Simplificado (zh), Hindi (hi) y Portugues (pt).
   - Terminologia tecnica formal, utilitarismo funcional y politica estricta de cero emojis en codigo e interfaz.

------------------------------------------------------------
ARQUITECTURA DEL CODIGO FUENTE (PASO A PASO)
------------------------------------------------------------

El proyecto se estructura en capas funcionales independientes para garantizar mantenibilidad y aislamiento de responsabilidades:

1. Consola_de_Comando/
   - app.py: Ventana principal, barra de menus (Archivo, Configuracion, Ayuda), barra de herramientas, gestor de pestanas dinamicas, explorador de arbol y despachador de eventos de fondo.
   - i18n.py / i18n.json: Motor de traduccion internacional y base de cadenas en JSON puro.
   - terminal_ia.py: Consola de comandos y nexo interactivo.
   - themes.py: Definicion de temas visuales (Light, Dark, Matrix, Forerunner).

2. Nucleos_Positronicos/
   - Nucleo_de_Aldeanos/:
     * npc_editor.py: Visor tabular de NPCs, dialogo de detalles de aldeano y vinculacion de activos.
     * npcs.py / npcs_v2.py: Parsers de tablas de memoria de NPCs y resolucion de estructuras.
   - Nucleo_de_Rutinas_AI/:
     * editor_rutinas_npc.py: Editor de horarios diarios, cronograma de NPCs e inspector flotante.
     * route_map_canvas.py: Lienzo de visualizacion de mapas de ruta, proyeccion de coordenadas y waypoints.
     * macro_map_view.py: Vista macromapa interactiva de Mineral Town con conexiones de nodos.
     * world_graph.py / world_graph.json: Topologia y grafo de conectividad espacial de mapas.
     * fomt_map_names.py: Diccionario canonico de identificadores de mapas, headers y nombres tecnicos.
   - Nucleo_de_Mapas/:
     * titan_map_editor.py: Editor de mapas, capas graficas, atributos y warps.
     * codec_tiles.py: Conversores de color BGR555 a RGB y decodificacion de bloques de tiles.
     * map_parser.py: Parser de tablas de cabeceras de mapas y asignacion de punteros en la ROM.
   - Nucleo_de_Scripts/:
     * script_ide.py: Editor de codigo fuente para eventos.
     * teatro_eventos.py: Visor de flujo visual y analisis de bloques de eventos.
     * SlipSpace_Script_Engine/: Compilador, descompilador, emisor de bytecode y decoradores semanticos.
   - Nucleo_de_Sprites/:
     * visor_metasprites.py: Editor de metasprites y retratos con lienzo pixel art.
     * visor_sprites.py: Visor de hojas de sprites y animaciones.
     * dump_sprites.py / dump_metasprites.py: Extractores de activos graficos.
   - Nucleo_de_Portraits/:
     * Melody_Portrait_Engine/: Motor especializado en decodificacion, volcado y reempaquetado de retratos.
   - Nucleo_de_Items/:
     * item_bulk_editor.py: Editor de registros masivos para herramientas, comidas y objetos.
     * item_parser.py: Parser de tablas GToolInfo y GFoodInfo.
   - Nucleo_de_Sonido/:
     * sappy_viewer.py: Visualizador de pistas y cabeceras de sonido Sappy.
     * midi_compiler.py: Compilador de archivos MIDI a formato de sonido GBA.

3. Banco_de_Datos/
   - super_lib.py: Base de conocimiento centralizada de la ROM, deteccion dinamica de tablas, scan de firmas LZ77 y gestion de cache persistente.
   - proyecto.py: Controlador del ciclo de vida del proyecto (sesion, carga, compilacion, guardado).
   - Cilixes/: Tablas de mapeo CSV de eventos, nombres, mapas, punteros y offsets especificos para FoMT y MFoMT.
   - Parches/: Inyectores de parches para caracteres extendidos (N), correccion de z-sorting y utilidades del sistema.
   - INTegerGuard.dll / INTegerGuard.c: Componente nativo de validacion de integridad y proteccion de autor.

------------------------------------------------------------
REQUISITOS DEL SISTEMA Y EJECUCION
------------------------------------------------------------

Requisitos minimos:
- Sistema Operativo: Windows 10/11 (64-bit), Ubuntu Linux 20.04+, o macOS 12+
- Python: Version 3.10 o superior
- Dependencias de Python: PyQt6, Pillow

Instalacion de dependencias:
```bash
pip install PyQt6 Pillow
```

Ejecucion en entorno de desarrollo:
```bash
python main.py
```

Compilacion de ejecutable autonomo (PyInstaller):
```bash
pyinstaller FoMT_Studio_v4.0.0_FinalRelease.spec
```

------------------------------------------------------------
CREDITOS Y AGRADECIMIENTOS
------------------------------------------------------------

El desarrollo de esta suite ha sido posible gracias al esfuerzo conjunto de la comunidad de ingenieria inversa:
* u/MelodyCrystel (Reddit): Por la documentacion de offsets criticos y paletas maestras de sprites.
* StanHash: Por sus repositorios y herramientas de analisis Mary y FoMT.
* Andrey Moura (HM-Studio): Por sus aportes sobre la estructura interna de Friends of Mineral Town.

------------------------------------------------------------
LICENCIA Y AUTORIA
------------------------------------------------------------

Este software se distribuye bajo la licencia GNU General Public License v3 (GPLv3).

Desarrollado por: Denisovich728
Todos los derechos reservados (c) 2026.
============================================================

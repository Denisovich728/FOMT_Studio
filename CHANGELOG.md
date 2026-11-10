# FOMT Studio - Registro de Cambios (Changelog)

## Version 4.0.2 "The Greatest Show" - Script Engine & Intellisense Release
**Fecha:** 2026-11-10
**Estado:** Correccion de Descompilacion de Scripts de Aldeanos, Autocompletado Contextual y Localizacion Multilingüe Integral

### Editor Interactivo de Condiciones y Mapa de Horarios NPC (`editor_rutinas_npc.py`)
- **Panel Desplegable de Edición de Condiciones de Rutinas:** Incorporación de panel interactivo conmutable (`btn_toggle_cond_edit`) dentro de la tarjeta de activación `cond_group`. Permite modificar los parámetros de activación de cada horario (`NPCSchedule`):
  - **Clima:** Selector desplegable con soporte para "Soleado", "Lluvia", "Tormenta / Ventisca", "Soleado / Nublado", "Cualquiera" y "Condicional / Evento".
  - **Temporada:** Configuración del código estacional GBA (`0x10` Todo el Año / Interior, `0x00` Primavera, `0x04` Verano, `0x08` Otoño, `0x0C` Invierno).
  - **Días:** Combo editable con presets de días ordinarios ("Lunes a Sábado", "Domingos", "Martes", "Cualquiera", "Días de festival", "Días de mal tiempo", etc.).
  - **Hora Inicio:** Selector numérico de minutos con conversión en tiempo real a formato digital legible `HH:MM` y sincronización con el hito inicial.
  - **Zona / Ubicación:** Combo editable con zonas canónicas del valle ("Granja del Jugador", "Pueblo Sur", "Pueblo Norte", "Plaza Rosa", "Playa Mineral", "Colina Madre", "Interior", "Zona de Festival", "Mineral Town").
  - **Mapa de Rutinas:** Selector sincronizado con los 66 mapas canónicos de `CANONICAL_MAP_INFO`.
- **Acción 'Aplicar Mapa a Todo el Horario' (`btn_apply_map_to_sched`):** Con un solo clic empaqueta el nuevo `packed_map_id` (`(season_code << 8) | (base_map_id & 0xFF)`), actualiza todos los waypoints del horario actual, los marca como editados (`is_edited = True`) para recompilación atómica a la ROM, recarga el visor de mapas y refresca los tramos en la tabla orquestadora.
- **Acción 'Guardar Condiciones' (`btn_save_cond`):** Persiste los parámetros en `schedule.condition_info`, actualiza las etiquetas del selector de horarios (`combo_schedule`), refresca la tarjeta de condiciones (`_update_condition_banner`) y notifica en la barra de estado.
- **Soporte Dinámico `retranslate_ui(lang)` en Editor de Rutinas:** Implementación del protocolo de re-traducción en `EditorRutinasNPCWidget`. Actualiza dinámicamente títulos de grupos, selectores de modo, encabezados de columnas de la tabla de tramos, controles de edición de condiciones y nombres de mapas según el idioma seleccionado.

### Retraducción Dinámica de Menús, Toolbar y Menús Contextuales (`app.py`)
- **Factorización y Reconstrucción Dinámica de la Toolbar (`_setup_toolbar`):** Se separó la construcción de la barra de herramientas principal (`self.toolbar`) en el método dedicado `_setup_toolbar(self)`. Al alternar idiomas en tiempo de ejecución (`apply_language`), se limpian y reconstruyen con las nuevas traducciones todos los botones de la barra de herramientas (`tb_explorer`, `tb_save_rom`, `tb_compile_rom`, `tb_event_editor`, `tb_npc_db`, `tb_more_tools`) y los más de 20 submenús y acciones hijas agrupadas en `btn_more` (`cat_editors_ui`, `cat_graphics_audio`, `cat_data_maps`, `cat_internal_db`, `menu_bulk_items`, `menu_patches`).
- **Localización de Menús Contextuales y Marcadores de Posición:**
  - `_on_tab_context_menu`: "Hacer Flotante" y "Cerrar" ahora utilizan las claves localizadas `tr("menu_float_tab", lang)` y `tr("menu_close_tab", lang)`.
  - `_on_tree_context_menu`: "Abrir en Editor de Scripts (IDE)" utiliza `tr("menu_open_ide", lang)`.
  - Cuadro de búsqueda: El placeholder del explorador lateral se actualiza dinámicamente con `tr("search_placeholder", lang)`.
  - Pestañas y Ventanas Flotantes: Bucle de actualización reactivo que invoca `retranslate_ui(lang)` en todos los widgets abiertos y actualiza sus títulos de pestaña.

### Corrección de Excepciones en Editor de Rutinas y Lienzo de Mapas
- **Resolución de `UnboundLocalError: 'lang'` en `editor_rutinas_npc.py`:** Se corrigió el orden de asignación en `_build_floating_inspector_ui`, asegurando que `lang = self.lang` se declare al inicio del método antes de inicializar los combos y etiquetas de mapas.
- **Resolución de `AttributeError: 'RouteVectorOverlayItem' has no attribute 'canvas'` en `route_map_canvas.py`:** Se corrigió la llamada en `paint()` para invocar `self.canvas_view.get_lang()` y se añadió el alias retrocompatible `self.canvas = canvas_view` en `RouteVectorOverlayItem.__init__`.

### Internacionalizacion Integral de Submodulos de Rutinas e Interfaz (i18n & Zero Emojis)
- **Localizacion Completa de Todos los Submodulos del Editor de Rutinas:**
  - `editor_rutinas_npc.py`: Reemplazo de cadenas estaticas en espanol por claves `tr(key, lang)`. Traduccion de selectores de modo (Por Aldeano / Por Mapa), tarjetas de condicion climatica (`rt_weather`, `rt_days`, `rt_main_zone`), inspectores de hitos, barras de herramientas de rutas, botones de accion ("Añadir Hito", "Eliminar", "Editar Hito en Mapa", "Ajustar", "Malla Caminable", "Inspector Flotante"), tablas de tramos y mensajes modales de confirmacion e inyeccion en ROM.
  - `route_map_canvas.py`: Localizacion dinamica de tooltips de nodos interactivos (`[Punto A (Inicio)]`, `[Punto B (Destino)]`, `[Punto A/B (Bucle Continuo)]`, `[Punto de Inflexión #X]`, `Trayectoria`), menus contextuales de clic derecho ("Centrar Inflexión #X en Calle/Tile", "Eliminar Punto de Inflexión #X") y badges de bucle en lienzo con fallback automatico de idioma.
  - `native_proc_viewer.py`: Traduccion integral de cabeceras, etiquetas de estado, grupos ("Valores Detectados", "Pseudo-Script"), columnas de tabla ("Tipo", "Valor", "Descripcion", "Offset"), boton de accion ("Modificar y Parchear en ROM" sin emojis) y dialogos modales de parcheo de bytes e instrucciones Thumb.
  - `npc_schedule_conditions.py`: Incorporacion de resolucion multilingüe en `ScheduleCondition` (`get_localized_weather`, `get_localized_days`, `get_localized_badge`) para traducir condiciones climaticas ("Soleado", "Lluvia", "Tormenta / Ventisca"), dias de la semana ("Lunes a Sábado", "Domingos", "Días de Festival") y zonas del mapa ("Player's Farm", "Festival Area", "Indoors") a ingles y demas idiomas soportados.
- **Politica de Cero Emojis en Toda la Suite:** Eliminacion estricta y verificada de emojis en literales de cadenas, botones, tooltips y menus contextuales.

### Sistema Multilingüe de Nombres de Mapas y Eventos (CSVs & SuperLibrary)
- **Nombres de Mapas Multilingües:** Actualizacion de `fomt_map_names.py` y `super_lib.py`. La funcion `get_map_display_name(map_id, include_season=False, lang="es")` y el metodo `get_map_name_hint(map_id, lang="es")` ahora resuelven nombres canonicos exactos segun el idioma activo (`es`, `en`, `jp`, `de`, `ru`, `zh`, `pt`, `hi`). Se incluye traduccion de sufijos estacionales (Primavera/Spring, Verano/Summer, etc.), pisos de mina ("Mine (Floor X)") y estados de despawn ("Off-Map (Despawn / Limbo)").
- **Alias de Mapas en Autocompletado y Compilador:** Carga automatica de nombres traducidos en `super_lib.map_map`. Permite autocompletar y resolver tanto identificadores en ingles (`"Farm"`, `"Church"`) como nombres localizados (`"Granja del Jugador"`, `"Player's Farm"`), unificando el autocompletado en bloques `case` y la resolucion en tiempo de compilacion.
- **Nombres de Eventos Multilingües:** Implementacion de `get_translated_event_name` en `super_lib.py`. Traduce los 72 eventos canonicos (`Popuri_Personality` -> `Personalidad de Popuri` / `Popuri Personality`, `Morning_Engine` -> `Motor Matutino (Despertar)` / `Morning Engine (Wakeup)`, `Sleep_SUper_Engine` -> `Motor Nocturno (Dormir)` / `Sleep Engine (Bedtime)`, `Golden_Lumber_Retribition` -> `Retribución de Madera Dorada` / `Golden Lumber Retribution`) y eventos no identificados a todos los idiomas de la aplicacion. Sincronizacion directa con el arbol de proyecto y pestanas del IDE en `app.py`.
- **Diccionario de Documentacion de Opcodes Multilingüe (`opcode_docs.py`):** Creacion del modulo `Banco_de_Datos/opcode_docs.py` con explicaciones tecnicas, argumentos y tooltips localizados para las funciones VM del motor FoMT (`SetEntityPosition`, `GetEntityLocation`, `SetEntityFacing`, `Execute_Movement`, `Show_Emote`, `Fade_Out`, `Fade_In`, `TalkOpen`, `TalkMessage`, `Give_Item`, `Check_Flag`, `Set_Flag`, etc.). Integracion reactiva con el autocompletado de `script_ide.py`.
- **72 Nuevas Claves de Traduccion en `i18n.json`:** Cobertura completa de claves para editores de rutinas, lienzo y visores en 8 idiomas.

### Descompilacion Robusta de Scripts de Personalidad (NPC Personality Profile)
- **Carga Automatizada de Nombres de Eventos Canonicos:** Modificacion de `_load_custom_names` en `super_lib.py` para invocar de forma transparente `load_event_names_from_csv("Fomt_Events_Listname.csv")` en la inicializacion. Todos los 1328 eventos de la ROM ahora disponen de su nombre canonico (`0993 - Popuri_Personality`, `0994 - Lilia_Personaliti`, etc.) sin requerir importacion manual.
- **Resolucion Multi-Entorno y Fallback de Scripts en Perfil de Aldeanos:** Actualizacion de `_resolve_script_personality` y `abrir_script` en `npc_editor.py`. Resuelve de forma robusta la ruta absoluta de `Fomt_Events_Listname.csv` mediante `get_data_path` y consulta el diccionario `custom_event_names` de `super_lib`, enlazando de forma directa a 38 de 42 NPCs con su script canonico en el `ScriptIDEWidget`.
- **Normalizacion Defensiva de Punteros ROM GBA (0x08XXXXXX -> Offset Fisico):** Implementacion de mascara de bits `offset &= 0x01FFFFFF` en `read_rom` (`proyecto.py`), `decompile_from_offset` (`eventos.py`), `load_rom_script` (`script_ide.py`) y `open_script_offset` (`app.py`). Elimina de raiz el bug donde la apertura de scripts por offset arbitrario leia fuera de los limites de la memoria virtual generando buffers vacios (`script ROM Test { }`).
- **Prevencion de Crasheos en Gestion de Pestanas Qt:** Saneamiento exhaustivo en `_close_tab` (`app.py`), `CodeEditor.closeEvent` y `ScriptIDEWidget.closeEvent`. Se detienen ordenadamente los temporizadores en segundo plano `parse_timer` y se limpian las referencias de widgets cerrados en `MainWindow`, erradicando crasheos por llamadas tardias sobre objetos C++ destruidos (`RuntimeError: wrapped C/C++ object has been deleted`).

### Autocompletado Inteligente Sensible al Contexto (Smart Switch-Case & Maps)
- **Deteccion Automatica de Expresiones Envolventes en Switch:** Incorporacion de `get_enclosing_switch_expr()` en `CodeEditor` (`script_ide.py`), que rastrea hacia atras las llaves abiertas para identificar la llamada evaluada en `switch (...)`.
- **Filtrado Contextual de Mapas en Bloques `case`:** Al escribir `case ` dentro de un switch que evalua `GetEntityLocation(...)` o `Get_Entity_Location(...)`, el motor Intellisense activa automaticamente el filtro de mapas (`filter_type = "map"`), desplegando al instante los 306 nombres canonicos de mapas del valle en el popup de autocompletado y envolviendo la seleccion con comillas dobles (`case "Farm":`, `case "Church":`).
- **Soporte Extendido de Constantes:** Registro en el modelo de autocompletado para Temporadas (`Spring`, `Summer`, `Autumn`, `Winter`), Climas (`Sunny`, `Rainy`, `Snowy`, `Typhoon`, `Blizzard`) y Orientaciones (`Up`, `Down`, `Left`, `Right`).
- **Disparo Inmediato al Escribir `case `:** Apertura reactiva del popup de sugerencias al introducir la palabra clave `case ` con espacio o comilla sin requerir pulsacion manual de teclas de ayuda.

### Internacionalizacion Exhaustiva y Eliminacion de Emojis (i18n & Clean UI)
- **Auditoria y Traduccion al Ingles:** Incorporacion de 39 nuevas claves de traduccion en `i18n.json` y conexion via `tr(key, lang)` en `npc_editor.py` y `editor_rutinas_npc.py`.
- **Localizacion de Controles de Rutinas e Inspector:** Traduccion completa de cabeceras de tabla, horarios, tarjetas de activacion, inspector flotante ("Time, Wait & Facing", "Center on Tiles", "Stand Still", "Recalculate A*", "Loop Mode") y dialogos informativos.
- **Politica Estricta de Cero Emojis:** Remocion total de emojis en interfaces, botones y textos (`btn_ai`, `btn_search`, `btn_clear`, inspectores de tiempo y eventos).

## Version 4.0.1 "The Greatest Show"-Update Release
**Fecha:** 2026-11-08
**Estado:** Actualizacion de Estabilidad y Herramientas de Mapeo

### Redimensionado Dinamico de Mapas y Paneles Flexibles (Titan Engine)
- **Accion Rapida 'Quedarse Quieto' (Standing Still) en Editor de Rutinas NPC:** Incorporacion de boton dedicado `btn_stand_still` ("Quedarse Quieto") en el Inspector Flotante de `editor_rutinas_npc.py`. Permite con 1 solo clic colapsar el tramo a un unico nodo estatico (`Destino B == Origen A`, `dist = 0`), garantizando que el compilador emita `num_points = 0` y `pts_ptr = 0` en la estructura `PathInfo` de la ROM. El NPC permanece estacionario mirando en la direccion seleccionada sin requerir configuracion manual de bucles.
- **Generacion Robusta de Parches IPS (Diff Binario de Respaldo):** Actualizacion de `export_ips` en `proyecto.py` para calcular automaticamente bloques diferenciales contiguos entre la ROM virgen limpia y la ROM virtual/activa cuando el diccionario de parches en memoria este vacio. Erradica la generacion de archivos IPS vacios de 8 bytes (`PATCHEOF`) y asegura parches funcionales listos para emulador.
- **Manual Tecnico Exhaustivo de IA y Rutinas (NPC_ROUTINES_AND_AI_GUIDE.md):** Creacion de guia tecnica integral en ingles documentando la jerarquia binaria de la tabla maestra `0x3D9A4`, la relacion entre `evaluator_func` y los horarios climaticos, direccionamiento de vista y delays en ticks, transicion inter-mapas, diagnostico y solucion del bug de dialogos en mapas no contemplados (`switch (GetEntityLocation)` sin caso `default`), y la anomalia de guardado en salas cerradas.
- **Cambio Instantaneo de Capas y Caching en RAM de Estructuras Dinamicas:** Optimizacion critica en `fomt_mapdata.py` y `visor_mapas.py`. Los buffers de trabajo (`active_tilemap_bg3`, `active_tilemap_bg2`, `active_tilemap_bg1`, `active_collision_map` y `active_behavior_dict`) se calculan y estampan una sola vez al cargar el mapa y se preservan en memoria RAM, eliminando las clonaciones de listas y los bucles de estampado redundantes en cada cambio de pestana. La destruccion e invalidacion del cache se ejecuta de forma controlada unicamente al seleccionar otro mapa, reiniciar posiciones o compilar a la ROM. En `_on_edit_mode_changed` se reemplazo `_re_render()` por `_re_render_map_only()`, evitando el redibujado innecesario de los 1024 tiles del tileset. La latencia al alternar entre Capas 1 (BG3), 2 (BG2), 3 (BG1) y General se redujo de ~3000 ms a <30 ms en mapas gigantes (128x88).
- **Sombra de Colisiones Conmutable en Todas las Capas:** Agregado de control `QCheckBox("Sombra de Colisiones")` en la barra superior de herramientas (`tools_row1`) de `visor_mapas.py`. Permite proyectar una mascara de colisiones y triggers translucida (alpha 80-120) sobre cualquiera de las capas graficas individuales (BG3 fondo, BG2 medio, BG1 frente) o la composicion general, facilitando la alineacion visual de solidos, zonas cultivables y scripts sin abandonar el modo de edicion de tiles.
- **Edicion Ultrarrapida en Cache/RAM y Compilacion Diferida en ROM:** Eliminacion de la re-renderizacion completa del mapa (de hasta 11.264 tiles) y de las escrituras directas a la ROM en cada iteracion de pintado o arrastre de estructuras. Implementacion de `render_cell` en `fomt_mapdata.py` (0.01 ms por celda) y parcheo incremental sobre `_cached_qimage` a 60 FPS sin saturacion de GUI en `visor_mapas.py`. Las modificaciones de capas, colisiones y estructuras dinamicas se capturan y preservan en memoria RAM sin degradacion de rendimiento hasta que el usuario ejecuta **Compilar y Guardar (ROM)**, momento en el cual se compilan, inyectan y sincronizan en la ROM de forma atomica.
- **Exportacion Canonica en Lote de 4 Capas BMP y Previsualizacion PNG:** Actualizacion de `_export_map_image` y `_render_collision_grid_image` en `visor_mapas.py` para exportar de forma limpia y atomica las 4 capas individuales del mapa en formato BMP (`_bg3.bmp` Suelo/Fondo base, `_bg2.bmp` Medio/Objetos/Muebles, `_bg1.bmp` Frente/Overlay/Techos y `_col.bmp` Malla de Colisiones y Triggers) junto con su vista previa compuesta (`_preview.png`). Soporte alternativo para exportacion de imagen compuesta unica en PNG o BMP.
- **Importacion Inteligente de Capas Individuales o por Lote:** Deteccion automatica de capas hermanas (`_bg3`, `_bg2`, `_bg1`, `_col`) al importar cualquier imagen en `_import_map_image`. Opcion de importacion en lote con parseo directo de colisiones coloreadas sobre `collision_map` y reconstruccion de capas graficas sobre los tilemaps respectivos con refresco visual instantaneo.
- **Redimensionador Dinamico de Mapas (Expansion Superior-Izquierda sin Quiebre de Coordenadas):** Implementacion de `resize_map` en `mapas.py` y `visor_mapas.py` con repunteo en espacio seguro de la ROM para los 3 tilemaps (`p_bg3`, `p_bg2`, `p_bg1`), mapa de colisiones (`p_obj2`) y dimensiones en la tabla maestra. Opcion de expansion hacia arriba y a la izquierda (`expand_top_left=True`) que preserva el sistema de coordenadas base de puertas y paredes. Desplazamiento sincronizado automatico de todas las estructuras dinamicas por `(dx, dy)` con persistencia inmediata en la ROM.
- **Sincronizacion Integral de Buffer ROM en Tiempo Real:** Reemplazo de escrituras parciales por sincronizacion completa de `renderer.rom` con `base_rom_data` extendido, eliminando el fallo en el que el editor no detectaba el nuevo puntero y permitiendo la expansion y visualizacion inmediata en la misma sesion sin recargar.
- **Correccion de Crasheo de Colisiones (Byte Range Overflow):** Aplicacion de mascara `found_idx & 0xFF` y validacion de limites 2D (`0 <= x < width`, `0 <= y < height`) en `_stamp_rom_structure` dentro de `fomt_mapdata.py`, eliminando el crasheo `ValueError: byte must be in range(0, 256)`.
- **Ajuste Pixel-Perfect del Bounding Box de la Caja de Herramientas:** Delimitacion exacta a 3x4 tiles visuales (`vis_ox: 0`, `vis_oy: 2`) eliminando la seleccion sobre espacio vacio. Sincronizacion de las rutinas ensamblador GBA de apertura (`0x080A6138`) y cierre (`0x080A6194`) en ROM para los mapas 41, 42 y 43, erradicando el glitch visual donde la tapa abierta se dibujaba en la coordenada original.
- **Paneles Redimensionables y Colapsables en Toda la Suite:** Sustitucion de layouts rigidos por `QSplitter` horizontal entre el visor de mapa y visor de tileset (`viewers_splitter`), ajuste de `left_panel` en `visor_mapas.py` y el explorador en `app.py` con `setMinimumWidth(0)` y `setChildrenCollapsible(True)`, permitiendo al usuario achicar, ajustar o colapsar libremente cualquier panel. Resaltado interactivo `:hover` y `:pressed` en los tiradores `QSplitter::handle` en los temas Forerunner, Hacker, Dark y Dracula.
- **Nombrado Automatizado de Eventos con Llama 3B y Guias Fogu:** Generador en segundo plano con deteccion de 42 NPCs del valle, clasificacion de eventos de corazon (`<Candidata>_Heart_<Color>`) y rivales con aislamiento en carpeta de pruebas (`Test_Event_Names/Fomt_Events_Listname_named.csv`).

## Version 4.0.0 "The Greatest Show"-Final Release
**Fecha:** 2026-11-07
**Estado:** Lanzamiento Final Oficial / Suite Integral de ROM Hacking

### Estructuras Dinamicas y Utensilios de Cocina (Titan Engine Final)
- **Aislamiento Total de Sesiones y Workspaces (Inmunidad Windows Defender):** Redireccion de las rutas por defecto de sesiones de trabajo automáticas y proyectos (`get_sessions_dir()`, `get_default_workspace_dir()`) a subdirectorios locales dentro de la carpeta raíz de la aplicación (`<app_root>/Sessions` y `<app_root>/Workspace`), erradicando bloqueos de *Acceso controlado a carpetas* (Controlled Folder Access / WinError 2) provocados por Windows Defender en `Documents`.
- **Persistencia Binaria de Coordenadas en ROM:** Inyeccion directa y parcheo de coordenadas (X, Y) en las rutinas de desensamblado del motor GBA (`0x08017180` y `0x080A5BD8`) para Granja (Casa Lv1/Lv2/Lv3, Granero Lv1/Lv2, Gallinero Lv1/Lv2, Buzon), Establo (Maquinas de Queso y Lana), Gallinero (Maquina de Mayonesa) y Casa (Mueble de Cocina), evitando que las estructuras se quemen de forma destructiva sobre los tilemaps base en la ROM.
- **Sincronizacion de Capas Base Limpias:** Separacion estricta entre capas editables (`tilemap_bg*`) y capas de renderizado activo (`active_tilemap_bg*`), garantizando que guardar el mapa en ROM no corrompa el terreno base ni duplique edificios fantasma al entrar al mapa en la GBA.
- **Panel de Ajustes No Modal y Reactivo en Tiempo Real:** Conversion del dialogo de Estructuras Dinamicas y del selector de Utensilios a ventanas no modales (`NonModal`), permitiendo interactuar con el visor del mapa (zoom, paneo, edicion de capas) mientras los cambios en botones, checkboxes y selectores se reflejan instantaneamente en el lienzo sin bloquear la UI ni requerir confirmacion manual.
- **Prioridad de Dibujado de Cuadro Selector:** Prioridad visual absoluta en el renderizado para los recuadros de seleccion, resaltado interactivo y etiquetas de coordenadas de estructuras dinamicas sobre todas las capas graficas.
- **Disposicion Canonica de Utensilios de Cocina:** Alineacion pixel-perfect de los 8 utensilios de cocina con el hardware original GBA (`0x080A5BD8` / `0x08017180`): horno microondas (`327`), rodillo (`313`), batidora (`64`) y especiero (`400`) sobre la tabla de preparacion izquierda; sarten (`204`) y olla (`346`) sobre los quemadores centrales; cuchillo (`265`) y batidor globo (`472`) sobre la encimera alicatada derecha bajo el fregadero.
- **Fondo Opaco de Camara de Combustion en Chimenea (Mapa 43):** Correccion del descriptor `0x106B6C` (`fireplace`) para rellenar la camara de ladrillo/ceniza en BG3 (`0x4177..0x417A`), erradicando la transparencia defectuosa hacia el papel tapiz y piso de madera posterior.
- **Restauracion de Paleta del Tocadiscos:** Correccion y fijacion de la paleta canonica 10 (`PAL_10`) para el mueble del tocadiscos en la sala de la casa.

### Editor de Rutinas Diarias y Orquestador de Movimiento (NPC AI Engine)
- **Topologia y Grafo Mundial:** Implementacion del macromapa interactivo del valle con navegacion espacial bidireccional sobre 41 nodos de mapas y 39 conexiones canonicas.
- **Mapeo Canonico de 42 NPCs:** Correccion de desfaces en mapas canonicos (Mina Lago 0x2B, Entrada Mina 0x33, Piso 1 0x34, mapas de tutorial y pisos procedurales).
- **Normalizacion de Flags de Limbo:** Resolucion de discrepancia de mascaras de bits (0x3FF vs 0xFF) que impedia la visualizacion y edicion de waypoints inactivos o de despawn con flag 0x200 (0x234).
- **Centrado Dinamico de Camara:** Navegacion y enfoque automatico al seleccionar waypoints o nodos del macromapa.

### Editor de Mapas y Tilesets (Titan Engine)
- **Compresion 100% Python Nativa:** Descompresion y compresion binaria sin dependencias externas de ejecutables legados de 32 bits para formatos BIOS LZ77 (0x10), Marvelous Arcano LZ (0x70) y RLE.
- **Estructuras Dinamicas y Malla de Colision Binaria:** Ingenieria inversa 100% fiel al motor decompilado original de Harvest Moon FoMT (rutinas `ApplyMapPatch_Blitter_080A5BD8` y `func_08017180`). Blitting autentico directo desde la ROM para las capas BG1, BG2 y BG3 (cero PNGs y cero figuras simuladas), estampando la tabla LUT de 32 bits de colisiones y disparadores de puertas (`0x0154`, `0x0156`, `0x014E`) sobre las mejoras de la Casa de Campo (Lv1, Lv2, Lv3), Establo, Gallinero, Buzon y Villas del Valle, con sincronizacion automatica hacia el algoritmo de navegacion A* (`TilePathfinder`).
- **Insercion e Importacion de Bitmaps:** Pipeline completo de importacion, exportacion y reinyeccion de mapas completos y tilesets graficos en formato PNG/BMP indexado a 16 colores.
- **Edicion de Metatiles y Warps:** Soporte para edicion de atributos de colision, elevacion y conexiones de teletransporte entre mapas.

### Base de Datos Maestra de Items y NPCs
- **Edicion Masiva de Items (Bulk Edit Mode):** Edicion rapida de nombres, descripciones y valores de compra/venta para herramientas, comidas y articulos generales.
- **Base de Datos de NPCs en Toolbar:** Acceso directo en la barra de herramientas principal con sincronizacion hacia el editor de metasprites y retratos.

### Editor de Retratos y Metasprites (Melody & Symphony)
- **Seleccion Automatica por Hex ID:** Redireccion directa desde el detalle del aldeano hacia el editor de metasprites seleccionando instantaneamente el portrait correspondiente en el lienzo.
- **Correccion de Bugs Graficos:** Reconstruccion de la decodificacion dinamica en RAM y resolucion de paletas maestras de 16 colores.
- **Lienzo de Pixel Art:** Suite de herramientas de dibujo (pincel, borrador, gotero, cubeta de relleno, selector de paleta, deshacer/rehacer).

### Motor de Scripts SlipSpace v4
- **Optimizacion de Bytecode:** Consolidacion de saltos de linea (\r\n), pausas (\w para WAIT_CLICK) y saltos (\b para BREAK).
- **Poda Exhaustiva de Saltos Fantasma y Etiquetas LBL:** Reestructuracion del pase de limpieza `ASTOptimizer._cleanup` en `ins_decompiler.py` para incluir ramas `StmtDoWhile` en la recoleccion y filtrado de etiquetas activas (`used_labels`), erradicando etiquetas huerfanas `LBL_` y saltos muertos en scripts complejos (como el script 1051, 1014, 1008, 0316) reduciendolos a 0 gotos y 0 labels en codigo C estructurado limpio.
- **Emparejamiento Estricto de Bifurcaciones Condicionales:** Correccion en `_collect_body_stmts` para emparejar expresiones booleanas con saltos `TokenBne` y `TokenBeq` directamente, eliminando la emision de expresiones huerfanas como sentencias aisladas.
- **Puente Nativo de Compilacion agbcc 2.9.x:** Integracion de `agbcc_bridge.py` enlazando el compilador oficial de GBA `agbcc.exe` (GNU C 2.9-arm-000512 thumb-elf) y GNU Binutils (`arm-none-eabi-as` y `arm-none-eabi-objcopy`) para compilar rutinas de eventos C nativas a codigo maquina THUMB inyectable en ROM y vinculable a la tabla de dispatch (`0x03F900`).
- **Resolucion de Bifurcaciones:** Optimizacion de secuencias goto/lbl actuando como retorno estructurado a funciones padre sin desbordamiento de bytecode.
- **Especificacion Formal:** Documentacion integral de la sintaxis C-like de alto nivel para desarrolladores y modelos LLM.

### Rendimiento y Carga de Proyecto
- **Aceleracion Masiva:** Reduccion del tiempo de escaneo grafico inicial de 10.783 ms a 28,5 ms mediante cache persistente indexado por hash SHA-256.
- **Explorador Fluido:** Insercion por lotes (appendRows) con supresion de repintado y debounce de 150 ms en el filtrado de busqueda.
- **Tiempo de Carga de ROM:** Reducido de mas de 13 segundos a 1,7 segundos.

### Internacionalizacion (i18n) en JSON Puro
- **Desacoplamiento a i18n.json:** Extraccion de cadenas a JSON modular con 308 claves simetricas por idioma en 8 idiomas (es, en, jp, ru, de, zh, hi, pt).
- **Jerga Tecnica Formal:** Eliminacion del 100% de emojis, signos informales y sobrenombres de modulos internos en la interfaz.

---

## Versión 3.7.1 "Listen The World"
**Fecha:** 2026-05-15
**Estado:** Lanzamiento Estable / Ingeniería Inversa Avanzada

### Restauración del Motor de Audio Sappy (v3.7.0)
- **Pipeline de Audio Nativo:** Restauración de las dependencias limpias de `gba-mus-ripper` y `fluidsynth` para renderizado fiel al hardware original (solucionando problemas graves de interferencia).
- **Importador y Exportador MIDI:** Implementación completa del flujo bidireccional. Permite exportar partituras a MIDI estándar junto a sus bancos de sonido (SF2).
- **Compilador Python a Sappy:** Se construyó un compilador nativo en Python (`midi_compiler.py`) que lee archivos MIDI subidos por el usuario, los traduce a bytecodes de Sappy e inyecta la pista en espacio libre repunteando automáticamente en la ROM.
- **Categorización Inteligente:** Organización de la tabla de sonidos, separando dinámicamente "Músicas" (IDs 1-37) de los Efectos de Sonido "SFX" (IDs 101+).

### Decompilador de Patrones Nativos (v3.7.0)
- **Motor de Análisis THUMB:** Implementación de un nuevo visor de rutinas nativas con detección semántica de patrones.
- **Detección de Diálogos y Objetos:**
    - Integración con el charset de FoMT (soporte de `0x05 \BRK` y tildes).
    - Detección automática de ítems, herramientas y consumibles desde la base de datos del proyecto.
    - Resolución de retratos (`Lilia_Happy`, `Rick_Afraid`, etc.) en comparaciones lógicas.
- **Mapeo de Funciones del Engine:** Identificación de llamadas internas como `Register_Shipment`, `Init_Shop_UI`, `Play_SE` y transacciones de dinero.
- **Corrección en `Routine_State_Override`:** Se ajustó la decoración del segundo argumento para usar el formato `Script_ID`, permitiendo una referencia clara a los eventos de diálogo.

### Mejoras en SlipSpace Engine (v3.7.0)
- **Robustez del Desensamblador:** Se corrigió el error `Bad opcode: FF` permitiendo que el motor ignore el padding de la ROM al final de los scripts.
- **Resolución de Compilación:** Corrección crítica en la llamada a `compile_script` que impedía la resolución de nombres decorados (Items/NPCs) a IDs binarios.


### Interfaz y Depuración
- **Nuevo Panel de Debugger:** Se añadió un sistema de control de depuración accesible mediante `Control + Shift + L`.
    - Permite activar/desactivar decorados dinámicamente (Coordenadas, IDs, Flags, etc.) para facilitar la ingeniería inversa.
    - Menú flotante con persistencia de estado entre sesiones.


## Versión 3.7.0 "Sincronización de Datos Cilixes"
**Fecha:** 2026-05-12
**Estado:** Lanzamiento Estable

### Mejoras de Distribución y CSV
- **Sincronización Global de CSV:** Se forzó la actualización de todos los recursos de la suite Cilixes en la compilación, asegurando que los cambios en flags, animaciones y punteros se reflejen correctamente en la versión final.
- **Corrección de Dependencias (EXE):** Optimización del proceso de empaquetado para resolver conflictos de carga de DLLs (`LoadLibrary`) en entornos Windows. Se recomienda una limpieza total de carpetas temporales antes de cada compilación.
- **Estabilidad de Punteros:** Refinamiento en la carga de `Fomt_Lib.csv` y `MFomt_Lib.csv` para evitar colisiones de identificadores durante el autocompletado.


## Versión 3.7.0 "Estabilización y Paridad de Bytecode"
**Fecha:** 2026-05-11
**Estado:** Lanzamiento Estable

### Estabilización del Motor SlipSpace (v3.7.0)
- **Corrección de Inflación de Bytecode:** Se optimizó la codificación de instrucciones `PUSH` para números negativos. Ahora los valores pequeños se emiten como `PUSH8` o `PUSH16` en lugar de forzar siempre `PUSH32`, restaurando la paridad 1:1 en ediciones In-Place.
- **Inyección Inteligente 1:1:** Se eliminó el padding forzado de 4 bytes en el MemoryManager que causaba repunteos innecesarios al final de la ROM cuando el script conservaba su tamaño original.
- **Sincronización de Tabla de Punteros:** Se corrigió un error de desfase (off-by-one) en el cálculo de la Master Table de eventos, asegurando que los repunteos actualicen la ranura de ID correcta.
- **Mejoras de Autocompletado IDE:**
    - Filtrado contextual dinámico para comandos de entidad (`SetEntityPosition`, `Show_Emote`, etc.).
    - Inserción automática de comillas `""` para nombres de personajes.
    - Soporte de autocompletado para secuencias de escape (`\r`, `\n`, `\BRK`, `\WAIT_CLICK`).
- **Robustez del Compilador:** Implementación de fallbacks para identificadores no mapeados (`Char_`, `Map_`, etc.) y corrección del parsing matemático para valores hexadecimales negativos.

## Versión 3.3.2 "Actualización La Imposibilidad"
**Fecha:** 2026-05-11
**Estado:** Lanzamiento Estable / Internacionalización Completa

### La Soberanía de la Ñ (Core v3.3)
- **Extensión de Glifos Nativos:** Implementación de soporte nativo para caracteres del español (**Ñ, á, é, í, ó, ú**) mediante inyección directa en el font 1bpp de la pantalla de nombres.
- **Corrección de Alineación de Font:** Re-ingeniería del espaciado vertical. Se ha desplazado el abecedario completo (A-z) para permitir tildes de 2 píxeles sin colisiones, estandarizando la estética con el patrón diagonal `0x0C/0x10`.
- **Restauración de ID 0x7E (Ó):** Creación del glifo de la 'Ó' mayúscula a partir de una base corregida de la 'Q', manteniendo el valor `0x4F` (O normal) intacto para evitar colisiones de software nativo.
- **Sincronización de IDs:** Alineación de offsets en `0x4F9A50` para evitar el desplazamiento de IDs y la impresión errónea de Kanjis.

### Mejoras en Suite Cilixes
- **Tile Editor Extreme v2.1:**
    - Implementación de panel lateral scrolleable para mejorar la visibilidad en bajas resoluciones.
    - Aumento de escala de edición (Zoom x50) para trabajos de precisión en glifos.
    - Nuevo preset **Keyboard** configurado automáticamente a 1bpp con stride desactivado.
- **Estabilidad de la Suite:**
    - Corrección de `NameError` en el Bulk Item Editor (importación de `QFont`).
    - Optimización del editor hexadecimal para sincronización inmediata con el canvas.
- **Motor de Scripts SlipSpace (v3.3.2):**
    - **Alineación Atómica de 4 Bytes:** Implementación de alineación forzada en el bytecode para instrucciones y argumentos de 16/32 bits, garantizando compatibilidad con el hardware GBA.
    - **Remapeo de Coordenadas:** Mejora estética en la decoración de coordenadas (`pos_x`, `pos_y`) ahora en formato decimal para facilitar la edición visual.
    - **Resolución Inversa:** El compilador ahora resuelve automáticamente los nombres decorados de emotes, animaciones y coordenadas a sus valores binarios originales.



## Versión 3.2.0 "Actualización La Imposibilidad"
**Fecha:** 2026-05-11
**Estado:** Lanzamiento Estable / Expansión de Herramientas de Edición

### Evolución del SlipSpace Engine (v2.0 Core)
- **Abstracción de Control de Flujo:** Refactorización del motor de saltos dinámicos. Las instrucciones de bajo nivel ahora se abstraen en estructuras de control de alto nivel (`GOTO`, `IF`, `SWITCH/CASE` y bucles algorítmicos), optimizando la legibilidad de la lógica de eventos.
- **Mapeo de Identificadores:** Indexación completa de IDs para animaciones de NPCs y disparadores de *emotes*.
- **Desacoplamiento de UI:** El motor ahora expone las cadenas de texto de la interfaz de usuario para su edición externa, facilitando la localización sin tocar el binario del motor.
- **Optimización de Renderizado:** Mejoras en el manejo de resolución dinámica y escalado de ventana.

### Nuevos Módulos y Herramientas (Suite Cilixes)
- **Tilemap Editor v1.0:** Implementación de un nuevo editor de tiles nativo con soporte para capas y colisiones.
- **Localización (Instalador de Glifos):** Adición de módulo de inyección de caracteres especiales (Ñ, tildes) y activos gráficos en español.
- **Entorno de Trabajo Multitarea:** Implementación de un sistema de pestañas flotantes y acoplables (Docking System), permitiendo la edición simultánea de múltiples scripts y activos.

### Interfaz y Experiencia (UX)
- **Tema "Forerunner":** Nueva paleta visual basada en tonos cian de alta intensidad y estética neón sobre fondos oscuros.
- **Ofuscación de Integración AI:** Se han eliminado las referencias explícitas a servicios externos en la documentación pública y UI para mantener la integridad del "Easter Egg" técnico.

### Refactorización y Deuda Técnica
- **Normalización de Referencias:** Corrección de punteros y referencias cruzadas en la base de datos de objetos.
- **Embellecimiento de Código (Decoración):** Aplicación de estándares de legibilidad para facilitar el mantenimiento autónomo del repositorio.
- **Mejora en Pipeline de Traducción:** Optimización de los diccionarios de internacionalización para soporte multi-idioma.

> [!NOTE]
> **Análisis de Sistema:** La transición de saltos dinámicos a estructuras de control (`IF/SWITCH`) reduce significativamente la complejidad ciclomática del código descompilado, facilitando la depuración de eventos complejos en las ROMs. El sistema de pestañas flotantes requiere una gestión estricta de los estados de los archivos para evitar condiciones de carrera al guardar múltiples scripts simultáneamente.

---

## Versión 3.1.0 "The Imposibility Update"
**Fecha:** 2026-05-11
**Estado:** Lanzamiento Estable / Refactorización Profesional

### Profesionalización de la Base de Código
- **Refactorización de Comentarios:** Se han eliminado todas las referencias informales y comentarios personales, sustituyéndolos por documentación técnica en tercera persona.
- **Normalización de Nombres:** Renombrado de métodos internos y variables para seguir estándares de ingeniería (ej. `_parse_mary_bible` -> `_load_opcode_library`).
- **Limpieza de Activos:** Eliminación de archivos `.json` huérfanos y scripts de inspección obsoletos en la raíz y subcarpetas de datos.

### Mejoras en el Motor SlipSpace
- **Documentación Técnica:** Actualización de los comentarios en el compilador y descompilador para reflejar la lógica del motor sin ambigüedades.
---

## Versión 3.0.0 "The Imposibility Update"
**Fecha:** 2026-05-11
**Estado:** Lanzamiento Crítico / Arquitectura Cilixes

### Reconstrucción de la Arquitectura de Datos (Cilixes)
- **Migración Total:** Eliminación de la carpeta legacy `data` y transición completa a la suite de datos **Cilixes**.
- **Multitenencia:** Soporte nativo para FoMT y MFoMT mediante subcarpetas dedicadas (`fomt/`, `Mfomt/`) y prefijos de archivos (`Fomt_`, `MFomt_`).
- **Detección por Header (A0-AF):** Identificación quirúrgica de la ROM mediante el header de 16 bytes, permitiendo una carga de recursos 100% precisa.
- **Rutas Dinámicas:** Refactorización de `get_data_path` para soportar la resolución dinámica de activos según la versión detectada.

### Optimización y Limpieza
- **Purga de Repositorio:** Eliminación masiva de archivos temporales, rastros de depuración y logs para un despliegue limpio.
- **Seguridad:** Verificación y blindaje de API Keys mediante almacenamiento en sistema de registro local (fuera del código fuente).
- **Control de Versiones:** Implementación de un `.gitignore` profesional para evitar la subida de binarios y cache.

### Herramientas y IDE
- **Script IDE v3:** El autocompletado y el descompilador ahora inyectan dinámicamente las librerías correctas (`Fomt_Lib.csv` / `MFomt_Lib.csv`).
- **Visor de Sprites:** Actualizado para el pipeline de Cilixes, garantizando la carga de `Sprite_data.csv` sin errores de ruta.

---

## Versión 2.0.0 "The Shiao_Fujikawa Update"
**Fecha:** 2026-04-26
**Estado:** Estable / Nueva Generación

### Nuevo Núcleo de Scripting Ahora Llamado (SlipSpace Engine)
**Motivo del Cambio:** Mejora Significativa en la descompresion y recompresion de scripts..
- **Escapes Legibles:** Implementación de `\BRK` (0x05) y `\WAIT_CLICK` (0x0C) para una edición intuitiva.
- **Buscador Inteligente:** Sistema de búsqueda multihilo que localiza diálogos instantáneamente sin bloquear la UI.
- **Autocompletado:** Añadido sistema de sugerencias de funciones y comandos en el IDE.
- **Decoración de Ítems:** Sustitución dinámica de IDs hexadecimales por nombres de objetos (ej. `GiveItem(0x27)` -> `GiveItem(Jewel of Truth)`).

### Gráficos y Visualización
- **Depuración de Motor:** Se eliminó por completo el motor gráfico anterior por su ineficiencia.
- **Editor de Sprites:** Implementación del nuevo editor de sprites con soporte para visualización dinámica.
- **Colaboración Externa:** Integración de offsets y paletas maestras gracias al dump del usuario de Reddit **u/MelodyCrystel**, permitiendo una reconstrucción fiel de los personajes.
- **Descompresión GBA-GE:** Montaje de la lógica de descompresión gráfica basada en el estándar GBA-GE.

### Gestión de Memoria y Repunteo
- **Buscador de Espacio Libre:** Nuevo sistema que localiza bloques vacíos en la ROM para inserciones seguras.
- **Reciclaje de Bancos:** Al mover o repuntear un evento, la dirección anterior se marca como disponible para reciclaje, optimizando el uso de la ROM.
- **Alineación de 4 Bytes:** Inserción de datos respetando siempre direcciones múltiplos de 4 para evitar desalineación de instrucciones y crasheos en el hardware real/emuladores de GBA.
- **Master Table Scanning:** Mejora en el escaneo de NPCs y eventos basada en punteros de la Tabla Maestra.

### Internacionalización (i18n)
- **Soporte Global:** Expansión a 8 idiomas (ES, EN, JP, RU, DE, ZH, HI, PT).
- **Localización Nativa:** Corrección de términos en Japonés (Harvest Moon nativo) y expansión técnica en Ruso.
- **Cobertura:** 127 llaves de traducción verificadas y sincronizadas por idioma.

---

## Versión 1.5.0 "The Mineral Town Expansion"
**Fecha:** 2026-04-22
**Estado:** Antigua

### Características de la v1.5
- **Compatibilidad con MFoMT:** Detección dinámica para la versión femenina.
- **Motor de Audio:** Migración a sistema nativo para evitar bloqueos de archivos.
- **Carga Asíncrona:** Uso de `QThread` para escaneo de ROMs.
- **Estabilidad:** Protecciones básicas contra instrucciones desconocidas.

---
### Errores Conocidos
- Algunos fallos menores al reproducir audio en pistas mudas (trabajo en proceso).

# FOMT Studio - Registro de Cambios (Changelog)

## Versión 3.3.4 "Estabilización y Paridad de Bytecode"
**Fecha:** 2026-05-11
**Estado:** Lanzamiento Estable

### Estabilización del Motor SlipSpace (v3.3.4)
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

# FOMT Studio - Registro de Cambios (Changelog)

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

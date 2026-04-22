# FOMT Studio - Registro de Cambios (Changelog)

## Versión 1.5.0 "The Mineral Town Expansion"
**Fecha:** 2026-04-22
**Estado:** Estable

### Nuevas Características
- **Compatibilidad con MFoMT (More Friends of Mineral Town):**
    - Implementación de detección dinámica de ROM para la versión femenina (Girl version).
    - Soporte completo para el offset de la tabla de canciones de MFoMT (`0x144FF4`).
    - Adaptación del descompilador de scripts para eventos exclusivos de la versión MFoMT.
- **Rediseño del Motor de Audio:**
    - Migración de `QMediaPlayer` a `winsound` nativo para eliminar bloqueos de archivos y errores de códecs en Windows.
    - Implementación de un sistema de pre-procesamiento de audio más rápido que genera vistas previas WAV sin latencia.
### Mejoras y Optimizaciones
- **Carga Asíncrona de Proyectos:** Los proyectos ahora se escanean en segundo plano usando hilos (`QThread`), permitiendo que la UI responda durante el análisis de ROMs grandes.
- **Limpieza Automática de Sesión:** Al cambiar de proyecto o ROM, todos los paneles se reinician correctamente, evitando datos fantasma de la sesión anterior.
- **Estabilidad del Descompilador:** Se han añadido protecciones contra instrucciones desconocidas que anteriormente causaban cierres inesperados (Catastrophic Failures).

### Errores Corregidos
- Corregido el fallo donde la lista de audios no se poblaba al cargar MFoMT después de FoMT.
- Solucionado el error de descriptor de archivo (OSError [Errno 9]) al cerrar archivos de log de audio.
- Eliminados los bloqueos de archivos WAV temporales que impedían la reproducción múltiple.


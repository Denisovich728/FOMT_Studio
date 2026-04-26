============================================================
           FOMT STUDIO - Suite de Ingeniería Inversa
============================================================

¡Gracias por descargar este proyecto! 

FOMT Studio es un entorno de desarrollo de bajo nivel diseñado para la investigación, desensamblado y modificación (ROM Hacking) del ecosistema "Harvest Moon: Friends of Mineral Town" (GBA).

------------------------------------------------------------
ESTADO ACTUAL DEL PROYECTO (v2.0.0 - The Shiao_Fujikawa Update)
------------------------------------------------------------
La herramienta ha evolucionado de un visor a una suite de inyección integral con arquitectura profesional:

1. MOTOR DE SCRIPTS (SLIPSPACE ENGINE):
   - Descompilación y recompilación avanzada de eventos.
   - Lógica de mensajes "Mary & Popuri" con soporte de constantes `const MESSAGE_X`.
   - Soporte de escapes legibles: `\BRK` (0x05) y `\WAIT_CLICK` (0x0C).
   - IDE con autocompletado inteligente y resaltado de sintaxis dinámico.

2. GESTIÓN GRÁFICA Y MULTIMEDIA:
   - Editor de Sprites integrado con descompresión basada en el estándar GBA-GE.
   - Motor de Audio optimizado con integración de `gba-mus-ripper`.
   - Soporte para 8 idiomas (ES, EN, JP, RU, DE, ZH, HI, PT).

3. INGENIERÍA DE MEMORIA:
   - Buscador de espacio libre y sistema de repunteo inteligente.
   - Reciclaje de bancos de datos y alineación estricta de 4 bytes para evitar crasheos.
   - Escaneo de precisión basado en la Tabla Maestra (Master Table).

------------------------------------------------------------
CRÉDITOS Y COLABORACIONES
------------------------------------------------------------
El desarrollo de la versión 2.0.0 ha sido posible gracias a la comunidad. Un agradecimiento especial a:

* **u/MelodyCrystel (Reddit)**: Por proporcionar los offsets críticos y las paletas maestras de los sprites, fundamentales para la reconstrucción gráfica del motor.

------------------------------------------------------------
TRABAJO EN PROGRESO (ROADMAP)
------------------------------------------------------------
- Visor y editor avanzado de Mapas de Scripts, Tilesets y Warps.
- Implementación de un generador de parches en formato IPS para la distribución legal.
- Mejora de la emulación de audio para pistas complejas.

------------------------------------------------------------
CONTRIBUCIONES Y CÓDIGO ABIERTO
------------------------------------------------------------
Este programa es de código abierto bajo la licencia GNU GPL v3. Si eres desarrollador y quieres ayudar a que esta herramienta sea un estándar de la comunidad, te invitamos al repositorio oficial:

URL: https://github.com/Denisovich728/FOMT_Studio

Este software se distribuye "tal cual", con el objetivo de fomentar la preservación y el estudio de sistemas legados.

Desarrollado por: Denisovich728
Todos Los Derechos Reservados
============================================================

============================================================
           FOMT STUDIO - Suite de Ingeniería Inversa
============================================================

¡Gracias por descargar este proyecto! 

FOMT Studio es un entorno de desarrollo de bajo nivel diseñado para la investigación, desensamblado y modificación (ROM Hacking) del ecosistema "Harvest Moon: Friends of Mineral Town" (GBA).

------------------------------------------------------------
ESTADO ACTUAL DEL PROYECTO (v3.3.4 - Actualización La Imposibilidad)
------------------------------------------------------------
La herramienta ha sido sometida a una refactorización integral de su base de código, profesionalizando la documentación y eliminando redundancias:

1. ARQUITECTURA CILIXES (NUEVA):
   - Migración total a un sistema de datos modular y escalable.
   - Soporte nativo y simultáneo para FoMT (Harvest Moon) y MFoMT (More Friends of Mineral Town).
   - Detección quirúrgica de ROM mediante el header de 16 bytes (A0-AF), garantizando carga de recursos 100% precisa.
   - Resolución dinámica de rutas según la versión detectada para evitar conflictos de activos.

2. MOTOR DE SCRIPTS (SLIPSPACE ENGINE v3):
   - Descompilación y recompilación avanzada con inyección dinámica de librerías (Lib_Fomt / Lib_MFomt).
   - Lógica de mensajes "Mary & Popuri" con soporte de constantes `const MESSAGE_X`.
   - Soporte de escapes legibles: `\BRK` (0x05) y `\WAIT_CLICK` (0x0C).
   - IDE con autocompletado inteligente y resaltado de sintaxis dinámico.

3. GESTIÓN GRÁFICA Y MULTIMEDIA:
   - Editor de Sprites integrado con descompresión basada en el estándar GBA-GE.
   - Visor de Sprites actualizado para el pipeline de Cilixes.
   - Motor de Audio optimizado con integración de `gba-mus-ripper`.
   - Soporte para 8 idiomas (ES, EN, JP, RU, DE, ZH, HI, PT).

4. INGENIERÍA DE MEMORIA Y SEGURIDAD:
   - Buscador de espacio libre y sistema de repunteo inteligente.
   - Reciclaje de bancos de datos y alineación estricta de 4 bytes para evitar crasheos.
   - Blindaje de API Keys (IA) mediante almacenamiento en registro local, fuera del código fuente.
   - Purga masiva de archivos temporales y optimización de repositorio para despliegues limpios.

------------------------------------------------------------
CRÉDITOS Y COLABORACIONES
------------------------------------------------------------
El desarrollo de esta suite ha sido posible gracias a la comunidad. Un agradecimiento especial a:

* **u/MelodyCrystel (Reddit)**: Por proporcionar los offsets críticos y las paletas maestras de los sprites, fundamentales para la reconstrucción gráfica del motor.
* **StanHash**: Por sus proyectos [Mary](https://github.com/StanHash/mary) y [FoMT](https://github.com/StanHash/fomt).
* **HM-Studio (Andrey Moura)**: Por su repositorio [HM-Studio](https://github.com/andrey-moura/HM-Studio).

Sin sus valiosos aportes y código fuente, no habría sido posible descifrar la complejidad del código del juego original.

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

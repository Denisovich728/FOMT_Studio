============================================================
           FOMT STUDIO - Suite de Ingeniería Inversa
============================================================

¡Gracias por descargar este proyecto! 

FOMT Studio es un entorno de desarrollo de bajo nivel diseñado para la 
investigación, desensamblado y modificación (ROM Hacking) del ecosistema 
"Harvest Moon: Friends of Mineral Town" (GBA).

------------------------------------------------------------
ESTADO ACTUAL DEL PROYECTO (v1.x)
------------------------------------------------------------
La herramienta cuenta con una arquitectura profesional en PyQt6 que 
gestiona los offsets de memoria para la manipulación de:
* Atributos de Ítems, Personajes y Eventos.
* Soporte Multilingüe completo (Japonés, Inglés, Español).
* Gestión de Temas Dinámicos (Claro, Oscuro, Matrix).
* MOTOR DE TELEMETRÍA: Sistema de reporte automatizado vía protocolo 
  mailto para la depuración proactiva basada en feedback del usuario.
* Lógica inicial de Repunteo (Re-pointing) de scripts de eventos.

------------------------------------------------------------
TRABAJO EN PROGRESO (ROADMAP V2.0 - PRÓXIMAMENTE)
------------------------------------------------------------
El desarrollo actual se enfoca en la transición de "Visor" a "Editor 
de Inyección Integral". Se están trabajando los siguientes módulos:

1. MOTOR MULTIMEDIA Y AUDIO:
   - Descompiladores de Audio, Sprites y activos multimedia.
   - Motor de audio para asignación de IDs y conversión a hexadecimal 
     legible para re-inserción atómica en la ROM.

2. INGENIERÍA DE RUTINAS Y MAPEO:
   - Depuración del motor de detección, lectura y escritura de rutinas.
   - Visor y editor avanzado de Mapas de Scripts, Tilesets y Warps.

3. ESTÁNDARES DE DISTRIBUCIÓN:
   - Implementación de un generador de parches en formato IPS para la 
     distribución legal y segura de modificaciones.

------------------------------------------------------------
CONTRIBUCIONES Y CÓDIGO ABIERTO
------------------------------------------------------------
Este programa es de código abierto bajo la licencia GNU GPL v3. 
Si eres desarrollador y quieres ayudar a que esta herramienta sea 
un estándar de la comunidad, te invito al repositorio oficial:

URL: https://github.com/Denisovich728/FOMT_Studio

Este software se distribuye "tal cual", con el objetivo de fomentar 
la preservación y el estudio de sistemas legados.

Desarrollado por: Denisovich728
Todos Los Derechos Reservados
============================================================
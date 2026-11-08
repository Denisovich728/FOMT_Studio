# Cómo colaborar con FOMT Studio

Gracias por querer ayudar. FOMT Studio es un proyecto de ROM hacking para
*Harvest Moon: Friends of Mineral Town* y *More Friends of Mineral Town* (GBA).
Esta guía resume las reglas que ya sigue el proyecto para que tus cambios se
puedan revisar e integrar rápido.

## Antes de empezar

- **Nunca subas ROMs ni partidas** (`.gba`, `.sav`). El `.gitignore` ya las
  excluye; no lo cambies.
- Para cambios grandes, abre primero un issue y cuenta qué quieres hacer.
- Un pull request = un solo tema. Es más fácil revisar «traducir el Visor de
  Mapas» que «traducir, cambiar colores y arreglar un bug» en el mismo PR.

## Preparar el entorno

Requisitos: Python 3.10 o superior (probado también con 3.14).

```bash
pip install -r requirements.txt
python main.py
```

Para generar el ejecutable:

```bash
pyinstaller FoMT_Studio_v4.0.0_FinalRelease.spec
```

## Estructura (dónde va cada cosa)

| Carpeta | Contenido | Tipo de cambio |
| :--- | :--- | :--- |
| `Consola_de_Comando/` | Ventana principal, temas, idiomas, diálogos generales | Interfaz |
| `Nucleos_Positronicos/` | Editores y visores de cada sistema (mapas, NPC, scripts, sprites, sonido, items) | Interfaz y lógica |
| `Banco_de_Datos/` | Lectura y escritura de la ROM, tablas `Cilixes`, gestor de memoria | Backend |
| `Nucleo_Herramientas/` | Utilidades auxiliares | Backend |

Si tu cambio es solo de interfaz, **no modifiques `Banco_de_Datos/` ni la
forma en que se leen o escriben datos de la ROM**. Si necesitas tocar el
backend, explícalo en el PR.

## Reglas de interfaz

### 1. Ningún texto fijo: todo pasa por `i18n.json`

Los textos visibles (botones, etiquetas, pestañas, títulos, mensajes, filtros
de diálogos de archivo, tooltips) van en
[`Consola_de_Comando/i18n.json`](Consola_de_Comando/i18n.json) y se leen con
`tr()`:

```python
from Consola_de_Comando.i18n import tr

boton = QPushButton(tr("vmap_btn_save", lang))
QMessageBox.information(self, tr("msg_success", lang),
                        tr("vmap_map_exported", lang).format(path=path))
```

- Cada clave nueva se añade **en los 8 idiomas**: `es`, `en`, `jp`, `ru`,
  `de`, `zh`, `hi`, `pt`. Si no sabes un idioma, pon el texto en inglés y
  avísalo en el PR para que alguien lo revise.
- Usa un prefijo por módulo (`vmap_` para el Visor de Mapas, `npc_` para
  NPC, etc.) y reutiliza las claves genéricas que ya existen (`btn_cancel`,
  `msg_error`, `msg_warning`, `msg_success`).
- Los datos variables van como huecos con nombre: `"Mapa exportado a:\n{path}"`.
  Todos los idiomas deben tener los mismos huecos.
- Antes de enviar, ejecuta el comprobador:

  ```bash
  python .github/scripts/check_i18n.py
  ```

- Si el código lee el texto de un combo (`currentText()`), no lo traduzcas sin
  cambiar esa lectura a `currentIndex()` o `currentData()`.

### 2. Cero emojis

Ni en el código ni en la interfaz. Tampoco símbolos decorativos que Windows
muestra como emoji (por ejemplo ⬇ o ⬆).

### 3. Lenguaje técnico formal

Textos claros y profesionales, sin modismos ni apodos internos de módulos.

### 4. Colores del tema, no colores fijos

FOMT Studio tiene varios temas en
[`Consola_de_Comando/themes.py`](Consola_de_Comando/themes.py). Evita
`setStyleSheet("color: #44aaff")` con colores escritos a mano: en otro tema
pueden quedar ilegibles. Usa los colores del tema activo.

## Commits

Mensajes en español, en minúsculas y con el formato que ya usa el historial:

```
tipo(área): descripción breve
```

Tipos habituales: `feat`, `fix`, `docs`, `refactor`, `release`.
Ejemplos: `fix(maps): corregir paleta del tocadiscos`,
`feat(i18n): internacionalizar el Visor de Mapas`.

## Pull requests

1. Haz un fork y crea una rama con nombre descriptivo (`i18n/visor-mapas`,
   `fix/paleta-tocadiscos`).
2. Prueba el cambio abriendo la aplicación y cargando una ROM.
3. Rellena la plantilla del PR: qué cambia, cómo lo probaste y si toca el
   backend.

## Reportar errores

Usa la plantilla de **Reporte de error** al abrir un issue. Indica siempre:

- Versión de FOMT Studio (aparece en el título de la ventana).
- Juego y región de la ROM (FoMT o MFoMT; USA, EUR, JPN).
- Sistema operativo y si usas el `.exe` o `python main.py`.
- Pasos para reproducirlo y el contenido de `fomt_studio_error.log` si existe.

## Licencia

Al contribuir aceptas que tu código se publique bajo la licencia
[GPLv3](LICENSE) del proyecto.

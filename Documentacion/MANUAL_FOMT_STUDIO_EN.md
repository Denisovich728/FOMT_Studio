# FOMT Studio User Manual

Reverse Engineering, Translation, and Modding Suite for *Harvest Moon: Friends of Mineral Town* and *More Friends of Mineral Town* (Game Boy Advance).

---

## 1. Requirements & Setup

- **Operating System:** Windows 10/11 (compatible with Linux and macOS when running from source).
- **Python:** Python 3.10 or higher.
- **Core Dependencies:** PyQt6, Pillow (PIL), NumPy (for graphics/map modules).

### Running from Source
From the `FOMT_Studio` root directory:

```bash
python main.py
```

If a critical startup error occurs, details are automatically written to `fomt_studio_error.log` in the project root.

---

## 2. Workspace Layout

The repository is organized by domain to keep development and assets clean:

- `main.py`: Application GUI entry point.
- `Consola_de_Comando/`: Main UI shell (`app.py`), multi-language system (`i18n.py` / `i18n.json`), visual themes (`themes.py`), menu/intro editors, and settings dialog.
- `Nucleos_Positronicos/`: Domain-specific engines:
  - `Nucleo_de_Scripts/`: SlipSpace IDE, compiler/decompiler (`SlipSpace_Script_Engine/`), Event Theater, Block Puzzle, and `memory_extend_engine.py` (flag expander).
  - `Nucleo_de_Imagenes/`: Extreme tile editor (`tile_editor_extreme.py`), animation viewer, and extractor.
  - `Nucleo_de_Sprites/`: Sprite and metasprite viewers.
  - `Nucleo_de_Mapas/`: Map/tileset editor and compression/decompression utilities (`decompress_auto`).
  - `Nucleo_de_Aldeanos/`: NPC, portrait, and AI routine editors.
  - `Nucleo_de_Items/`: Single and bulk item/tool/food editors.
  - `Nucleo_de_Sonido/`: Sappy (MP2K) audio viewer.
  - `Nucleo_de_Rutinas_AI/`: Native procedure viewer.
- `Banco_de_Datos/`: Project data model (`proyecto.py`), Spanish font patch (`parche_font.py`), `Textos_UI/` CSV tables (`strings_fuera_de_eventos (esp).csv`), and compression `Utilidades/`.
- `Herramientas/`: Standalone CLI tools (`inyector_strings_ui.py` for bulk UI string injection, `bin.py` for hex inspection).
- `Nucleo_Herramientas/`: Helper utilities (`flagser.py` CLI flag expander, `config_manager.py`, `visor_parches.py`, `visor_tilesets.py`).
- `Documentacion/`: SlipSpace Engine reference, NPC AI guides, and FOMT Studio manuals (ES/EN).
- `Assets_Graficos/` & `Archivos_Trabajo/`: Graphic assets, extraction dumps, and working backups.

---

## 3. Getting Started

1. **Create or Load a Project (`File -> New Project` / `Load Project`):**
   - Select a `.gba` ROM of *Harvest Moon: Friends of Mineral Town* (USA) or *More Friends of Mineral Town* (USA).
   - FOMT Studio detects the ROM header (`HARVESTMOGBA` / `HM MFOM USA`) and populates the left-hand project tree.
2. **Save & Compile (`Ctrl+S` / `File -> Compile ROM`):**
   - **Save Project** stores your edits in the local project workspace.
   - **Compile ROM** builds a patched `.gba` ROM with all modifications and updates the GBA header complement checksum (`0xBD`).
3. **Customization (`Configuration`):**
   - **Themes:** Light, Dark, Dracula (VS Code), Matrix, and Forerunner.
   - **Languages:** Spanish, English, Japanese, Russian, German, Chinese, Hindi, and Portuguese.
   - **System Settings (`Ctrl+Alt+S`):** Advanced paths and preferences.

---

## 4. Core Modules & Editors

The main toolbar and **More Tools** dropdown organize editors into clear categories:

### 4.1 Scripts & Events (SlipSpace)
- **SlipSpace IDE:** High-level C-style script editor with syntax highlighting, compilation, and direct decompilation from the ROM event table (`0x0F89D4` in FoMT). See [SlipSpace_Engine_Manual.md](file:///J:/Laboratorio/FOMT_Studio/Documentacion/SlipSpace_Engine_Manual.md) for full language documentation.
- **Event Theater:** Visual preview of event scenes, dialogues, and animations.
- **Block Puzzle:** Visual block-based editor for building event logic without writing code manually.

### 4.2 UI Editors
- **UI / Menu Texts:** Edit system strings outside events (inventory, farm menus, calendar, naming and confirmation screens).
- **Intro Texts:** Edit the opening intro sequence strings.

### 4.3 Graphics & Audio
- **Metasprite & Sprite Viewers:** Inspect and edit sprite sheets and OAM metasprite layouts.
- **Animation Viewer & Extractor:** Frame-by-frame inspection and extraction of character/object animations.
- **Extreme Tile Editor:** 4bpp/8bpp tile graphics and BGR555 palette editing.
- **Sappy Audio:** Inspect and play Sappy (MP2K) sound engine tracks.

### 4.4 Data, Maps & Internal Database
- **Map Editor:** View map layers, tilesets, and collision data.
- **Visual NPC & NPC Routines Editor:** Edit villager schedules, locations, and daily AI behaviors.
- **Internal Database (RAW):** Direct access to NPC, Item, Menu tables, and the Master Pointer Editor.
- **Bulk Item Editor:** Batch editing for Tools, Foods/Consumables, and Misc items.

---

## 5. Tools Section

Accessible directly from the top **`Tools`** menu or under **`More Tools -> Tools`**:

1. **In-Slot Flags & Memory Expansion (Flag Editor):**
   - Audits the current ROM flag range and registers custom flags (`bit`, `u8`, `u16`, `u32`) inside the free Save Slot 1 tail (`0x34AC..0x34C3`) without breaking the native save checksum.
   - Repoints the flag dispatcher tables to free ROM space (`0x75B000` by default).
   - Also available via CLI: `python Nucleo_Herramientas/flagser.py <rom.gba>`.
2. **Save File Editor (`.sav`):**
   - Loads 64 KB / 128 KB SRAM save files to inspect and edit gold, date, inventory, affection, and active flags.
3. **Shop Editor:**
   - Modifies shop inventories, prices, and item availability.

---

## 6. Engine Patches & Spanish Localization

Under **`More Tools -> Patches & Modifications`** you can apply binary patches:

- **Ñ & Latin Characters Patch:** Installs extended Latin glyphs (`ÁÉÍÓÚáéíóúÑñÜü¿¡`) into the 16px game font and enables `CHARMAP_ES`.
- **Z-Sorting / Stairs / Teleport Stone Patches:** Engine and quality-of-life enhancements for custom ROM hacks.

### Bulk UI String Injection from CSV
To inject or update UI strings from `Banco_de_Datos/Textos_UI/strings_fuera_de_eventos (esp).csv` into a ROM:

```bash
python Herramientas/inyector_strings_ui.py --rom "path/to/rom.gba" --out "path/to/translated_rom.gba"
```

---

## 7. Preparing `.ips` Patches for Production

To distribute a translation or mod without sharing a full ROM:
1. Start from the clean original ROM (No-Intro USA, SHA-1 `a2fc3574f0a65a4fcf7682fb274b9d7eebdef963` for FoMT USA).
2. Build your final compiled ROM (verifying the GBA header complement byte at `0xBD`).
3. Generate the `.ips` patch comparing both ROMs (`PATCH` header + 3-byte offset/2-byte size records + `EOF`).
4. Always run a roundtrip check by applying the `.ips` to the clean base ROM and verifying that the resulting SHA-1 matches your production ROM.


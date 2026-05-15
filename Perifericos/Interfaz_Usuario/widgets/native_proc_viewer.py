# ============================================================
# FOMT Studio - Suite de Ingenieria Inversa (v3.6.5)
# "Actualizacion La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
# native_proc_viewer.py
# Widget de visualizacion de rutinas nativas (THUMB) del engine.
# Detecta patrones de alto nivel en el codigo ARM/THUMB:
#   - Portraits invocados (IDs de Fomt_Portraits.csv)
#   - Items referenciados (Flag IDs de Fomt_Flags.csv)
#   - Constantes de cantidades (MOV inmediatos)
#   - Llamadas a funciones VM conocidas (dispatch table)
#   - Punteros a strings en ROM
# ============================================================
import struct
import csv
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLabel, QComboBox, QPushButton, QSplitter, QGroupBox, QTableWidget, 
    QTableWidgetItem, QHeaderView, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter


class NativeProcHighlighter(QSyntaxHighlighter):
    """Resaltador de sintaxis para pseudo-script de rutinas nativas."""
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def highlightBlock(self, text):
        # Comentarios
        if text.strip().startswith("//"):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#6A9955"))
            self.setFormat(0, len(text), fmt)
            return
        
        # Secciones
        if text.strip().startswith("==="):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#C586C0"))
            fmt.setFontWeight(QFont.Weight.Bold)
            self.setFormat(0, len(text), fmt)
            return
        
        # Keywords
        import re
        keywords = {
            r'\b(Portrait|portrait_id|Set_Portrait)\b': "#4EC9B0",
            r'\b(Flag|Check_Flag|Set_Flag)\b': "#DCDCAA",
            r'\b(Item|Give_Item|item_id)\b': "#CE9178",
            r'\b(VM_Call|Engine_Call)\b': "#569CD6",
            r'\b(quantity|amount|count)\b': "#B5CEA8",
            r'\b(TalkOpen|TalkClose|TalkMessage)\b': "#4FC1FF",
            r'0x[0-9A-Fa-f]+': "#B5CEA8",
            r'"[^"]*"': "#CE9178",
        }
        for pattern, color in keywords.items():
            for m in re.finditer(pattern, text):
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(color))
                self.setFormat(m.start(), m.end() - m.start(), fmt)


class NativeProcDecompiler:
    """
    Decompilador de patrones de alto nivel para rutinas THUMB nativas.
    No genera desensamblado completo -- solo extrae valores conocidos.
    """
    
    DISPATCH_TABLE_FOMT = 0x03F900
    TABLE_COUNT = 328
    
    # Charset FoMT para lectura de strings nativos del engine
    CHARMAP = {
        0x01: "{PLAYER}", 0x02: "{VALUE1}", 0x03: "{VALUE2}",
        0x04: "{VALUE4}", 0x05: None,  # BRK = terminador
        0x06: "{BREAK}", 0x07: "{BREAK2}", 0x08: "{VALUE8}",
        0x09: "{VALUE9}", 0x0A: "\n", 0x0C: "{WAIT}",
        0x0D: "\r", 0x19: "{HORSE}",
    }
    # Cantidades conocidas del engine
    KNOWN_QUANTITIES = {99: "MAX_BUY_QTY", 255: "MAX_BYTE", 100: "PERCENT_100"}

    def __init__(self, rom_data, cilixes_dir, project=None):
        self.rom = rom_data
        self.rom_size = len(rom_data)
        self.project = project
        
        # Cargar tablas de referencia
        self.portraits = {}  # hex_id -> name
        self.flags = {}      # int_id -> name
        self.lib = {}        # call_id -> (name, type, args)
        self.reverse_dispatch = {}  # gba_addr -> (call_id, name)
        self.maps = {}       # map_id -> name
        self.items = {}      # item_id -> name (articulos)
        self.foods = {}      # food_id -> name
        self.tools = {}      # tool_id -> name
        self.characters = {} # char_id -> name
        
        self._load_csv(cilixes_dir)
        self._load_project_data()
        self._build_reverse_dispatch()
    
    def _load_csv(self, base_dir):
        # Portraits
        path = os.path.join(base_dir, "Fomt_Portraits.csv")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if len(row) >= 2 and row[1].strip():
                        try:
                            pid = int(row[1].strip(), 16)
                            self.portraits[pid] = row[0].strip()
                        except ValueError:
                            pass
        
        # Flags
        path = os.path.join(base_dir, "Fomt_Flags.csv")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if len(row) >= 2:
                        try:
                            fid = int(row[0].strip(), 16)
                            self.flags[fid] = row[1].strip()
                        except ValueError:
                            pass
        
        # Lib (opcodes)
        path = os.path.join(base_dir, "Fomt_Lib.csv")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if len(row) >= 4:
                        etype = row[0].strip()
                        dec_id = int(row[2].strip())
                        name = row[3].strip()
                        args = row[4].strip() if len(row) > 4 else ""
                        self.lib[dec_id] = (name, etype, args)
        
        # Maps
        path = os.path.join(base_dir, "Fomt_Mapas.csv")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if len(row) >= 2:
                        try:
                            mid = int(row[0].strip())
                            self.maps[mid] = row[1].strip()
                        except ValueError:
                            pass

    def _load_project_data(self):
        """Carga items/tools/food/npcs del proyecto si esta disponible."""
        if not self.project:
            return
        try:
            if self.project.item_parser:
                items = self.project.item_parser.scan_foods()
                for itm in items:
                    name = itm.name_str.replace('\n', ' ').strip('\x00').strip()
                    if not name:
                        name = "Item_%d" % itm.index
                    if itm.category == "Articulo" or itm.category == "Artículo":
                        self.items[itm.index] = name
                    elif "Comida" in itm.category or "Consumible" in itm.category:
                        self.foods[itm.index] = name
                    elif "Herramienta" in itm.category:
                        self.tools[itm.index] = name
            if self.project.npc_parser:
                npcs = self.project.npc_parser.scan_npcs()
                for npc in npcs:
                    name = npc.name_str.strip('\x00').strip()
                    if name:
                        self.characters[npc.index + 1] = name
        except Exception:
            pass

    def _build_reverse_dispatch(self):
        for cid in range(self.TABLE_COUNT):
            off = self.DISPATCH_TABLE_FOMT + cid * 4
            if off + 4 > self.rom_size:
                break
            ptr = struct.unpack_from('<I', self.rom, off)[0]
            if ptr != 0:
                clean = ptr & 0xFFFFFFFE
                name = self.lib.get(cid, ('Unk_%03X' % cid, 'unk', ''))[0]
                self.reverse_dispatch[clean] = (cid, name)
                self.reverse_dispatch[ptr] = (cid, name)
    
    def get_proc_list(self):
        """Retorna la lista de todos los procs con sus direcciones."""
        procs = []
        for cid in range(self.TABLE_COUNT):
            off = self.DISPATCH_TABLE_FOMT + cid * 4
            if off + 4 > self.rom_size:
                break
            ptr = struct.unpack_from('<I', self.rom, off)[0]
            if ptr == 0:
                continue
            info = self.lib.get(cid)
            if info:
                name, etype, args = info
                rom_off = (ptr & 0xFFFFFFFE) & 0x01FFFFFF
                procs.append((cid, name, etype, rom_off, args))
        return procs
    
    def decompile_pattern(self, call_id):
        """
        Decompila una rutina nativa extrayendo SOLO los patrones de alto nivel:
        - Constantes inmediatas (portraits, items, flags, cantidades)
        - Llamadas a funciones VM conocidas
        - Punteros a datos en ROM
        """
        off = self.DISPATCH_TABLE_FOMT + call_id * 4
        if off + 4 > self.rom_size:
            return "// Error: Call ID fuera de rango", []
        
        ptr = struct.unpack_from('<I', self.rom, off)[0]
        if ptr == 0:
            return "// Error: Call ID sin handler (NULL)", []
        
        rom_off = (ptr & 0xFFFFFFFE) & 0x01FFFFFF
        info = self.lib.get(call_id, ('Proc%03X' % call_id, 'proc', ''))
        proc_name = info[0]
        
        # Scan up to 2KB of THUMB code
        max_scan = min(2048, self.rom_size - rom_off)
        code = self.rom[rom_off:rom_off + max_scan]
        
        lines = []
        detections = []  # (type, value, description, offset)
        
        lines.append("// ================================================================")
        lines.append("// Rutina Nativa: %s  (Call ID %d / 0x%03X)" % (proc_name, call_id, call_id))
        lines.append("// ROM: 0x%06X  |  GBA: 0x%08X  |  Modo: THUMB" % (rom_off, ptr))
        lines.append("// ================================================================")
        lines.append("")
        
        # Track immediate constants and their computed values
        regs = {}  # reg -> (raw_value, computed_value, shift_info)
        
        i = 0
        found_return = False
        section_num = 1
        last_bl_name = None
        
        while i < len(code) - 2 and not found_return:
            w = struct.unpack_from('<H', code, i)[0]
            addr = rom_off + i
            
            # ═══ MOV Rd, #imm ═══
            if (w & 0xF800) == 0x2000:
                rd = (w >> 8) & 7
                imm = w & 0xFF
                regs[rd] = (imm, imm, None)
                
                # Peek ahead: if next instruction is LSL, this is a struct offset, skip detection
                is_struct_offset = False
                if i + 2 < len(code):
                    next_w = struct.unpack_from('<H', code, i + 2)[0]
                    if (next_w & 0xF800) in (0x0000, 0x0800) and (next_w >> 6) & 0x1F != 0:
                        is_struct_offset = True
                
                if not is_struct_offset and imm > 0x02:
                    # Detect known constant values (skip 0x00-0x02 as common clear/flag values)
                    portrait_name = self.portraits.get(imm)
                    flag_name = self.flags.get(imm)
                    map_name = self.maps.get(imm)
                    item_info = self._resolve_imm_as_item(imm)
                    
                    if portrait_name and imm < 0xB8:
                        detections.append(("Portrait", "0x%02X" % imm, portrait_name, addr))
                        lines.append('    Set_Portrait("%s");  // portrait_id = 0x%02X' % (portrait_name, imm))
                    elif item_info:
                        itype, iname = item_info
                        detections.append((itype, "ID %d" % imm, iname, addr))
                        lines.append('    // %s: %s (ID=%d)' % (itype, iname, imm))
                    elif flag_name and not flag_name.startswith("Flag_0x"):
                        detections.append(("Flag", "0x%02X" % imm, flag_name, addr))
                    elif map_name:
                        detections.append(("Map", "%d" % imm, map_name, addr))
                
                i += 2
                continue
            
            # ═══ LSL Rd, Rs, #imm (compute offset) ═══
            if (w & 0xF800) == 0x0000 and (w >> 6) & 0x1F != 0:
                rd = w & 7
                rs = (w >> 3) & 7
                shift = (w >> 6) & 0x1F
                if rs in regs:
                    computed = regs[rs][0] << shift
                    regs[rd] = (regs[rs][0], computed, "LSL #%d" % shift)
                i += 2
                continue
            
            # ═══ LSR Rd, Rs, #imm ═══
            if (w & 0xF800) == 0x0800:
                rd = w & 7
                rs = (w >> 3) & 7
                shift = (w >> 6) & 0x1F
                if rs in regs:
                    computed = regs[rs][0] >> shift
                    regs[rd] = (regs[rs][0], computed, "LSR #%d" % shift)
                i += 2
                continue
            
            # ═══ ADD/SUB with immediates ═══
            if (w & 0xF800) in (0x3000, 0x3800):
                rd = (w >> 8) & 7
                imm = w & 0xFF
                if (w & 0xF800) == 0x3000 and rd in regs:
                    regs[rd] = (regs[rd][0], regs[rd][1] + imm, "ADD #%d" % imm)
                i += 2
                continue
            
            # ═══ CMP Rd, #imm ═══
            if (w & 0xF800) == 0x2800:
                rd = (w >> 8) & 7
                imm = w & 0xFF
                
                # Detect known quantities first
                qty_name = self.KNOWN_QUANTITIES.get(imm)
                if qty_name and imm > 0:
                    detections.append(("Quantity", str(imm), qty_name, addr))
                    lines.append('    // Quantity check: %d (%s)' % (imm, qty_name))
                    i += 2
                    continue
                
                # Detect comparison with known values
                portrait_name = self.portraits.get(imm)
                flag_name = self.flags.get(imm)
                
                if imm > 0 and portrait_name:
                    detections.append(("Check", "0x%02X" % imm, "Compare portrait: %s" % portrait_name, addr))
                    lines.append('    // Compare: portrait_id == 0x%02X (%s)' % (imm, portrait_name))
                elif imm > 0 and flag_name and flag_name != "Flag_0x%X" % imm:
                    detections.append(("Check", "0x%02X" % imm, "Compare flag: %s" % flag_name, addr))
                    lines.append('    // Compare: flag == 0x%02X (%s)' % (imm, flag_name))
                
                i += 2
                continue
            
            # ═══ LDR Rd, [PC, #imm] - LITERAL POOL (important!) ═══
            if (w & 0xF800) == 0x4800:
                rd = (w >> 8) & 7
                imm = (w & 0xFF) * 4
                pool_addr = ((addr + 4) & ~3) + imm
                if pool_addr + 4 <= self.rom_size:
                    pool_val = struct.unpack_from('<I', self.rom, pool_addr)[0]
                    regs[rd] = (pool_val, pool_val, "pool")
                    
                    # Detect pointers to known data regions
                    if 0x08000000 <= pool_val < 0x09000000:
                        rom_ptr = (pool_val & 0xFFFFFFFE) & 0x01FFFFFF
                        # Skip code regions (0x03F-0x04F are engine code)
                        is_data_region = rom_ptr >= 0x0F0000 or rom_ptr < 0x030000
                        if is_data_region:
                            s = self._try_read_string(rom_ptr)
                            if s and len(s) > 3:
                                detections.append(("String", "0x%06X" % rom_ptr, '"%s"' % s, addr))
                                lines.append('    // String: "%s"  (ROM: 0x%06X)' % (s, rom_ptr))
                    elif 0x02000000 <= pool_val < 0x03000000:
                        detections.append(("EWRAM", "0x%08X" % pool_val, "EWRAM pointer (game state)", addr))
                    elif 0x03000000 <= pool_val < 0x04000000:
                        detections.append(("IWRAM", "0x%08X" % pool_val, "IWRAM pointer (fast RAM)", addr))
                
                i += 2
                continue
            
            # ═══ STR (write to memory - flag/state modification) ═══
            if (w & 0xF800) == 0x6000:
                rd = w & 7
                rn = (w >> 3) & 7
                imm = ((w >> 6) & 0x1F) * 4
                
                # If we know the stored value
                if rd in regs and isinstance(regs[rd][1], int):
                    val = regs[rd][1]
                    if val < 0x300:
                        flag_name = self.flags.get(val, "")
                        if flag_name:
                            detections.append(("Write", "0x%X" % val, "Write to %s" % flag_name, addr))
                            lines.append('    Set_State(%s, ...);  // 0x%X' % (flag_name, val))
                
                i += 2
                continue
            
            # ═══ BL (function call - most important!) ═══
            if (w & 0xF800) == 0xF000 and i + 4 <= len(code):
                nw = struct.unpack_from('<H', code, i + 2)[0]
                if (nw & 0xF800) in (0xF800, 0xE800):
                    ohi = w & 0x7FF
                    olo = nw & 0x7FF
                    foff = (ohi << 12) | (olo << 1)
                    if foff & 0x400000: foff -= 0x800000
                    target = rom_off + i + 4 + foff
                    gba_target = target | 0x08000000
                    
                    match = self.reverse_dispatch.get(gba_target) or \
                            self.reverse_dispatch.get(gba_target & 0xFFFFFFFE)
                    
                    if match:
                        cid, name = match
                        info = self.lib.get(cid, (name, 'proc', ''))
                        # Build argument string from tracked registers
                        arg_str = self._guess_args(regs, info[2])
                        call_str = '%s(%s);' % (name, arg_str)
                        detections.append(("VM_Call", "ID %d" % cid, call_str, addr))
                        lines.append('    %s  // VM opcode 0x%03X' % (call_str, cid))
                        last_bl_name = name
                    else:
                        # Internal function - try to identify
                        rom_target = target & 0x01FFFFFF
                        label = self._identify_func(rom_target, regs)
                        if label != "internal":
                            detections.append(("Engine", "0x%06X" % rom_target, label, addr))
                            lines.append('    %s();  // 0x%06X' % (label, rom_target))
                    
                    i += 4
                    continue
            
            # ═══ BX LR / POP PC (return) ═══
            if w == 0x4770 or (w & 0xFF00) == 0xBD00:
                found_return = True
                lines.append('')
                lines.append('    return;')
                i += 2
                continue
            
            # Skip other instructions
            i += 2
        
        lines.append("}")
        lines.append("")
        
        # Summary section
        if detections:
            lines.append("")
            lines.append("// === RESUMEN DE VALORES DETECTADOS ===")
            for dtype, dval, ddesc, daddr in detections:
                lines.append("// [%s] %s : %s  (0x%06X)" % (dtype, dval, ddesc, daddr))
        
        return "\n".join(lines), detections
    
    def _try_read_string(self, rom_off):
        """Lee un string usando el charset FoMT (soporta 0x05 BRK como terminador)."""
        if rom_off >= self.rom_size:
            return None
        result = []
        has_printable = False
        for j in range(min(200, self.rom_size - rom_off)):
            b = self.rom[rom_off + j]
            if b == 0x05 or b == 0x00:  # BRK or NULL = end of string
                break
            if b in self.CHARMAP:
                mapped = self.CHARMAP[b]
                if mapped:
                    result.append(mapped)
            elif 0x20 <= b <= 0x7E:
                result.append(chr(b))
                has_printable = True
            elif b in (0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9):
                # Accented vowels
                accents = {0xF0:'A',0xF1:'E',0xF2:'I',0xF3:'O',0xF4:'U',0xF5:'a',0xF6:'e',0xF7:'i',0xF8:'o',0xF9:'u'}
                result.append(accents.get(b, '?'))
                has_printable = True
            elif b == 0x2B:
                result.append('N~')
                has_printable = True
            elif b == 0x2D:
                result.append('n~')
                has_printable = True
            else:
                # Unknown byte - if too many, not a string
                if len(result) < 2:
                    return None
                break
        s = ''.join(result)
        if not has_printable or len(s) < 2:
            return None
        return s
    
    def _guess_args(self, regs, arg_spec):
        """Intenta reconstruir argumentos de una llamada VM desde los registros."""
        if not arg_spec:
            return ""
        args = arg_spec.split(',')
        result = []
        for idx, arg_name in enumerate(args):
            arg_name = arg_name.strip()
            if idx in regs and isinstance(regs[idx][1], int):
                val = regs[idx][1]
                # Try to resolve known values
                if 'portrait' in arg_name.lower():
                    pname = self.portraits.get(val)
                    if pname:
                        result.append('"%s"' % pname)
                        continue
                if 'flag' in arg_name.lower():
                    fname = self.flags.get(val)
                    if fname:
                        result.append('"%s"' % fname)
                        continue
                if 'map' in arg_name.lower():
                    mname = self.maps.get(val)
                    if mname:
                        result.append('"%s"' % mname)
                        continue
                result.append("0x%X" % val)
            else:
                result.append(arg_name)
        return ", ".join(result)
    
    def _resolve_imm_as_item(self, imm):
        """Intenta resolver un inmediato como item/tool/food."""
        if imm in self.tools:
            return ("Tool", self.tools[imm])
        if imm in self.items:
            return ("Item", self.items[imm])
        if imm in self.foods:
            return ("Food", self.foods[imm])
        return None

    def _identify_func(self, rom_off, regs):
        """Identifica funciones internas conocidas."""
        known = {
            0x04168A: "VM_Yield_Wait_Frame",
            0x045572: "Register_Shipment",
            0x045166: "Init_Shop_UI",
            0x0454B2: "Finalize_Transaction",
            0x0454C8: "Init_Animal_Stats",
            0x0454FA: "Play_SE",
            0x044CF6: "Update_Inventory_Display",
        }
        if rom_off in known:
            return known[rom_off]
        
        if 0x013000 <= rom_off < 0x014200:
            return "Engine_Update_%02X" % ((rom_off - 0x013000) >> 4)
        if 0x00C000 <= rom_off < 0x00D400:
            return "Kernel_%04X" % (rom_off & 0xFFFF)
        if 0x016000 <= rom_off < 0x017000:
            return "GFX_Update_%04X" % (rom_off & 0xFFFF)
        
        return "internal"


class NativeProcViewerWidget(QWidget):
    """Widget principal para explorar y pseudo-decompilar rutinas nativas."""
    
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.parent_app = parent
        self.decompiler = None
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Header
        header = QLabel("Rutinas Nativas del Engine (THUMB)")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)
        
        # Splitter: detections table | pseudo-code
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Top: Detections table
        det_group = QGroupBox("Valores Detectados")
        det_layout = QVBoxLayout(det_group)
        self.det_table = QTableWidget()
        self.det_table.setColumnCount(4)
        self.det_table.setHorizontalHeaderLabels(["Tipo", "Valor", "Descripcion", "Offset"])
        self.det_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.det_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.det_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        det_layout.addWidget(self.det_table)
        splitter.addWidget(det_group)
        
        # Bottom: Pseudo-code view
        code_group = QGroupBox("Pseudo-Script")
        code_layout = QVBoxLayout(code_group)
        self.code_view = QTextEdit()
        self.code_view.setReadOnly(True)
        self.code_view.setFont(QFont("Consolas", 10))
        self.highlighter = NativeProcHighlighter(self.code_view.document())
        code_layout.addWidget(self.code_view)
        splitter.addWidget(code_group)
        
        splitter.setSizes([200, 400])
        layout.addWidget(splitter)
    
    def _load_data(self):
        if not self.project or not self.project.base_rom_path:
            return
        
        try:
            rom_path = self.project.base_rom_path
            with open(rom_path, 'rb') as f:
                rom_data = f.read()
            
            cilixes_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "Nucleos_de_Procesamiento", "Cilixes", "fomt"
            )
            
            self.decompiler = NativeProcDecompiler(rom_data, cilixes_dir, self.project)
        except Exception as e:
            self.code_view.setPlainText("// Error al cargar ROM: %s" % str(e))
    
    def load_proc(self, call_id):
        """Carga y decompila un proc/func nativo."""
        if not self.decompiler:
            self._load_data()
            if not self.decompiler:
                return
        
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            pseudo_code, detections = self.decompiler.decompile_pattern(call_id)
            
            # Update code view
            self.code_view.setPlainText(pseudo_code)
            
            # Update detections table
            self.det_table.setRowCount(len(detections))
            type_colors = {
                "Portrait": "#4EC9B0",
                "Flag": "#DCDCAA",
                "Item": "#CE9178",
                "VM_Call": "#569CD6",
                "Engine": "#808080",
                "String": "#CE9178",
                "Check": "#C586C0",
                "Write": "#F44747",
                "Map": "#4FC1FF",
                "EWRAM": "#808080",
                "IWRAM": "#808080",
                "Quantity": "#D7BA7D",
                "Tool": "#E06C75",
                "Food": "#98C379",
                "Item": "#61AFEF",
            }
            
            for row, (dtype, dval, ddesc, daddr) in enumerate(detections):
                items = [
                    QTableWidgetItem(dtype),
                    QTableWidgetItem(dval),
                    QTableWidgetItem(ddesc),
                    QTableWidgetItem("0x%06X" % daddr),
                ]
                color = QColor(type_colors.get(dtype, "#FFFFFF"))
                for item in items:
                    item.setForeground(color)
                    self.det_table.setItem(row, items.index(item), item)
        finally:
            QApplication.restoreOverrideCursor()

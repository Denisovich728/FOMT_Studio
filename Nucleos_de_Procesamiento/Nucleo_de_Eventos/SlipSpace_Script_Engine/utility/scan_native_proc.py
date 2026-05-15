# ============================================================
# FOMT Studio - Suite de Ingenieria Inversa (v3.6.5)
# "Actualizacion La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
# scan_native_proc.py
# ────────────────────────────────────────────────────────────
# Pseudo-decompilador de rutinas nativas (THUMB) del engine.
# Analiza el codigo ARM/THUMB de procs/funcs nativos y genera
# pseudo-codigo legible en estilo SlipSpace Script.
#
# Estas rutinas NO son scripts bytecode (RIFF/SCR), son codigo
# C compilado a THUMB que reside directamente en la ROM.
# Este modulo las traduce a pseudo-script para entender su
# logica sin necesitar Ghidra.
# ============================================================
import struct
import csv
import os
from typing import Dict, List, Tuple, Optional


def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from('<H', data, offset)[0]

def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from('<I', data, offset)[0]


class NativeDisassembler:
    """Desensamblador THUMB basico con traduccion a pseudo-script."""
    
    DISPATCH_TABLE_FOMT = 0x03F900
    DISPATCH_TABLE_MFOMT = None  # TODO: localizar para MFoMT
    
    def __init__(self, rom_data: bytes, lib_path: str = None, flags_path: str = None, 
                 portraits_path: str = None):
        self.rom = rom_data
        self.rom_size = len(rom_data)
        
        # Detectar version
        if b"HARVESTMOGBA" in rom_data[0xA0:0xAC]:
            self.dispatch_table = self.DISPATCH_TABLE_FOMT
            self.table_count = 328
        else:
            self.dispatch_table = self.DISPATCH_TABLE_FOMT  # Fallback
            self.table_count = 328
        
        # Construir tablas de referencia
        self.call_id_to_name: Dict[int, Tuple[str, str, str]] = {}
        self.reverse_dispatch: Dict[int, Tuple[int, str]] = {}
        self.flags: Dict[int, str] = {}
        self.portraits: Dict[int, str] = {}
        
        if lib_path:
            self._load_lib(lib_path)
        if flags_path:
            self._load_flags(flags_path)
        if portraits_path:
            self._load_portraits(portraits_path)
    
    def _load_lib(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if len(row) >= 4:
                    entry_type = row[0].strip()
                    dec_id = int(row[2].strip())
                    name = row[3].strip()
                    args = row[4].strip() if len(row) > 4 else ""
                    self.call_id_to_name[dec_id] = (name, entry_type, args)
        
        # Build reverse dispatch
        for cid in range(self.table_count):
            ptr = read_u32(self.rom, self.dispatch_table + cid * 4)
            if ptr != 0:
                clean = ptr & 0xFFFFFFFE
                name_info = self.call_id_to_name.get(cid, ('Unk_%03X' % cid, 'unk', ''))
                self.reverse_dispatch[clean] = (cid, name_info[0])
                self.reverse_dispatch[ptr] = (cid, name_info[0])
    
    def _load_flags(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) >= 2:
                    flag_id = int(row[0].strip(), 16)
                    flag_name = row[1].strip()
                    self.flags[flag_id] = flag_name
    
    def _load_portraits(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    name = row[0].strip()
                    try:
                        pid = int(row[1].strip(), 16)
                        self.portraits[pid] = name
                    except ValueError:
                        pass
    
    def get_proc_address(self, call_id: int) -> Optional[int]:
        """Obtiene la direccion ROM de un proc/func por su Call ID."""
        if self.dispatch_table is None:
            return None
        ptr_offset = self.dispatch_table + call_id * 4
        if ptr_offset + 4 > self.rom_size:
            return None
        ptr = read_u32(self.rom, ptr_offset)
        if ptr == 0:
            return None
        return (ptr & 0xFFFFFFFE) & 0x01FFFFFF
    
    def decompile_native_proc(self, call_id: int, max_bytes: int = 1024) -> str:
        """
        Pseudo-decompila una rutina nativa a codigo legible.
        
        Args:
            call_id: Call ID del proc/func (decimal)
            max_bytes: Maximo de bytes a analizar
            
        Returns:
            String con pseudo-script legible
        """
        rom_off = self.get_proc_address(call_id)
        if rom_off is None:
            return "// ERROR: No se pudo localizar Call ID %d (0x%03X)" % (call_id, call_id)
        
        name_info = self.call_id_to_name.get(call_id, ('Proc%03X' % call_id, 'proc', ''))
        proc_name = name_info[0]
        
        lines = []
        lines.append("// ================================================================")
        lines.append("// PSEUDO-DECOMPILACION NATIVA: %s" % proc_name)
        lines.append("// Call ID: %d (0x%03X)" % (call_id, call_id))
        lines.append("// ROM Offset: 0x%06X (GBA: 0x%08X)" % (rom_off, rom_off | 0x08000000))
        lines.append("// Tipo: Codigo THUMB nativo (NO bytecode de script)")
        lines.append("// NOTA: Esta es una aproximacion, no una decompilacion exacta.")
        lines.append("// ================================================================")
        lines.append("")
        lines.append("native_proc %s() {" % proc_name)
        
        func_bytes = self.rom[rom_off:rom_off + max_bytes]
        
        # Track register values for constant propagation
        regs = {i: None for i in range(8)}
        indent = 1
        i = 0
        prev_was_cmp = False
        cmp_reg = -1
        cmp_val = -1
        
        while i < len(func_bytes) - 2:
            word = read_u16(func_bytes, i)
            addr = rom_off + i
            
            # ═══ PUSH (function prologue) ═══
            if (word & 0xFF00) == 0xB500:
                rlist = []
                for bit in range(8):
                    if word & (1 << bit):
                        rlist.append('r%d' % bit)
                if word & 0x100:
                    rlist.append('LR')
                lines.append("    " * indent + "// [prologue: save %s]" % ', '.join(rlist))
                i += 2
                continue
            
            # ═══ POP PC (function return) ═══
            if (word & 0xFF00) == 0xBD00:
                lines.append("    " * indent + "return;  // POP {PC}")
                lines.append("}")
                lines.append("")
                break
            
            # ═══ BX LR (return) ═══
            if word == 0x4770:
                lines.append("    " * indent + "return;")
                lines.append("}")
                lines.append("")
                break
            
            # ═══ MOV Rd, #imm ═══
            if (word & 0xF800) == 0x2000:
                rd = (word >> 8) & 7
                imm = word & 0xFF
                regs[rd] = imm
                i += 2
                continue  # Don't emit MOV, track for constant propagation
            
            # ═══ LSL Rd, Rs, #imm ═══
            if (word & 0xF800) == 0x0000 and (word >> 6) & 0x1F != 0:
                rd = word & 7
                rs = (word >> 3) & 7
                imm = (word >> 6) & 0x1F
                if regs[rs] is not None:
                    regs[rd] = regs[rs] << imm
                else:
                    regs[rd] = None
                i += 2
                continue  # Track for propagation
            
            # ═══ LSR Rd, Rs, #imm ═══
            if (word & 0xF800) == 0x0800:
                rd = word & 7
                rs = (word >> 3) & 7
                imm = (word >> 6) & 0x1F
                if regs[rs] is not None:
                    regs[rd] = regs[rs] >> imm
                else:
                    regs[rd] = None
                i += 2
                continue
            
            # ═══ ADD Rd, Rn, Rm (detect state access r5+offset) ═══
            if (word & 0xFE00) == 0x1800:
                rd = word & 7
                rn = (word >> 3) & 7
                rm = (word >> 6) & 7
                # Track computed address for r5+offset patterns
                if rn == 5 and regs[rm] is not None:
                    regs[rd] = ('state_ptr', regs[rm])
                elif rm == 5 and regs[rn] is not None:
                    regs[rd] = ('state_ptr', regs[rn])
                else:
                    regs[rd] = None
                i += 2
                continue
            
            # ═══ ADD Rd, Rn, #imm3 ═══
            if (word & 0xFE00) == 0x1C00:
                rd = word & 7
                rn = (word >> 3) & 7
                imm = (word >> 6) & 7
                regs[rd] = None
                i += 2
                continue
            
            # ═══ SUB Rd, Rn, #imm3 ═══
            if (word & 0xFE00) == 0x1E00:
                rd = word & 7
                rn = (word >> 3) & 7
                imm = (word >> 6) & 7
                regs[rd] = None
                
                # Detect decrement pattern (timer--)
                if imm == 1:
                    lines.append("    " * indent + "// timer decrement")
                i += 2
                continue
            
            # ═══ LDR Rd, [Rn, #imm] ═══
            if (word & 0xF800) == 0x6800:
                rd = word & 7
                rn = (word >> 3) & 7
                imm = ((word >> 6) & 0x1F) * 4
                
                if isinstance(regs.get(rn), tuple) and regs[rn][0] == 'state_ptr':
                    state_off = regs[rn][1] + imm
                    flag_name = self.flags.get(state_off, "field_0x%X" % state_off)
                    lines.append("    " * indent + "// Read: state[0x%X] (%s)" % (state_off, flag_name))
                elif rn == 5:
                    flag_name = self.flags.get(imm, "field_0x%X" % imm)
                    lines.append("    " * indent + "// Read: state[0x%X] (%s)" % (imm, flag_name))
                
                regs[rd] = None
                i += 2
                continue
            
            # ═══ STR Rd, [Rn, #imm] ═══
            if (word & 0xF800) == 0x6000:
                rd = word & 7
                rn = (word >> 3) & 7
                imm = ((word >> 6) & 0x1F) * 4
                
                if isinstance(regs.get(rn), tuple) and regs[rn][0] == 'state_ptr':
                    state_off = regs[rn][1] + imm
                    flag_name = self.flags.get(state_off, "field_0x%X" % state_off)
                    lines.append("    " * indent + "Set_State(0x%X, ...);  // %s" % (state_off, flag_name))
                elif rn == 5:
                    flag_name = self.flags.get(imm, "field_0x%X" % imm)
                    lines.append("    " * indent + "Set_State(0x%X, ...);  // %s" % (imm, flag_name))
                else:
                    lines.append("    " * indent + "// WRITE: [r%d + 0x%X]" % (rn, imm))
                i += 2
                continue
            
            # ═══ CMP Rd, #imm ═══
            if (word & 0xF800) == 0x2800:
                rd = (word >> 8) & 7
                imm = word & 0xFF
                prev_was_cmp = True
                cmp_reg = rd
                cmp_val = imm
                i += 2
                continue
            
            # ═══ CMP Rn, Rm ═══
            if (word & 0xFFC0) == 0x4280:
                prev_was_cmp = True
                cmp_reg = word & 7
                cmp_val = -1
                i += 2
                continue
            
            # ═══ BEQ ═══
            if (word & 0xFF00) == 0xD000:
                ofs = word & 0xFF
                if ofs & 0x80: ofs -= 0x100
                target = rom_off + i + 4 + ofs * 2
                if prev_was_cmp:
                    lines.append("    " * indent + "if (r%d == 0x%X) goto 0x%06X;" % (cmp_reg, cmp_val, target))
                else:
                    lines.append("    " * indent + "if (equal) goto 0x%06X;" % target)
                prev_was_cmp = False
                i += 2
                continue
            
            # ═══ BNE ═══
            if (word & 0xFF00) == 0xD100:
                ofs = word & 0xFF
                if ofs & 0x80: ofs -= 0x100
                target = rom_off + i + 4 + ofs * 2
                if prev_was_cmp:
                    lines.append("    " * indent + "if (r%d != 0x%X) goto 0x%06X;" % (cmp_reg, cmp_val, target))
                else:
                    lines.append("    " * indent + "if (!equal) goto 0x%06X;" % target)
                prev_was_cmp = False
                i += 2
                continue
            
            # ═══ B (unconditional) ═══
            if (word & 0xF800) == 0xE000:
                ofs = word & 0x7FF
                if ofs & 0x400: ofs -= 0x800
                target = rom_off + i + 4 + ofs * 2
                lines.append("    " * indent + "goto 0x%06X;" % target)
                i += 2
                continue
            
            # ═══ BL (function call) ═══
            if (word & 0xF800) == 0xF000 and i + 4 <= len(func_bytes):
                next_word = read_u16(func_bytes, i + 2)
                if (next_word & 0xF800) in (0xF800, 0xE800):
                    ohi = word & 0x7FF
                    olo = next_word & 0x7FF
                    foff = (ohi << 12) | (olo << 1)
                    if foff & 0x400000: foff -= 0x800000
                    target = rom_off + i + 4 + foff
                    gba_target = target | 0x08000000
                    
                    # Lookup in dispatch table
                    match = self.reverse_dispatch.get(gba_target) or \
                            self.reverse_dispatch.get(gba_target & 0xFFFFFFFE)
                    
                    if match:
                        cid, name = match
                        name_info = self.call_id_to_name.get(cid, (name, 'proc', ''))
                        lines.append("    " * indent + "%s();  // VM Call ID %d" % (name, cid))
                    else:
                        # Try to identify by known function addresses
                        rom_target = target & 0x01FFFFFF
                        func_label = self._identify_internal_func(rom_target)
                        lines.append("    " * indent + "%s();  // 0x%06X" % (func_label, rom_target))
                    
                    i += 4
                    prev_was_cmp = False
                    continue
            
            # ═══ LDR Rd, [PC, #imm] (literal pool) ═══
            if (word & 0xF800) == 0x4800:
                rd = (word >> 8) & 7
                imm = (word & 0xFF) * 4
                pool_addr = ((addr + 4) & ~3) + imm
                if pool_addr + 4 <= self.rom_size:
                    pool_val = read_u32(self.rom, pool_addr)
                    regs[rd] = pool_val
                    # Annotate known values
                    if 0x02000000 <= pool_val < 0x03000000:
                        lines.append("    " * indent + "// Load EWRAM ptr: 0x%08X" % pool_val)
                    elif 0x03000000 <= pool_val < 0x04000000:
                        lines.append("    " * indent + "// Load IWRAM ptr: 0x%08X" % pool_val)
                    elif 0x04000000 <= pool_val < 0x05000000:
                        lines.append("    " * indent + "// Load IO register: 0x%08X" % pool_val)
                i += 2
                continue
            
            # ═══ ADD Rd, #imm8 ═══
            if (word & 0xF800) == 0x3000:
                rd = (word >> 8) & 7
                imm = word & 0xFF
                if isinstance(regs[rd], int):
                    regs[rd] += imm
                else:
                    regs[rd] = None
                i += 2
                continue
            
            # ═══ SUB Rd, #imm8 ═══
            if (word & 0xF800) == 0x3800:
                rd = (word >> 8) & 7
                imm = word & 0xFF
                regs[rd] = None
                i += 2
                continue
            
            # ═══ ALU operations ═══
            if (word & 0xFC00) == 0x4000:
                op = (word >> 6) & 0xF
                rd = word & 7
                rs = (word >> 3) & 7
                regs[rd] = None
                i += 2
                continue
            
            # ═══ High register MOV/ADD/CMP/BX ═══
            if (word & 0xFC00) == 0x4400:
                op = (word >> 8) & 3
                rd = (word & 7) | ((word >> 4) & 8)
                rs = (word >> 3) & 0xF
                if op == 3:  # BX
                    lines.append("    " * indent + "// BX r%d (indirect jump)" % rs)
                i += 2
                continue
            
            # ═══ LDRH / STRH ═══
            if (word & 0xF800) == 0x8800:
                i += 2
                continue
            if (word & 0xF800) == 0x8000:
                i += 2
                continue
            
            # ═══ SP-relative load/store ═══
            if (word & 0xF800) == 0x9800 or (word & 0xF800) == 0x9000:
                i += 2
                continue
            
            # ═══ ADD to PC/SP ═══
            if (word & 0xF800) in (0xA000, 0xA800):
                i += 2
                continue
            
            # ═══ SP adjustment ═══
            if (word & 0xFF80) == 0xB000:
                i += 2
                continue
            
            # ═══ LDRB / STRB ═══
            if (word & 0xF800) == 0x7800:
                rd = word & 7
                rn = (word >> 3) & 7
                imm = (word >> 6) & 0x1F
                lines.append("    " * indent + "// Read byte: [r%d + 0x%X]" % (rn, imm))
                regs[rd] = None
                i += 2
                continue
            if (word & 0xF800) == 0x7000:
                rd = word & 7
                rn = (word >> 3) & 7
                imm = (word >> 6) & 0x1F
                lines.append("    " * indent + "// Write byte: [r%d + 0x%X]" % (rn, imm))
                i += 2
                continue
            
            # Default: skip unknown
            i += 2
            prev_was_cmp = False
        
        return "\n".join(lines)
    
    def _identify_internal_func(self, rom_offset: int) -> str:
        """Intenta identificar funciones internas conocidas por su direccion."""
        known = {
            0x04168A: "VM_Yield_Wait_Frame",
            0x045572: "Register_Shipment_Achievement",
            0x045166: "Init_Shop_Display",
        }
        
        # Check exact match
        if rom_offset in known:
            return known[rom_offset]
        
        # Check if it's in the 0x013XXX kernel range
        if 0x013000 <= rom_offset < 0x014100:
            # These are sequential engine subsystem calls
            idx = (rom_offset - 0x013000) // 0x94
            return "Engine_Subsystem_%d" % idx
        
        if 0x00C000 <= rom_offset < 0x00D000:
            return "Kernel_Utility_0x%04X" % (rom_offset & 0xFFFF)
        
        return "Native_0x%06X" % rom_offset
    
    def decompile_all_block(self, start_id: int, end_id: int) -> str:
        """Decompila un bloque de procs consecutivos."""
        result = []
        for cid in range(start_id, end_id + 1):
            if cid in self.call_id_to_name:
                result.append(self.decompile_native_proc(cid))
                result.append("")
        return "\n".join(result)


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python scan_native_proc.py <rom.gba> [--lib Fomt_Lib.csv] "
              "[--flags Fomt_Flags.csv] [--portraits Fomt_Portraits.csv] "
              "[--proc 0x95] [--block 0x8E-0x9F]")
        sys.exit(1)
    
    rom_path = sys.argv[1]
    lib_path = None
    flags_path = None
    portraits_path = None
    target_id = None
    block_range = None
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--lib" and i + 1 < len(sys.argv):
            lib_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--flags" and i + 1 < len(sys.argv):
            flags_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--portraits" and i + 1 < len(sys.argv):
            portraits_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--proc" and i + 1 < len(sys.argv):
            target_id = int(sys.argv[i + 1], 0)
            i += 2
        elif sys.argv[i] == "--block" and i + 1 < len(sys.argv):
            parts = sys.argv[i + 1].split('-')
            block_range = (int(parts[0], 0), int(parts[1], 0))
            i += 2
        else:
            i += 1
    
    with open(rom_path, 'rb') as f:
        rom_data = f.read()
    
    disasm = NativeDisassembler(rom_data, lib_path, flags_path, portraits_path)
    
    if target_id is not None:
        print(disasm.decompile_native_proc(target_id))
    elif block_range:
        print(disasm.decompile_all_block(block_range[0], block_range[1]))
    else:
        # Default: Proc095
        print(disasm.decompile_native_proc(0x95))


if __name__ == "__main__":
    main()

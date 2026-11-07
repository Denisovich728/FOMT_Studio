# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
# agbcc_bridge.py
# ────────────────────────────────────────────────────────────
# Puente de compilación nativa ARM/THUMB usando agbcc 2.9.x
# (GNU C 2.9-arm-000512 thumb-elf) y GNU Binutils.
#
# Permite compilar rutinas de eventos en C nativo para inyectar
# en la ROM y enlazar en la tabla de dispatch de la VM (Call ID).
# ============================================================
import os
import sys
import subprocess
import tempfile
import shutil
from typing import Optional, Tuple, List

DEFAULT_AGBCC_PATHS = [
    r"J:\Laboratorio\FOMT-MATCH-ENGINE\UTILITYS\agbcc\bin\agbcc.exe",
    r"C:\agbcc\bin\agbcc.exe",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "FOMT-MATCH-ENGINE", "UTILITYS", "agbcc", "bin", "agbcc.exe"),
]

DEFAULT_INCLUDE_PATHS = [
    r"J:\Laboratorio\FOMT-MATCH-ENGINE\UTILITYS\agbcc\include",
]


class AgbccBridge:
    """Compilador y ensamblador para rutinas nativas C (THUMB) de FoMT."""

    def __init__(self, agbcc_path: Optional[str] = None, as_path: Optional[str] = None, objcopy_path: Optional[str] = None):
        self.agbcc = self._locate_tool(agbcc_path, "agbcc.exe", DEFAULT_AGBCC_PATHS)
        self.as_bin = self._locate_tool(as_path, "arm-none-eabi-as.exe", [
            r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\arm-none-eabi-as.exe",
        ])
        self.objcopy = self._locate_tool(objcopy_path, "arm-none-eabi-objcopy.exe", [
            r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\arm-none-eabi-objcopy.exe",
        ])
        self.include_dir = self._locate_dir(DEFAULT_INCLUDE_PATHS)

    def _locate_tool(self, explicit_path: Optional[str], binary_name: str, fallback_candidates: List[str]) -> Optional[str]:
        if explicit_path and os.path.isfile(explicit_path):
            return explicit_path
        which_path = shutil.which(binary_name)
        if which_path and os.path.isfile(which_path):
            return which_path
        for candidate in fallback_candidates:
            if os.path.isfile(candidate):
                return candidate
        return None

    def _locate_dir(self, candidates: List[str]) -> Optional[str]:
        for d in candidates:
            if os.path.isdir(d):
                return d
        return None

    def is_available(self) -> bool:
        return bool(self.agbcc and os.path.isfile(self.agbcc))

    def get_version(self) -> str:
        if not self.is_available():
            return "agbcc no disponible"
        try:
            res = subprocess.run([self.agbcc, "-version", "NUL"], capture_output=True, text=True, timeout=5)
            output = (res.stderr + res.stdout).strip()
            return output if output else "agbcc detectado"
        except Exception as e:
            return f"Error ejecutando agbcc: {e}"

    def compile_c_to_asm(self, c_source: str, output_s: str, opt_level: str = "-O2") -> Tuple[bool, str]:
        """Compila código C a ensamblador THUMB (.s) usando agbcc 2.9.x."""
        if not self.is_available():
            return False, "agbcc.exe no fue encontrado."

        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False, encoding="utf-8") as tmp_c:
            tmp_c.write(c_source)
            tmp_c_path = tmp_c.name

        try:
            # agbcc es nativamente un compilador Thumb-ELF
            cmd = [self.agbcc, tmp_c_path, opt_level, "-o", output_s]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                return False, f"agbcc error: {res.stderr}\n{res.stdout}"
            return True, output_s
        finally:
            if os.path.exists(tmp_c_path):
                try:
                    os.remove(tmp_c_path)
                except OSError:
                    pass

    def compile_c_to_bin(self, c_source: str, opt_level: str = "-O2") -> Tuple[bool, Optional[bytes], str]:
        """Compila C a bytes de máquina THUMB directo para inyección en ROM."""
        if not self.is_available():
            return False, None, "agbcc no encontrado"
        if not self.as_bin:
            return False, None, "arm-none-eabi-as no encontrado en el sistema"
        if not self.objcopy:
            return False, None, "arm-none-eabi-objcopy no encontrado en el sistema"

        temp_dir = tempfile.mkdtemp()
        s_path = os.path.join(temp_dir, "temp.s")
        o_path = os.path.join(temp_dir, "temp.o")
        bin_path = os.path.join(temp_dir, "temp.bin")

        try:
            ok, msg = self.compile_c_to_asm(c_source, s_path, opt_level)
            if not ok:
                return False, None, msg

            # Ensamblar .s -> .o
            res_as = subprocess.run([self.as_bin, "-mthumb", s_path, "-o", o_path], capture_output=True, text=True, timeout=10)
            if res_as.returncode != 0:
                return False, None, f"as error: {res_as.stderr}"

            # Extraer binario puro (.o -> .bin)
            res_objcopy = subprocess.run([self.objcopy, "-O", "binary", o_path, bin_path], capture_output=True, text=True, timeout=10)
            if res_objcopy.returncode != 0:
                return False, None, f"objcopy error: {res_objcopy.stderr}"

            with open(bin_path, "rb") as f:
                code_bytes = f.read()

            return True, code_bytes, "Compilación exitosa"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    bridge = AgbccBridge()
    print("Agbcc status:")
    print("  agbcc:   ", bridge.agbcc)
    print("  as:      ", bridge.as_bin)
    print("  objcopy: ", bridge.objcopy)
    print("  version: ", bridge.get_version())

    test_c = """
    int custom_event_proc(int arg1, int arg2) {
        return (arg1 * 2) + (arg2 - 5);
    }
    """
    ok, b, msg = bridge.compile_c_to_bin(test_c)
    print(f"Test compilation: ok={ok}, bytes={len(b) if b else 0}, hex={b.hex(' ') if b else ''}, msg={msg}")

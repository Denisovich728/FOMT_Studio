import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject

project = FoMTProject()
project.step_1_detect_rom("Modded_FoMT3.gba")

slib = project.super_lib

# Verificar map_map
print("=== map_map (Name -> ID) ===")
for name, val in sorted(slib.map_map.items(), key=lambda x: x[1])[:15]:
    print(f"  {name!r} -> {val} (type={type(val).__name__})")

# Verificar map_map_inv
map_map_inv = {v: k for k, v in slib.map_map.items()}
print("\n=== map_map_inv (ID -> Name) ===")
for k in sorted(map_map_inv.keys())[:15]:
    print(f"  {k} (type={type(k).__name__}) -> {map_map_inv[k]!r}")

# Test: ID 5 y 12
print(f"\n=== Lookup test ===")
print(f"  5 in map_map_inv: {5 in map_map_inv}")
print(f"  12 in map_map_inv: {12 in map_map_inv}")
if 5 in map_map_inv:
    print(f"  map_map_inv[5] = {map_map_inv[5]!r}")
if 12 in map_map_inv:
    print(f"  map_map_inv[12] = {map_map_inv[12]!r}")

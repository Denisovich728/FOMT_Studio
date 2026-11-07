# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
"""
sync_user_connections.py
══════════════════════════════════════════════════════════════
Sincroniza y liga las conexiones manuales exportadas desde el
interactivo web (HTML/JS/JSON) con la estructura del motor WorldGraph.
"""

import sys
import os
import json
import re

# Añadir ruta del laboratorio
SYS_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SYS_BASE not in sys.path:
    sys.path.insert(0, SYS_BASE)

from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.world_graph import WorldGraph

DEFAULT_WORLD_JSON = os.path.join(SYS_BASE, "Banco_de_Datos", "world_graph.json")
DEFAULT_USER_JSON = os.path.join(SYS_BASE, "Banco_de_Datos", "user_world_connections.json")


def load_file_content(path: str) -> dict:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # Si es un archivo JS con module.exports o const WORLD_CONNECTIONS_DATA
    if "WORLD_CONNECTIONS_DATA" in text or "module.exports" in text:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]

    return json.loads(text)


def apply_connections(input_path: str = None) -> bool:
    if not input_path:
        # Probar en Banco_de_Datos/user_world_connections.json
        if os.path.exists(DEFAULT_USER_JSON):
            input_path = DEFAULT_USER_JSON
        else:
            print(f"[Sync] No se especificó archivo y no existe {DEFAULT_USER_JSON}")
            return False

    if not os.path.exists(input_path):
        print(f"[Sync] Error: El archivo especificado no existe: {input_path}")
        return False

    try:
        data = load_file_content(input_path)
    except Exception as e:
        print(f"[Sync] Error al parsear JSON/JS en {input_path}: {e}")
        return False

    print(f"[Sync] Cargando grafo base desde: {DEFAULT_WORLD_JSON}")
    graph = WorldGraph.load_from_json(DEFAULT_WORLD_JSON)

    # Sobrescribir nodos y conexiones
    updated_nodes = 0
    updated_warps = 0
    for n_data in data.get("nodes", []):
        mid = int(n_data.get("map_id", 0))
        node = graph.get_node(mid)
        if node:
            if "canvas_x" in n_data: node.canvas_x = float(n_data["canvas_x"])
            if "canvas_y" in n_data: node.canvas_y = float(n_data["canvas_y"])
            if "warps" in n_data:
                for w_data in n_data["warps"]:
                    from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.world_graph import WarpPoint
                    warp = WarpPoint.from_dict(w_data)
                    node.add_warp(warp)
                    updated_warps += 1
            updated_nodes += 1

    conns_added = 0
    for c_data in data.get("connections", []):
        from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.world_graph import WarpConnection
        conn = WarpConnection.from_dict(c_data)
        # Reemplazar existente si tiene el mismo ID
        graph.connections = [c for c in graph.connections if c.conn_id != conn.conn_id]
        graph.add_connection(conn)
        conns_added += 1

    # Guardar tanto en el archivo oficial como en user_world_connections.json
    graph.save_to_json(DEFAULT_WORLD_JSON)
    if input_path != DEFAULT_USER_JSON:
        graph.save_to_json(DEFAULT_USER_JSON)

    print(f"[Sync] Sincronización Exitosa:")
    print(f"       - Mapas actualizados: {updated_nodes}")
    print(f"       - Warps registrados: {updated_warps}")
    print(f"       - Conexiones enlazadas: {conns_added}")
    print(f"       - Guardado en: {DEFAULT_WORLD_JSON}")
    return True


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    success = apply_connections(target)
    sys.exit(0 if success else 1)

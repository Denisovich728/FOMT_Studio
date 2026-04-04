import sys
import os

# Añadir el path del root del repositorio para poder importar los módulos como 'fomt_studio'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Nucleos_de_Procesamiento.Nucleo_de_Eventos.npcs import Npc, NpcParser

class MockProject:
    def __init__(self, is_mfomt=False):
        self.is_mfomt = is_mfomt
    def read_rom(self, offset, size):
        return b'\x00' * size
    def write_patch(self, offset, data):
        pass

def test_roles():
    print("Testing NPC Roles by Name...")
    
    # Test FoMT (Male Protagonist)
    project_fomt = MockProject(is_mfomt=False)
    parser_fomt = NpcParser(project_fomt)
    
    npc_ann = Npc(parser_fomt, 1, 0)
    npc_ann.name_str = "Ann"
    print(f"Ann (FoMT): {npc_ann.role_key}")
    assert npc_ann.role_key == "role_bachelorette"
    
    npc_cliff = Npc(parser_fomt, 2, 0)
    npc_cliff.name_str = "Cliff"
    print(f"Cliff (FoMT): {npc_cliff.role_key}")
    assert npc_cliff.role_key == "role_rival"
    
    # Test MFoMT (Female Protagonist)
    project_mfomt = MockProject(is_mfomt=True)
    parser_mfomt = NpcParser(project_mfomt)
    
    npc_ann_m = Npc(parser_mfomt, 1, 0)
    npc_ann_m.name_str = "Ann"
    print(f"Ann (MFoMT): {npc_ann_m.role_key}")
    assert npc_ann_m.role_key == "role_rival"
    
    npc_cliff_m = Npc(parser_mfomt, 2, 0)
    npc_cliff_m.name_str = "Cliff"
    print(f"Cliff (MFoMT): {npc_cliff_m.role_key}")
    assert npc_cliff_m.role_key == "role_bachelor"
    
    npc_sprite = Npc(parser_mfomt, 3, 0)
    npc_sprite.name_str = "Chef"
    print(f"Chef: {npc_sprite.role_key}")
    assert npc_sprite.role_key == "role_special"
    
    npc_villager = Npc(parser_mfomt, 4, 0)
    npc_villager.name_str = "Thomas"
    print(f"Thomas: {npc_villager.role_key}")
    assert npc_villager.role_key == "role_villager"
    
    print("NPC Roles test passed!")

if __name__ == "__main__":
    try:
        test_roles()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show"
# Desarrollado por: Denisovich728
# ============================================================
import os
import json

DEFAULT_CONFIG = {
    "max_ram_mb": 2048,
    "cpu_p_cores": 1,
    "cpu_e_cores": 0,
    "cpu_threads": 2,
    "default_project_dir": ""
}

class ConfigManager:
    @staticmethod
    def get_config_path() -> str:
        """Obtiene la ruta dinámica y persistente hacia fomt_config.json."""
        try:
            from Banco_de_Datos.Utilidades.rutas import get_config_file_path
            return get_config_file_path()
        except Exception:
            return os.path.join(os.getcwd(), "fomt_config.json")

    @staticmethod
    def load_config():
        config_file = ConfigManager.get_config_path()
        if not os.path.exists(config_file):
            ConfigManager.save_config(DEFAULT_CONFIG)
            return dict(DEFAULT_CONFIG)
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Merge defaults for any missing keys
                merged = dict(DEFAULT_CONFIG)
                merged.update(data)
                return merged
        except Exception as e:
            print(f"Error loading config from {config_file}: {e}. Using defaults.")
            return dict(DEFAULT_CONFIG)

    @staticmethod
    def save_config(config_dict):
        config_file = ConfigManager.get_config_path()
        try:
            cfg_dir = os.path.dirname(config_file)
            if cfg_dir and not os.path.exists(cfg_dir):
                os.makedirs(cfg_dir, exist_ok=True)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=4)
        except Exception as e:
            print(f"Error saving config to {config_file}: {e}")

    @staticmethod
    def get(key):
        cfg = ConfigManager.load_config()
        return cfg.get(key, DEFAULT_CONFIG.get(key))

    @staticmethod
    def set(key, value):
        cfg = ConfigManager.load_config()
        cfg[key] = value
        ConfigManager.save_config(cfg)

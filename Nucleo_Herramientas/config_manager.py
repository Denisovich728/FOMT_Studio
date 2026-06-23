import os
import json

CONFIG_FILE = os.path.join(os.getcwd(), "fomt_config.json")

DEFAULT_CONFIG = {
    "max_ram_mb": 2048,
    "cpu_p_cores": 1,
    "cpu_e_cores": 0,
    "cpu_threads": 2,
    "default_project_dir": ""
}

class ConfigManager:
    @staticmethod
    def load_config():
        if not os.path.exists(CONFIG_FILE):
            ConfigManager.save_config(DEFAULT_CONFIG)
            return dict(DEFAULT_CONFIG)
            
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Merge defaults for any missing keys
                merged = dict(DEFAULT_CONFIG)
                merged.update(data)
                return merged
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
            return dict(DEFAULT_CONFIG)

    @staticmethod
    def save_config(config_dict):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    @staticmethod
    def get(key):
        cfg = ConfigManager.load_config()
        return cfg.get(key, DEFAULT_CONFIG.get(key))

    @staticmethod
    def set(key, value):
        cfg = ConfigManager.load_config()
        cfg[key] = value
        ConfigManager.save_config(cfg)

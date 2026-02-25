import os
import json
from dotenv import load_dotenv
from modules import logger

log = logger.get_logger("QuickAI.config")

load_dotenv()

DATE_DIR = "date"
CONFIG_FILE = os.path.join(DATE_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                log.debug(f"加载配置文件: {CONFIG_FILE}")
                return config_data
        except Exception as e:
            log.error(f"加载配置文件失败: {e}")
    log.debug("使用默认配置")
    return {
        "api_key": os.getenv("QUICKAI_API_KEY", ""),
        "base_url": os.getenv("QUICKAI_BASE_URL", "https://api.deepseek.com"),
        "model": "deepseek-chat",
        "work_directory": "workplace",
        "skills": {}
    }

def save_config(config):
    if not os.path.exists(DATE_DIR):
        os.makedirs(DATE_DIR)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    log.debug(f"保存配置文件: {CONFIG_FILE}")

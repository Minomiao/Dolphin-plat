import os
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, set_key
from modules import logger

log = logger.get_logger("Dolphin.config")

DATE_DIR = "date"
CONFIG_FILE = os.path.join(DATE_DIR, "config.json")
ENV_FILE = os.path.join(DATE_DIR, ".env")

load_dotenv(ENV_FILE)


def _ensure_env_file():
    """如果 .env 不存在且 config.json 存在，自动导入 api_key 和 work_directory 到 .env"""
    env_path = Path(ENV_FILE)
    if env_path.exists():
        return

    api_key = ""
    work_dir = ""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            api_key = config_data.get("api_key", "")
            work_dir = config_data.get("work_directory", "")
        except Exception as e:
            log.warning(f"读取 config.json 失败: {e}")

    try:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.touch()
        if api_key:
            set_key(ENV_FILE, "QUICKAI_API_KEY", api_key)
        if work_dir:
            set_key(ENV_FILE, "QUICKAI_WORK_DIRECTORY", work_dir)
        log.info(f"已自动创建 .env 文件并从 config.json 导入配置")
        load_dotenv(ENV_FILE, override=True)
    except Exception as e:
        log.warning(f"创建 .env 文件失败: {e}")


_ensure_env_file()

MODEL_REGISTRY = {
    "deepseek-v4-flash": {
        "name": "deepseek-v4-flash",
        "description": "DeepSeek V4 Flash (快速模型)",
        "deprecated": False,
    },
    "deepseek-v4-pro": {
        "name": "deepseek-v4-pro",
        "description": "DeepSeek V4 Pro (高性能模型)",
        "deprecated": False,
    },
    "deepseek-chat": {
        "name": "deepseek-chat",
        "description": "DeepSeek Chat (已废弃，对应 deepseek-v4-flash 非思考模式)",
        "deprecated": True,
        "deprecation_date": "2026-07-24",
        "replacement": "deepseek-v4-flash",
    },
    "deepseek-reasoner": {
        "name": "deepseek-reasoner",
        "description": "DeepSeek Reasoner (已废弃，对应 deepseek-v4-flash 思考模式)",
        "deprecated": True,
        "deprecation_date": "2026-07-24",
        "replacement": "deepseek-v4-flash",
    },
    "deepseek-coder": {
        "name": "deepseek-coder",
        "description": "DeepSeek Coder (已废弃)",
        "deprecated": True,
        "deprecation_date": "2026-07-24",
        "replacement": "deepseek-v4-flash",
    },
}

def get_available_models():
    """获取可用模型列表，返回带有废弃信息的模型列表"""
    models = []
    for model_name, model_info in MODEL_REGISTRY.items():
        models.append(model_info)
    return models

def check_model_deprecation(model_name):
    """检查模型是否已废弃或即将废弃，返回警告信息"""
    if model_name not in MODEL_REGISTRY:
        return None
    
    model_info = MODEL_REGISTRY[model_name]
    if not model_info.get("deprecated"):
        return None
    
    deprecation_date_str = model_info.get("deprecation_date", "")
    replacement = model_info.get("replacement", "")
    
    try:
        deprecation_date = datetime.strptime(deprecation_date_str, "%Y-%m-%d")
        now = datetime.now()
        
        if now >= deprecation_date:
            msg = f"模型 '{model_name}' 已于 {deprecation_date_str} 废弃"
        else:
            days_left = (deprecation_date - now).days
            msg = f"模型 '{model_name}' 将于 {deprecation_date_str} 废弃 (剩余 {days_left} 天)"
        
        if replacement:
            msg += f"，请改用 '{replacement}'"
        return msg
    except (ValueError, TypeError):
        return None

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                log.debug(f"加载配置文件: {CONFIG_FILE}")
            config_data.pop("api_key", None)
            config_data.pop("work_directory", None)
            config_data["api_key"] = os.getenv("QUICKAI_API_KEY", "")
            config_data["work_directory"] = os.getenv("QUICKAI_WORK_DIRECTORY", "workplace")
            return config_data
        except Exception as e:
            log.error(f"加载配置文件失败: {e}")
    log.debug("使用默认配置")
    return {
        "api_key": os.getenv("QUICKAI_API_KEY", ""),
        "base_url": os.getenv("QUICKAI_BASE_URL", "https://api.deepseek.com"),
        "model": "deepseek-v4-flash",
        "work_directory": os.getenv("QUICKAI_WORK_DIRECTORY", "workplace"),
        "command_prefix": "/",
        "skills": {}
    }


def save_config(config):
    try:
        api_key = config.get("api_key", "")
        work_dir = config.get("work_directory", "")
        env_path = Path(ENV_FILE)
        if not env_path.exists():
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.touch()
        if api_key:
            set_key(ENV_FILE, "QUICKAI_API_KEY", api_key)
        if work_dir:
            set_key(ENV_FILE, "QUICKAI_WORK_DIRECTORY", work_dir)
        load_dotenv(ENV_FILE, override=True)
    except Exception as e:
        log.warning(f"更新 .env 文件失败: {e}")

    config_to_save = {k: v for k, v in config.items() if k not in ("api_key", "work_directory")}
    if not os.path.exists(DATE_DIR):
        os.makedirs(DATE_DIR)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_to_save, f, ensure_ascii=False, indent=2)
    log.debug(f"保存配置文件: {CONFIG_FILE}")

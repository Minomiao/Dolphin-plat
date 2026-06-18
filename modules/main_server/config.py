import os
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, set_key
from modules.logger import get_logger
from modules import bootstrap as app_paths

from modules.bootstrap import constants

log = get_logger("Dolphin.config")

load_dotenv(app_paths.ENV_FILE)


def _ensure_env_file():
    """如果 .env 不存在且 config.json 存在，自动导入 api_key 和 work_directory 到 .env"""
    env_path = Path(app_paths.ENV_FILE)
    if env_path.exists():
        return

    api_key = ""
    work_dir = ""
    if os.path.exists(app_paths.CONFIG_FILE):
        try:
            with open(app_paths.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            api_key = config_data.get("api_key", "")
            work_dir = config_data.get("work_directory", "")
        except Exception as e:
            log.warning(f"读取 config.json 失败: {e}")

    try:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.touch()
        if api_key:
            set_key(app_paths.ENV_FILE, "QUICKAI_API_KEY", api_key)
        if work_dir:
            set_key(app_paths.ENV_FILE, "QUICKAI_WORK_DIRECTORY", work_dir)
        log.info(f"已自动创建 .env 文件并从 config.json 导入配置")
        load_dotenv(app_paths.ENV_FILE, override=True)
    except Exception as e:
        log.warning(f"创建 .env 文件失败: {e}")


_ensure_env_file()

MODEL_REGISTRY = constants.MODEL_REGISTRY

def get_available_models():
    """获取可用模型列表，返回带有废弃信息的模型列表"""
    models = []
    for model_name, model_info in MODEL_REGISTRY.items():
        models.append(model_info)
    return models

def get_context_window(model_name: str) -> int:
    """获取指定模型的上下文窗口大小。"""
    model_info = MODEL_REGISTRY.get(model_name, {})
    return model_info.get("context_window", 128000)

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

def _get_default_config():
    return {
        "base_url": os.getenv("QUICKAI_BASE_URL", "https://api.deepseek.com"),
        "model": "deepseek-v4-flash",
        "command_prefix": "/",
        "max_tokens": 8192,
        "reasoning": True,
        "skills": {"web_search": False},
        "plugins": {},
        "show_thinking": False,
    }


def load_config():
    defaults = _get_default_config()

    if os.path.exists(app_paths.CONFIG_FILE):
        try:
            with open(app_paths.CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
                log.debug(f"加载配置文件: {app_paths.CONFIG_FILE}")
        except Exception as e:
            log.error(f"加载配置文件失败: {e}")
            file_data = {}
    else:
        file_data = {}

    config_data = dict(defaults)
    config_data.update({k: v for k, v in file_data.items() if k not in ("api_key", "work_directory")})
    config_data["api_key"] = os.getenv("QUICKAI_API_KEY", "")
    config_data["work_directory"] = os.getenv("QUICKAI_WORK_DIRECTORY", "workplace")

    missing_keys = [k for k in defaults if k not in file_data]
    if missing_keys:
        log.info(f"补全缺失的配置键: {missing_keys}")
        save_config(config_data)

    return config_data


def save_config(config):
    try:
        api_key = config.get("api_key", "")
        work_dir = config.get("work_directory", "")
        env_path = Path(app_paths.ENV_FILE)
        if not env_path.exists():
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.touch()
        if api_key:
            set_key(app_paths.ENV_FILE, "QUICKAI_API_KEY", api_key)
        if work_dir:
            set_key(app_paths.ENV_FILE, "QUICKAI_WORK_DIRECTORY", work_dir)
        load_dotenv(app_paths.ENV_FILE, override=True)
    except Exception as e:
        log.warning(f"更新 .env 文件失败: {e}")

    config_to_save = {k: v for k, v in config.items() if k not in ("api_key", "work_directory")}
    if not os.path.exists(app_paths.DATE_DIR):
        os.makedirs(app_paths.DATE_DIR)
    with open(app_paths.CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_to_save, f, ensure_ascii=False, indent=2)
    log.debug(f"保存配置文件: {app_paths.CONFIG_FILE}")

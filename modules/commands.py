import os
import json
from modules import logger

log = logger.get_logger("Dolphin.commands")

DATE_DIR = "date"
COMMANDS_FILE = os.path.join(DATE_DIR, "commands.json")
CONFIG_FILE = os.path.join(DATE_DIR, "config.json")


def _get_default_commands():
    return {
        "commands": {
            "set": {
                "input": "set",
                "description": "进入设置模式"
            },
            "back": {
                "input": "back",
                "description": "返回 (在设置模式中使用)"
            },
            "help": {
                "input": "help",
                "description": "显示此帮助信息"
            },
            "quit": {
                "input": "quit",
                "description": "退出程序"
            },
            "clear": {
                "input": "clear",
                "description": "清空对话历史"
            },
            "new": {
                "input": "new",
                "description": "开启新对话"
            },
            "load": {
                "input": "load",
                "description": "加载旧对话"
            },
            "save_as": {
                "input": "saveas",
                "description": "保存对话"
            },
            "list": {
                "input": "list",
                "description": "查看所有对话"
            },
            "tools": {
                "input": "tools",
                "description": "查看可用工具"
            },
            "skills": {
                "input": "skills",
                "description": "查看可用技能"
            },
            "toggle": {
                "input": "toggle",
                "description": "切换工具启用/禁用状态"
            },
            "skill": {
                "input": "skill",
                "description": "管理技能启用/禁用状态"
            },
            "open": {
                "input": "open",
                "description": "打开/切换工作目录"
            },
            "model": {
                "input": "model",
                "description": "切换模型和配置 API 密钥"
            }
        }
    }


def _get_prefix():
    config_path = CONFIG_FILE
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return config_data.get("command_prefix", "/")
        except Exception as e:
            log.debug(f"读取命令前缀失败: {e}")
    return "/"


def _validate_commands():
    if not os.path.exists(COMMANDS_FILE):
        return

    try:
        with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
            file_data = json.load(f)
    except Exception as e:
        log.warning(f"读取命令文件失败，跳过校验: {e}")
        return

    file_commands = file_data.get("commands", {})
    if not file_commands:
        return

    defaults = _get_default_commands()
    default_commands = defaults["commands"]
    changed = False

    for key, default_info in default_commands.items():
        expected_keyword = default_info["input"]
        if key in file_commands:
            current_keyword = file_commands[key].get("input", "")
            if current_keyword != expected_keyword:
                log.warning(f"命令 '{key}' 关键词异常 (当前: '{current_keyword}', 期望: '{expected_keyword}')，已自动修复")
                file_commands[key]["input"] = expected_keyword
                changed = True
        else:
            file_commands[key] = {
                "input": default_info["input"],
                "description": default_info["description"]
            }
            log.info(f"命令 '{key}' 缺失，已自动添加")
            changed = True

    if changed:
        with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"commands": file_commands}, f, ensure_ascii=False, indent=2)
        log.info("命令文件校验完成，已修复异常项")


_validate_commands()


def load_commands():
    prefix = _get_prefix()
    resolved = {"commands": {}}

    keywords = {}
    if os.path.exists(COMMANDS_FILE):
        try:
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            for key, info in file_data.get("commands", {}).items():
                keywords[key] = info.get("input", key)
        except Exception as e:
            log.warning(f"读取命令文件失败: {e}")

    defaults = _get_default_commands()
    for key, info in defaults["commands"].items():
        keyword = keywords.get(key, info["input"])
        resolved["commands"][key] = {
            "input": prefix + keyword,
            "description": info["description"]
        }
    return resolved


def save_commands(prefix=None):
    if prefix is not None:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except Exception as e:
                log.warning(f"读取配置文件失败: {e}")
                config_data = {}
        else:
            config_data = {}
        config_data["command_prefix"] = prefix
        if not os.path.exists(DATE_DIR):
            os.makedirs(DATE_DIR)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        log.info(f"命令前缀已保存: {prefix}")

    existing_commands = {}
    if os.path.exists(COMMANDS_FILE):
        try:
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            existing_commands = existing_data.get("commands", {})
        except Exception as e:
            log.warning(f"读取现有命令文件失败: {e}")

    defaults = _get_default_commands()
    resolved = {"commands": {}}

    for key, info in defaults["commands"].items():
        resolved["commands"][key] = {
            "input": info["input"],
            "description": info["description"]
        }

    for key, info in existing_commands.items():
        if key not in resolved["commands"]:
            resolved["commands"][key] = info

    if not os.path.exists(DATE_DIR):
        os.makedirs(DATE_DIR)
    with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(resolved, f, ensure_ascii=False, indent=2)
    log.debug(f"已生成帮助文件: {COMMANDS_FILE}")


def get_command(cmd_key):
    prefix = _get_prefix()
    defaults = _get_default_commands()
    cmd_list = defaults.get("commands", {})
    if cmd_key in cmd_list:
        return prefix + cmd_list[cmd_key].get("input", cmd_key)
    return prefix + cmd_key


def get_command_description(cmd_key):
    defaults = _get_default_commands()
    cmd_list = defaults.get("commands", {})
    if cmd_key in cmd_list:
        return cmd_list[cmd_key].get("description", "")
    return ""


def _fuzzy_match_keyword(user_input):
    prefix = _get_prefix()
    if not user_input.startswith(prefix):
        return None
    keyword = user_input[len(prefix):]

    defaults = _get_default_commands()
    candidates = []

    for cmd_key, info in defaults["commands"].items():
        cmd_keyword = info["input"]
        match_count = 0
        for a, b in zip(keyword, cmd_keyword):
            if a == b:
                match_count += 1
            else:
                break

        if match_count > 0:
            candidates.append((match_count, cmd_keyword, cmd_key))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return prefix + candidates[0][1]

import os
import json
from modules import logger

log = logger.get_logger("Dolphin.commands")

DATE_DIR = "date"
COMMANDS_FILE = os.path.join(DATE_DIR, "commands.json")

def load_commands():
    if os.path.exists(COMMANDS_FILE):
        try:
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                commands_data = json.load(f)
                log.debug(f"加载命令文件: {COMMANDS_FILE}")
                return commands_data
        except Exception as e:
            log.error(f"加载命令文件失败: {e}")
    log.debug("使用默认命令配置")
    return {
        "commands": {
            "set": {
                "input": ".set",
                "description": "进入设置模式"
            },
            "back": {
                "input": ".back",
                "description": "返回 (在设置模式中使用)"
            },
            "help": {
                "input": ".help",
                "description": "显示此帮助信息"
            },
            "quit": {
                "input": ".quit",
                "description": "退出程序"
            },
            "clear": {
                "input": ".clear",
                "description": "清空对话历史"
            },
            "new": {
                "input": ".new",
                "description": "开启新对话"
            },
            "load": {
                "input": ".load",
                "description": "加载旧对话"
            },
            "save_as": {
                "input": ".save as",
                "description": "保存对话"
            },
            "list": {
                "input": ".list",
                "description": "查看所有对话"
            },
            "tools": {
                "input": ".tools",
                "description": "查看可用工具"
            },
            "skills": {
                "input": ".skills",
                "description": "查看可用技能"
            },
            "toggle": {
                "input": ".toggle",
                "description": "切换工具启用/禁用状态"
            },
            "skill": {
                "input": ".skill",
                "description": "管理技能启用/禁用状态"
            }
        }
    }

def save_commands(commands):
    if not os.path.exists(DATE_DIR):
        os.makedirs(DATE_DIR)
    with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(commands, f, ensure_ascii=False, indent=2)
    log.debug(f"保存命令文件: {COMMANDS_FILE}")

def get_command(cmd_key):
    commands = load_commands()
    cmd_list = commands.get("commands", {})
    if cmd_key in cmd_list:
        return cmd_list[cmd_key].get("input", f".{cmd_key}")
    return f".{cmd_key}"

def get_command_description(cmd_key):
    commands = load_commands()
    cmd_list = commands.get("commands", {})
    if cmd_key in cmd_list:
        return cmd_list[cmd_key].get("description", "")
    return ""

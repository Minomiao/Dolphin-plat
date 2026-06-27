import random
import secrets
from typing import List, Dict, Any
from colorama import Fore, Style


skill_info = {
    "name": "random_generator",
    "description": "随机数生成器技能，提供各种随机数生成功能",
    "functions": {
        "random_int": {
            "description": "生成指定范围内的随机整数",
            "parameters": {
                "type": "object",
                "properties": {
                    "min": {"type": "integer", "description": "最小值"},
                    "max": {"type": "integer", "description": "最大值"}
                },
                "required": ["min", "max"]
            }
        },
        "random_float": {
            "description": "生成指定范围内的随机浮点数",
            "parameters": {
                "type": "object",
                "properties": {
                    "min": {"type": "number", "description": "最小值"},
                    "max": {"type": "number", "description": "最大值"}
                },
                "required": ["min", "max"]
            }
        },
        "random_choice": {
            "description": "从列表中随机选择一个元素",
            "parameters": {
                "type": "object",
                "properties": {
                    "choices": {"type": "array", "items": {"type": "string"}, "description": "选项列表"}
                },
                "required": ["choices"]
            }
        },
        "random_password": {
            "description": "生成随机密码",
            "parameters": {
                "type": "object",
                "properties": {
                    "length": {"type": "integer", "description": "密码长度，默认为12"},
                    "include_uppercase": {"type": "boolean", "description": "是否包含大写字母，默认为True"},
                    "include_lowercase": {"type": "boolean", "description": "是否包含小写字母，默认为True"},
                    "include_digits": {"type": "boolean", "description": "是否包含数字，默认为True"},
                    "include_special": {"type": "boolean", "description": "是否包含特殊字符，默认为True"}
                },
                "required": []
            }
        }
    }
}


def random_int(min: int, max: int) -> Dict[str, Any]:
    value = random.randint(min, max)
    return {
        "success": True,
        "result": value,
        "user_output": {"label": "Random", "content": f"--int {Fore.LIGHTBLACK_EX}({min}-{max}){Style.RESET_ALL}"}
    }


def random_float(min: float, max: float) -> Dict[str, Any]:
    value = random.uniform(min, max)
    return {
        "success": True,
        "result": value,
        "user_output": {"label": "Random", "content": f"--float {Fore.LIGHTBLACK_EX}({min}-{max}){Style.RESET_ALL}"}
    }


def random_choice(choices: List[str]) -> Dict[str, Any]:
    if not choices:
        return {
            "success": False,
            "error": "选项列表不能为空",
            "user_output": {"label": "Random", "content": f"--choices {Fore.RED}Error{Style.RESET_ALL}"}
        }
    value = random.choice(choices)
    preview = choices[:3]
    options_str = ", ".join(preview)
    if len(choices) > 3:
        options_str += ", ..."
    return {
        "success": True,
        "result": value,
        "user_output": {"label": "Random", "content": f"--choices {Fore.LIGHTBLACK_EX}({options_str}){Style.RESET_ALL}"}
    }


def random_password(
    length: int = 12,
    include_uppercase: bool = True,
    include_lowercase: bool = True,
    include_digits: bool = True,
    include_special: bool = True
) -> Dict[str, Any]:
    uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lowercase = "abcdefghijklmnopqrstuvwxyz"
    digits = "0123456789"
    special = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    charset = ""
    if include_uppercase:
        charset += uppercase
    if include_lowercase:
        charset += lowercase
    if include_digits:
        charset += digits
    if include_special:
        charset += special

    if not charset:
        return {"success": False, "error": "至少需要选择一种字符类型", "user_output": {"label": "Random", "content": f"--password {Fore.LIGHTBLACK_EX}({length}){Style.RESET_ALL} {Fore.RED}Error{Style.RESET_ALL}"}}

    password = []
    for _ in range(length):
        password.append(secrets.choice(charset))

    value = ''.join(password)
    return {
        "success": True,
        "result": value,
        "user_output": {"label": "Random", "content": f"--password {Fore.LIGHTBLACK_EX}({length}){Style.RESET_ALL}"}
    }

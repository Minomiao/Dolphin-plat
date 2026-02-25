import datetime


skill_info = {
    "name": "calculator",
    "description": "计算器技能，提供基本的数学计算功能",
    "functions": {
        "add": {
            "description": "加法运算",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "第一个数字"},
                    "b": {"type": "number", "description": "第二个数字"}
                },
                "required": ["a", "b"]
            }
        },
        "subtract": {
            "description": "减法运算",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "第一个数字"},
                    "b": {"type": "number", "description": "第二个数字"}
                },
                "required": ["a", "b"]
            }
        },
        "multiply": {
            "description": "乘法运算",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "第一个数字"},
                    "b": {"type": "number", "description": "第二个数字"}
                },
                "required": ["a", "b"]
            }
        },
        "divide": {
            "description": "除法运算",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "被除数"},
                    "b": {"type": "number", "description": "除数"}
                },
                "required": ["a", "b"]
            }
        },
        "get_current_time": {
            "description": "获取当前时间",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
}


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("除数不能为零")
    return a / b


def get_current_time() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

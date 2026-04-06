def request_user_input(prompt: str, input_type: str = "text", default_value: str = None, validation_pattern: str = None) -> dict:
    """向用户请求输入信息"""
    # 返回一个特殊结构，指示主程序需要向用户提问
    return {
        "type": "user_input_request",
        "prompt": prompt,
        "input_type": input_type,
        "default_value": default_value,
        "validation_pattern": validation_pattern
    }

def confirm_action(action: str, default: bool = False) -> dict:
    """向用户确认一个操作是否执行"""
    # 返回一个特殊结构，指示主程序需要向用户确认
    return {
        "type": "confirmation_request",
        "action": action,
        "default": default
    }
from modules import request_manager

rm = request_manager.get_request_manager()

def request_user_input(prompt: str, input_type: str = "text", default_value: str = None, validation_pattern: str = None) -> dict:
    """向用户请求输入信息"""
    # 使用请求管理器创建用户输入申请
    return rm.create_user_input_request(prompt, input_type, default_value, validation_pattern)
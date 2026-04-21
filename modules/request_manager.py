import json
from typing import Dict, Any, Optional
from modules import logger

log = logger.get_logger("Dolphin.request_manager")

class RequestType:
    """申请类型枚举"""
    USER_INPUT = "user_input_request"
    CONFIRMATION = "confirmation_request"
    SKILL_CONFIRMATION = "skill_confirmation"
    CONSOLE_OUTPUT = "console_output"

class RequestManager:
    """申请管理器"""
    def __init__(self):
        self.pending_requests = []
        log.info("RequestManager 初始化完成")
    
    def create_user_input_request(self, prompt: str, input_type: str = "text", 
                               default_value: Optional[str] = None, 
                               validation_pattern: Optional[str] = None) -> Dict[str, Any]:
        """创建用户输入申请"""
        request = {
            "type": RequestType.USER_INPUT,
            "prompt": prompt,
            "input_type": input_type,
            "default_value": default_value,
            "validation_pattern": validation_pattern
        }
        self.pending_requests.append(request)
        log.debug(f"创建用户输入申请: {prompt}")
        return request
    
    def create_confirmation_request(self, action: str, default: bool = False) -> Dict[str, Any]:
        """创建操作确认申请"""
        request = {
            "type": RequestType.CONFIRMATION,
            "action": action,
            "default": default
        }
        self.pending_requests.append(request)
        log.debug(f"创建操作确认申请: {action}")
        return request
    
    def create_skill_confirmation(self, message: str, action: str, **kwargs) -> Dict[str, Any]:
        """创建技能确认申请"""
        request = {
            "type": RequestType.SKILL_CONFIRMATION,
            "requires_confirmation": True,
            "message": message,
            "action": action,
            **kwargs
        }
        self.pending_requests.append(request)
        log.debug(f"创建技能确认申请: {action}")
        return request
    
    def create_console_output(self, content: str, level: str = "info", request_type: Optional[str] = None) -> Dict[str, Any]:
        """创建控制台输出申请"""
        request = {
            "type": RequestType.CONSOLE_OUTPUT,
            "content": content,
            "level": level,
            "request_type": request_type
        }
        self.pending_requests.append(request)
        log.debug(f"创建控制台输出: {level}, 申请类型: {request_type}")
        return request
    
    def create_request_output(self, request: Dict[str, Any], content: str, level: str = "info") -> Dict[str, Any]:
        """创建与申请相关的控制台输出"""
        return self.create_console_output(
            content=content,
            level=level,
            request_type=request.get("type")
        )
    
    def get_pending_requests(self) -> list:
        """获取待处理的申请"""
        return self.pending_requests.copy()
    
    def clear_pending_requests(self):
        """清空待处理的申请"""
        self.pending_requests.clear()
        log.debug("清空待处理申请")
    
    def is_request(self, data: Any) -> bool:
        """判断是否为申请"""
        if not isinstance(data, dict):
            return False
        
        # 检查是否为用户输入申请、确认申请或控制台输出
        if data.get("type") in [RequestType.USER_INPUT, RequestType.CONFIRMATION, RequestType.CONSOLE_OUTPUT]:
            return True
        
        # 检查是否为技能确认申请
        if data.get("requires_confirmation"):
            return True
        
        return False
    
    def handle_request(self, request: Dict[str, Any], callback) -> Any:
        """处理申请"""
        if not self.is_request(request):
            return request
        
        request_type = request.get("type")
        
        if request_type == RequestType.USER_INPUT:
            # 处理用户输入申请
            return self._handle_user_input_request(request, callback)
        elif request_type == RequestType.CONFIRMATION:
            # 处理操作确认申请
            return self._handle_confirmation_request(request, callback)
        elif request_type == RequestType.CONSOLE_OUTPUT:
            # 处理控制台输出申请
            return self._handle_console_output(request, callback)
        elif request.get("requires_confirmation"):
            # 处理技能确认申请
            return self._handle_skill_confirmation(request, callback)
        
        return request
    
    def _handle_user_input_request(self, request: Dict[str, Any], callback) -> Any:
        """处理用户输入申请"""
        prompt = request.get('prompt', '')
        log.info(f"处理用户输入申请: {prompt}")
        
        # 创建控制台输出
        output = self.create_request_output(
            request=request,
            content=f"需要输入: {prompt}",
            level="info"
        )
        
        # 这里需要通过回调函数获取用户输入
        # 实际处理逻辑在主程序中
        return request
    
    def _handle_confirmation_request(self, request: Dict[str, Any], callback) -> Any:
        """处理操作确认申请"""
        action = request.get('action', '')
        log.info(f"处理操作确认申请: {action}")
        
        # 创建控制台输出
        output = self.create_request_output(
            request=request,
            content=f"需要确认: {action}",
            level="info"
        )
        
        # 这里需要通过回调函数获取用户确认
        # 实际处理逻辑在主程序中
        return request
    
    def _handle_skill_confirmation(self, request: Dict[str, Any], callback) -> Any:
        """处理技能确认申请"""
        action = request.get('action', '')
        message = request.get('message', '')
        log.info(f"处理技能确认申请: {action}")
        
        # 创建控制台输出
        output = self.create_request_output(
            request=request,
            content=f"需要确认: {message}",
            level="warning"
        )
        
        # 这里需要通过回调函数获取用户确认
        # 实际处理逻辑在主程序中
        return request
    
    def _handle_console_output(self, request: Dict[str, Any], callback) -> Any:
        """处理控制台输出申请"""
        content = request.get('content', '')
        level = request.get('level', 'info')
        log.info(f"处理控制台输出: {level}, 内容: {content}")
        # 这里需要通过回调函数输出内容
        # 实际处理逻辑在主程序中
        return request


# 单例模式
_request_manager = None

def get_request_manager() -> RequestManager:
    global _request_manager
    if _request_manager is None:
        _request_manager = RequestManager()
    return _request_manager

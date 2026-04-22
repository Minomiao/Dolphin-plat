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
    PROMPT_REQUEST = "prompt_request"
    FILE_OPERATION = "file_operation"
    CONFIG_REQUEST = "config_request"
    LOGGER_REQUEST = "logger_request"
    SKILL_REQUEST = "skill_request"

class RequestManager:
    """申请管理器"""
    def __init__(self):
        self.pending_requests = []
        self._prompt_manager = None
        self._file_operation = None
        log.info("RequestManager 初始化完成")
    
    def _get_prompt_manager(self):
        """延迟加载提示词管理器"""
        if self._prompt_manager is None:
            from modules import prompt_manager
            self._prompt_manager = prompt_manager.get_prompt_manager()
        return self._prompt_manager
    
    def _get_file_operation(self):
        """延迟加载文件操作管理器"""
        if self._file_operation is None:
            from modules import file_operation
            self._file_operation = file_operation.get_file_operation()
        return self._file_operation
    
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
    
    def create_prompt_request(self, prompt_key: str, **kwargs) -> Dict[str, Any]:
        """创建提示词请求"""
        request = {
            "type": RequestType.PROMPT_REQUEST,
            "prompt_key": prompt_key,
            "kwargs": kwargs
        }
        self.pending_requests.append(request)
        log.debug(f"创建提示词请求: {prompt_key}")
        return request
    
    def create_file_operation_request(self, operation_type: str, **kwargs) -> Dict[str, Any]:
        """创建文件操作请求"""
        request = {
            "type": RequestType.FILE_OPERATION,
            "operation_type": operation_type,
            **kwargs
        }
        self.pending_requests.append(request)
        log.debug(f"创建文件操作请求: {operation_type}")
        return request
    
    def create_config_request(self, operation_type: str, **kwargs) -> Dict[str, Any]:
        """创建配置请求"""
        request = {
            "type": RequestType.CONFIG_REQUEST,
            "operation_type": operation_type,
            **kwargs
        }
        self.pending_requests.append(request)
        log.debug(f"创建配置请求: {operation_type}")
        return request
    
    def create_logger_request(self, operation_type: str, **kwargs) -> Dict[str, Any]:
        """创建日志请求"""
        request = {
            "type": RequestType.LOGGER_REQUEST,
            "operation_type": operation_type,
            **kwargs
        }
        self.pending_requests.append(request)
        log.debug(f"创建日志请求: {operation_type}")
        return request
    
    def create_skill_request(self, skill_name: str, function_name: str, **kwargs) -> Dict[str, Any]:
        """创建技能请求"""
        request = {
            "type": RequestType.SKILL_REQUEST,
            "skill_name": skill_name,
            "function_name": function_name,
            **kwargs
        }
        self.pending_requests.append(request)
        log.debug(f"创建技能请求: {skill_name}.{function_name}")
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
        
        # 检查是否为用户输入申请、确认申请、控制台输出、提示词请求、文件操作请求、配置请求、日志请求或技能请求
        if data.get("type") in [RequestType.USER_INPUT, RequestType.CONFIRMATION, 
                               RequestType.CONSOLE_OUTPUT, RequestType.PROMPT_REQUEST, 
                               RequestType.FILE_OPERATION, RequestType.CONFIG_REQUEST, 
                               RequestType.LOGGER_REQUEST, RequestType.SKILL_REQUEST]:
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
        elif request_type == RequestType.PROMPT_REQUEST:
            # 处理提示词请求
            return self._handle_prompt_request(request)
        elif request_type == RequestType.FILE_OPERATION:
            # 处理文件操作请求
            return self._handle_file_operation(request)
        elif request_type == RequestType.CONFIG_REQUEST:
            # 处理配置请求
            return self._handle_config_request(request)
        elif request_type == RequestType.LOGGER_REQUEST:
            # 处理日志请求
            return self._handle_logger_request(request)
        elif request_type == RequestType.SKILL_REQUEST:
            # 处理技能请求
            return self._handle_skill_request(request)
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
    
    def _handle_prompt_request(self, request: Dict[str, Any]) -> Any:
        """处理提示词请求"""
        try:
            prompt_key = request.get('prompt_key')
            kwargs = request.get('kwargs', {})
            
            prompt_manager = self._get_prompt_manager()
            result = prompt_manager.handle_request(request)
            
            log.info(f"处理提示词请求: {prompt_key}, 成功: {result.get('success', False)}")
            return result
        except Exception as e:
            log.error(f"处理提示词请求失败: {e}")
            return {"error": str(e)}
    
    def _handle_file_operation(self, request: Dict[str, Any]) -> Any:
        """处理文件操作请求"""
        try:
            operation_type = request.get('operation_type')
            
            file_operation = self._get_file_operation()
            result = file_operation.handle_request(request)
            
            log.info(f"处理文件操作请求: {operation_type}, 成功: {result.get('success', False)}")
            return result
        except Exception as e:
            log.error(f"处理文件操作请求失败: {e}")
            return {"error": str(e)}
    
    def _handle_config_request(self, request: Dict[str, Any]) -> Any:
        """处理配置请求"""
        try:
            operation_type = request.get('operation_type')
            
            from modules import config
            
            if operation_type == 'load':
                result = config.load_config()
            elif operation_type == 'save':
                config_data = request.get('config', {})
                config.save_config(config_data)
                result = {"success": True, "message": "配置已保存"}
            elif operation_type == 'get':
                key = request.get('key')
                config_data = config.load_config()
                result = {"success": True, "value": config_data.get(key)}
            elif operation_type == 'set':
                key = request.get('key')
                value = request.get('value')
                config_data = config.load_config()
                config_data[key] = value
                config.save_config(config_data)
                result = {"success": True, "message": f"配置 {key} 已设置"}
            else:
                result = {"error": f"未知的配置操作: {operation_type}"}
            
            log.info(f"处理配置请求: {operation_type}, 成功: {result.get('success', False)}")
            return result
        except Exception as e:
            log.error(f"处理配置请求失败: {e}")
            return {"error": str(e)}
    
    def _handle_logger_request(self, request: Dict[str, Any]) -> Any:
        """处理日志请求"""
        try:
            operation_type = request.get('operation_type')
            
            from modules import logger
            
            if operation_type == 'get':
                logger_name = request.get('name', 'Dolphin')
                logger_instance = logger.get_logger(logger_name)
                result = {"success": True, "logger": logger_instance}
            elif operation_type == 'log':
                level = request.get('level', 'info')
                message = request.get('message', '')
                logger_name = request.get('name', 'Dolphin')
                logger_instance = logger.get_logger(logger_name)
                
                if level == 'debug':
                    logger_instance.debug(message)
                elif level == 'info':
                    logger_instance.info(message)
                elif level == 'warning':
                    logger_instance.warning(message)
                elif level == 'error':
                    logger_instance.error(message)
                elif level == 'critical':
                    logger_instance.critical(message)
                
                result = {"success": True, "message": "日志已记录"}
            else:
                result = {"error": f"未知的日志操作: {operation_type}"}
            
            log.info(f"处理日志请求: {operation_type}, 成功: {result.get('success', False)}")
            return result
        except Exception as e:
            log.error(f"处理日志请求失败: {e}")
            return {"error": str(e)}
    
    def _handle_skill_request(self, request: Dict[str, Any]) -> Any:
        """处理技能请求"""
        try:
            skill_name = request.get('skill_name')
            function_name = request.get('function_name')
            arguments = request.get('arguments', {})
            
            from modules import skill_manager
            skill_mgr = skill_manager.get_skill_manager()
            
            # 构建工具名称
            tool_name = f"skill_{skill_name}_{function_name}"
            result = skill_mgr.call_tool(tool_name, arguments)
            
            log.info(f"处理技能请求: {skill_name}.{function_name}, 成功: {result.get('success', False) if isinstance(result, dict) else True}")
            return result
        except Exception as e:
            log.error(f"处理技能请求失败: {e}")
            return {"error": str(e)}


# 单例模式
_request_manager = None

def get_request_manager() -> RequestManager:
    global _request_manager
    if _request_manager is None:
        _request_manager = RequestManager()
    return _request_manager

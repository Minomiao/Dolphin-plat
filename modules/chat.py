from openai import OpenAI
from modules import config
from modules import conversation
from modules import mcp_manager
from modules import skill_manager
from modules import plugin_skill_loader
from modules import request_manager
from modules import logger
import json
import asyncio

log = logger.get_logger("Dolphin.chat")

def format_tool_result(result_str):
    """格式化工具返回结果，使其更易读"""
    try:
        result = json.loads(result_str)
        formatted_lines = []
        
        def format_value(key, value, indent=0):
            prefix = "  " * indent
            if isinstance(value, dict):
                formatted_lines.append(f"{prefix}{key}:")
                for k, v in value.items():
                    format_value(k, v, indent + 1)
            elif isinstance(value, list):
                formatted_lines.append(f"{prefix}{key}: [{len(value)} 项]")
                for i, v in enumerate(value):
                    format_value(f"[{i}]", v, indent + 1)
            elif isinstance(value, str):
                if '\n' in value:
                    lines = value.strip().split('\n')
                    formatted_lines.append(f"{prefix}{key}:")
                    for line in lines:
                        formatted_lines.append(f"{prefix}  {line}")
                else:
                    formatted_lines.append(f"{prefix}{key}: {value}")
            elif isinstance(value, bool):
                formatted_lines.append(f"{prefix}{key}: {'是' if value else '否'}")
            elif value is None:
                formatted_lines.append(f"{prefix}{key}: (空)")
            else:
                formatted_lines.append(f"{prefix}{key}: {value}")
        
        if isinstance(result, dict):
            for key, value in result.items():
                format_value(key, value)
        else:
            # 处理非字典类型的返回值
            formatted_lines.append(f"result: {result}")
        
        return '\n'.join(formatted_lines)
    except (json.JSONDecodeError, TypeError):
        return None

class QuickAIChat:
    def __init__(self, model="deepseek-chat", temperature=0.7, max_tokens=None, enable_tools=True, callback=None):
        self.model = model
        self.temperature = temperature
        
        # 从配置中读取 max_tokens，如果没有提供或配置中没有，则使用默认值 8192
        if max_tokens is None:
            config_data = config.load_config()
            max_tokens = config_data.get('max_tokens', 8192)
        
        self.max_tokens = max_tokens
        self.messages = []
        self.enable_tools = enable_tools
        self.callback = callback or (lambda *args, **kwargs: None)
        self.client = OpenAI(
            api_key=config.load_config().get("api_key"),
            base_url=config.load_config().get("base_url", "https://api.deepseek.com")
        )
        self.mcp_mgr = mcp_manager.get_mcp_manager()
        self.skill_mgr = skill_manager.get_skill_manager()
        self.plugin_loader = plugin_skill_loader.get_plugin_skill_loader()
        self.request_manager = request_manager.get_request_manager()
        self.tools = []
        self._update_tools()
        log.info(f"初始化 QuickAIChat: model={model}, temperature={temperature}, max_tokens={max_tokens}, enable_tools={enable_tools}")
    
    def add_message(self, role, content, tool_calls=None, reasoning_content=None):
        message = {"role": role, "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        if reasoning_content:
            message["reasoning_content"] = reasoning_content
        self.messages.append(message)
        log.debug(f"添加消息: role={role}, content_length={len(content)}, tool_calls={len(tool_calls) if tool_calls else 0}")
    
    def _update_tools(self):
        self.tools = []
        if self.enable_tools:
            skill_tools = self.skill_mgr.get_all_tools()
            self.tools.extend(skill_tools)
            
            # 添加插件技能工具
            plugin_tools = self.plugin_loader.get_all_tools()
            self.tools.extend(plugin_tools)
        log.debug(f"更新工具列表: 共 {len(self.tools)} 个工具")
    
    async def _call_callback(self, event_type, data):
        """调用回调函数，支持同步和异步回调"""
        try:
            if asyncio.iscoroutinefunction(self.callback):
                result = await self.callback(event_type, data)
                return result
            else:
                result = self.callback(event_type, data)
                return result
        except Exception as e:
            log.error(f"回调函数执行失败: {e}")
            return None
    
    async def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        log.info(f"执行工具: {tool_name}, 参数: {arguments}")
        try:
            if tool_name.startswith("skill_"):
                result = await self.skill_mgr.call_tool(tool_name, arguments)
            elif tool_name.startswith("plugin_"):
                result = await self.plugin_loader.call_tool(tool_name, arguments)
            elif "_" in tool_name:
                result = await self.mcp_mgr.call_tool(tool_name, arguments)
            else:
                result = {"error": f"未知的工具: {tool_name}"}
            
            # 使用请求管理器处理申请
            if self.request_manager and isinstance(result, dict):
                # 检查是否为申请
                if self.request_manager.is_request(result):
                    log.debug(f"检测到申请: {result.get('type', 'unknown')}")
                    # 处理申请（实际处理逻辑在回调中）
                    result = self.request_manager.handle_request(result, self.callback)
                    
                    # 处理与申请相关的控制台输出
                    pending_requests = self.request_manager.get_pending_requests()
                    for req in pending_requests:
                        if req.get('type') == 'console_output':
                            log.debug(f"处理控制台输出: {req.get('content')}")
                            await self._call_callback('console_output', req)
                    
                    # 清空待处理申请
                    self.request_manager.clear_pending_requests()
            
            if isinstance(result, dict):
                result_str = json.dumps(result, ensure_ascii=False)
            else:
                result_str = str(result)
            log.debug(f"工具执行结果: {result_str}")
            return result_str
        except Exception as e:
            error_msg = json.dumps({"error": str(e)}, ensure_ascii=False)
            log.error(f"工具执行失败: {tool_name}, 错误: {str(e)}")
            return error_msg
    
    async def _execute_tool_sync(self, tool_name: str, arguments: dict) -> str:
        return await self._execute_tool(tool_name, arguments)
    
    async def chat(self, user_input):
        log.info(f"开始聊天 (非流式): 输入长度={len(user_input)}")
        
        # 添加系统提示
        system_message = {
            "role": "system",
            "content": "你是一个智能助手，可以帮助用户创建和修改文件。重要提示：\n1. 创建文件时，如果内容超过 400 行，应该先创建一个基本框架（不超过 400 行），然后使用 modify_file 函数分多次进行修改。\n2. 对于大文件或复杂文件，建议分步骤逐步构建，每次修改范围不要太大。\n3. 这样可以确保操作的稳定性和可追溯性。"
        }
        
        # 检查是否已有系统消息
        has_system_message = any(msg.get("role") == "system" for msg in self.messages)
        
        # 如果没有系统消息，添加到开头
        if not has_system_message:
            self.messages.insert(0, system_message)
        
        self.add_message("user", user_input)
        
        kwargs = {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        if self.tools:
            kwargs["tools"] = self.tools
        
        response = self.client.chat.completions.create(**kwargs)
        assistant_message = response.choices[0].message
        
        reasoning = None
        if hasattr(assistant_message, 'model_extra') and assistant_message.model_extra:
            reasoning = assistant_message.model_extra.get('reasoning_content')
        
        if reasoning:
            log.debug(f"思考过程长度: {len(reasoning)}")
            await self._call_callback('thinking', {
                'content': reasoning
            })
        
        tool_calls = assistant_message.tool_calls
        
        if tool_calls:
            log.info(f"检测到 {len(tool_calls)} 个工具调用")
            tool_calls_list = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in tool_calls
            ]
            self.add_message("assistant", assistant_message.content or "", tool_calls_list, reasoning_content=reasoning)
            
            await self._call_callback('tool_calls', {
                'calls': [
                    {
                        'name': tc.function.name,
                        'arguments': tc.function.arguments
                    }
                    for tc in tool_calls
                ]
            })
            
            tool_responses = []
            for tc in tool_calls:
                tool_name = tc.function.name
                arguments_str = tc.function.arguments
                
                try:
                    arguments = json.loads(arguments_str)
                except json.JSONDecodeError as e:
                    log.error(f"JSON解析失败: {tool_name}, 错误: {str(e)}")
                    log.error(f"原始参数: {arguments_str}")
                    error_result = {
                        "error": "工具调用参数解析失败",
                        "tool_name": tool_name,
                        "reason": "参数可能被截断或格式错误",
                        "details": str(e),
                        "suggestion": "请尝试重新表述您的需求，或者减少单次操作的复杂度"
                    }
                    tool_responses.append({
                        "tool_call_id": tc.id,
                        "role": "tool",
                        "content": json.dumps(error_result, ensure_ascii=False)
                    })
                    log.info(f"工具调用失败: {tool_name}")
                    continue
                
                result = await self._execute_tool_sync(tool_name, arguments)
                
                try:
                    result_dict = json.loads(result)
                    
                    # 检查是否为申请
                    if self.request_manager and self.request_manager.is_request(result_dict):
                        request_type = result_dict.get('type')
                        
                        if request_type == request_manager.RequestType.USER_INPUT:
                            # 处理用户输入申请
                            input_data = {
                                'prompt': result_dict.get('prompt'),
                                'input_type': result_dict.get('input_type'),
                                'default_value': result_dict.get('default_value')
                            }
                            user_input = await self._call_callback('user_input_required', input_data)
                            result = json.dumps({"success": True, "input": user_input}, ensure_ascii=False)
                        elif request_type == request_manager.RequestType.CONFIRMATION:
                            # 处理操作确认申请
                            confirmation_data = {
                                'action': result_dict.get('action'),
                                'default': result_dict.get('default')
                            }
                            confirm = await self._call_callback('confirmation_required', confirmation_data)
                            result = json.dumps({"success": True, "confirmed": confirm == 'y'}, ensure_ascii=False)
                        elif result_dict.get("requires_confirmation"):
                            # 处理技能确认申请
                            confirmation_data = {
                                'action': result_dict.get('action', 'unknown'),
                                'script_preview': result_dict.get('script_preview'),
                                'file_path': result_dict.get('file_path'),
                                'work_directory': result_dict.get('work_directory'),
                                'error': result_dict.get('error')
                            }
                            confirm = await self._call_callback('confirmation_required', confirmation_data)
                            if confirm != 'y':
                                tool_responses.append({
                                    "tool_call_id": tc.id,
                                    "role": "tool",
                                    "content": json.dumps({"error": "用户取消操作"}, ensure_ascii=False)
                                })
                                log.info(f"用户取消操作: {tool_name}")
                                await self._call_callback('operation_canceled', {})
                                continue
                            else:
                                log.info(f"用户确认操作: {tool_name}")
                                await self._call_callback('operation_confirmed', {})
                                # 直接执行脚本（如果是 PowerShell 脚本）
                                if result_dict.get('action') == 'run_powershell_script' and result_dict.get('script'):
                                    import subprocess
                                    from pathlib import Path
                                    import os
                                    import sys
                                    
                                    # 获取工作目录
                                    try:
                                        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                                        from modules import config
                                        work_dir = config.load_config().get('work_directory', 'workplace')
                                    except:
                                        work_dir = 'workplace'
                                    
                                    work_path = Path(work_dir).resolve()
                                    if not work_path.exists():
                                        work_path.mkdir(parents=True, exist_ok=True)
                                    
                                    script = result_dict.get('script')
                                    script_length = len(script)
                                    
                                    try:
                                        # 执行 PowerShell 脚本
                                        ps_result = subprocess.run(
                                            ['powershell', '-Command', script],
                                            capture_output=True,
                                            text=True,
                                            timeout=30,
                                            encoding='utf-8',
                                            errors='ignore',
                                            cwd=str(work_path)
                                        )
                                        
                                        stdout = ps_result.stdout or ""
                                        stderr = ps_result.stderr or ""
                                        
                                        # 处理输出截断
                                        MAX_OUTPUT_LENGTH = 50000
                                        if len(stdout) > MAX_OUTPUT_LENGTH:
                                            stdout = stdout[:MAX_OUTPUT_LENGTH] + f"\n... (输出已截断，共 {len(ps_result.stdout)} 字符)"
                                        if len(stderr) > MAX_OUTPUT_LENGTH:
                                            stderr = stderr[:MAX_OUTPUT_LENGTH] + f"\n... (错误输出已截断，共 {len(ps_result.stderr)} 字符)"
                                        
                                        result = json.dumps({
                                            "success": True,
                                            "return_code": ps_result.returncode,
                                            "stdout": stdout,
                                            "stderr": stderr,
                                            "script_length": script_length,
                                            "message": f"脚本执行完成，返回码: {ps_result.returncode}"
                                        }, ensure_ascii=False)
                                    except subprocess.TimeoutExpired:
                                        result = json.dumps({
                                            "success": False,
                                            "error": "脚本执行超时（30 秒）",
                                            "message": "脚本执行超时"
                                        }, ensure_ascii=False)
                                    except Exception as e:
                                        result = json.dumps({
                                            "error": f"脚本执行失败: {str(e)}",
                                            "message": "脚本执行失败"
                                        }, ensure_ascii=False)
                                else:
                                    # 其他需要确认的操作，使用原有的确认机制
                                    if isinstance(arguments, dict):
                                        arguments['confirmed'] = True
                                    else:
                                        arguments = {'confirmed': True}
                                    result = await self._execute_tool_sync(tool_name, arguments)
                except:
                    pass
                
                tool_responses.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": result
                })
                
                formatted = format_tool_result(result)
                await self._call_callback('tool_result', {
                    'raw': result,
                    'formatted': formatted
                })
            
            self.messages.extend(tool_responses)
            
            kwargs["messages"] = self.messages
            response = self.client.chat.completions.create(**kwargs)
            assistant_message = response.choices[0].message
        
        final_content = assistant_message.content or ""
        log.info(f"聊天完成: 响应长度={len(final_content)}")
        self.add_message("assistant", final_content)
        return final_content
    
    async def chat_stream(self, user_input):
        log.info(f"开始聊天 (流式): 输入长度={len(user_input)}")
        self.add_message("user", user_input)
        
        system_message = "你是一个AI助手。当用户要求完成任务时，必须确保完成所有必要的步骤，不要中途停止。重要限制：每次只能调用一个工具（skill），等待工具返回结果后，再决定是否需要调用下一个工具。不要同时调用多个工具。重要：在每次回答结束时，必须至少给出一个正常的输出（除了思考过程和工具调用之外的内容），让用户知道发生了什么。始终以完整的回答结束对话。"
        
        kwargs = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_message}] + self.messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True
        }
        
        if self.tools:
            kwargs["tools"] = self.tools
        
        stream = self.client.chat.completions.create(**kwargs)
        full_response = ""
        full_reasoning = ""
        tool_calls_buffer = {}
        reasoning_started = False
        has_tool_calls = False
        response_started = False
        
        for chunk in stream:
            delta = chunk.choices[0].delta
            
            if hasattr(delta, 'model_extra') and delta.model_extra:
                reasoning = delta.model_extra.get('reasoning_content')
                if reasoning:
                    if not reasoning_started:
                        await self._call_callback('thinking_start', {})
                        reasoning_started = True
                    full_reasoning += reasoning
                    await self._call_callback('thinking_chunk', {
                        'content': reasoning
                    })
            
            if delta.content:
                content = delta.content
                full_response += content
                if not response_started:
                    response_started = True
            
            if delta.tool_calls:
                has_tool_calls = True
                for tc in delta.tool_calls:
                    if tc.index not in tool_calls_buffer:
                        tool_calls_buffer[tc.index] = {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name if tc.function.name else "",
                                "arguments": tc.function.arguments if tc.function.arguments else ""
                            }
                        }
                    else:
                        if tc.function.name:
                            tool_calls_buffer[tc.index]["function"]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_buffer[tc.index]["function"]["arguments"] += tc.function.arguments
        
        if reasoning_started:
            log.debug(f"思考过程长度: {len(full_reasoning)}")
            await self._call_callback('thinking_end', {})
        
        if response_started:
            await self._call_callback('response', {
                'content': full_response
            })
        
        if not has_tool_calls:
            self.add_message("assistant", full_response, reasoning_content=full_reasoning)
        
        if has_tool_calls and tool_calls_buffer:
            tool_calls = list(tool_calls_buffer.values())
            log.info(f"检测到 {len(tool_calls)} 个工具调用")
            self.add_message("assistant", full_response or "", tool_calls, reasoning_content=full_reasoning)
            
            await self._call_callback('tool_calls', {
                'calls': [
                    {
                        'name': tc['function']['name'],
                        'arguments': tc['function']['arguments']
                    }
                    for tc in tool_calls
                ]
            })
            
            tool_responses = []
            for tc in tool_calls:
                tool_name = tc['function']['name']
                try:
                    arguments = json.loads(tc['function']['arguments'])
                except:
                    arguments = {}
                
                result = await self._execute_tool_sync(tool_name, arguments)
                
                try:
                    result_dict = json.loads(result)
                    
                    # 检查是否为申请
                    if self.request_manager and self.request_manager.is_request(result_dict):
                        request_type = result_dict.get('type')
                        
                        if request_type == request_manager.RequestType.USER_INPUT:
                            # 处理用户输入申请
                            input_data = {
                                'prompt': result_dict.get('prompt'),
                                'input_type': result_dict.get('input_type'),
                                'default_value': result_dict.get('default_value')
                            }
                            user_input = await self._call_callback('user_input_required', input_data)
                            result = json.dumps({"success": True, "input": user_input}, ensure_ascii=False)
                        elif request_type == request_manager.RequestType.CONFIRMATION:
                            # 处理操作确认申请
                            confirmation_data = {
                                'action': result_dict.get('action'),
                                'default': result_dict.get('default')
                            }
                            confirm = await self._call_callback('confirmation_required', confirmation_data)
                            result = json.dumps({"success": True, "confirmed": confirm == 'y'}, ensure_ascii=False)
                        elif result_dict.get("requires_confirmation"):
                            # 处理技能确认申请
                            confirmation_data = {
                                'action': result_dict.get('action', 'unknown'),
                                'script_preview': result_dict.get('script_preview'),
                                'file_path': result_dict.get('file_path'),
                                'work_directory': result_dict.get('work_directory'),
                                'error': result_dict.get('error')
                            }
                            confirm = await self._call_callback('confirmation_required', confirmation_data)
                            if confirm != 'y':
                                tool_responses.append({
                                    "tool_call_id": tc['id'],
                                    "role": "tool",
                                    "content": json.dumps({"error": "用户取消操作"}, ensure_ascii=False)
                                })
                                log.info(f"用户取消操作: {tool_name}")
                                await self._call_callback('operation_canceled', {})
                                continue
                            else:
                                log.info(f"用户确认操作: {tool_name}")
                                await self._call_callback('operation_confirmed', {})
                                # 直接执行脚本（如果是 PowerShell 脚本）
                                if result_dict.get('action') == 'run_powershell_script' and result_dict.get('script'):
                                    import subprocess
                                    from pathlib import Path
                                    import os
                                    import sys
                                    
                                    # 获取工作目录
                                    try:
                                        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                                        from modules import config
                                        work_dir = config.load_config().get('work_directory', 'workplace')
                                    except:
                                        work_dir = 'workplace'
                                    
                                    work_path = Path(work_dir).resolve()
                                    if not work_path.exists():
                                        work_path.mkdir(parents=True, exist_ok=True)
                                    
                                    script = result_dict.get('script')
                                    script_length = len(script)
                                    
                                    try:
                                        # 执行 PowerShell 脚本
                                        ps_result = subprocess.run(
                                            ['powershell', '-Command', script],
                                            capture_output=True,
                                            text=True,
                                            timeout=30,
                                            encoding='utf-8',
                                            errors='ignore',
                                            cwd=str(work_path)
                                        )
                                        
                                        stdout = ps_result.stdout or ""
                                        stderr = ps_result.stderr or ""
                                        
                                        # 处理输出截断
                                        MAX_OUTPUT_LENGTH = 50000
                                        if len(stdout) > MAX_OUTPUT_LENGTH:
                                            stdout = stdout[:MAX_OUTPUT_LENGTH] + f"\n... (输出已截断，共 {len(ps_result.stdout)} 字符)"
                                        if len(stderr) > MAX_OUTPUT_LENGTH:
                                            stderr = stderr[:MAX_OUTPUT_LENGTH] + f"\n... (错误输出已截断，共 {len(ps_result.stderr)} 字符)"
                                        
                                        result = json.dumps({
                                            "success": True,
                                            "return_code": ps_result.returncode,
                                            "stdout": stdout,
                                            "stderr": stderr,
                                            "script_length": script_length,
                                            "message": f"脚本执行完成，返回码: {ps_result.returncode}"
                                        }, ensure_ascii=False)
                                    except subprocess.TimeoutExpired:
                                        result = json.dumps({
                                            "success": False,
                                            "error": "脚本执行超时（30 秒）",
                                            "message": "脚本执行超时"
                                        }, ensure_ascii=False)
                                    except Exception as e:
                                        result = json.dumps({
                                            "error": f"脚本执行失败: {str(e)}",
                                            "message": "脚本执行失败"
                                        }, ensure_ascii=False)
                                else:
                                    # 其他需要确认的操作，使用原有的确认机制
                                    if isinstance(arguments, dict):
                                        arguments['confirmed'] = True
                                    else:
                                        arguments = {'confirmed': True}
                                    result = await self._execute_tool_sync(tool_name, arguments)
                except:
                    pass
                
                tool_responses.append({
                    "tool_call_id": tc['id'],
                    "role": "tool",
                    "content": result
                })
                
                formatted = format_tool_result(result)
                await self._call_callback('tool_result', {
                    'raw': result,
                    'formatted': formatted
                })
            
            self.messages.extend(tool_responses)
            
            max_iterations = 10
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                log.debug(f"工具调用迭代 {iteration}/{max_iterations}")
                
                kwargs["messages"] = [{"role": "system", "content": system_message}] + self.messages
                kwargs["stream"] = True
                stream = self.client.chat.completions.create(**kwargs)
                
                full_response = ""
                full_reasoning = ""
                reasoning_started = False
                response_started = False
                tool_calls_buffer = {}
                has_tool_calls = False
                
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    
                    if hasattr(delta, 'model_extra') and delta.model_extra:
                        reasoning = delta.model_extra.get('reasoning_content')
                        if reasoning:
                            if not reasoning_started:
                                await self._call_callback('thinking_start', {})
                                reasoning_started = True
                            full_reasoning += reasoning
                            await self._call_callback('thinking_chunk', {
                                'content': reasoning
                            })
                    
                    if delta.content:
                        content = delta.content
                        full_response += content
                        if not response_started:
                            response_started = True
                    
                    if delta.tool_calls:
                        has_tool_calls = True
                        for tc in delta.tool_calls:
                            if tc.index not in tool_calls_buffer:
                                tool_calls_buffer[tc.index] = {
                                    "id": tc.id,
                                    "type": tc.type,
                                    "function": {
                                        "name": tc.function.name if tc.function.name else "",
                                        "arguments": tc.function.arguments if tc.function.arguments else ""
                                    }
                                }
                            else:
                                if tc.function.name:
                                    tool_calls_buffer[tc.index]["function"]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls_buffer[tc.index]["function"]["arguments"] += tc.function.arguments
                
                if reasoning_started:
                    await self._call_callback('thinking_end', {})
                
                if response_started:
                    await self._call_callback('response', {
                        'content': full_response
                    })
                
                if has_tool_calls and tool_calls_buffer:
                    tool_calls = list(tool_calls_buffer.values())
                    log.info(f"迭代 {iteration}: 检测到 {len(tool_calls)} 个工具调用")
                    self.add_message("assistant", full_response or "", tool_calls, reasoning_content=full_reasoning)
                    
                    await self._call_callback('tool_calls', {
                        'calls': [
                            {
                                'name': tc['function']['name'],
                                'arguments': tc['function']['arguments']
                            }
                            for tc in tool_calls
                        ]
                    })
                    
                    tool_responses = []
                    for tc in tool_calls:
                        tool_name = tc['function']['name']
                        try:
                            arguments = json.loads(tc['function']['arguments'])
                        except:
                            arguments = {}
                        
                        result = await self._execute_tool_sync(tool_name, arguments)
                        
                        try:
                            result_dict = json.loads(result)
                            
                            # 检查是否为申请
                            if self.request_manager and self.request_manager.is_request(result_dict):
                                request_type = result_dict.get('type')
                                
                                if request_type == request_manager.RequestType.USER_INPUT:
                                    # 处理用户输入申请
                                    input_data = {
                                        'prompt': result_dict.get('prompt'),
                                        'input_type': result_dict.get('input_type'),
                                        'default_value': result_dict.get('default_value')
                                    }
                                    user_input = await self._call_callback('user_input_required', input_data)
                                    result = json.dumps({"success": True, "input": user_input}, ensure_ascii=False)
                                elif request_type == request_manager.RequestType.CONFIRMATION:
                                    # 处理操作确认申请
                                    confirmation_data = {
                                        'action': result_dict.get('action'),
                                        'default': result_dict.get('default')
                                    }
                                    confirm = await self._call_callback('confirmation_required', confirmation_data)
                                    result = json.dumps({"success": True, "confirmed": confirm == 'y'}, ensure_ascii=False)
                                elif result_dict.get("requires_confirmation"):
                                    # 处理技能确认申请
                                    confirmation_data = {
                                        'action': result_dict.get('action', 'unknown'),
                                        'script_preview': result_dict.get('script_preview'),
                                        'file_path': result_dict.get('file_path'),
                                        'work_directory': result_dict.get('work_directory'),
                                        'error': result_dict.get('error')
                                    }
                                    confirm = await self._call_callback('confirmation_required', confirmation_data)
                                    if confirm != 'y':
                                        tool_responses.append({
                                            "tool_call_id": tc['id'],
                                            "role": "tool",
                                            "content": json.dumps({"error": "用户取消操作"}, ensure_ascii=False)
                                        })
                                        log.info(f"用户取消操作: {tool_name}")
                                        await self._call_callback('operation_canceled', {})
                                        continue
                                    else:
                                        log.info(f"用户确认操作: {tool_name}")
                                        await self._call_callback('operation_confirmed', {})
                                        # 直接执行脚本（如果是 PowerShell 脚本）
                                        if result_dict.get('action') == 'run_powershell_script' and result_dict.get('script'):
                                            import subprocess
                                            from pathlib import Path
                                            import os
                                            import sys
                                            
                                            # 获取工作目录
                                            try:
                                                sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                                                from modules import config
                                                work_dir = config.load_config().get('work_directory', 'workplace')
                                            except:
                                                work_dir = 'workplace'
                                            
                                            work_path = Path(work_dir).resolve()
                                            if not work_path.exists():
                                                work_path.mkdir(parents=True, exist_ok=True)
                                            
                                            script = result_dict.get('script')
                                            script_length = len(script)
                                            
                                            try:
                                                # 执行 PowerShell 脚本
                                                ps_result = subprocess.run(
                                                    ['powershell', '-Command', script],
                                                    capture_output=True,
                                                    text=True,
                                                    timeout=30,
                                                    encoding='utf-8',
                                                    errors='ignore',
                                                    cwd=str(work_path)
                                                )
                                                
                                                stdout = ps_result.stdout or ""
                                                stderr = ps_result.stderr or ""
                                                
                                                # 处理输出截断
                                                MAX_OUTPUT_LENGTH = 50000
                                                if len(stdout) > MAX_OUTPUT_LENGTH:
                                                    stdout = stdout[:MAX_OUTPUT_LENGTH] + f"\n... (输出已截断，共 {len(ps_result.stdout)} 字符)"
                                                if len(stderr) > MAX_OUTPUT_LENGTH:
                                                    stderr = stderr[:MAX_OUTPUT_LENGTH] + f"\n... (错误输出已截断，共 {len(ps_result.stderr)} 字符)"
                                                
                                                result = json.dumps({
                                                    "success": True,
                                                    "return_code": ps_result.returncode,
                                                    "stdout": stdout,
                                                    "stderr": stderr,
                                                    "script_length": script_length,
                                                    "message": f"脚本执行完成，返回码: {ps_result.returncode}"
                                                }, ensure_ascii=False)
                                            except subprocess.TimeoutExpired:
                                                result = json.dumps({
                                                    "success": False,
                                                    "error": "脚本执行超时（30 秒）",
                                                    "message": "脚本执行超时"
                                                }, ensure_ascii=False)
                                            except Exception as e:
                                                result = json.dumps({
                                                    "error": f"脚本执行失败: {str(e)}",
                                                    "message": "脚本执行失败"
                                                }, ensure_ascii=False)
                                        else:
                                            # 其他需要确认的操作，使用原有的确认机制
                                            if isinstance(arguments, dict):
                                                arguments['confirmed'] = True
                                            else:
                                                arguments = {'confirmed': True}
                                            result = await self._execute_tool_sync(tool_name, arguments)
                        except:
                            pass
                        
                        tool_responses.append({
                            "tool_call_id": tc['id'],
                            "role": "tool",
                            "content": result
                        })
                        
                        formatted = format_tool_result(result)
                        await self._call_callback('tool_result', {
                            'raw': result,
                            'formatted': formatted
                        })
                    
                    self.messages.extend(tool_responses)
                    continue
                else:
                    break
            
            if iteration >= max_iterations:
                log.warning(f"达到最大工具调用迭代次数: {max_iterations}")
                await self._call_callback('max_iterations_reached', {
                    'iterations': max_iterations
                })
                if not full_response:
                    full_response = f"已达到最大工具调用迭代次数 ({max_iterations} 次)。如果任务未完成，请继续对话以继续执行。"
        
        log.info(f"流式聊天完成: 响应长度={len(full_response)}")
        return full_response
    
    def clear_history(self):
        self.messages = []
    
    def save_conversation(self, name):
        conversation.save_conversation(self.messages, name)
    
    def load_conversation(self, name):
        messages = conversation.load_conversation(name)
        if messages:
            self.messages = messages
            return True
        return False
    
    def list_conversations(self):
        return conversation.list_conversations()
    
    def list_available_tools(self):
        if not self.enable_tools:
            return []
        
        tools_info = []
        for tool in self.tools:
            tool_name = tool["function"]["name"]
            tool_desc = tool["function"]["description"]
            tools_info.append({
                "name": tool_name,
                "description": tool_desc
            })
        return tools_info
    
    def enable_tool(self, enabled: bool):
        self.enable_tools = enabled
        self._update_tools()
    
    def list_skills(self):
        # 合并普通技能和插件技能
        skills = self.skill_mgr.list_skills()
        plugin_skills = self.plugin_loader.list_skills()
        skills.extend(plugin_skills)
        return skills

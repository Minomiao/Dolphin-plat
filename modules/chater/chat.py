from openai import OpenAI
from colorama import Fore, Style
from modules.main_server import config
from modules.chater import conversation
from modules.chater.context import ContextManager
from modules.loader import mcp_manager
from modules.loader import skill_manager
from modules.loader import plugin_skill_loader
from modules.main_server.middleware import request_manager
from modules.logger import get_logger, log_thinking
import json
import asyncio
import uuid

log = get_logger("Dolphin.chat")

def format_tool_result(result_str):
    """格式化工具返回结果，使其更易读"""
    try:
        result = json.loads(result_str)
        formatted_lines = []
        
        def format_value(key, value, indent=0):
            prefix = "  " * indent
            match value:
                case dict():
                    formatted_lines.append(f"{prefix}{key}:")
                    for k, v in value.items():
                        format_value(k, v, indent + 1)
                case list():
                    formatted_lines.append(f"{prefix}{key}: [{len(value)} 项]")
                    for i, v in enumerate(value):
                        format_value(f"[{i}]", v, indent + 1)
                case str():
                    if '\n' in value:
                        lines = value.strip().split('\n')
                        formatted_lines.append(f"{prefix}{key}:")
                        for line in lines:
                            formatted_lines.append(f"{prefix}  {line}")
                    else:
                        formatted_lines.append(f"{prefix}{key}: {value}")
                case bool():
                    formatted_lines.append(f"{prefix}{key}: {'是' if value else '否'}")
                case None:
                    formatted_lines.append(f"{prefix}{key}: (空)")
                case _:
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
    def __init__(self, model="deepseek-v4-flash", temperature=0.7, max_tokens=None, enable_tools=True, callback=None):
        self.model = model
        self.temperature = temperature
        
        # 从配置中读取 max_tokens，如果没有提供或配置中没有，则使用默认值 8192
        if max_tokens is None:
            config_data = config.load_config()
            max_tokens = config_data.get('max_tokens', 8192)
        
        self.max_tokens = max_tokens
        self.messages = []
        self.context = ContextManager(self.get_system_prompt)
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
        
        # 导入备份管理器
        from modules.functions import backup_manager
        self.backup_mgr = backup_manager.get_backup_manager()
        
        # 生成对话ID
        self.dialog_id = str(uuid.uuid4())
        log.info(f"生成对话ID: {self.dialog_id}")
        
        # 设置备份管理器的对话ID
        if self.backup_mgr:
            self.backup_mgr.set_current_dialog_id(self.dialog_id)
        
        self.tools = []
        self._update_tools()
        self._save_dir_id = None
        self._save_conv_id = None
        
        # 工具分发链: (谓词, 处理器) 对
        self._tool_dispatch = [
            (lambda n: n.startswith("skill_"), self.skill_mgr.call_tool),
            (lambda n: n.startswith("plugin_"), self.plugin_loader.call_tool),
            (lambda n: "_" in n, self.mcp_mgr.call_tool),
        ]

        # 确认请求分发链: (谓词, 处理器) 对
        rm_type = request_manager.RequestType
        self._confirmation_dispatch = [
            (lambda d, t: t == rm_type.USER_INPUT, self._handle_user_input_request),
            (lambda d, t: t == rm_type.CONFIRMATION, self._handle_confirmation_request),
            (lambda d, t: d.get("requires_confirmation"), self._handle_requires_confirmation_request),
        ]
        
        # 从配置读取默认工作目录
        self.default_work_directory = config.load_config().get('work_directory', 'workplace')
        self.current_work_directory = self.default_work_directory
        from modules.main_server.middleware import request_manager as rm
        rm.reset_ai_work_directory()
        
        log.info(f"初始化 QuickAIChat: model={model}, temperature={temperature}, max_tokens={max_tokens}, enable_tools={enable_tools}")
    
    def add_message(self, role, content, tool_calls=None, reasoning_content=None):
        message = {"role": role, "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        if reasoning_content:
            message["reasoning_content"] = reasoning_content
        self.messages.append(message)
        log.debug(f"添加消息: role={role}, content_length={len(content)}, tool_calls={len(tool_calls) if tool_calls else 0}")
        self._auto_save()

    def set_save_target(self, dir_id, conv_id):
        self._save_dir_id = dir_id
        self._save_conv_id = conv_id
        log.debug(f"设置保存目标: dir={dir_id}, conv={conv_id}")

    def _auto_save(self):
        if self._save_dir_id and self._save_conv_id:
            conversation.save_conversation(self.messages, self._save_dir_id, self._save_conv_id)
            log.debug(f"实时保存: {len(self.messages)} 条消息")
    
    def _update_tools(self):
        self.tools = []
        if self.enable_tools:
            skill_tools = self.skill_mgr.get_all_tools()
            self.tools.extend(skill_tools)
            
            # 添加插件技能工具
            plugin_tools = self.plugin_loader.get_all_tools()
            self.tools.extend(plugin_tools)
        log.debug(f"更新工具列表: 共 {len(self.tools)} 个工具")
    
    def reset_work_directory(self):
        """重置工作目录到默认配置"""
        self.current_work_directory = self.default_work_directory
        from modules.main_server.middleware import request_manager as rm
        rm.reset_ai_work_directory()
        log.info(f"工作目录已重置为: {self.current_work_directory}")
    
    def get_system_prompt(self) -> str:
        """获取系统提示，包含工作目录信息"""
        # 通过 request_manager 获取提示词
        prompt_request = self.request_manager.create_prompt_request(
            "system",
            work_directory=self.current_work_directory,
            directory_structure=self.get_directory_structure()
        )
        
        # 处理提示词请求
        result = self.request_manager.handle_request(prompt_request, None)
        
        if result.get("success"):
            return result.get("prompt", "")
        else:
            #  fallback to default prompt
            directory_structure = self.get_directory_structure()
            default_prompt = f"你是一个AI助手。当用户要求完成任务时，必须确保完成所有必要的步骤，不要中途停止。重要限制：每次只能调用一个工具（skill），等待工具返回结果后，再决定是否需要调用下一个工具。不要同时调用多个工具。重要：在每次回答结束时，必须至少给出一个正常的输出（除了思考过程和工具调用之外的内容），让用户知道发生了什么。始终以完整的回答结束对话。重要：你的所有输出都将显示在终端中，因此请使用纯文本格式输出，不要使用Markdown格式（如 **粗体**、*斜体*、# 标题、- 列表、`代码块`、```代码围栏```、表格、> 引用等），使用自然语言和空格缩进来表达结构和层级。不要输出表情符号（如 emoji）。当前工作目录：{self.current_work_directory}。所有文件操作都在此目录下进行，可以使用子文件夹路径，例如 'subdir/file.txt' 或 'subdir1/subdir2/file.txt'。如果需要切换工作目录，请使用 file_manager 技能的 set_work_directory 函数。切换后的工作目录仅在当前对话有效，下次对话开始时会恢复为此目录。\n\n当前工作目录的文件结构：\n{directory_structure}"
            return default_prompt
    
    def get_directory_structure(self) -> str:
        """获取当前工作目录的目录结构"""
        try:
            # 尝试直接调用 file_reader 技能的 list_directory 函数
            from skills.file_reader.skill import list_directory
            result = list_directory(".", max_depth=3, show_hidden=False)
            if result.get("success"):
                return result.get("tree", "")
            else:
                return "无法获取目录结构"
        except Exception as e:
            log.error(f"获取目录结构失败: {e}")
            return "无法获取目录结构"
    
    async def _check_context_usage(self):
        """在每轮对话结束后检查上下文用量，接近窗口上限时通过回调通知。"""
        context_window = config.get_context_window(self.model)
        usage = self.context.check_context_usage(self.messages, context_window)
        if usage:
            await self._call_callback("context_usage", usage)
    
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
            for check, handler in self._tool_dispatch:
                if check(tool_name):
                    result = await handler(tool_name, arguments)
                    break
            else:
                result = {"error": f"未知的工具: {tool_name}"}
            
            # 使用请求管理器处理申请
            if self.request_manager and isinstance(result, dict):
                if self.request_manager.is_request(result):
                    log.debug(f"检测到申请: {result.get('type', 'unknown')}")
                    self.request_manager.handle_request(result, self.callback)
            
            # 从请求管理器获取 user_output 并转发
            self._last_tool_had_user_output = False
            self._last_user_output_data = None
            if self.request_manager:
                uo = self.request_manager.pop_last_user_output()
                if uo:
                    if isinstance(uo, dict):
                        await self._call_callback('user_output', uo)
                    else:
                        await self._call_callback('user_output', {'content': str(uo)})
                    self._last_tool_had_user_output = True
                    self._last_user_output_data = uo
            
            if isinstance(result, dict):
                # 拦截 set_work_directory 成功结果，同步更新 AI 临时工作目录
                if result.get("success") and "set_work_directory" in tool_name and result.get("work_directory"):
                    self.current_work_directory = result["work_directory"]
                    from modules.main_server.middleware import request_manager as rm
                    rm.set_ai_work_directory(result["work_directory"])
                    log.info(f"AI 临时工作目录已更新: {self.current_work_directory}")
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

    async def _execute_powershell_script(self, script: str, timeout: int = 30, wait_time: int = 10) -> dict:
        from modules.loader import powershell_manager
        return await powershell_manager.execute_script(script, timeout, wait_time)

    async def _handle_auto_execute(self, result_dict: dict) -> tuple:
        """处理 auto_execute 请求，直接执行 PowerShell 脚本"""
        ps_timeout = result_dict.get('timeout', 30)
        ps_wait = result_dict.get('wait_time', 10)
        ps_result = await self._execute_powershell_script(result_dict['script'], ps_timeout, ps_wait)
        return json.dumps(ps_result, ensure_ascii=False), False

    async def _handle_user_input_request(self, result_dict: dict, tool_name: str, arguments: dict) -> tuple:
        """处理 USER_INPUT 类型的请求"""
        input_data = {
            'prompt': result_dict.get('prompt'),
            'input_type': result_dict.get('input_type'),
            'default_value': result_dict.get('default_value')
        }
        user_input = await self._call_callback('user_input_required', input_data)
        user_out_content = f"{result_dict.get('prompt', '')} {Fore.LIGHTBLACK_EX}{user_input}{Style.RESET_ALL}"
        user_out_data = {'label': 'Input', 'content': user_out_content}
        await self._call_callback('user_output', user_out_data)
        self._last_tool_had_user_output = True
        self._last_confirmation_output_data = user_out_data
        return json.dumps({"success": True, "input": user_input}, ensure_ascii=False), False

    async def _handle_confirmation_request(self, result_dict: dict, tool_name: str, arguments: dict) -> tuple:
        """处理 CONFIRMATION 类型的请求"""
        confirmation_data = {
            'action': result_dict.get('action'),
            'default': result_dict.get('default')
        }
        confirm = await self._call_callback('confirmation_required', confirmation_data)
        status = Fore.GREEN + "已确认" + Style.RESET_ALL if confirm == 'y' else Fore.RED + "已取消" + Style.RESET_ALL
        user_out_data = {'label': 'Confirm', 'content': f"{result_dict.get('action', 'unknown')} {status}"}
        await self._call_callback('user_output', user_out_data)
        self._last_tool_had_user_output = True
        self._last_confirmation_output_data = user_out_data
        return json.dumps({"success": True, "confirmed": confirm == 'y'}, ensure_ascii=False), False

    async def _handle_requires_confirmation_request(self, result_dict: dict, tool_name: str, arguments: dict) -> tuple:
        """处理 requires_confirmation 类型的请求"""
        confirmation_data = {
            'action': result_dict.get('action', 'unknown'),
            'script_preview': result_dict.get('script_preview'),
            'file_path': result_dict.get('file_path'),
            'work_directory': result_dict.get('work_directory'),
            'error': result_dict.get('error')
        }
        confirm = await self._call_callback('confirmation_required', confirmation_data)

        if confirm != 'y':
            log.info(f"用户取消操作: {tool_name}")
            await self._call_callback('operation_canceled', {})
            return json.dumps({"error": "用户取消操作"}, ensure_ascii=False), True

        log.info(f"用户确认操作: {tool_name}")
        await self._call_callback('operation_confirmed', {})

        if result_dict.get('action') == 'run_powershell_script' and result_dict.get('script'):
            ps_timeout = result_dict.get('timeout', 30)
            ps_wait = result_dict.get('wait_time', 10)
            ps_result = await self._execute_powershell_script(result_dict['script'], ps_timeout, ps_wait)
            return json.dumps(ps_result, ensure_ascii=False), False

        if isinstance(arguments, dict):
            arguments['confirmed'] = True
        else:
            arguments = {'confirmed': True}
        result = await self._execute_tool_sync(tool_name, arguments)
        return result, False

    async def _process_tool_confirmation(self, result_raw: str, tool_name: str, arguments: dict):
        """处理工具返回的确认申请，返回 (result_str, should_skip)"""
        self._last_confirmation_output_data = None
        try:
            result_dict = json.loads(result_raw)
        except (json.JSONDecodeError, TypeError):
            return result_raw, False

        if result_dict.get('auto_execute') and result_dict.get('script'):
            return await self._handle_auto_execute(result_dict)

        if not self.request_manager or not self.request_manager.is_request(result_dict):
            return result_raw, False

        request_type = result_dict.get('type')

        for check, handler in self._confirmation_dispatch:
            if check(result_dict, request_type):
                return await handler(result_dict, tool_name, arguments)

        return result_raw, False

    async def chat(self, user_input):
        log.info(f"开始聊天 (非流式): 输入长度={len(user_input)}")
        
        self.add_message("user", user_input)
        
        kwargs = {
            "model": self.model,
            "messages": self.context.prepare_messages(self.messages),
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
            log_thinking(reasoning)
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
            
            tool_responses = []
            displayed_calls = []
            displayed_results = []
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
                has_user_output = self._last_tool_had_user_output
                uo_data = self._last_user_output_data
                
                result, skip = await self._process_tool_confirmation(result, tool_name, arguments)
                has_user_output = has_user_output or self._last_tool_had_user_output
                uo_data = uo_data or self._last_confirmation_output_data
                if skip:
                    entry = {"tool_call_id": tc.id, "role": "tool", "content": result}
                    if uo_data:
                        entry["user_output"] = uo_data
                    tool_responses.append(entry)
                    self._last_user_output_data = None
                    self._last_confirmation_output_data = None
                    continue
                
                entry = {"tool_call_id": tc.id, "role": "tool", "content": result}
                if uo_data:
                    entry["user_output"] = uo_data
                tool_responses.append(entry)
                self._last_user_output_data = None
                self._last_confirmation_output_data = None
                
                if not has_user_output:
                    displayed_calls.append(tc)
                    displayed_results.append((result, format_tool_result(result)))
            
            self.messages.extend(tool_responses)
            self._auto_save()
            
            if displayed_calls:
                await self._call_callback('tool_calls', {
                    'calls': [
                        {
                            'name': tc.function.name,
                            'arguments': tc.function.arguments
                        }
                        for tc in displayed_calls
                    ]
                })
                for raw, formatted in displayed_results:
                    await self._call_callback('tool_result', {
                        'raw': raw,
                        'formatted': formatted
                    })
            
            kwargs["messages"] = self.context.prepare_messages(self.messages)
            response = self.client.chat.completions.create(**kwargs)
            assistant_message = response.choices[0].message
        
        final_content = assistant_message.content or ""
        log.info(f"聊天完成: 响应长度={len(final_content)}")
        self.add_message("assistant", final_content)
        
        # 结束对话备份
        if self.backup_mgr:
            self.backup_mgr.end_dialog_backup()
            log.info("对话备份已结束")
        
        await self._check_context_usage()
        
        return final_content
    
    async def _process_stream(self, stream):
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
                    if reasoning_started:
                        await self._call_callback('thinking_end', {})
                        reasoning_started = False
                await self._call_callback('response_chunk', {
                    'content': content
                })

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
            await self._call_callback('response_end', {})

        return full_response, full_reasoning, tool_calls_buffer, has_tool_calls

    async def chat_stream(self, user_input):
        log.info(f"开始聊天 (流式): 输入长度={len(user_input)}")
        
        self.add_message("user", user_input)
        
        kwargs = {
            "model": self.model,
            "messages": self.context.prepare_messages(self.messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True
        }
        
        if self.tools:
            kwargs["tools"] = self.tools
        
        stream = self.client.chat.completions.create(**kwargs)
        full_response, full_reasoning, tool_calls_buffer, has_tool_calls = await self._process_stream(stream)

        if full_reasoning:
            log_thinking(full_reasoning)

        if not has_tool_calls:
            self.add_message("assistant", full_response, reasoning_content=full_reasoning)
        
        if has_tool_calls and tool_calls_buffer:
            tool_calls = list(tool_calls_buffer.values())
            log.info(f"检测到 {len(tool_calls)} 个工具调用")
            self.add_message("assistant", full_response or "", tool_calls, reasoning_content=full_reasoning)
            
            tool_responses = []
            displayed_calls = []
            displayed_results = []
            for tc in tool_calls:
                tool_name = tc['function']['name']
                try:
                    arguments = json.loads(tc['function']['arguments'])
                except:
                    arguments = {}
                
                result = await self._execute_tool_sync(tool_name, arguments)
                has_user_output = self._last_tool_had_user_output
                uo_data = self._last_user_output_data
                
                result, skip = await self._process_tool_confirmation(result, tool_name, arguments)
                has_user_output = has_user_output or self._last_tool_had_user_output
                uo_data = uo_data or self._last_confirmation_output_data
                if skip:
                    entry = {"tool_call_id": tc['id'], "role": "tool", "content": result}
                    if uo_data:
                        entry["user_output"] = uo_data
                    tool_responses.append(entry)
                    self._last_user_output_data = None
                    self._last_confirmation_output_data = None
                    continue
                
                entry = {"tool_call_id": tc['id'], "role": "tool", "content": result}
                if uo_data:
                    entry["user_output"] = uo_data
                tool_responses.append(entry)
                self._last_user_output_data = None
                self._last_confirmation_output_data = None
                
                if not has_user_output:
                    displayed_calls.append(tc)
                    displayed_results.append((result, format_tool_result(result)))
            
            self.messages.extend(tool_responses)
            self._auto_save()
            
            if displayed_calls:
                await self._call_callback('tool_calls', {
                    'calls': [
                        {
                            'name': tc['function']['name'],
                            'arguments': tc['function']['arguments']
                        }
                        for tc in displayed_calls
                    ]
                })
                for raw, formatted in displayed_results:
                    await self._call_callback('tool_result', {
                        'raw': raw,
                        'formatted': formatted
                    })
            
            MAX_HARD_LIMIT = 100
            INITIAL_MAX = 30
            EXTEND_BY = 20

            max_iterations = INITIAL_MAX
            iteration = 1

            while iteration < min(max_iterations, MAX_HARD_LIMIT):
                iteration += 1
                log.debug(f"工具调用迭代 {iteration}/{max_iterations} (hard limit: {MAX_HARD_LIMIT})")

                kwargs["messages"] = self.context.prepare_messages(self.messages)
                kwargs["stream"] = True
                stream = self.client.chat.completions.create(**kwargs)

                full_response, full_reasoning, tool_calls_buffer, has_tool_calls = await self._process_stream(stream)

                if full_reasoning:
                    log_thinking(f"[迭代 {iteration}] {full_reasoning}")
                if has_tool_calls and tool_calls_buffer:
                    tool_calls = list(tool_calls_buffer.values())
                    log.info(f"迭代 {iteration}: 检测到 {len(tool_calls)} 个工具调用")
                    self.add_message("assistant", full_response or "", tool_calls, reasoning_content=full_reasoning)

                    tool_responses = []
                    displayed_calls = []
                    displayed_results = []
                    for tc in tool_calls:
                        tool_name = tc['function']['name']
                        try:
                            arguments = json.loads(tc['function']['arguments'])
                        except:
                            arguments = {}

                        result = await self._execute_tool_sync(tool_name, arguments)
                        has_user_output = self._last_tool_had_user_output
                        uo_data = self._last_user_output_data

                        result, skip = await self._process_tool_confirmation(result, tool_name, arguments)
                        has_user_output = has_user_output or self._last_tool_had_user_output
                        uo_data = uo_data or self._last_confirmation_output_data
                        if skip:
                            entry = {"tool_call_id": tc['id'], "role": "tool", "content": result}
                            if uo_data:
                                entry["user_output"] = uo_data
                            tool_responses.append(entry)
                            self._last_user_output_data = None
                            self._last_confirmation_output_data = None
                            continue

                        entry = {"tool_call_id": tc['id'], "role": "tool", "content": result}
                        if uo_data:
                            entry["user_output"] = uo_data
                        tool_responses.append(entry)
                        self._last_user_output_data = None
                        self._last_confirmation_output_data = None

                        if not has_user_output:
                            displayed_calls.append(tc)
                            displayed_results.append((result, format_tool_result(result)))

                    self.messages.extend(tool_responses)
                    self._auto_save()

                    if displayed_calls:
                        await self._call_callback('tool_calls', {
                            'calls': [
                                {
                                    'name': tc['function']['name'],
                                    'arguments': tc['function']['arguments']
                                }
                                for tc in displayed_calls
                            ]
                        })
                        for raw, formatted in displayed_results:
                            await self._call_callback('tool_result', {
                                'raw': raw,
                                'formatted': formatted
                            })

                    if iteration >= max_iterations:
                        if iteration >= MAX_HARD_LIMIT:
                            break
                        log.info(f"达到当前迭代上限 {max_iterations}，询问用户是否继续")
                        result = await self._call_callback('max_iterations_reached', {
                            'iterations': iteration,
                            'max_iterations': max_iterations,
                            'hard_limit': MAX_HARD_LIMIT
                        })
                        if result == 'y':
                            max_iterations = min(max_iterations + EXTEND_BY, MAX_HARD_LIMIT)
                            log.info(f"用户确认续期，新上限: {max_iterations}")
                            continue
                        else:
                            log.info("用户选择不继续迭代")
                            break
                    continue
                else:
                    self.add_message("assistant", full_response, reasoning_content=full_reasoning)
                    break
        
        # 结束对话备份
        if self.backup_mgr:
            self.backup_mgr.end_dialog_backup()
            log.info("对话备份已结束")
        
        await self._check_context_usage()
        
        log.info(f"流式聊天完成: 响应长度={len(full_response)}")
        return full_response
    
    def clear_history(self):
        self.messages = []
        self.reset_work_directory()
    
    def save_conversation(self, dir_id, conv_id):
        conversation.save_conversation(self.messages, dir_id, conv_id)

    def load_conversation(self, dir_id, conv_id):
        messages = conversation.load_conversation(dir_id, conv_id)
        if messages:
            messages = conversation.repair_conversation_messages(
                messages, work_dir=self.default_work_directory
            )
            self.messages = messages
            self.reset_work_directory()
            return True
        return False
    
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

import json
import asyncio
import time
import uuid

from openai import OpenAI
from modules.main_server import config
from modules.chater import conversation
from modules.chater.context import ContextManager
from modules.loader import mcp_manager
from modules.loader import skill_manager
from modules.loader import plugin_skill_loader
from modules.main_server.middleware import request_manager
from modules.functions import backup_manager, powershell_manager
from modules.logger import get_logger, log_thinking

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


def _parse_display_name(tool_name: str, skill_mgr=None, plugin_loader=None) -> str:
    """将 tool_name 解析为 'skill.func' 格式的显示名，用于预览。"""
    if tool_name.startswith("skill_"):
        rest = tool_name[6:]
        parts = rest.split("_")
        if skill_mgr:
            for i in range(len(parts), 0, -1):
                possible_skill = "_".join(parts[:i])
                if possible_skill in skill_mgr.skills:
                    func = "_".join(parts[i:])
                    return f"{possible_skill}.{func}"
        return rest
    elif tool_name.startswith("plugin_"):
        rest = tool_name[7:]
        parts = rest.split("_")
        if plugin_loader:
            for i in range(len(parts), 0, -1):
                possible_skill = "_".join(parts[:i])
                if possible_skill in plugin_loader.skills:
                    func = "_".join(parts[i:])
                    return f"{possible_skill}.{func}"
        return rest
    else:
        return tool_name


class DolphinChat:
    def __init__(self, model="deepseek-v4-flash", temperature=0.7, max_tokens=None, enable_tools=True, callback=None):
        self.model = model
        self.temperature = temperature
        
        # 缓存配置，避免重复读取文件
        _cfg = config.load_config()
        
        # 从配置中读取 max_tokens，如果没有提供或配置中没有，则使用默认值 18000
        if max_tokens is None:
            max_tokens = _cfg.get('max_tokens', 18000)
        
        self.max_tokens = max_tokens
        self.effort_level = "fine"  # fine / normal / high
        self.messages = []
        self.context = ContextManager(self.get_system_prompt, self.get_context_prompt)
        self.enable_tools = enable_tools
        self.callback = callback or (lambda *args, **kwargs: None)
        self.client = OpenAI(
            api_key=_cfg.get("api_key"),
            base_url=_cfg.get("base_url", "https://api.deepseek.com")
        )
        self.mcp_mgr = mcp_manager.get_mcp_manager()
        self.skill_mgr = skill_manager.get_skill_manager()
        self.plugin_loader = plugin_skill_loader.get_plugin_skill_loader()
        self.request_manager = request_manager.get_request_manager()
        
        self.backup_mgr = backup_manager.get_backup_manager()
        
        # dialog_id = conv_id（在 set_save_target 时统一设置）
        self.dialog_id = None

        self._update_tools()
        self._save_dir_id = None
        self._save_conv_id = None

        # 防抖自动保存状态
        self._save_pending = False
        self._save_timer = None
        
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
        self.default_work_directory = _cfg.get('work_directory', 'workplace')
        self.current_work_directory = self.default_work_directory
        request_manager.reset_ai_work_directory()

        log.info(f"初始化 DolphinChat: model={model}, temperature={temperature}, max_tokens={max_tokens}, enable_tools={enable_tools}")
    
    def add_message(self, role, content, tool_calls=None, reasoning_content=None):
        message = {"role": role, "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        if reasoning_content:
            message["reasoning_content"] = reasoning_content
        self.messages.append(message)
        log.debug(f"添加消息: role={role}, content_length={len(content)}, tool_calls={len(tool_calls) if tool_calls else 0}")
        self._schedule_auto_save()

    def set_save_target(self, dir_id, conv_id):
        self._save_dir_id = dir_id
        self._save_conv_id = conv_id
        # dialog_id = conv_id（统一标识）
        self.dialog_id = conv_id
        # 同步设置备份管理器的会话上下文
        if self.backup_mgr:
            self.backup_mgr.set_session(dir_id, conv_id)
        log.debug(f"设置保存目标: dir={dir_id}, conv={conv_id}, dialog_id={conv_id}")

    def _auto_save(self):
        if self._save_dir_id and self._save_conv_id:
            conversation.save_conversation(self.messages, self._save_dir_id, self._save_conv_id)
            log.debug(f"实时保存: {len(self.messages)} 条消息")

    def _schedule_auto_save(self):
        """延迟保存：同一次同步块内的多次消息变更合并为一次写盘。"""
        if not self._save_dir_id or not self._save_conv_id:
            return
        self._save_pending = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 不在事件循环中（如启动阶段），立即保存
            self._flush_auto_save()
            return

        if self._save_timer is None or self._save_timer.cancelled():
            self._save_timer = loop.call_later(0.25, self._flush_auto_save)

    def _flush_auto_save(self):
        """立即执行待保存。"""
        if self._save_timer and not self._save_timer.cancelled():
            self._save_timer.cancel()
        self._save_timer = None
        if not self._save_pending:
            return
        self._auto_save()
        self._save_pending = False

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
        request_manager.reset_ai_work_directory()
        log.info(f"工作目录已重置为: {self.current_work_directory}")
    
    def get_system_prompt(self) -> str:
        """获取静态系统提示词（仅行为规则，用于 prompt caching）"""
        prompt_request = self.request_manager.create_prompt_request("system")
        result = self.request_manager.handle_request(prompt_request, None)

        if result.get("success"):
            return result.get("prompt", "")

        log.warning("PromptManager 获取系统提示词失败，使用最小化 fallback")
        return "你是一个AI助手。"

    def get_context_prompt(self) -> str:
        """获取每轮动态上下文（工作目录 + 目录结构 + 努力程度）"""
        prompt_request = self.request_manager.create_prompt_request(
            "context",
            work_directory=self.current_work_directory,
            directory_structure=self.get_directory_structure(),
            effort_level=self.effort_level
        )
        result = self.request_manager.handle_request(prompt_request, None)

        if result.get("success"):
            return result.get("prompt", "")

        log.warning("PromptManager 获取上下文提示词失败，使用最小化 fallback")
        return f"当前工作目录：{self.current_work_directory}。"
    
    def get_directory_structure(self) -> str:
        """获取当前工作目录的目录结构"""
        try:
            from skills.file_reader.skill import list_directory
            from modules.loader.skill_context import create_default_context
            ctx = create_default_context(self.current_work_directory)
            result = list_directory(ctx, ".", max_depth=3, show_hidden=False)
            if result.get("success"):
                return result.get("tree", "")
            else:
                log.warning(f"list_directory 失败: {result.get('error', 'unknown')}")
                return "无法获取目录结构"
        except Exception as e:
            log.error(f"获取目录结构失败: {e}")
            return "无法获取目录结构"
    
    async def _check_context_usage(self):
        """在每轮对话结束后检查上下文用量，通过回调通知。"""
        context_window = config.get_context_window(self.model)
        usage = self.context.check_context_usage(self.messages, context_window)
        # 每轮都发送 usage 信息（不再只在告警时发送）
        await self._call_callback("context_usage", usage)
    
    async def _call_callback(self, event_type, data):
        """调用回调函数，支持同步和异步回调"""
        try:
            if asyncio.iscoroutinefunction(self.callback):
                result = await self.callback(event_type, data)
                return result
            else:
                result = self.callback(event_type, data)
                if event_type == 'tool_start':
                    await asyncio.sleep(0)
                return result
        except Exception as e:
            log.error(f"回调函数执行失败: {e}")
            return None
    
    async def _execute_tool(self, tool_name: str, arguments: dict) -> tuple:
        """执行工具，返回 (result_str, had_user_output, user_output)。"""
        log.info(f"执行工具: {tool_name}, 参数: {arguments}")
        start = time.perf_counter()
        had_user_output = False
        user_output = None
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

            # 从工具返回结果中直接提取 user_output（显式传递，不再依赖 request_manager 隐式状态）
            if isinstance(result, dict) and result.get("user_output"):
                uo = result.pop("user_output")
                if isinstance(uo, dict):
                    await self._call_callback('user_output', uo)
                else:
                    await self._call_callback('user_output', {'content': str(uo)})
                had_user_output = True
                user_output = uo

            if isinstance(result, dict):
                # 拦截 set_work_directory 成功结果，同步更新 AI 临时工作目录
                if result.get("success") and "set_work_directory" in tool_name and result.get("work_directory"):
                    self.current_work_directory = result["work_directory"]
                    request_manager.set_ai_work_directory(result["work_directory"])
                    self.skill_mgr.set_work_dir(result["work_directory"])
                    log.info(f"AI 临时工作目录已更新: {self.current_work_directory}")
                result_str = json.dumps(result, ensure_ascii=False)
            else:
                result_str = str(result)
            elapsed = time.perf_counter() - start
            log.debug(f"工具执行完成: {tool_name}, 耗时={elapsed:.3f}s, 结果长度={len(result_str)}")
            return result_str, had_user_output, user_output
        except Exception as e:
            elapsed = time.perf_counter() - start
            error_msg = json.dumps({"error": str(e)}, ensure_ascii=False)
            log.error(f"工具执行失败: {tool_name}, 耗时={elapsed:.3f}s, 错误: {str(e)}")
            return error_msg, False, None
    
    async def _execute_powershell_script(self, script: str, timeout: int = 30, wait_time: int = 10) -> dict:
        return await powershell_manager.execute_script(script, timeout, wait_time)

    async def _handle_auto_execute(self, result_dict: dict) -> tuple:
        """处理 auto_execute 请求，直接执行 PowerShell 脚本"""
        ps_timeout = result_dict.get('timeout', 30)
        ps_wait = result_dict.get('wait_time', 10)
        ps_result = await self._execute_powershell_script(result_dict['script'], ps_timeout, ps_wait)
        return json.dumps(ps_result, ensure_ascii=False), False, None

    async def _handle_user_input_request(self, result_dict: dict, tool_name: str, arguments: dict) -> tuple:
        """处理 USER_INPUT 类型的请求"""
        input_data = {
            'prompt': result_dict.get('prompt'),
            'input_type': result_dict.get('input_type'),
            'default_value': result_dict.get('default_value')
        }
        user_input = await self._call_callback('user_input_required', input_data)
        user_out_data = {'label': 'Input', 'parts': [
            {"text": result_dict.get('prompt', '')},
            {"text": user_input, "style": "gray"}
        ]}
        await self._call_callback('user_output', user_out_data)
        return json.dumps({"success": True, "input": user_input}, ensure_ascii=False), False, user_out_data

    async def _handle_confirmation_request(self, result_dict: dict, tool_name: str, arguments: dict) -> tuple:
        """处理 CONFIRMATION 类型的请求"""
        confirmation_data = {
            'action': result_dict.get('action'),
            'default': result_dict.get('default')
        }
        confirm = await self._call_callback('confirmation_required', confirmation_data)
        status_style = "green" if confirm == 'y' else "red"
        status_text = "已确认" if confirm == 'y' else "已取消"
        user_out_data = {'label': 'Confirm', 'parts': [
            {"text": result_dict.get('action', 'unknown')},
            {"text": status_text, "style": status_style}
        ]}
        await self._call_callback('user_output', user_out_data)
        return json.dumps({"success": True, "confirmed": confirm == 'y'}, ensure_ascii=False), False, user_out_data

    async def _handle_requires_confirmation_request(self, result_dict: dict, tool_name: str, arguments: dict) -> tuple:
        """处理 requires_confirmation 类型的请求"""
        confirmation_data = {
            'action': result_dict.get('action', 'unknown'),
            'script_preview': result_dict.get('script_preview'),
            'script': result_dict.get('script'),
            'file_path': result_dict.get('file_path'),
            'work_directory': result_dict.get('work_directory'),
            'error': result_dict.get('error')
        }
        confirm = await self._call_callback('confirmation_required', confirmation_data)

        if confirm != 'y':
            log.info(f"用户取消操作: {tool_name}")
            await self._call_callback('operation_canceled', {})
            return json.dumps({"error": "用户取消操作"}, ensure_ascii=False), True, None

        log.info(f"用户确认操作: {tool_name}")
        await self._call_callback('operation_confirmed', {})

        if result_dict.get('action') == 'run_powershell_script' and result_dict.get('script'):
            ps_timeout = result_dict.get('timeout', 30)
            ps_wait = result_dict.get('wait_time', 10)
            ps_result = await self._execute_powershell_script(result_dict['script'], ps_timeout, ps_wait)
            return json.dumps(ps_result, ensure_ascii=False), False, None

        if isinstance(arguments, dict):
            arguments['confirmed'] = True
        else:
            arguments = {'confirmed': True}
        result_str, _, reexec_uo = await self._execute_tool(tool_name, arguments)
        return result_str, False, reexec_uo

    async def _process_tool_confirmation(self, result_raw: str, tool_name: str, arguments: dict):
        """处理工具返回的确认申请，返回 (result_str, should_skip, user_output)"""
        try:
            result_dict = json.loads(result_raw)
        except (json.JSONDecodeError, TypeError):
            return result_raw, False, None

        if result_dict.get('auto_execute') and result_dict.get('script'):
            return await self._handle_auto_execute(result_dict)

        if not self.request_manager or not self.request_manager.is_request(result_dict):
            return result_raw, False, None

        request_type = result_dict.get('type')

        for check, handler in self._confirmation_dispatch:
            if check(result_dict, request_type):
                return await handler(result_dict, tool_name, arguments)

        return result_raw, False, None

    async def _run_tool_calls(self, tool_calls: list) -> list:
        """统一执行一批 tool_calls，返回生成的 tool 角色消息列表。"""
        start = time.perf_counter()
        tool_responses = []
        displayed_calls = []
        displayed_results = []

        for tc in tool_calls:
            tool_name = tc['function']['name']
            arguments_str = tc['function'].get('arguments', '{}')

            try:
                arguments = json.loads(arguments_str)
            except (json.JSONDecodeError, TypeError) as e:
                log.error(f"JSON解析失败: {tool_name}, 错误: {str(e)}")
                error_result = {
                    "error": "工具调用参数解析失败",
                    "tool_name": tool_name,
                    "reason": "参数可能被截断或格式错误",
                    "details": str(e),
                    "suggestion": "请尝试重新表述您的需求，或者减少单次操作的复杂度"
                }
                tool_responses.append({
                    "tool_call_id": tc['id'],
                    "role": "tool",
                    "content": json.dumps(error_result, ensure_ascii=False)
                })
                continue

            display_name = _parse_display_name(tool_name, self.skill_mgr, self.plugin_loader)
            await self._call_callback('tool_start', {'name': display_name})

            result, _, skill_uo = await self._execute_tool(tool_name, arguments)
            result, skip, conf_uo = await self._process_tool_confirmation(result, tool_name, arguments)

            final_uo = skill_uo if skill_uo is not None else conf_uo
            has_user_output = final_uo is not None

            entry = {
                "tool_call_id": tc['id'],
                "role": "tool",
                "content": result
            }
            if final_uo is not None:
                entry["user_output"] = final_uo
            tool_responses.append(entry)

            if skip:
                continue

            if not has_user_output:
                displayed_calls.append(tc)
                displayed_results.append((result, format_tool_result(result)))

        self.messages.extend(tool_responses)
        self._schedule_auto_save()

        if displayed_calls:
            await self._call_callback('tool_calls', {
                'calls': [
                    {
                        'name': tc['function']['name'],
                        'arguments': tc['function'].get('arguments', '')
                    }
                    for tc in displayed_calls
                ]
            })
            for raw, formatted in displayed_results:
                await self._call_callback('tool_result', {
                    'raw': raw,
                    'formatted': formatted
                })

        elapsed = time.perf_counter() - start
        log.info(f"工具调用批次完成: {len(tool_calls)} 个, 耗时={elapsed:.3f}s")
        return tool_responses

    def _apply_effort_params(self, kwargs):
        """根据 effort_level 添加 thinking mode 参数。normal 不传参。"""
        if self.effort_level == "normal":
            return
        effort_map = {"fine": "high", "high": "max"}
        kwargs["reasoning_effort"] = effort_map.get(self.effort_level, "high")
        kwargs.setdefault("extra_body", {})
        kwargs["extra_body"]["thinking"] = {"type": "enabled"}

    async def chat(self, user_input):
        log.info(f"开始聊天 (非流式): 输入长度={len(user_input)}")
        chat_start = time.perf_counter()

        self.add_message("user", user_input)
        
        kwargs = {
            "model": self.model,
            "messages": self.context.prepare_messages(self.messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        if self.tools:
            kwargs["tools"] = self.tools
        
        self._apply_effort_params(kwargs)
        
        api_start = time.perf_counter()
        response = self.client.chat.completions.create(**kwargs)
        api_elapsed = time.perf_counter() - api_start
        log.info(f"API 调用完成 (非流式): 耗时={api_elapsed:.3f}s")
        # 保存 API 返回的精确 token 用量
        if hasattr(response, 'usage') and response.usage:
            self.context.update_usage_from_api(response.usage)
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

            await self._run_tool_calls(tool_calls_list)

            kwargs["messages"] = self.context.prepare_messages(self.messages)
            api_start = time.perf_counter()
            response = self.client.chat.completions.create(**kwargs)
            api_elapsed = time.perf_counter() - api_start
            log.info(f"API 调用完成 (非流式, 工具后): 耗时={api_elapsed:.3f}s")
            # 保存 API 返回的精确 token 用量
            if hasattr(response, 'usage') and response.usage:
                self.context.update_usage_from_api(response.usage)
            assistant_message = response.choices[0].message

        final_content = assistant_message.content or ""
        total_elapsed = time.perf_counter() - chat_start
        log.info(f"聊天完成: 响应长度={len(final_content)}, 总耗时={total_elapsed:.3f}s")
        self.add_message("assistant", final_content)
        self._flush_auto_save()

        # 新架构：无需清理内存缓存（持久化存储）
        log.debug("对话完成（备份记录已持久化）")

        await self._check_context_usage()

        return final_content
    
    async def _process_stream(self, stream):
        full_response = ""
        full_reasoning = ""
        tool_calls_buffer = {}
        reasoning_started = False
        has_tool_calls = False
        response_started = False
        last_usage = None  # 捕获流式响应的 usage

        for chunk in stream:
            # 检查 usage 信息（流式响应的最后一块可能包含 usage）
            if hasattr(chunk, 'usage') and chunk.usage:
                last_usage = chunk.usage

            # usage-only chunk 没有 choices，跳过
            if not chunk.choices:
                continue

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

        return full_response, full_reasoning, tool_calls_buffer, has_tool_calls, last_usage

    async def chat_stream(self, user_input):
        log.info(f"开始聊天 (流式): 输入长度={len(user_input)}")
        chat_start = time.perf_counter()

        self.add_message("user", user_input)
        
        kwargs = {
            "model": self.model,
            "messages": self.context.prepare_messages(self.messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True}  # 请求 API 返回 token 用量
        }
        
        if self.tools:
            kwargs["tools"] = self.tools
        
        self._apply_effort_params(kwargs)
        
        api_start = time.perf_counter()
        stream = self.client.chat.completions.create(**kwargs)
        full_response, full_reasoning, tool_calls_buffer, has_tool_calls, last_usage = await self._process_stream(stream)
        api_elapsed = time.perf_counter() - api_start
        log.info(f"API 流式调用完成: 耗时={api_elapsed:.3f}s")

        # 保存 API 返回的精确 token 用量
        if last_usage:
            self.context.update_usage_from_api(last_usage)

        if full_reasoning:
            log_thinking(full_reasoning)

        if not has_tool_calls:
            self.add_message("assistant", full_response, reasoning_content=full_reasoning)
        
        if has_tool_calls and tool_calls_buffer:
            tool_calls = list(tool_calls_buffer.values())
            log.info(f"检测到 {len(tool_calls)} 个工具调用")
            self.add_message("assistant", full_response or "", tool_calls, reasoning_content=full_reasoning)

            await self._run_tool_calls(tool_calls)

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

                full_response, full_reasoning, tool_calls_buffer, has_tool_calls, last_usage = await self._process_stream(stream)

                # 保存 API 返回的精确 token 用量
                if last_usage:
                    self.context.update_usage_from_api(last_usage)

                if full_reasoning:
                    log_thinking(f"[迭代 {iteration}] {full_reasoning}")
                if has_tool_calls and tool_calls_buffer:
                    tool_calls = list(tool_calls_buffer.values())
                    log.info(f"迭代 {iteration}: 检测到 {len(tool_calls)} 个工具调用")
                    self.add_message("assistant", full_response or "", tool_calls, reasoning_content=full_reasoning)

                    await self._run_tool_calls(tool_calls)

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

        self._flush_auto_save()

        # 新架构：无需清理内存缓存（持久化存储）
        log.debug("流式对话完成（备份记录已持久化）")

        await self._check_context_usage()

        total_elapsed = time.perf_counter() - chat_start
        log.info(f"流式聊天完成: 响应长度={len(full_response)}, 总耗时={total_elapsed:.3f}s")
        return full_response
    
    def clear_history(self):
        self.messages = []
        self.context.reset_usage()  # 重置 token 用量统计
        self.reset_work_directory()
        # 新架构：无需清理内存缓存（持久化存储）
        log.debug("历史已清空（备份记录已持久化）")
    
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

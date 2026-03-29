from openai import OpenAI
from modules import config
from modules import conversation
from modules import mcp_manager
from modules import skill_manager
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
                for i, v in enumerate(value[:5]):
                    format_value(f"[{i}]", v, indent + 1)
                if len(value) > 5:
                    formatted_lines.append(f"{prefix}  ... 还有 {len(value) - 5} 项")
            elif isinstance(value, str):
                if '\n' in value:
                    lines = value.strip().split('\n')
                    formatted_lines.append(f"{prefix}{key}:")
                    for line in lines[:10]:
                        formatted_lines.append(f"{prefix}  {line}")
                    if len(lines) > 10:
                        formatted_lines.append(f"{prefix}  ... 还有 {len(lines) - 10} 行")
                else:
                    display = value[:100] + "..." if len(value) > 100 else value
                    formatted_lines.append(f"{prefix}{key}: {display}")
            elif isinstance(value, bool):
                formatted_lines.append(f"{prefix}{key}: {'是' if value else '否'}")
            elif value is None:
                formatted_lines.append(f"{prefix}{key}: (空)")
            else:
                formatted_lines.append(f"{prefix}{key}: {value}")
        
        for key, value in result.items():
            format_value(key, value)
        
        return '\n'.join(formatted_lines)
    except (json.JSONDecodeError, TypeError):
        return None

class QuickAIChat:
    def __init__(self, model="deepseek-chat", temperature=0.7, max_tokens=None, enable_tools=True):
        self.model = model
        self.temperature = temperature
        
        # 从配置中读取 max_tokens，如果没有提供或配置中没有，则使用默认值 8192
        if max_tokens is None:
            config_data = config.load_config()
            max_tokens = config_data.get('max_tokens', 8192)
        
        self.max_tokens = max_tokens
        self.messages = []
        self.enable_tools = enable_tools
        self.client = OpenAI(
            api_key=config.load_config().get("api_key"),
            base_url=config.load_config().get("base_url", "https://api.deepseek.com")
        )
        self.mcp_mgr = mcp_manager.get_mcp_manager()
        self.skill_mgr = skill_manager.get_skill_manager()
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
        log.debug(f"更新工具列表: 共 {len(self.tools)} 个工具")
    
    async def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        log.info(f"执行工具: {tool_name}, 参数: {arguments}")
        try:
            if tool_name.startswith("skill_"):
                result = await self.skill_mgr.call_tool(tool_name, arguments)
            elif "_" in tool_name:
                result = await self.mcp_mgr.call_tool(tool_name, arguments)
            else:
                result = {"error": f"未知的工具: {tool_name}"}
            
            if isinstance(result, dict):
                result_str = json.dumps(result, ensure_ascii=False)
            else:
                result_str = str(result)
            log.debug(f"工具执行结果: {result_str[:200]}{'...' if len(result_str) > 200 else ''}")
            return result_str
        except Exception as e:
            error_msg = json.dumps({"error": str(e)}, ensure_ascii=False)
            log.error(f"工具执行失败: {tool_name}, 错误: {str(e)}")
            return error_msg
    
    def _execute_tool_sync(self, tool_name: str, arguments: dict) -> str:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._execute_tool(tool_name, arguments))
        finally:
            loop.close()
    
    def chat(self, user_input):
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
            print(f"思考过程:\n{reasoning}\n--- 思考过程结束 ---\n")
        
        tool_calls = assistant_message.tool_calls
        
        if tool_calls:
            log.info(f"检测到 {len(tool_calls)} 个工具调用")
            self.add_message("assistant", assistant_message.content or "", [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in tool_calls
            ], reasoning_content=reasoning)
            
            print("工具调用:")
            for tc in tool_calls:
                print(f"  - {tc.function.name}")
                print(f"    参数: {tc.function.arguments}")
            
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
                
                result = self._execute_tool_sync(tool_name, arguments)
                
                try:
                    result_dict = json.loads(result)
                    if result_dict.get("requires_confirmation"):
                        print(f"\n⚠️  需要确认:")
                        print(f"  操作: {result_dict.get('action', 'unknown')}")
                        print(f"  文件: {result_dict.get('file_path', 'unknown')}")
                        print(f"  工作目录: {result_dict.get('work_directory', 'unknown')}")
                        print(f"  原因: {result_dict.get('error', 'unknown')}")
                        
                        confirm = input("\n是否确认此操作? (y/n): ").lower()
                        if confirm != 'y':
                            tool_responses.append({
                                "tool_call_id": tc.id,
                                "role": "tool",
                                "content": json.dumps({"error": "用户取消操作"}, ensure_ascii=False)
                            })
                            log.info(f"用户取消操作: {tool_name}")
                            print("操作已取消")
                            continue
                        else:
                            log.info(f"用户确认操作: {tool_name}")
                            print("操作已确认，正在重新执行...")
                            # 添加 confirmed 参数
                            if isinstance(arguments, dict):
                                arguments['confirmed'] = True
                            else:
                                arguments = {'confirmed': True}
                            result = self._execute_tool_sync(tool_name, arguments)
                except:
                    pass
                
                tool_responses.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": result
                })
                
                print(f"  结果: {result}")
                formatted = format_tool_result(result)
                if formatted:
                    print(f"\n  格式化结果:\n{formatted}")
            
            self.messages.extend(tool_responses)
            
            kwargs["messages"] = self.messages
            response = self.client.chat.completions.create(**kwargs)
            assistant_message = response.choices[0].message
        
        final_content = assistant_message.content or ""
        log.info(f"聊天完成: 响应长度={len(final_content)}")
        self.add_message("assistant", final_content)
        return final_content
    
    def chat_stream(self, user_input):
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
                        print("思考过程:")
                        reasoning_started = True
                    full_reasoning += reasoning
                    print(reasoning, end="", flush=True)
            
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
            print("\n--- 思考过程结束 ---\n")
        
        if response_started:
            print(full_response, end="", flush=True)
            print()
        
        if has_tool_calls and tool_calls_buffer:
            tool_calls = list(tool_calls_buffer.values())
            log.info(f"检测到 {len(tool_calls)} 个工具调用")
            self.add_message("assistant", full_response or "", tool_calls, reasoning_content=full_reasoning)
            
            print("工具调用:")
            for tc in tool_calls:
                print(f"  - {tc['function']['name']}")
                print(f"    参数: {tc['function']['arguments']}")
            
            tool_responses = []
            for tc in tool_calls:
                tool_name = tc['function']['name']
                try:
                    arguments = json.loads(tc['function']['arguments'])
                except:
                    arguments = {}
                
                result = self._execute_tool_sync(tool_name, arguments)
                
                try:
                    result_dict = json.loads(result)
                    
                    # 处理需要确认的操作（检查 skill 是否有自己的确认机制）
                    if result_dict.get("requires_confirmation"):
                        # 检查 skill 是否已经处理了确认（通过检查是否有 confirmed 字段）
                        if not result_dict.get("confirmed"):
                            print(f"\n⚠️  需要确认:")
                            print(f"  操作: {result_dict.get('action', 'unknown')}")
                            print(f"  文件: {result_dict.get('file_path', 'unknown')}")
                            print(f"  工作目录: {result_dict.get('work_directory', 'unknown')}")
                            print(f"  原因: {result_dict.get('error', 'unknown')}")
                            
                            confirm = input("\n是否确认此操作? (y/n): ").lower()
                            if confirm != 'y':
                                tool_responses.append({
                                    "tool_call_id": tc['id'],
                                    "role": "tool",
                                    "content": json.dumps({"error": "用户取消操作"}, ensure_ascii=False)
                                })
                                log.info(f"用户取消操作: {tool_name}")
                                print("操作已取消")
                                continue
                            else:
                                log.info(f"用户确认操作: {tool_name}")
                                print("操作已确认，正在重新执行...")
                                # 添加 confirmed 参数
                                if isinstance(arguments, dict):
                                    arguments['confirmed'] = True
                                else:
                                    arguments = {'confirmed': True}
                                result = self._execute_tool_sync(tool_name, arguments)
                except:
                    pass
                
                tool_responses.append({
                    "tool_call_id": tc['id'],
                    "role": "tool",
                    "content": result
                })
                
                print(f"  结果: {result}")
                formatted = format_tool_result(result)
                if formatted:
                    print(f"\n  格式化结果:\n{formatted}")
            
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
                                print("思考过程:")
                                reasoning_started = True
                            full_reasoning += reasoning
                            print(reasoning, end="", flush=True)
                    
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
                    print("\n--- 思考过程结束 ---\n")
                
                if response_started:
                    print(full_response, end="", flush=True)
                    print()
                
                if has_tool_calls and tool_calls_buffer:
                    tool_calls = list(tool_calls_buffer.values())
                    log.info(f"迭代 {iteration}: 检测到 {len(tool_calls)} 个工具调用")
                    self.add_message("assistant", full_response or "", tool_calls, reasoning_content=full_reasoning)
                    
                    print("工具调用:")
                    for tc in tool_calls:
                        print(f"  - {tc['function']['name']}")
                        print(f"    参数: {tc['function']['arguments']}")
                    
                    tool_responses = []
                    for tc in tool_calls:
                        tool_name = tc['function']['name']
                        try:
                            arguments = json.loads(tc['function']['arguments'])
                        except:
                            arguments = {}
                        
                        result = self._execute_tool_sync(tool_name, arguments)
                        
                        try:
                            result_dict = json.loads(result)
                            if result_dict.get("requires_confirmation"):
                                print(f"\n⚠️  需要确认:")
                                print(f"  操作: {result_dict.get('action', 'unknown')}")
                                print(f"  文件: {result_dict.get('file_path', 'unknown')}")
                                print(f"  工作目录: {result_dict.get('work_directory', 'unknown')}")
                                print(f"  原因: {result_dict.get('error', 'unknown')}")
                                
                                confirm = input("\n是否确认此操作? (y/n): ").lower()
                                if confirm != 'y':
                                    tool_responses.append({
                                        "tool_call_id": tc['id'],
                                        "role": "tool",
                                        "content": json.dumps({"error": "用户取消操作"}, ensure_ascii=False)
                                    })
                                    log.info(f"用户取消操作: {tool_name}")
                                    print("操作已取消")
                                    continue
                                else:
                                    log.info(f"用户确认操作: {tool_name}")
                                    print("操作已确认，正在重新执行...")
                                    # 添加 confirmed 参数
                                    if isinstance(arguments, dict):
                                        arguments['confirmed'] = True
                                    else:
                                        arguments = {'confirmed': True}
                                    result = self._execute_tool_sync(tool_name, arguments)
                        except:
                            pass
                        
                        tool_responses.append({
                            "tool_call_id": tc['id'],
                            "role": "tool",
                            "content": result
                        })
                        
                        print(f"  结果: {result}")
                        formatted = format_tool_result(result)
                        if formatted:
                            print(f"\n  格式化结果:\n{formatted}")
                    
                    self.messages.extend(tool_responses)
                    continue
                else:
                    break
            
            if iteration >= max_iterations:
                log.warning(f"达到最大工具调用迭代次数: {max_iterations}")
                print(f"\n⚠️  注意: 已达到最大工具调用迭代次数 ({max_iterations} 次)")
                print("如果任务未完成，请继续对话以继续执行。")
                if not full_response:
                    full_response = f"已达到最大工具调用迭代次数 ({max_iterations} 次)。如果任务未完成，请继续对话以继续执行。"
            
            if full_response or (not has_tool_calls and not reasoning_started):
                print()
                self.add_message("assistant", full_response)
            elif not full_response and has_tool_calls:
                print()
                self.add_message("assistant", "")
        
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
        return self.skill_mgr.list_skills()

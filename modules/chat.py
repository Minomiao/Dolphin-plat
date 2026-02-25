from openai import OpenAI
from modules import config
from modules import conversation
from modules import mcp_manager
from modules import skill_manager
from modules import logger
import json
import asyncio

log = logger.get_logger("QuickAI.chat")

class QuickAIChat:
    def __init__(self, model="deepseek-chat", temperature=0.7, max_tokens=4096, enable_tools=True):
        self.model = model
        self.temperature = temperature
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
                try:
                    arguments = json.loads(tc.function.arguments)
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
                                "tool_call_id": tc.id,
                                "role": "tool",
                                "content": json.dumps({"error": "用户取消操作"}, ensure_ascii=False)
                            })
                            log.info(f"用户取消操作: {tool_name}")
                            print("操作已取消")
                            continue
                        else:
                            log.info(f"用户确认操作: {tool_name}")
                            print("操作已确认")
                except:
                    pass
                
                tool_responses.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": result
                })
                
                print(f"  结果: {result}")
            
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
        
        system_message = "你是一个AI助手。当用户要求完成任务时，必须确保完成所有必要的步骤，不要中途停止。如果需要执行多个工具调用，应该一次性完成所有必要的操作，而不是等待用户继续。重要：在每次回答结束时，必须至少给出一个正常的输出（除了思考过程和工具调用之外的内容），让用户知道发生了什么。始终以完整的回答结束对话。"
        
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
                    
                    if result_dict.get("requires_confirmation"):
                        if tool_name == "skill_powershell_executor_run_script":
                            print(f"\n⚠️  需要确认运行 PowerShell 脚本:")
                            print(f"  脚本长度: {result_dict.get('script_length', 'unknown')} 字符")
                            script_preview = result_dict.get('script_preview', '')
                            print(f"  脚本预览:")
                            print(f"    {script_preview}")
                            
                            confirm = input("\n是否确认运行此脚本? (y/n): ").lower()
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
                                print("操作已确认，正在运行脚本...")
                                confirm_result = self._execute_tool_sync("skill_powershell_executor_confirm_run_script", arguments)
                                tool_responses.append({
                                    "tool_call_id": tc['id'],
                                    "role": "tool",
                                    "content": confirm_result
                                })
                                print(f"  结果: {confirm_result}")
                                continue
                        else:
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
                                print("操作已确认")
                except:
                    pass
                
                tool_responses.append({
                    "tool_call_id": tc['id'],
                    "role": "tool",
                    "content": result
                })
                
                print(f"  结果: {result}")
            
            self.messages.extend(tool_responses)
            
            max_iterations = 5
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
                                    print("操作已确认")
                        except:
                            pass
                        
                        tool_responses.append({
                            "tool_call_id": tc['id'],
                            "role": "tool",
                            "content": result
                        })
                        
                        print(f"  结果: {result}")
                    
                    self.messages.extend(tool_responses)
                    continue
                else:
                    break
            
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

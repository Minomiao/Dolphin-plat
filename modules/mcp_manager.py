import asyncio
import json
from typing import Dict, List, Any, Optional
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from modules import logger

log = logger.get_logger("QuickAI.mcp_manager")


class MCPManager:
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, Dict[str, Any]] = {}
        log.debug("初始化 MCPManager")
    
    async def connect_server(self, name: str, command: List[str]) -> bool:
        log.info(f"连接 MCP 服务器: {name}, 命令: {command}")
        try:
            server_params = {
                "command": command[0],
                "args": command[1:] if len(command) > 1 else []
            }
            
            stdio_transport = await stdio_client(server_params)
            stdio, write = stdio_transport
            
            session = ClientSession(stdio, write)
            await session.initialize()
            
            self.sessions[name] = session
            
            tools_response = await session.list_tools()
            for tool in tools_response.tools:
                self.tools[f"{name}.{tool.name}"] = {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                    "server": name
                }
            
            log.info(f"MCP 服务器 {name} 连接成功，加载 {len(tools_response.tools)} 个工具")
            return True
        except Exception as e:
            log.error(f"连接 MCP 服务器 {name} 失败: {e}")
            print(f"连接 MCP 服务器 {name} 失败: {e}")
            return False
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        log.info(f"调用 MCP 工具: {tool_name}, 参数: {arguments}")
        if "." not in tool_name:
            log.error(f"工具名称格式错误: {tool_name}")
            raise ValueError(f"工具名称格式错误: {tool_name}")
        
        server_name, actual_tool_name = tool_name.split(".", 1)
        
        if server_name not in self.sessions:
            log.error(f"MCP 服务器 {server_name} 未连接")
            raise ValueError(f"MCP 服务器 {server_name} 未连接")
        
        session = self.sessions[server_name]
        result = await session.call_tool(actual_tool_name, arguments)
        log.debug(f"MCP 工具执行结果: {str(result)[:200]}{'...' if len(str(result)) > 200 else ''}")
        
        return result
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_info["description"],
                    "parameters": tool_info["input_schema"]
                }
            }
            for tool_name, tool_info in self.tools.items()
        ]
    
    def get_tool_names(self) -> List[str]:
        return list(self.tools.keys())
    
    async def close_all(self):
        for session in self.sessions.values():
            try:
                await session.close()
            except:
                pass
        self.sessions.clear()
        self.tools.clear()


_mcp_manager = None


def get_mcp_manager() -> MCPManager:
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager


async def run_async(coro):
    loop = asyncio.get_event_loop()
    return await loop.run_until_complete(coro)

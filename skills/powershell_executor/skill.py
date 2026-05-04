import os
import sys
from typing import Dict, Any

MAX_SCRIPT_LENGTH = 10000


def get_logger():
    try:
        from modules import request_manager
        req_mgr = request_manager.get_request_manager()
        logger_request = req_mgr.create_logger_request('get', name="QuickAI.powershell_executor")
        logger_result = req_mgr.handle_request(logger_request, None)
        return logger_result.get('logger')
    except:
        return None


def get_request_manager():
    try:
        from modules import request_manager
        return request_manager.get_request_manager()
    except:
        return None


skill_info = {
    "name": "powershell_executor",
    "description": "PowerShell 脚本执行器技能，可以运行 PowerShell 命令和脚本。",
    "functions": {
        "run_script": {
            "description": "运行 PowerShell 命令或脚本。重要提示：1. 此技能会自动捕获所有输出和错误，不需要在脚本中手动实现输出捕获。2. 请使用简单直接的命令，如 'python script.py' 或 'dir'，避免生成复杂的脚本。3. 脚本长度限制为 10000 字符。4. 输出长度限制为 50000 字符。5. 命令会在工作目录下执行，使用相对路径即可访问工作区文件。6. AI 只需要调用一次函数，等待执行完成即可，不需要处理确认逻辑。7. 命令异步运行，wait_time 秒后返回当前控制台内容；若命令未完成则附带 command_id 可后续查询。",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "PowerShell 命令或脚本内容。建议使用简单直接的命令，如 'python script.py'、'dir'、'Get-ChildItem' 等。命令会在工作目录下执行。"},
                    "timeout": {"type": "integer", "description": "超时时间（秒），默认为 30"},
                    "wait_time": {"type": "integer", "description": "等待时间（秒），默认 10。命令开始运行后等待此时间再返回结果。若命令已完成则返回完整输出，若未完成则返回当前控制台内容并附带 command_id"}
                },
                "required": ["script"]
            }
        },
        "check_script": {
            "description": "查询后台运行命令的状态和输出。若命令已完成则立即返回结果；若命令未完成，等待 wait_time 秒后返回当前状态和输出。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command_id": {"type": "string", "description": "命令 ID，由 run_script 返回"},
                    "wait_time": {"type": "integer", "description": "等待时间（秒），默认 10。命令完成则立即返回，未完成则等待此时长后返回当前状态"}
                },
                "required": ["command_id"]
            }
        },
        "kill_command": {
            "description": "强制终止后台运行的命令。返回被终止命令的最后输出内容和状态。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command_id": {"type": "string", "description": "命令 ID，由 run_script 返回"}
                },
                "required": ["command_id"]
            }
        }
    }
}


def run_script(script: str, timeout: int = None, wait_time: int = None) -> Dict[str, Any]:
    log = get_logger()
    rm = get_request_manager()

    try:
        script_length = len(script)

        if script_length > MAX_SCRIPT_LENGTH:
            if log:
                log.warning(f"脚本过长: {script_length} 字符，最大允许: {MAX_SCRIPT_LENGTH} 字符")
            return {
                "error": f"脚本过长: {script_length} 字符，最大允许: {MAX_SCRIPT_LENGTH} 字符",
                "script_length": script_length,
                "max_length": MAX_SCRIPT_LENGTH
            }

        actual_timeout = timeout if timeout is not None else 30
        actual_wait = wait_time if wait_time is not None else 10

        if log:
            log.info(f"AI 请求运行 PowerShell 脚本 (长度: {script_length} 字符, 超时: {actual_timeout}s, 等待: {actual_wait}s)")

        script_preview = script[:500] + "..." if len(script) > 500 else script
        message = f"确认运行 PowerShell 脚本 (长度: {script_length} 字符, 超时: {actual_timeout}s, 等待: {actual_wait}s):\n{script_preview}"

        if rm:
            return rm.create_skill_confirmation(
                message=message,
                action="run_powershell_script",
                script=script,
                timeout=actual_timeout,
                wait_time=actual_wait
            )
        else:
            return {
                "requires_confirmation": True,
                "message": message,
                "action": "run_powershell_script",
                "script": script,
                "timeout": actual_timeout,
                "wait_time": actual_wait
            }

    except Exception as e:
        if log:
            log.error(f"运行脚本失败: {str(e)}")
        return {"error": f"运行脚本失败: {str(e)}"}


async def check_script(command_id: str, wait_time: int = None) -> Dict[str, Any]:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from modules import powershell_manager
    actual_wait = wait_time if wait_time is not None else 10
    return await powershell_manager.check_script(command_id, actual_wait)


def kill_command(command_id: str) -> Dict[str, Any]:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from modules import powershell_manager
    return powershell_manager.kill_command(command_id)

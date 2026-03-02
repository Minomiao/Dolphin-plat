import subprocess
from typing import Dict, Any


MAX_SCRIPT_LENGTH = 10000
MAX_OUTPUT_LENGTH = 50000
TIMEOUT = 30


def set_timeout(timeout: int) -> Dict[str, Any]:
    global TIMEOUT
    TIMEOUT = timeout
    return {
        "success": True,
        "timeout": TIMEOUT,
        "message": f"超时时间已设置为: {TIMEOUT} 秒"
    }


skill_info = {
    "name": "powershell_executor",
    "description": "PowerShell 脚本执行器技能，可以运行 PowerShell 命令和脚本。重要提示：此技能会自动捕获所有输出（stdout 和 stderr）以及返回码，不需要在脚本中手动实现输出捕获。请使用简单直接的命令，避免生成复杂的脚本。所有命令都需要用户确认后才能执行。",
    "functions": {
        "set_timeout": {
            "description": "设置脚本执行的超时时间（秒）",
            "parameters": {
                "type": "object",
                "properties": {
                    "timeout": {"type": "integer", "description": "超时时间（秒），默认为 30"}
                },
                "required": ["timeout"]
            }
        },
        "run_script": {
            "description": "请求运行 PowerShell 命令或脚本（需要用户确认，确认后会调用 confirm_run_script 函数执行）。重要提示：1. 此技能会自动捕获所有输出和错误，不需要在脚本中手动实现输出捕获。2. 请使用简单直接的命令，如 'python script.py' 或 'dir'，避免生成复杂的脚本。3. 脚本长度限制为 10000 字符。4. 输出长度限制为 50000 字符。5. 所有命令都需要用户确认后才能执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "PowerShell 命令或脚本内容。建议使用简单直接的命令，如 'python script.py'、'dir'、'Get-ChildItem' 等。"}
                },
                "required": ["script"]
            }
        },
        "confirm_run_script": {
            "description": "确认运行 PowerShell 命令或脚本（在用户确认后调用，执行脚本并返回结果）。此函数会自动捕获标准输出、错误输出和返回码，无需手动处理。",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "PowerShell 命令或脚本内容"}
                },
                "required": ["script"]
            }
        }
    }
}


def run_script(script: str) -> Dict[str, Any]:
    try:
        script_length = len(script)
        
        if script_length > MAX_SCRIPT_LENGTH:
            return {
                "error": f"脚本过长: {script_length} 字符，最大允许: {MAX_SCRIPT_LENGTH} 字符",
                "script_length": script_length,
                "max_length": MAX_SCRIPT_LENGTH
            }
        
        script_preview = script[:500] + "..." if len(script) > 500 else script
        
        return {
            "success": True,
            "script_length": script_length,
            "script_preview": script_preview,
            "requires_confirmation": True,
            "message": "需要用户确认才能运行 PowerShell 脚本，请调用 confirm_run_script 函数进行确认",
            "action": "confirm_run_script",
            "script": script
        }
    
    except Exception as e:
        return {"error": f"请求运行脚本失败: {str(e)}"}


def confirm_run_script(script: str) -> Dict[str, Any]:
    try:
        script_length = len(script)
        
        if script_length > MAX_SCRIPT_LENGTH:
            return {
                "error": f"脚本过长: {script_length} 字符，最大允许: {MAX_SCRIPT_LENGTH} 字符",
                "script_length": script_length,
                "max_length": MAX_SCRIPT_LENGTH
            }
        
        try:
            result = subprocess.run(
                ['powershell', '-Command', script],
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                encoding='utf-8',
                errors='ignore'
            )
            
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            
            if len(stdout) > MAX_OUTPUT_LENGTH:
                stdout = stdout[:MAX_OUTPUT_LENGTH] + f"\n... (输出已截断，共 {len(result.stdout)} 字符)"
            
            if len(stderr) > MAX_OUTPUT_LENGTH:
                stderr = stderr[:MAX_OUTPUT_LENGTH] + f"\n... (错误输出已截断，共 {len(result.stderr)} 字符)"
            
            return {
                "success": True,
                "return_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "script_length": script_length,
                "timeout": TIMEOUT,
                "message": f"用户已确认运行脚本，脚本执行完成，返回码: {result.returncode}",
                "confirmed": True
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"脚本执行超时（{TIMEOUT} 秒）",
                "timeout": TIMEOUT,
                "message": "用户已确认运行脚本，但执行超时"
            }
        
        except Exception as e:
            return {
                "error": f"脚本执行失败: {str(e)}",
                "message": "用户已确认运行脚本，但执行失败"
            }
    
    except Exception as e:
        return {"error": f"确认运行脚本失败: {str(e)}"}

import subprocess
from typing import Dict, Any


CONFIRMATION_REQUIRED = False
MAX_SCRIPT_LENGTH = 10000
MAX_OUTPUT_LENGTH = 50000
TIMEOUT = 30


def set_confirmation_required(required: bool) -> Dict[str, Any]:
    global CONFIRMATION_REQUIRED
    CONFIRMATION_REQUIRED = required
    return {
        "success": True,
        "confirmation_required": CONFIRMATION_REQUIRED,
        "message": f"确认机制已{'启用' if CONFIRMATION_REQUIRED else '禁用'}"
    }


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
    "description": "PowerShell 脚本执行器技能，可以运行 PowerShell 脚本",
    "functions": {
        "set_confirmation_required": {
            "description": "设置是否需要用户确认（启用后，运行脚本前需要用户确认）",
            "parameters": {
                "type": "object",
                "properties": {
                    "required": {"type": "boolean", "description": "是否需要确认"}
                },
                "required": ["required"]
            }
        },
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
            "description": "请求运行 PowerShell 脚本（显示脚本内容，请求用户确认）",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "PowerShell 脚本内容"}
                },
                "required": ["script"]
            }
        },
        "confirm_run_script": {
            "description": "确认运行 PowerShell 脚本（在用户确认后调用）",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "PowerShell 脚本内容"}
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
            "message": f"确认运行 PowerShell 脚本（长度: {script_length} 字符）"
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
                "message": f"脚本执行完成，返回码: {result.returncode}"
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"脚本执行超时（{TIMEOUT} 秒）",
                "timeout": TIMEOUT
            }
        
        except Exception as e:
            return {
                "error": f"脚本执行失败: {str(e)}"
            }
    
    except Exception as e:
        return {"error": f"确认运行脚本失败: {str(e)}"}

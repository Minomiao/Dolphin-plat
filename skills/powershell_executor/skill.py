import subprocess
import sys
import os
from typing import Dict, Any
from pathlib import Path


MAX_SCRIPT_LENGTH = 10000
MAX_OUTPUT_LENGTH = 50000
TIMEOUT = 30


def get_work_dir():
    """获取工作目录"""
    try:
        from modules import request_manager
        req_mgr = request_manager.get_request_manager()
        config_request = req_mgr.create_config_request('load')
        config_data = req_mgr.handle_request(config_request, None)
        return config_data.get('work_directory', 'workplace')
    except:
        return 'workplace'


def get_logger():
    """获取日志记录器"""
    try:
        from modules import request_manager
        req_mgr = request_manager.get_request_manager()
        logger_request = req_mgr.create_logger_request('get', name="QuickAI.powershell_executor")
        logger_result = req_mgr.handle_request(logger_request, None)
        return logger_result.get('logger')
    except:
        return None


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
    "description": "PowerShell 脚本执行器技能，可以运行 PowerShell 命令和脚本。",
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
            "description": "运行 PowerShell 命令或脚本。重要提示：1. 此技能会自动捕获所有输出和错误，不需要在脚本中手动实现输出捕获。2. 请使用简单直接的命令，如 'python script.py' 或 'dir'，避免生成复杂的脚本。3. 脚本长度限制为 10000 字符。4. 输出长度限制为 50000 字符。5. 命令会在工作目录下执行，使用相对路径即可访问工作区文件。6. AI 只需要调用一次函数，等待执行完成即可，不需要处理确认逻辑。", 
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "PowerShell 命令或脚本内容。建议使用简单直接的命令，如 'python script.py'、'dir'、'Get-ChildItem' 等。命令会在工作目录下执行。"}
                },
                "required": ["script"]
            }
        }
    }
}


def get_request_manager():
    """获取请求管理器"""
    try:
        from modules import request_manager
        return request_manager.get_request_manager()
    except:
        return None

def run_script(script: str) -> Dict[str, Any]:
    """运行 PowerShell 脚本（自动处理用户确认和执行）"""
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
        
        # 记录脚本到日志（保留完整内容）
        if log:
            log.info(f"AI 请求运行 PowerShell 脚本 (长度: {script_length} 字符): {script}")
        
        # 使用请求管理器创建技能确认申请
        script_preview = script[:500] + "..." if len(script) > 500 else script
        message = f"确认运行 PowerShell 脚本 (长度: {script_length} 字符):\n{script_preview}"
        
        if rm:
            return rm.create_skill_confirmation(
                message=message,
                action="run_powershell_script",
                script=script,
                script_length=script_length,
                script_preview=script_preview
            )
        else:
            # 降级处理：直接返回确认申请
            return {
                "requires_confirmation": True,
                "message": message,
                "action": "run_powershell_script",
                "script": script,
                "script_length": script_length,
                "script_preview": script_preview
            }
    
    except Exception as e:
        if log:
            log.error(f"运行脚本失败: {str(e)}")
        return {"error": f"运行脚本失败: {str(e)}"}


def _execute_script(script: str, script_length: int) -> Dict[str, Any]:
    """内部函数：执行 PowerShell 脚本"""
    log = get_logger()
    
    try:
        # 获取工作目录
        work_dir = get_work_dir()
        work_path = Path(work_dir).resolve()
        
        # 确保工作目录存在
        if not work_path.exists():
            work_path.mkdir(parents=True, exist_ok=True)
        
        if log:
            log.info(f"在工作目录 '{work_dir}' 下执行脚本: {script}")
        
        try:
            result = subprocess.run(
                ['powershell', '-Command', script],
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                encoding='utf-8',
                errors='ignore',
                cwd=str(work_path)  # 在工作目录下执行
            )
            
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            
            # 记录执行结果到日志
            if log:
                log.info(f"脚本执行完成 - 返回码: {result.returncode}, stdout长度: {len(stdout)}, stderr长度: {len(stderr)}")
                if stderr:
                    log.warning(f"脚本执行有错误输出: {stderr}")
            
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
                "message": f"脚本执行完成，返回码: {result.returncode}",
                "confirmed": True
            }
        
        except subprocess.TimeoutExpired:
            if log:
                log.error(f"脚本执行超时（{TIMEOUT} 秒）: {script}")
            return {
                "success": False,
                "error": f"脚本执行超时（{TIMEOUT} 秒）",
                "timeout": TIMEOUT,
                "message": "脚本执行超时"
            }
        
        except Exception as e:
            if log:
                log.error(f"脚本执行失败: {str(e)}, 脚本: {script}")
            return {
                "error": f"脚本执行失败: {str(e)}",
                "message": "脚本执行失败"
            }
    
    except Exception as e:
        if log:
            log.error(f"执行脚本失败: {str(e)}")
        return {"error": f"执行脚本失败: {str(e)}"}

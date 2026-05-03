from typing import Dict, Any
import sys
import os
from pathlib import Path

MAX_FILE_SIZE = 10 * 1024 * 1024

def get_request_manager():
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from modules import request_manager
        return request_manager.get_request_manager()
    except Exception as e:
        print(f"获取 request_manager 失败: {e}")
        return None

def get_work_dir():
    try:
        req_mgr = get_request_manager()
        if req_mgr:
            config_request = req_mgr.create_config_request('load')
            config_data = req_mgr.handle_request(config_request, None)
            return config_data.get('work_directory', 'workplace')
        return 'workplace'
    except Exception as e:
        print(f"获取工作目录失败: {e}")
        return 'workplace'

def get_backup_manager():
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from modules import backup_manager
        return backup_manager
    except Exception as e:
        print(f"获取 backup_manager 失败: {e}")
        return None


def set_work_directory(directory: str) -> Dict[str, Any]:
    try:
        from modules.request_manager import get_persisted_work_directory, get_ai_work_directory
        base_work_dir = get_persisted_work_directory()
        base_path = Path(base_work_dir).resolve()

        # 获取 AI 当前所在目录，用于解析相对路径
        ai_current_dir = get_ai_work_directory()
        if ai_current_dir:
            current_path = Path(ai_current_dir).resolve()
        else:
            current_path = base_path

        input_path = Path(directory)

        if input_path.is_absolute():
            resolved_path = input_path.resolve()
        else:
            resolved_path = (current_path / input_path).resolve()

        # 验证解析后的路径仍在持久化工作目录下，越界则回退到根目录
        try:
            resolved_path.relative_to(base_path)
        except ValueError:
            resolved_path = base_path

        if not resolved_path.exists():
            return {"error": f"目录不存在: {resolved_path}"}
        if not resolved_path.is_dir():
            return {"error": f"路径不是目录: {resolved_path}"}

        relative_path = str(resolved_path.relative_to(base_path))
        if relative_path == ".":
            relative_path = ""
        temp_work_dir = str(resolved_path)

        return {
            "success": True,
            "work_directory": temp_work_dir,
            "relative_path": relative_path if relative_path else ".",
            "message": f"临时工作目录已切换为: {temp_work_dir}",
            "format_hint": "建议使用相对路径格式，例如: 'subdir' 或 'subdir1/subdir2'，使用 '..' 返回上级目录",
            "warning": "注意：此设置为临时切换，下次对话开始时将恢复为默认工作目录",
            "user_output": f"Work Place --{relative_path or '.'}"
        }
    except Exception as e:
        return {"error": f"设置工作目录失败: {str(e)}"}


skill_info = {
    "name": "file_manager",
    "description": "文件管理器技能，可以创建、修改和删除文件",
    "functions": {
        "set_work_directory": {
            "description": "设置工作目录（所有文件操作将限制在此目录内）。路径必须是当前工作目录的子目录，默认解析为相对路径。",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "工作目录路径（建议使用相对路径格式，例如: 'subdir' 或 'subdir1/subdir2'）"}
                },
                "required": ["directory"]
            }
        },
        "create_file": {
            "description": "创建文件并写入内容。限制：最大文件大小10MB，最大行数500行。提示：创建文件时不要一次性写入过多内容，先创建基本框架，然后使用 modify_file 函数分多次进行修改。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径（相对于工作目录），AI 可以决定文件名和后缀"},
                    "content": {"type": "string", "description": "文件内容，单次不要超过500行"},
                    "encoding": {"type": "string", "description": "文件编码，默认为 'utf-8'"}
                },
                "required": ["file_path", "content"]
            }
        },
        "modify_file": {
            "description": "修改文件内容。需要提供要修改的起始行、结束行、首行内容、末行内容和新内容。限制：单次修改最多500行，最大文件大小10MB。提示：对于大文件修改，建议分多次进行，每次修改范围不要太大，以确保操作的稳定性和可追溯性。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径（相对于工作目录）"},
                    "start_line": {"type": "integer", "description": "要修改的起始行号（从1开始）"},
                    "end_line": {"type": "integer", "description": "要修改的结束行号"},
                    "start_line_content": {"type": "string", "description": "起始行的内容，用于校验"},
                    "end_line_content": {"type": "string", "description": "结束行的内容，用于校验"},
                    "new_lines": {"type": "array", "items": {"type": "string"}, "description": "新的内容行列表，每行一个元素，不需要包含换行符"},
                    "encoding": {"type": "string", "description": "文件编码，默认为 'utf-8'"}
                },
                "required": ["file_path", "start_line", "end_line", "start_line_content", "end_line_content", "new_lines"]
            }
        },
        "delete_file": {
            "description": "删除文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径（相对于工作目录）"}
                },
                "required": ["file_path"]
            }
        }
    }
}


def create_file(file_path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
    try:
        req_mgr = get_request_manager()
        work_dir = get_work_dir()
        
        create_request = req_mgr.create_file_operation_request(
            "create_file",
            file_path=file_path,
            content=content,
            encoding=encoding,
            work_directory=work_dir
        )
        
        result = req_mgr.handle_request(create_request, None)
        if result.get("success"):
            full_path = result.get("file_path", file_path)
            parent = str(Path(full_path).parent)
            filename = Path(full_path).name
            line_count = result.get("line_count", 0)
            if parent and parent != ".":
                result["user_output"] = f"File Change {filename} --{parent} +{line_count} -0"
            else:
                result["user_output"] = f"File Change {filename} +{line_count} -0"
        return result
    except Exception as e:
        return {"error": f"创建文件失败: {str(e)}"}


def modify_file(file_path: str, start_line: int, end_line: int, start_line_content: str, end_line_content: str, new_lines: list, encoding: str = "utf-8") -> Dict[str, Any]:
    try:
        req_mgr = get_request_manager()
        work_dir = get_work_dir()
        
        modify_request = req_mgr.create_file_operation_request(
            "modify_file",
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            start_line_content=start_line_content,
            end_line_content=end_line_content,
            new_lines=new_lines,
            encoding=encoding,
            work_directory=work_dir
        )
        
        result = req_mgr.handle_request(modify_request, None)
        if result.get("success"):
            full_path = result.get("file_path", file_path)
            parent = str(Path(full_path).parent)
            filename = Path(full_path).name
            new_count = result.get("new_lines_count", 0)
            old_count = result.get("modified_lines", 0)
            if parent and parent != ".":
                result["user_output"] = f"File Change {filename} --{parent} +{new_count} -{old_count}"
            else:
                result["user_output"] = f"File Change {filename} +{new_count} -{old_count}"
        return result
    except Exception as e:
        return {"error": f"修改文件失败: {str(e)}"}


def delete_file(file_path: str, confirmed: bool = False) -> Dict[str, Any]:
    if not confirmed:
        return {
            "requires_confirmation": True,
            "message": f"确认删除文件: {file_path}",
            "action": "delete_file",
            "file_path": file_path,
            "work_directory": get_work_dir()
        }

    try:
        req_mgr = get_request_manager()
        work_dir = get_work_dir()
        
        delete_request = req_mgr.create_file_operation_request(
            "delete_file",
            file_path=file_path,
            work_directory=work_dir
        )
        
        result = req_mgr.handle_request(delete_request, None)
        if result.get("success"):
            full_path = result.get("file_path", file_path)
            filename = Path(full_path).name
            result["user_output"] = f"File Change --{filename} Delet"
        return result
    except Exception as e:
        return {"error": f"删除文件失败: {str(e)}"}

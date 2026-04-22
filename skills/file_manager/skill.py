from typing import Dict, Any
import sys
import os

MAX_FILE_SIZE = 10 * 1024 * 1024
CONFIRMATION_REQUIRED = False

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

def get_config():
    try:
        # 现在通过 request_manager 访问配置
        req_mgr = get_request_manager()
        return req_mgr
    except Exception as e:
        print(f"获取 config 失败: {e}")
        return None


def set_work_directory(directory: str) -> Dict[str, Any]:
    try:
        base_work_dir = get_work_dir()
        base_path = Path(base_work_dir).resolve()
        
        input_path = Path(directory)
        
        if input_path.is_absolute():
            resolved_path = input_path.resolve()
            try:
                resolved_path.relative_to(base_path)
            except ValueError:
                return {
                    "error": f"路径必须是当前工作目录的子目录: {base_work_dir}",
                    "suggestion": "请使用相对路径或确保路径在当前工作目录下"
                }
        else:
            resolved_path = (base_path / input_path).resolve()
        
        if not resolved_path.exists():
            return {"error": f"目录不存在: {resolved_path}"}
        if not resolved_path.is_dir():
            return {"error": f"路径不是目录: {resolved_path}"}
        
        relative_path = str(resolved_path.relative_to(base_path))
        temp_work_dir = str(resolved_path)
        
        return {
            "success": True,
            "work_directory": temp_work_dir,
            "relative_path": relative_path,
            "message": f"临时工作目录已切换为: {temp_work_dir}",
            "format_hint": "建议使用相对路径格式，例如: 'subdir' 或 'subdir1/subdir2'",
            "warning": "注意：此设置为临时切换，下次对话开始时将恢复为默认工作目录"
        }
    except Exception as e:
        return {"error": f"设置工作目录失败: {str(e)}"}


def get_work_directory() -> str:
    return get_work_dir()


def set_confirmation_required(required: bool) -> Dict[str, Any]:
    global CONFIRMATION_REQUIRED
    CONFIRMATION_REQUIRED = required
    return {
        "success": True,
        "confirmation_required": CONFIRMATION_REQUIRED,
        "message": f"确认机制已{'启用' if CONFIRMATION_REQUIRED else '禁用'}"
    }


def _is_path_allowed(file_path: str) -> Dict[str, Any]:
    try:
        path = Path(file_path)
        
        work_path = Path(get_work_dir()).resolve()
        
        if path.is_absolute():
            resolved_path = path.resolve()
        else:
            resolved_path = (work_path / path).resolve()
        
        try:
            resolved_path.relative_to(work_path)
            return {"allowed": True, "path": str(resolved_path)}
        except ValueError:
            return {
                "allowed": False,
                "path": str(resolved_path),
                "work_directory": str(work_path),
                "requires_confirmation": True,
                "message": f"路径 '{file_path}' 不在工作目录 '{get_work_dir()}' 内"
            }
    except Exception as e:
        return {
            "allowed": False,
            "path": file_path,
            "error": str(e)
        }


skill_info = {
    "name": "file_manager",
    "description": "文件管理器技能，可以创建、修改和删除文件",
    "functions": {
        "get_work_directory": {
            "description": "获取当前工作目录",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
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
        "set_confirmation_required": {
            "description": "设置是否需要用户确认（启用后，操作工作目录外的文件需要确认）",
            "parameters": {
                "type": "object",
                "properties": {
                    "required": {"type": "boolean", "description": "是否需要确认"}
                },
                "required": ["required"]
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
            "description": "删除文件。需要用户确认才能执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径（相对于工作目录）"}
                },
                "required": ["file_path"]
            }
        },
        "confirm_delete_file": {
            "description": "确认删除文件（在用户确认后调用）",
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


def get_work_directory_func() -> Dict[str, Any]:
    return {
        "success": True,
        "work_directory": get_work_dir()
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
        return result
    except Exception as e:
        return {"error": f"修改文件失败: {str(e)}"}


def delete_file(file_path: str) -> Dict[str, Any]:
    try:
        req_mgr = get_request_manager()
        work_dir = get_work_dir()
        
        delete_request = req_mgr.create_file_operation_request(
            "delete_file",
            file_path=file_path,
            work_directory=work_dir
        )
        
        result = req_mgr.handle_request(delete_request, None)
        return result
    except Exception as e:
        return {"error": f"删除文件失败: {str(e)}"}


def confirm_delete_file(file_path: str) -> Dict[str, Any]:
    try:
        req_mgr = get_request_manager()
        work_dir = get_work_dir()
        
        delete_request = req_mgr.create_file_operation_request(
            "delete_file",
            file_path=file_path,
            work_directory=work_dir
        )
        
        result = req_mgr.handle_request(delete_request, None)
        return result
    except Exception as e:
        return {"error": f"删除文件失败: {str(e)}"}

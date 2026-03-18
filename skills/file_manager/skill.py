from typing import Dict, Any
from pathlib import Path
import sys
import os

MAX_FILE_SIZE = 10 * 1024 * 1024
CONFIRMATION_REQUIRED = False


def get_work_dir():
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from modules import config
        return config.load_config().get('work_directory', 'workplace')
    except:
        return 'workplace'


def get_backup_manager():
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from modules import backup_manager
        return backup_manager
    except:
        return None


def get_config():
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from modules import config
        return config
    except:
        return None


def set_work_directory(directory: str) -> Dict[str, Any]:
    try:
        path = Path(directory)
        if not path.exists():
            return {"error": f"目录不存在: {directory}"}
        if not path.is_dir():
            return {"error": f"路径不是目录: {directory}"}
        work_dir = str(path)
        
        config = get_config()
        if config:
            current_config = config.load_config()
            current_config['work_directory'] = work_dir
            config.save_config(current_config)
        
        return {
            "success": True,
            "work_directory": work_dir,
            "message": f"工作目录已设置为: {work_dir}"
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
            "description": "设置工作目录（所有文件操作将限制在此目录内）",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "工作目录路径"}
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
            "description": "创建文件并写入内容。限制：最大文件大小10MB。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径（相对于工作目录），AI 可以决定文件名和后缀"},
                    "content": {"type": "string", "description": "文件内容"},
                    "encoding": {"type": "string", "description": "文件编码，默认为 'utf-8'"}
                },
                "required": ["file_path", "content"]
            }
        },
        "modify_file": {
            "description": "修改文件内容。需要提供要修改的起始行、结束行、首行内容、末行内容和新内容。限制：单次修改最多200行，最大文件大小10MB。提示：对于大文件修改，建议分多次进行，每次修改范围不要太大，以确保操作的稳定性和可追溯性。",
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
        path_check = _is_path_allowed(file_path)
        if not path_check["allowed"]:
            if CONFIRMATION_REQUIRED:
                return {
                "error": path_check["message"],
                "requires_confirmation": True,
                "action": "create_file",
                "file_path": file_path,
                "work_directory": path_check["work_directory"],
                "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的路径和内容后再进行操作"
            }
            return {"error": path_check["message"], "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的路径和内容后再进行操作"}
        
        content_size = len(content.encode(encoding))
        
        if content_size > MAX_FILE_SIZE:
            return {
                "error": f"文件内容过大: {content_size} 字节，最大允许: {MAX_FILE_SIZE} 字节",
                "content_size": content_size,
                "max_size": MAX_FILE_SIZE,
                "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的内容后再进行操作"
            }
        
        work_dir = get_work_dir()
        path = Path(work_dir) / file_path
        
        parent_dir = path.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
        
        backup_path = None
        pending_count = 0
        backup_mgr = get_backup_manager()
        if path.exists() and backup_mgr:
            backup_path = backup_mgr.backup_file(file_path, work_dir, action="create")
        
        with open(path, 'w', encoding=encoding, errors='ignore') as f:
            f.write(content)
        
        if backup_mgr:
            backup_mgr.record_change(
                action="create",
                file_path=file_path,
                work_dir=work_dir
            )
            pending_count = backup_mgr.get_pending_changes_count()
        
        return {
            "success": True,
            "file_path": str(path),
            "encoding": encoding,
            "content_size": content_size,
            "line_count": len(content.splitlines()),
            "backup_path": backup_path,
            "pending_changes": pending_count,
            "message": f"文件已创建: {file_path}"
        }
    
    except Exception as e:
        return {"error": f"创建文件失败: {str(e)}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件信息后再进行操作"}


def modify_file(file_path: str, start_line: int, end_line: int, start_line_content: str, end_line_content: str, new_lines: list, encoding: str = "utf-8") -> Dict[str, Any]:
    try:
        path_check = _is_path_allowed(file_path)
        if not path_check["allowed"]:
            if CONFIRMATION_REQUIRED:
                return {
                    "error": path_check["message"],
                    "requires_confirmation": True,
                    "action": "modify_file",
                    "file_path": file_path,
                    "work_directory": path_check["work_directory"]
                }
            return {"error": path_check["message"]}
        
        work_dir = get_work_dir()
        path = Path(work_dir) / file_path
        
        if not path.exists():
            return {"error": f"文件不存在: {file_path}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件路径后再进行操作"}
        
        if not path.is_file():
            return {"error": f"路径不是文件: {file_path}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件路径后再进行操作"}
        
        # 读取文件所有行
        with open(path, 'r', encoding=encoding, errors='ignore') as f:
            all_lines = f.readlines()
        
        total_lines = len(all_lines)
        
        # 验证行号范围
        if start_line < 1 or start_line > total_lines:
            return {"error": f"起始行号无效，文件共 {total_lines} 行", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的行号后再进行操作"}
        
        if end_line < start_line or end_line > total_lines:
            return {"error": f"结束行号无效，文件共 {total_lines} 行", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的行号后再进行操作"}
        
        # 检查修改范围是否超过200行
        line_count = end_line - start_line + 1
        if line_count > 200:
            return {"error": f"修改范围过大，单次修改最多支持200行，当前请求 {line_count} 行", "suggestion": "建议使用 read_file 函数重新阅读文件，分多次进行修改，每次修改范围不要超过200行"}
        
        # 计算数组索引（从0开始）
        start_index = start_line - 1
        end_index = end_line
        
        # 检查首末行内容是否匹配
        actual_start_content = all_lines[start_index].strip()
        actual_end_content = all_lines[end_index - 1].strip()
        
        # 如果首末行内容不匹配，进行滚动校验
        if actual_start_content != start_line_content.strip() or actual_end_content != end_line_content.strip():
            # 定义滚动范围（前后10行）
            scroll_start = max(0, start_index - 10)
            scroll_end = min(total_lines, end_index + 10)
            
            # 搜索匹配的首行
            matched_start = None
            for i in range(scroll_start, scroll_end):
                if all_lines[i].strip() == start_line_content.strip():
                    matched_start = i
                    break
            
            # 搜索匹配的末行
            matched_end = None
            if matched_start is not None:
                for i in range(matched_start, min(matched_start + 210, total_lines)):  # 最多搜索210行
                    if all_lines[i].strip() == end_line_content.strip():
                        matched_end = i + 1  # 转换为行号（从1开始）
                        matched_start_line = matched_start + 1  # 转换为行号（从1开始）
                        # 检查匹配的范围是否在合理范围内
                        if matched_end - matched_start_line + 1 == line_count:
                            # 更新行号和索引
                            start_line = matched_start_line
                            end_line = matched_end
                            start_index = matched_start
                            end_index = matched_end
                            break
            
            # 如果没有找到匹配的首末行
            if matched_start is None or matched_end is None:
                return {
                    "error": "首末行内容不匹配，且在前后10行范围内未找到相同内容",
                    "actual_start_content": actual_start_content,
                    "actual_end_content": actual_end_content,
                    "expected_start_content": start_line_content.strip(),
                    "expected_end_content": end_line_content.strip(),
                    "start_line": start_line,
                    "end_line": end_line,
                    "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的行号和内容后再进行修改"
                }
        
        # 备份文件
        backup_path = None
        pending_count = 0
        backup_mgr = get_backup_manager()
        if backup_mgr:
            backup_path = backup_mgr.backup_file(file_path, work_dir, action="modify")
        
        # 构建新的文件内容
        new_content = []
        new_content.extend(all_lines[:start_index])
        new_content.extend([line + '\n' if not line.endswith('\n') else line for line in new_lines])
        new_content.extend(all_lines[end_index:])
        
        # 写入新内容
        with open(path, 'w', encoding=encoding, errors='ignore') as f:
            f.writelines(new_content)
        
        # 记录变更
        if backup_mgr:
            backup_mgr.record_change(
                action="modify",
                file_path=file_path,
                work_dir=work_dir
            )
            pending_count = backup_mgr.get_pending_changes_count()
        
        # 计算内容大小
        new_content_str = ''.join(new_content)
        new_content_size = len(new_content_str.encode(encoding))
        
        return {
            "success": True,
            "file_path": str(path),
            "encoding": encoding,
            "start_line": start_line,
            "end_line": end_line,
            "modified_lines": line_count,
            "new_lines_count": len(new_lines),
            "total_lines": total_lines,
            "new_content_size": new_content_size,
            "backup_path": backup_path,
            "pending_changes": pending_count,
            "message": f"文件已修改: {file_path}，修改范围第 {start_line}-{end_line} 行"
        }
    
    except Exception as e:
        return {"error": f"修改文件失败: {str(e)}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件信息后再进行操作"}


def delete_file(file_path: str) -> Dict[str, Any]:
    try:
        path_check = _is_path_allowed(file_path)
        if not path_check["allowed"]:
            if CONFIRMATION_REQUIRED:
                return {
                "error": path_check["message"],
                "requires_confirmation": True,
                "action": "delete_file",
                "file_path": file_path,
                "work_directory": path_check["work_directory"],
                "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的路径后再进行操作"
            }
            return {"error": path_check["message"], "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的路径后再进行操作"}
        
        work_dir = get_work_dir()
        path = Path(work_dir) / file_path
        
        if not path.exists():
            return {"error": f"文件不存在: {file_path}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件路径后再进行操作"}
        
        if not path.is_file():
            return {"error": f"路径不是文件: {file_path}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件路径后再进行操作"}
        
        file_size = path.stat().st_size
        
        backup_path = None
        backup_mgr = get_backup_manager()
        if backup_mgr:
            backup_path = backup_mgr.backup_file(file_path, work_dir, action="delete")
        
        return {
            "success": True,
            "file_path": str(path),
            "file_size": file_size,
            "backup_path": backup_path,
            "requires_confirmation": True,
            "message": f"确认删除文件: {file_path} (大小: {file_size} 字节)"
        }
    
    except Exception as e:
        return {"error": f"删除文件失败: {str(e)}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件信息后再进行操作"}


def confirm_delete_file(file_path: str) -> Dict[str, Any]:
    try:
        work_dir = get_work_dir()
        path = Path(work_dir) / file_path
        
        if not path.exists():
            return {"error": f"文件不存在: {file_path}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件路径后再进行操作"}
        
        path.unlink()
        
        pending_count = 0
        backup_mgr = get_backup_manager()
        if backup_mgr:
            backup_mgr.record_change(
                action="delete",
                file_path=file_path,
                work_dir=work_dir
            )
            pending_count = backup_mgr.get_pending_changes_count()
        
        return {
            "success": True,
            "file_path": str(path),
            "pending_changes": pending_count,
            "message": f"文件已删除: {file_path}"
        }
    
    except Exception as e:
        return {"error": f"删除文件失败: {str(e)}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件信息后再进行操作"}
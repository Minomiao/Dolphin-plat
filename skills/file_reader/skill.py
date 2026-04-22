import os
from typing import Dict, Any, List
from pathlib import Path
import sys

CONFIRMATION_REQUIRED = False
MAX_FILES_TO_READ = 1000
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_SEARCH_RESULTS = 500
MAX_FILES_TO_SEARCH_IN_CONTENT = 100


def get_work_dir():
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from modules import request_manager
        req_mgr = request_manager.get_request_manager()
        config_request = req_mgr.create_config_request('load')
        config_data = req_mgr.handle_request(config_request, None)
        return config_data.get('work_directory', 'workplace')
    except:
        return 'workplace'


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
    "name": "file_reader",
    "description": "文件阅读器技能，可以搜索文件、列出目录结构和阅读文件内容",
    "functions": {
        "get_work_directory": {
            "description": "获取当前工作目录",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
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
        "search_files": {
            "description": "在指定目录下搜索文件（支持文件名和内容搜索）。限制：最多返回500个结果，内容搜索最多检查100个文件，跳过大于10MB的文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "搜索模式（文件名或内容关键词）"},
                    "directory": {"type": "string", "description": "搜索目录（相对于工作目录），默认为当前目录"},
                    "search_in_content": {"type": "boolean", "description": "是否在文件内容中搜索，默认为 false"},
                    "file_extension": {"type": "string", "description": "文件扩展名过滤（如 '.py', '.txt'），默认为所有文件"}
                },
                "required": ["pattern"]
            }
        },
        "list_directory": {
            "description": "列出目录结构（树形结构显示）。限制：最多显示1000个文件，最大递归深度10。",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "目录路径（相对于工作目录），默认为当前目录"},
                    "max_depth": {"type": "integer", "description": "最大递归深度，默认为 10"},
                    "show_hidden": {"type": "boolean", "description": "是否显示隐藏文件，默认为 false"}
                },
                "required": []
            }
        },
        "read_file": {
            "description": "读取文件内容。每次最多读取400行，支持分页读取。限制：最大文件大小10MB。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径（相对于工作目录）"},
                    "offset": {"type": "integer", "description": "起始行号（从0开始），默认为0"},
                    "limit": {"type": "integer", "description": "读取行数，默认为400，最大为400"},
                    "encoding": {"type": "string", "description": "文件编码，默认为 'utf-8'"}
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


def search_files(pattern: str, directory: str = ".", search_in_content: bool = False, file_extension: str = None) -> Dict[str, Any]:
    try:
        path_check = _is_path_allowed(directory)
        if not path_check["allowed"]:
            if CONFIRMATION_REQUIRED:
                return {
                "error": path_check["message"],
                "requires_confirmation": True,
                "action": "search_files",
                "directory": directory,
                "work_directory": path_check["work_directory"],
                "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的路径后再进行操作"
            }
            return {"error": path_check["message"], "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的路径后再进行操作"}
        
        search_path = Path(get_work_dir()) / directory
        
        if not search_path.exists():
            return {"error": f"目录不存在: {directory}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的目录路径后再进行操作"}
        
        if not search_path.is_dir():
            return {"error": f"路径不是目录: {directory}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的目录路径后再进行操作"}
        
        results = []
        files_searched = 0
        
        if search_in_content:
            for file_path in search_path.rglob("*"):
                if not file_path.is_file():
                    continue
                
                if file_extension and file_path.suffix != file_extension:
                    continue
                
                if len(results) >= MAX_SEARCH_RESULTS:
                    break
                
                if files_searched >= MAX_FILES_TO_SEARCH_IN_CONTENT:
                    break
                
                files_searched += 1
                
                try:
                    file_size = file_path.stat().st_size
                    if file_size > MAX_FILE_SIZE:
                        continue
                    
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if pattern.lower() in content.lower():
                            relative_path = file_path.relative_to(Path(get_work_dir()))
                            results.append({
                                "name": file_path.name,
                                "path": str(relative_path),
                                "size": file_size
                            })
                except:
                    pass
        else:
            for file_path in search_path.rglob("*"):
                if not file_path.is_file():
                    continue
                
                if file_extension and file_path.suffix != file_extension:
                    continue
                
                if len(results) >= MAX_SEARCH_RESULTS:
                    break
                
                if pattern.lower() in file_path.name.lower():
                    relative_path = file_path.relative_to(Path(get_work_dir()))
                    results.append({
                        "name": file_path.name,
                        "path": str(relative_path),
                        "size": file_path.stat().st_size
                    })
        
        truncated = False
        if search_in_content:
            truncated = files_searched >= MAX_FILES_TO_SEARCH_IN_CONTENT or len(results) >= MAX_SEARCH_RESULTS
        else:
            truncated = len(results) >= MAX_SEARCH_RESULTS
        
        return {
            "success": True,
            "directory": directory,
            "pattern": pattern,
            "search_in_content": search_in_content,
            "count": len(results),
            "files": results,
            "truncated": truncated,
            "max_results": MAX_SEARCH_RESULTS,
            "files_searched": files_searched if search_in_content else None
        }
    
    except Exception as e:
        return {"error": f"搜索文件失败: {str(e)}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件信息后再进行操作"}


def list_directory(directory: str = ".", max_depth: int = 10, show_hidden: bool = False) -> Dict[str, Any]:
    try:
        path_check = _is_path_allowed(directory)
        if not path_check["allowed"]:
            if CONFIRMATION_REQUIRED:
                return {
                "error": path_check["message"],
                "requires_confirmation": True,
                "action": "list_directory",
                "directory": directory,
                "work_directory": path_check["work_directory"],
                "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的路径后再进行操作"
            }
            return {"error": path_check["message"], "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的路径后再进行操作"}
        
        list_path = Path(get_work_dir()) / directory
        
        if not list_path.exists():
            return {"error": f"目录不存在: {directory}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的目录路径后再进行操作"}
        
        if not list_path.is_dir():
            return {"error": f"路径不是目录: {directory}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的目录路径后再进行操作"}
        
        file_count = 0
        
        def build_tree(path: Path, prefix: str = "", depth: int = 0) -> List[str]:
            nonlocal file_count
            if depth > max_depth:
                return []
            
            if file_count >= MAX_FILES_TO_READ:
                return [f"{prefix}└── ... (已达到最大文件数量限制 {MAX_FILES_TO_READ})"]
            
            lines = []
            try:
                items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except:
                return lines
            
            for i, item in enumerate(items):
                if not show_hidden and item.name.startswith('.'):
                    continue
                
                if file_count >= MAX_FILES_TO_READ:
                    lines.append(f"{prefix}└── ... (已达到最大文件数量限制 {MAX_FILES_TO_READ})")
                    break
                
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                lines.append(f"{prefix}{current_prefix}{item.name}")
                file_count += 1
                
                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    lines.extend(build_tree(item, prefix + extension, depth + 1))
            
            return lines
        
        tree_lines = build_tree(list_path)
        
        return {
            "success": True,
            "directory": directory,
            "tree": "\n".join(tree_lines),
            "line_count": len(tree_lines),
            "file_count": file_count,
            "truncated": file_count >= MAX_FILES_TO_READ
        }
    
    except Exception as e:
        return {"error": f"列出目录失败: {str(e)}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件信息后再进行操作"}


def read_file(file_path: str, offset: int = 0, limit: int = 400, encoding: str = "utf-8") -> Dict[str, Any]:
    try:
        path_check = _is_path_allowed(file_path)
        if not path_check["allowed"]:
            if CONFIRMATION_REQUIRED:
                return {
                "error": path_check["message"],
                "requires_confirmation": True,
                "action": "read_file",
                "file_path": file_path,
                "work_directory": path_check["work_directory"],
                "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的路径后再进行操作"
            }
            return {"error": path_check["message"], "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的路径后再进行操作"}
        
        path = Path(get_work_dir()) / file_path
        
        if not path.exists():
            return {"error": f"文件不存在: {file_path}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件路径后再进行操作"}
        
        if not path.is_file():
            return {"error": f"路径不是文件: {file_path}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件路径后再进行操作"}
        
        file_size = path.stat().st_size
        
        if file_size > MAX_FILE_SIZE:
            return {
                "error": f"文件过大: {file_path} (大小: {file_size} 字节，最大允许: {MAX_FILE_SIZE} 字节)",
                "file_size": file_size,
                "max_size": MAX_FILE_SIZE,
                "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件信息后再进行操作"
            }
        
        with open(path, 'r', encoding=encoding, errors='ignore') as f:
            all_lines = f.readlines()
        
        total_lines = len(all_lines)
        
        if offset >= total_lines:
            return {
                "success": True,
                "file_path": str(path),
                "encoding": encoding,
                "content": "",
                "lines": [],
                "line_count": 0,
                "total_lines": total_lines,
                "offset": offset,
                "limit": limit,
                "has_more": False,
                "size": file_size,
                "message": f"已到达文件末尾，文件共 {total_lines} 行"
            }
        
        end_line = min(offset + limit, total_lines)
        selected_lines = all_lines[offset:end_line]
        
        lines_with_numbers = []
        for i, line in enumerate(selected_lines):
            line_number = offset + i + 1
            lines_with_numbers.append(f"{line_number}: {line.rstrip()}")
        
        content_with_numbers = "\n".join(lines_with_numbers)
        
        return {
            "success": True,
            "file_path": str(path),
            "encoding": encoding,
            "content": content_with_numbers,
            "lines": lines_with_numbers,
            "line_count": len(selected_lines),
            "total_lines": total_lines,
            "offset": offset,
            "limit": limit,
            "start_line": offset + 1,
            "end_line": end_line,
            "has_more": end_line < total_lines,
            "size": file_size,
            "message": f"读取第 {offset + 1}-{end_line} 行，共 {total_lines} 行"
        }
    
    except Exception as e:
        return {"error": f"读取文件失败: {str(e)}", "suggestion": "建议使用 read_file 函数重新阅读文件，获取正确的文件信息后再进行操作"}
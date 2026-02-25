from typing import Dict, Any
from pathlib import Path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules import config

def get_work_dir():
    return config.load_config().get('work_directory', 'workplace')

CONFIRMATION_REQUIRED = False

MAX_FILE_SIZE = 10 * 1024 * 1024


def set_work_directory(directory: str) -> Dict[str, Any]:
    global WORK_DIR
    try:
        path = Path(directory)
        if not path.exists():
            return {"error": f"目录不存在: {directory}"}
        if not path.is_dir():
            return {"error": f"路径不是目录: {directory}"}
        WORK_DIR = str(path)
        
        current_config = config.load_config()
        current_config['work_directory'] = WORK_DIR
        config.save_config(current_config)
        
        return {
            "success": True,
            "work_directory": WORK_DIR,
            "message": f"工作目录已设置为: {WORK_DIR}"
        }
    except Exception as e:
        return {"error": f"设置工作目录失败: {str(e)}"}


def get_work_directory() -> str:
    return WORK_DIR


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
            "description": "修改文件内容。需要提供原有内容和修改后的内容。限制：最大文件大小10MB。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径（相对于工作目录）"},
                    "original_content": {"type": "string", "description": "文件的原有内容（用于验证）"},
                    "new_content": {"type": "string", "description": "修改后的新内容"},
                    "encoding": {"type": "string", "description": "文件编码，默认为 'utf-8'"}
                },
                "required": ["file_path", "original_content", "new_content"]
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
                    "work_directory": path_check["work_directory"]
                }
            return {"error": path_check["message"]}
        
        content_size = len(content.encode(encoding))
        
        if content_size > MAX_FILE_SIZE:
            return {
                "error": f"文件内容过大: {content_size} 字节，最大允许: {MAX_FILE_SIZE} 字节",
                "content_size": content_size,
                "max_size": MAX_FILE_SIZE
            }
        
        path = Path(get_work_dir()) / file_path
        
        parent_dir = path.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding=encoding, errors='ignore') as f:
            f.write(content)
        
        return {
            "success": True,
            "file_path": str(path),
            "encoding": encoding,
            "content_size": content_size,
            "line_count": len(content.splitlines()),
            "message": f"文件已创建: {file_path}"
        }
    
    except Exception as e:
        return {"error": f"创建文件失败: {str(e)}"}


def modify_file(file_path: str, original_content: str, new_content: str, encoding: str = "utf-8") -> Dict[str, Any]:
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
        
        new_content_size = len(new_content.encode(encoding))
        
        if new_content_size > MAX_FILE_SIZE:
            return {
                "error": f"新内容过大: {new_content_size} 字节，最大允许: {MAX_FILE_SIZE} 字节",
                "new_content_size": new_content_size,
                "max_size": MAX_FILE_SIZE
            }
        
        path = Path(get_work_dir()) / file_path
        
        if not path.exists():
            return {"error": f"文件不存在: {file_path}"}
        
        if not path.is_file():
            return {"error": f"路径不是文件: {file_path}"}
        
        with open(path, 'r', encoding=encoding, errors='ignore') as f:
            current_content = f.read()
        
        if current_content != original_content:
            return {
                "error": "文件内容已更改，原有内容不匹配",
                "current_content_length": len(current_content),
                "original_content_length": len(original_content)
            }
        
        with open(path, 'w', encoding=encoding, errors='ignore') as f:
            f.write(new_content)
        
        old_line_count = len(original_content.splitlines())
        new_line_count = len(new_content.splitlines())
        
        return {
            "success": True,
            "file_path": str(path),
            "encoding": encoding,
            "old_content_size": len(original_content.encode(encoding)),
            "new_content_size": new_content_size,
            "old_line_count": old_line_count,
            "new_line_count": new_line_count,
            "message": f"文件已修改: {file_path}"
        }
    
    except Exception as e:
        return {"error": f"修改文件失败: {str(e)}"}


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
                    "work_directory": path_check["work_directory"]
                }
            return {"error": path_check["message"]}
        
        path = Path(get_work_dir()) / file_path
        
        if not path.exists():
            return {"error": f"文件不存在: {file_path}"}
        
        if not path.is_file():
            return {"error": f"路径不是文件: {file_path}"}
        
        file_size = path.stat().st_size
        
        return {
            "success": True,
            "file_path": str(path),
            "file_size": file_size,
            "requires_confirmation": True,
            "message": f"确认删除文件: {file_path} (大小: {file_size} 字节)"
        }
    
    except Exception as e:
        return {"error": f"删除文件失败: {str(e)}"}


def confirm_delete_file(file_path: str) -> Dict[str, Any]:
    try:
        path = Path(get_work_dir()) / file_path
        
        if not path.exists():
            return {"error": f"文件不存在: {file_path}"}
        
        path.unlink()
        
        return {
            "success": True,
            "file_path": str(path),
            "message": f"文件已删除: {file_path}"
        }
    
    except Exception as e:
        return {"error": f"删除文件失败: {str(e)}"}

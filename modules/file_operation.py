import os
from pathlib import Path
from typing import Dict, Any, Optional
from modules import logger

log = logger.get_logger("Dolphin.file_operation")

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_LINE_COUNT = 600

class FileOperation:
    """文件操作管理器"""
    
    def __init__(self):
        log.info("FileOperation 初始化完成")
    
    def get_work_directory(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取工作目录"""
        try:
            from modules import config
            work_directory = config.load_config().get('work_directory', 'workplace')
            return {
                "success": True,
                "work_directory": work_directory
            }
        except Exception as e:
            log.error(f"获取工作目录失败: {e}")
            return {
                "error": f"获取工作目录失败: {str(e)}"
            }
    
    def create_file(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建文件"""
        try:
            # 获取参数
            file_path = request_data.get('file_path')
            content = request_data.get('content')
            encoding = request_data.get('encoding', 'utf-8')
            work_directory = request_data.get('work_directory')
            
            if not file_path:
                return {"error": "缺少 file_path 参数"}
            if content is None:
                return {"error": "缺少 content 参数"}
            if not work_directory:
                return {"error": "缺少 work_directory 参数"}
            
            # 验证内容大小
            content_size = len(content.encode(encoding))
            if content_size > MAX_FILE_SIZE:
                return {
                    "error": f"文件内容过大: {content_size} 字节，最大允许: {MAX_FILE_SIZE} 字节"
                }
            
            # 验证行数
            line_count = len(content.splitlines())
            if line_count > MAX_LINE_COUNT:
                return {
                    "error": f"文件行数过多: {line_count} 行，最大允许: {MAX_LINE_COUNT} 行"
                }
            
            # 构建完整路径
            work_path = Path(work_directory).resolve()
            file_path_obj = Path(file_path)
            
            if file_path_obj.is_absolute():
                # 绝对路径必须在工作目录内
                try:
                    resolved_path = file_path_obj.resolve()
                    resolved_path.relative_to(work_path)
                except ValueError:
                    return {
                        "error": f"路径必须是工作目录的子目录: {work_directory}"
                    }
            else:
                # 相对路径相对于工作目录
                resolved_path = (work_path / file_path_obj).resolve()
            
            # 确保父目录存在
            parent_dir = resolved_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(resolved_path, 'w', encoding=encoding, errors='ignore') as f:
                f.write(content)
            
            # 记录备份（如果有）
            backup_path = None
            pending_count = 0
            try:
                from modules import backup_manager
                backup_mgr = backup_manager.get_backup_manager()
                if backup_mgr:
                    backup_path = backup_mgr.backup_file(str(file_path_obj), work_directory, action="create")
                    backup_mgr.record_change(
                        action="create",
                        file_path=str(file_path_obj),
                        work_dir=work_directory
                    )
                    pending_count = backup_mgr.get_pending_changes_count()
            except Exception as e:
                log.warning(f"备份操作失败: {e}")
            
            return {
                "success": True,
                "file_path": str(resolved_path),
                "encoding": encoding,
                "content_size": content_size,
                "line_count": line_count,
                "backup_path": backup_path,
                "pending_changes": pending_count,
                "message": f"文件已创建: {file_path}"
            }
        except Exception as e:
            log.error(f"创建文件失败: {e}")
            return {
                "error": f"创建文件失败: {str(e)}"
            }
    
    def read_file(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """读取文件"""
        try:
            # 获取参数
            file_path = request_data.get('file_path')
            encoding = request_data.get('encoding', 'utf-8')
            offset = request_data.get('offset', 0)
            limit = request_data.get('limit', 400)
            work_directory = request_data.get('work_directory')
            
            if not file_path:
                return {"error": "缺少 file_path 参数"}
            if not work_directory:
                return {"error": "缺少 work_directory 参数"}
            
            # 构建完整路径
            work_path = Path(work_directory).resolve()
            file_path_obj = Path(file_path)
            
            if file_path_obj.is_absolute():
                # 绝对路径必须在工作目录内
                try:
                    resolved_path = file_path_obj.resolve()
                    resolved_path.relative_to(work_path)
                except ValueError:
                    return {
                        "error": f"路径必须是工作目录的子目录: {work_directory}"
                    }
            else:
                # 相对路径相对于工作目录
                resolved_path = (work_path / file_path_obj).resolve()
            
            # 检查文件是否存在
            if not resolved_path.exists():
                return {"error": f"文件不存在: {file_path}"}
            if not resolved_path.is_file():
                return {"error": f"路径不是文件: {file_path}"}
            
            # 检查文件大小
            file_size = resolved_path.stat().st_size
            if file_size > MAX_FILE_SIZE:
                return {
                    "error": f"文件过大: {file_size} 字节，最大允许: {MAX_FILE_SIZE} 字节"
                }
            
            # 读取文件内容
            with open(resolved_path, 'r', encoding=encoding, errors='ignore') as f:
                all_lines = f.readlines()
            
            total_lines = len(all_lines)
            
            # 验证偏移量
            if offset >= total_lines:
                return {
                    "success": True,
                    "file_path": str(resolved_path),
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
            
            # 计算读取范围
            end_line = min(offset + limit, total_lines)
            selected_lines = all_lines[offset:end_line]
            
            # 构建带行号的内容
            lines_with_numbers = []
            for i, line in enumerate(selected_lines):
                line_number = offset + i + 1
                lines_with_numbers.append(f"{line_number}: {line.rstrip()}")
            
            content_with_numbers = "\n".join(lines_with_numbers)
            
            return {
                "success": True,
                "file_path": str(resolved_path),
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
            log.error(f"读取文件失败: {e}")
            return {
                "error": f"读取文件失败: {str(e)}"
            }
    
    def modify_file(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """修改文件"""
        try:
            # 获取参数
            file_path = request_data.get('file_path')
            start_line = request_data.get('start_line')
            end_line = request_data.get('end_line')
            start_line_content = request_data.get('start_line_content')
            end_line_content = request_data.get('end_line_content')
            new_lines = request_data.get('new_lines')
            encoding = request_data.get('encoding', 'utf-8')
            work_directory = request_data.get('work_directory')
            
            if not file_path:
                return {"error": "缺少 file_path 参数"}
            if start_line is None or end_line is None:
                return {"error": "缺少 start_line 或 end_line 参数"}
            if start_line_content is None or end_line_content is None:
                return {"error": "缺少 start_line_content 或 end_line_content 参数"}
            if new_lines is None:
                return {"error": "缺少 new_lines 参数"}
            if not work_directory:
                return {"error": "缺少 work_directory 参数"}
            
            # 构建完整路径
            work_path = Path(work_directory).resolve()
            file_path_obj = Path(file_path)
            
            if file_path_obj.is_absolute():
                # 绝对路径必须在工作目录内
                try:
                    resolved_path = file_path_obj.resolve()
                    resolved_path.relative_to(work_path)
                except ValueError:
                    return {
                        "error": f"路径必须是工作目录的子目录: {work_directory}"
                    }
            else:
                # 相对路径相对于工作目录
                resolved_path = (work_path / file_path_obj).resolve()
            
            # 检查文件是否存在
            if not resolved_path.exists():
                return {"error": f"文件不存在: {file_path}"}
            if not resolved_path.is_file():
                return {"error": f"路径不是文件: {file_path}"}
            
            # 读取文件所有行
            with open(resolved_path, 'r', encoding=encoding, errors='ignore') as f:
                all_lines = f.readlines()
            
            total_lines = len(all_lines)
            
            # 验证行号范围
            if start_line < 1 or start_line > total_lines:
                return {"error": f"起始行号无效，文件共 {total_lines} 行"}
            
            if end_line < start_line or end_line > total_lines:
                return {"error": f"结束行号无效，文件共 {total_lines} 行"}
            
            # 检查修改范围是否超过600行
            line_count = end_line - start_line + 1
            if line_count > 600:
                return {"error": f"修改范围过大，单次修改最多支持600行，当前请求 {line_count} 行"}
            
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
                        "end_line": end_line
                    }
            
            # 备份文件
            backup_path = None
            pending_count = 0
            try:
                from modules import backup_manager
                backup_mgr = backup_manager.get_backup_manager()
                if backup_mgr:
                    backup_path = backup_mgr.backup_file(str(file_path_obj), work_directory, action="modify")
            except Exception as e:
                log.warning(f"备份操作失败: {e}")
            
            # 构建新的文件内容
            new_content = []
            new_content.extend(all_lines[:start_index])
            new_content.extend([line + '\n' if not line.endswith('\n') else line for line in new_lines])
            new_content.extend(all_lines[end_index:])
            
            # 写入新内容
            with open(resolved_path, 'w', encoding=encoding, errors='ignore') as f:
                f.writelines(new_content)
            
            # 记录变更
            try:
                from modules import backup_manager
                backup_mgr = backup_manager.get_backup_manager()
                if backup_mgr:
                    backup_mgr.record_change(
                        action="modify",
                        file_path=str(file_path_obj),
                        work_dir=work_directory
                    )
                    pending_count = backup_mgr.get_pending_changes_count()
            except Exception as e:
                log.warning(f"记录变更失败: {e}")
            
            # 计算内容大小
            new_content_str = ''.join(new_content)
            new_content_size = len(new_content_str.encode(encoding))
            
            return {
                "success": True,
                "file_path": str(resolved_path),
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
            log.error(f"修改文件失败: {e}")
            return {
                "error": f"修改文件失败: {str(e)}"
            }
    
    def delete_file(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """删除文件"""
        try:
            # 获取参数
            file_path = request_data.get('file_path')
            work_directory = request_data.get('work_directory')
            
            if not file_path:
                return {"error": "缺少 file_path 参数"}
            if not work_directory:
                return {"error": "缺少 work_directory 参数"}
            
            # 构建完整路径
            work_path = Path(work_directory).resolve()
            file_path_obj = Path(file_path)
            
            if file_path_obj.is_absolute():
                # 绝对路径必须在工作目录内
                try:
                    resolved_path = file_path_obj.resolve()
                    resolved_path.relative_to(work_path)
                except ValueError:
                    return {
                        "error": f"路径必须是工作目录的子目录: {work_directory}"
                    }
            else:
                # 相对路径相对于工作目录
                resolved_path = (work_path / file_path_obj).resolve()
            
            # 检查文件是否存在
            if not resolved_path.exists():
                return {"error": f"文件不存在: {file_path}"}
            if not resolved_path.is_file():
                return {"error": f"路径不是文件: {file_path}"}
            
            file_size = resolved_path.stat().st_size
            
            # 备份文件
            backup_path = None
            try:
                from modules import backup_manager
                backup_mgr = backup_manager.get_backup_manager()
                if backup_mgr:
                    backup_path = backup_mgr.backup_file(str(file_path_obj), work_directory, action="delete")
            except Exception as e:
                log.warning(f"备份操作失败: {e}")
            
            # 实际删除文件
            resolved_path.unlink()
            
            # 记录变更
            pending_count = 0
            try:
                from modules import backup_manager
                backup_mgr = backup_manager.get_backup_manager()
                if backup_mgr:
                    backup_mgr.record_change(
                        action="delete",
                        file_path=str(file_path_obj),
                        work_dir=work_directory
                    )
                    pending_count = backup_mgr.get_pending_changes_count()
            except Exception as e:
                log.warning(f"记录变更失败: {e}")
            
            return {
                "success": True,
                "file_path": str(resolved_path),
                "file_size": file_size,
                "backup_path": backup_path,
                "pending_changes": pending_count,
                "message": f"文件已删除: {file_path}"
            }
        except Exception as e:
            log.error(f"删除文件失败: {e}")
            return {
                "error": f"删除文件失败: {str(e)}"
            }
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理文件操作请求"""
        operation_type = request.get("operation_type")
        
        if operation_type == "get_work_directory":
            return self.get_work_directory(request)
        elif operation_type == "create_file":
            return self.create_file(request)
        elif operation_type == "read_file":
            return self.read_file(request)
        elif operation_type == "modify_file":
            return self.modify_file(request)
        elif operation_type == "delete_file":
            return self.delete_file(request)
        else:
            return {"error": "未知的操作类型"}

# 单例模式
_file_operation = None

def get_file_operation() -> FileOperation:
    global _file_operation
    if _file_operation is None:
        _file_operation = FileOperation()
    return _file_operation
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
from modules.logger import get_logger
from modules import bootstrap as app_paths

log = get_logger("Dolphin.backup_manager")

from rich.console import Console, Group
from rich.table import Table
from rich.text import Text

console = Console()

BACKUP_DIR = app_paths.BACKUP_DIR

# 对话级别的备份管理
dialog_backups = {}
current_dialog_id = None

def set_current_dialog_id(dialog_id: str):
    """设置当前对话ID"""
    global current_dialog_id
    current_dialog_id = dialog_id
    log.info(f"当前对话ID已设置: {dialog_id}")

def get_current_dialog_id() -> Optional[str]:
    """获取当前对话ID"""
    return current_dialog_id

def get_file_backup_dir(file_path: str) -> Path:
    """获取文件的备份目录，每个文件对应一个文件夹"""
    # 将文件路径转换为安全的文件夹名
    safe_name = file_path.replace('/', '_').replace('\\', '_')
    backup_path = Path(BACKUP_DIR) / safe_name
    if not backup_path.exists():
        backup_path.mkdir(parents=True, exist_ok=True)
    return backup_path

def get_file_backup_info_path(file_path: str) -> Path:
    """获取文件的备份信息文件路径"""
    return get_file_backup_dir(file_path) / "backup_info.json"

def get_file_backup_info(file_path: str) -> Dict[str, Any]:
    """获取文件的备份信息"""
    info_path = get_file_backup_info_path(file_path)
    if info_path.exists():
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    
    return {
        "file_path": file_path,
        "backups": []
    }

def save_file_backup_info(file_path: str, info: Dict[str, Any]):
    """保存文件的备份信息"""
    info_path = get_file_backup_info_path(file_path)
    info_path.parent.mkdir(parents=True, exist_ok=True)
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

def backup_file(file_path: str, work_dir: str, action: str = "modify") -> Optional[str]:
    """备份文件并记录信息（对话级别备份）"""
    try:
        global dialog_backups
        dialog_id = get_current_dialog_id()
        
        full_path = Path(work_dir) / file_path
        
        # 对于创建操作，不需要备份
        if action == "create" or not full_path.exists():
            log.debug(f"跳过备份: {file_path} (action={action}, exists={full_path.exists()})")
            return None
        
        # 检查是否已经为当前对话创建过备份
        if dialog_id and file_path in dialog_backups:
            log.debug(f"当前对话已存在备份: {file_path}")
            return dialog_backups[file_path]
        
        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{timestamp}.bak"
        backup_dir = get_file_backup_dir(file_path)
        backup_path = backup_dir / backup_name
        
        log.info(f"备份文件: {file_path} -> {backup_path}")
        
        # 复制文件到备份位置
        shutil.copy2(full_path, backup_path)
        
        # 记录到对话备份
        if dialog_id:
            dialog_backups[file_path] = str(backup_path)
        
        log.debug(f"备份完成: {file_path}, action={action}")
        return str(backup_path)
    except Exception as e:
        log.error(f"备份文件失败: {file_path}, 错误: {e}")
        return None

def record_change(
    action: str,
    file_path: str,
    work_dir: str = ""
) -> Dict[str, Any]:
    """记录文件更改（对话级别）"""
    log.debug(f"记录更改: {file_path}, action={action}")
    
    # 获取文件的备份信息
    info = get_file_backup_info(file_path)
    
    # 检查是否有未确认的备份记录
    unconfirmed_backup = None
    for backup in info["backups"]:
        if not backup.get("confirmed", False):
            unconfirmed_backup = backup
            break
    
    if unconfirmed_backup:
        # 更新现有记录
        unconfirmed_backup["action"] = action
        unconfirmed_backup["timestamp"] = datetime.now().isoformat()
        log.debug(f"更新未确认的备份记录: {file_path}")
    else:
        # 创建新记录
        backup_record = {
            "timestamp": datetime.now().isoformat(),
            "backup_file": dialog_backups.get(file_path),
            "action": action,
            "applied": False,
            "confirmed": False,
            "dialog_id": get_current_dialog_id()
        }
        info["backups"].append(backup_record)
        log.debug(f"创建新的备份记录: {file_path}")
    
    # 更新工作目录
    if work_dir:
        info["work_dir"] = work_dir
    
    # 保存备份信息
    save_file_backup_info(file_path, info)
    
    return info["backups"][-1]

def end_dialog_backup():
    """结束对话备份，清理对话级别的备份记录"""
    global dialog_backups
    dialog_backups.clear()
    log.info("对话备份已结束，备份记录已清理")

def get_all_file_backup_dirs() -> List[Path]:
    """获取所有文件的备份目录"""
    backup_root = Path(BACKUP_DIR)
    if not backup_root.exists():
        return []
    
    return [d for d in backup_root.iterdir() if d.is_dir()]

def get_pending_changes_count() -> int:
    """获取待确认的更改数量"""
    count = 0
    for backup_dir in get_all_file_backup_dirs():
        info_path = backup_dir / "backup_info.json"
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                    count += len([b for b in info["backups"] if not b.get("confirmed", False)])
            except Exception:
                pass
    return count

def get_pending_changes_list() -> List[Dict[str, Any]]:
    """获取待确认的更改列表"""
    pending_changes = []
    
    for backup_dir in get_all_file_backup_dirs():
        info_path = backup_dir / "backup_info.json"
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                    for backup in info["backups"]:
                        if not backup.get("confirmed", False):
                            pending_changes.append({
                                "file_path": info["file_path"],
                                "work_dir": info.get("work_dir", ""),
                                "backup_dir": str(backup_dir),
                                **backup
                            })
            except Exception:
                pass
    
    return pending_changes

def apply_all_changes() -> Dict[str, Any]:
    """应用所有待确认的更改"""
    log.info("开始应用所有待确认的更改")
    results = []
    applied_count = 0
    
    for backup_dir in get_all_file_backup_dirs():
        info_path = backup_dir / "backup_info.json"
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                    
                for backup in info["backups"]:
                    if not backup.get("confirmed", False):
                        backup["confirmed"] = True
                        backup["applied"] = True
                        results.append({
                            "file": info["file_path"],
                            "action": backup["action"],
                            "status": "applied"
                        })
                        applied_count += 1
                        log.info(f"应用更改: {info['file_path']}, action={backup['action']}")
                
                # 保存更新后的信息
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                log.error(f"应用更改失败: {info.get('file_path', 'unknown')}, 错误: {e}")
                results.append({
                    "file": info.get("file_path", "unknown"),
                    "action": "unknown",
                    "status": "failed",
                    "error": str(e)
                })
    
    # 清理对话备份
    end_dialog_backup()
    
    log.info(f"应用更改完成: {applied_count} 个")
    return {
        "success": True,
        "applied_count": applied_count,
        "changes": results,
        "message": f"已应用 {applied_count} 个更改"
    }

def revert_all_changes() -> Dict[str, Any]:
    """撤销所有待确认的更改"""
    log.info("开始撤销所有待确认的更改")
    results = []
    reverted_count = 0
    
    for backup_dir in get_all_file_backup_dirs():
        info_path = backup_dir / "backup_info.json"
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                
                file_path = info["file_path"]
                work_dir = info.get("work_dir", "workplace")
                full_path = Path(work_dir) / file_path
                
                # 从后往前处理备份
                for backup in reversed(info["backups"]):
                    if not backup.get("confirmed", False):
                        action = backup.get("action", "")
                        backup_file = backup.get("backup_file")
                        
                        try:
                            if action == "create":
                                # 创建操作：删除文件
                                if full_path.exists():
                                    full_path.unlink()
                                    results.append({
                                        "file": file_path,
                                        "action": "create",
                                        "status": "reverted (deleted)"
                                    })
                                    reverted_count += 1
                                    log.info(f"撤销创建: 删除文件 {file_path}")
                                else:
                                    results.append({
                                        "file": file_path,
                                        "action": "create",
                                        "status": "file not found"
                                    })
                                    log.warning(f"撤销创建失败: 文件不存在 {file_path}")
                            elif action in ["modify", "delete"]:
                                # 修改或删除操作：从备份恢复
                                if backup_file:
                                    backup_path = Path(backup_file)
                                    if backup_path.exists():
                                        shutil.copy2(backup_path, full_path)
                                        backup_path.unlink()
                                        results.append({
                                            "file": file_path,
                                            "action": action,
                                            "status": "reverted (restored from backup)"
                                        })
                                        reverted_count += 1
                                        log.info(f"撤销{action}: 恢复文件 {file_path}")
                                    else:
                                        results.append({
                                            "file": file_path,
                                            "action": action,
                                            "status": "backup not found"
                                        })
                                        log.warning(f"撤销{action}失败: 备份不存在 {file_path}")
                        except Exception as e:
                            results.append({
                                "file": file_path,
                                "action": action,
                                "status": "failed",
                                "error": str(e)
                            })
                            log.error(f"撤销更改失败: {file_path}, action={action}, 错误: {e}")
                
                # 移除已撤销的备份记录
                info["backups"] = [b for b in info["backups"] if b.get("confirmed", False)]
                
                # 保存更新后的信息
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                log.error(f"撤销更改失败: {info.get('file_path', 'unknown')}, 错误: {e}")
                results.append({
                    "file": info.get("file_path", "unknown"),
                    "action": "unknown",
                    "status": "failed",
                    "error": str(e)
                })
    
    # 清理对话备份
    end_dialog_backup()
    
    log.info(f"撤销更改完成: {reverted_count} 个")
    return {
        "success": True,
        "reverted_count": reverted_count,
        "changes": results,
        "message": f"已撤销 {reverted_count} 个更改"
    }

def show_pending_changes():
    """显示待确认的更改，返回 rich Table"""
    pending = get_pending_changes_list()
    if not pending:
        return None

    table = Table(show_header=True, header_style="bold cyan", border_style="dim", padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("操作", width=8)
    table.add_column("文件")

    action_style_map = {
        "create": "green",
        "delete": "red",
        "modify": "yellow",
    }
    action_label_map = {
        "create": "创建",
        "delete": "删除",
        "modify": "修改",
    }

    for i, change in enumerate(pending, 1):
        action = change["action"]
        label = action_label_map.get(action, action)
        style = action_style_map.get(action, "white")
        table.add_row(
            str(i),
            Text(label, style=style),
            change["file_path"],
        )

    return table

# 单例模式
_backup_manager = None

class BackupManager:
    """备份管理器"""
    
    def __init__(self):
        log.info("BackupManager 初始化完成")
    
    def backup_file(self, file_path: str, work_dir: str, action: str = "modify") -> Optional[str]:
        return backup_file(file_path, work_dir, action)
    
    def record_change(self, action: str, file_path: str, work_dir: str = "") -> Dict[str, Any]:
        return record_change(action, file_path, work_dir)
    
    def get_pending_changes_count(self) -> int:
        return get_pending_changes_count()
    
    def get_pending_changes_list(self) -> List[Dict[str, Any]]:
        return get_pending_changes_list()
    
    def apply_all_changes(self) -> Dict[str, Any]:
        return apply_all_changes()
    
    def revert_all_changes(self) -> Dict[str, Any]:
        return revert_all_changes()
    
    def show_pending_changes(self) -> str:
        return show_pending_changes()
    
    def set_current_dialog_id(self, dialog_id: str):
        set_current_dialog_id(dialog_id)
    
    def end_dialog_backup(self):
        end_dialog_backup()

def get_backup_manager() -> BackupManager:
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import json

BACKUP_DIR = "date/backup"

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
    """备份文件并记录信息"""
    try:
        full_path = Path(work_dir) / file_path
        
        # 对于创建操作，不需要备份
        if action == "create" or not full_path.exists():
            return None
        
        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{timestamp}.bak"
        backup_dir = get_file_backup_dir(file_path)
        backup_path = backup_dir / backup_name
        
        # 复制文件到备份位置
        shutil.copy2(full_path, backup_path)
        
        # 获取并更新备份信息
        info = get_file_backup_info(file_path)
        info["file_path"] = file_path
        info["work_dir"] = work_dir
        
        # 添加备份记录
        backup_record = {
            "timestamp": datetime.now().isoformat(),
            "backup_file": backup_name,
            "action": action,
            "applied": False,
            "confirmed": False
        }
        info["backups"].append(backup_record)
        
        # 保存备份信息
        save_file_backup_info(file_path, info)
        
        return str(backup_path)
    except Exception as e:
        print(f"备份文件失败: {e}")
        return None

def record_change(
    action: str,
    file_path: str,
    work_dir: str = ""
) -> Dict[str, Any]:
    """记录文件更改"""
    # 获取文件的备份信息
    info = get_file_backup_info(file_path)
    
    # 查找是否有未确认的备份记录
    unconfirmed_backup = None
    for backup in info["backups"]:
        if not backup.get("confirmed", False):
            unconfirmed_backup = backup
            break
    
    if unconfirmed_backup:
        # 更新现有记录
        unconfirmed_backup["action"] = action
        unconfirmed_backup["timestamp"] = datetime.now().isoformat()
    else:
        # 创建新记录（对于创建操作）
        if action == "create":
            backup_record = {
                "timestamp": datetime.now().isoformat(),
                "backup_file": None,
                "action": action,
                "applied": False,
                "confirmed": False
            }
            info["backups"].append(backup_record)
    
    # 更新工作目录
    if work_dir:
        info["work_dir"] = work_dir
    
    # 保存备份信息
    save_file_backup_info(file_path, info)
    
    return info["backups"][-1]

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
                
                # 保存更新后的信息
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                results.append({
                    "file": info.get("file_path", "unknown"),
                    "action": "unknown",
                    "status": "failed",
                    "error": str(e)
                })
    
    return {
        "success": True,
        "applied_count": applied_count,
        "changes": results,
        "message": f"已应用 {applied_count} 个更改"
    }

def revert_all_changes() -> Dict[str, Any]:
    """撤销所有待确认的更改"""
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
                                else:
                                    results.append({
                                        "file": file_path,
                                        "action": "create",
                                        "status": "file not found"
                                    })
                            elif action in ["modify", "delete"]:
                                # 修改或删除操作：从备份恢复
                                if backup_file:
                                    backup_path = backup_dir / backup_file
                                    if backup_path.exists():
                                        shutil.copy2(backup_path, full_path)
                                        backup_path.unlink()
                                        results.append({
                                            "file": file_path,
                                            "action": action,
                                            "status": "reverted (restored from backup)"
                                        })
                                        reverted_count += 1
                                    else:
                                        results.append({
                                            "file": file_path,
                                            "action": action,
                                            "status": "backup not found"
                                        })
                        except Exception as e:
                            results.append({
                                "file": file_path,
                                "action": action,
                                "status": "failed",
                                "error": str(e)
                            })
                
                # 移除已撤销的备份记录
                info["backups"] = [b for b in info["backups"] if b.get("confirmed", False)]
                
                # 保存更新后的信息
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                results.append({
                    "file": info.get("file_path", "unknown"),
                    "action": "unknown",
                    "status": "failed",
                    "error": str(e)
                })
    
    return {
        "success": True,
        "reverted_count": reverted_count,
        "changes": results,
        "message": f"已撤销 {reverted_count} 个更改"
    }

def show_pending_changes() -> str:
    """显示待确认的更改"""
    pending = get_pending_changes_list()
    if not pending:
        return "没有待确认的更改"
    
    lines = ["=== 待确认的更改 ==="]
    for i, change in enumerate(pending, 1):
        action_map = {
            "create": "创建",
            "modify": "修改",
            "delete": "删除"
        }
        action_text = action_map.get(change["action"], change["action"])
        lines.append(f"{i}. [{action_text}] {change['file_path']}")
        lines.append(f"   时间: {change['timestamp']}")
        if change.get("backup_file"):
            lines.append(f"   备份: {change['backup_file']}")
    
    return "\n".join(lines)
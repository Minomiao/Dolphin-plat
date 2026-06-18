import os
import json
import uuid
import ctypes
from datetime import datetime
from modules.logger import get_logger
from modules.bootstrap import constants

log = get_logger("Dolphin.dpc_manager")

DPC_FILENAME = constants.DPC_FILENAME
FILE_ATTRIBUTE_HIDDEN = constants.FILE_ATTRIBUTE_HIDDEN


def _read_raw(work_dir):
    dpc_path = os.path.join(work_dir, DPC_FILENAME)
    if not os.path.exists(dpc_path):
        return None
    try:
        with open(dpc_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, KeyError):
        log.warning(f".dpc 文件损坏: {dpc_path}")
        return None


def _set_hidden(path):
    if os.name == 'nt':
        attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
        ctypes.windll.kernel32.SetFileAttributesW(path, attrs | FILE_ATTRIBUTE_HIDDEN)


def _remove_hidden(path):
    if os.name == 'nt' and os.path.exists(path):
        attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
        if attrs & FILE_ATTRIBUTE_HIDDEN:
            ctypes.windll.kernel32.SetFileAttributesW(path, attrs & ~FILE_ATTRIBUTE_HIDDEN)


def _write_raw(work_dir, data):
    dpc_path = os.path.join(work_dir, DPC_FILENAME)
    _remove_hidden(dpc_path)
    with open(dpc_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _set_hidden(dpc_path)


def _migrate_old_format(data):
    if "dir_id" in data and "conversations" in data and isinstance(data["conversations"], list):
        if data["conversations"] and isinstance(data["conversations"][0], dict):
            if "restricted" not in data:
                data["restricted"] = [".dpc"]
            return data
    new = {
        "dir_id": data.get("dir_id", str(uuid.uuid4())),
        "conversations": [],
        "current": None,
        "updated_at": data.get("updated_at", datetime.now().isoformat()),
        "restricted": data.get("restricted", [".dpc"])
    }
    old_convs = data.get("conversations", [])
    old_current = data.get("current") or data.get("conversation")
    old_conversation = data.get("conversation")
    if old_conversation and old_conversation not in old_convs:
        old_convs.append(old_conversation)
    for name in old_convs:
        conv_id = str(uuid.uuid4())
        new["conversations"].append({"id": conv_id, "name": name})
        if name == old_current or name == old_conversation:
            new["current"] = conv_id
    if not new["current"] and new["conversations"]:
        new["current"] = new["conversations"][0]["id"]
    log.info(f"迁移旧 .dpc 格式: {len(new['conversations'])} 个对话")
    return new


def get_dir_id(work_dir):
    data = _read_raw(work_dir)
    if data is None:
        return None
    data = _migrate_old_format(data)
    return data.get("dir_id")


def ensure_dir_id(work_dir):
    data = _read_raw(work_dir)
    if data is not None:
        data = _migrate_old_format(data)
        needs_write = False
        if "dir_id" not in data:
            data["dir_id"] = str(uuid.uuid4())
            needs_write = True
        if "restricted" not in data:
            data["restricted"] = [".dpc"]
            needs_write = True
        if needs_write:
            _write_raw(work_dir, data)
        return data["dir_id"]
    dir_id = str(uuid.uuid4())
    data = {
        "dir_id": dir_id,
        "conversations": [],
        "current": None,
        "updated_at": datetime.now().isoformat(),
        "restricted": [".dpc"]
    }
    _write_raw(work_dir, data)
    log.info(f".dpc 初始化: dir_id={dir_id}")
    return dir_id


def get_conversations(work_dir):
    data = _read_raw(work_dir)
    if data is None:
        return []
    data = _migrate_old_format(data)
    return data.get("conversations", [])


def get_current(work_dir):
    data = _read_raw(work_dir)
    if data is None:
        return None, None
    data = _migrate_old_format(data)
    current_id = data.get("current")
    if not current_id:
        return None, None
    for c in data.get("conversations", []):
        if c["id"] == current_id:
            return current_id, c["name"]
    return current_id, None


def get_name_by_id(work_dir, conv_id):
    data = _read_raw(work_dir)
    if data is None:
        return None
    data = _migrate_old_format(data)
    for c in data.get("conversations", []):
        if c["id"] == conv_id:
            return c["name"]
    return None


def get_id_by_name(work_dir, name):
    data = _read_raw(work_dir)
    if data is None:
        return None
    data = _migrate_old_format(data)
    for c in data.get("conversations", []):
        if c["name"] == name:
            return c["id"]
    return None


def add_conversation(work_dir, name):
    data = _read_raw(work_dir) or {}
    data = _migrate_old_format(data)
    for c in data["conversations"]:
        if c["name"] == name:
            data["current"] = c["id"]
            data["updated_at"] = datetime.now().isoformat()
            _write_raw(work_dir, data)
            log.info(f".dpc: 切换到已有对话 '{name}' -> {c['id']}")
            return c["id"]
    conv_id = str(uuid.uuid4())
    data["conversations"].append({"id": conv_id, "name": name})
    data["current"] = conv_id
    data["updated_at"] = datetime.now().isoformat()
    _write_raw(work_dir, data)
    log.info(f".dpc: 新增对话 '{name}' -> {conv_id}")
    return conv_id


def set_current_by_id(work_dir, conv_id):
    data = _read_raw(work_dir)
    if data is None:
        return
    data = _migrate_old_format(data)
    data["current"] = conv_id
    data["updated_at"] = datetime.now().isoformat()
    _write_raw(work_dir, data)
    log.info(f".dpc: current -> {conv_id}")


def get_restricted_paths(work_dir):
    data = _read_raw(work_dir)
    if data is None:
        return [".dpc"]
    data = _migrate_old_format(data)
    return data.get("restricted", [".dpc"])


def is_path_allowed(work_dir, relative_path):
    import fnmatch
    restricted = get_restricted_paths(work_dir)
    normalized = relative_path.replace('\\', '/').lstrip('/')
    for pattern in restricted:
        if pattern == "*":
            return False, f"目录 {work_dir} 禁止访问"
        if fnmatch.fnmatch(normalized, pattern):
            return False, f"文件 '{relative_path}' 被 .dpc 限制访问"
        if fnmatch.fnmatch(os.path.basename(normalized), pattern):
            return False, f"文件 '{relative_path}' 被 .dpc 限制访问"
    return True, None


def filter_allowed_paths(work_dir, paths):
    allowed = []
    blocked = []
    for p in paths:
        ok, _ = is_path_allowed(work_dir, p)
        if ok:
            allowed.append(p)
        else:
            blocked.append(p)
    return allowed, blocked


def ensure_restriction(work_dir, restricted_patterns):
    data = _read_raw(work_dir)
    if data is None:
        dpc_dir_id = str(uuid.uuid4())
        data = {
            "dir_id": dpc_dir_id,
            "conversations": [],
            "current": None,
            "updated_at": datetime.now().isoformat(),
            "restricted": [".dpc"]
        }
        _write_raw(work_dir, data)
        log.info(f".dpc 初始化(restriction): dir_id={dpc_dir_id}")
        data = _read_raw(work_dir)

    data = _migrate_old_format(data)
    existing = set(data.get("restricted", [".dpc"]))
    for p in restricted_patterns:
        existing.add(p)
    data["restricted"] = list(existing)
    data["updated_at"] = datetime.now().isoformat()
    _write_raw(work_dir, data)
    log.info(f".dpc restriction 已更新: {data['restricted']}")

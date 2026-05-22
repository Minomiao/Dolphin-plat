import os
import json
import uuid
from datetime import datetime
from modules.logger import get_logger

log = get_logger("Dolphin.dpc_manager")

DPC_FILENAME = ".dpc"


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


def _write_raw(work_dir, data):
    dpc_path = os.path.join(work_dir, DPC_FILENAME)
    with open(dpc_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _migrate_old_format(data):
    if "dir_id" in data and "conversations" in data and isinstance(data["conversations"], list):
        if data["conversations"] and isinstance(data["conversations"][0], dict):
            return data
    new = {
        "dir_id": data.get("dir_id", str(uuid.uuid4())),
        "conversations": [],
        "current": None,
        "updated_at": data.get("updated_at", datetime.now().isoformat())
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
        if "dir_id" not in data:
            data["dir_id"] = str(uuid.uuid4())
            _write_raw(work_dir, data)
        return data["dir_id"]
    dir_id = str(uuid.uuid4())
    data = {
        "dir_id": dir_id,
        "conversations": [],
        "current": None,
        "updated_at": datetime.now().isoformat()
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

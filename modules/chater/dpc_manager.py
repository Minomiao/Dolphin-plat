import os
import json
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


def get_dpc_conversations(work_dir):
    data = _read_raw(work_dir)
    if data is None:
        return []
    convs = data.get("conversations")
    if convs is not None:
        return convs
    conv = data.get("conversation")
    if conv:
        return [conv]
    return []


def get_current_conversation(work_dir):
    data = _read_raw(work_dir)
    if data is None:
        return None
    current = data.get("current")
    if current:
        return current
    return data.get("conversation")


def add_to_dpc(work_dir, conversation_name):
    data = _read_raw(work_dir) or {}
    convs = data.get("conversations")
    if convs is None:
        old = data.get("conversation")
        convs = [old] if old else []
        data["conversations"] = convs
    if conversation_name not in convs:
        convs.append(conversation_name)
    data["current"] = conversation_name
    data["updated_at"] = datetime.now().isoformat()
    _write_raw(work_dir, data)
    log.info(f".dpc 已更新: {work_dir}, current={conversation_name}, conversations={convs}")


def set_current(work_dir, conversation_name):
    data = _read_raw(work_dir)
    if data is None:
        return
    data["current"] = conversation_name
    data["updated_at"] = datetime.now().isoformat()
    _write_raw(work_dir, data)
    log.info(f".dpc current 已更新: {work_dir} -> {conversation_name}")

import os
import json
from modules.logger import get_logger

log = get_logger("Dolphin.conversation")

CONVERSATIONS_DIR = os.path.join("date", "conversations")


def init_conversation(dir_id, conv_id, conv_name, work_dir):
    """
    Unified conversation initialization for all new conversation creation paths.
    - Registers in .dpc index (or returns existing conv_id if name already exists)
    - Creates empty JSON conversation file
    Returns (dir_id, conv_id).
    """
    from modules.chater import dpc_manager

    dir_id = dpc_manager.ensure_dir_id(work_dir)
    conv_id = dpc_manager.add_conversation(work_dir, conv_name)
    save_conversation([], dir_id, conv_id)
    log.info(f"初始化新对话: {conv_name} ({conv_id})")
    return dir_id, conv_id


def save_conversation(messages, dir_id, conv_id):
    conv_dir = os.path.join(CONVERSATIONS_DIR, dir_id)
    os.makedirs(conv_dir, exist_ok=True)
    filepath = os.path.join(conv_dir, f"{conv_id}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    log.info(f"保存对话: dir={dir_id}, conv={conv_id}, 消息数: {len(messages)}")


def load_conversation(dir_id, conv_id):
    filepath = os.path.join(CONVERSATIONS_DIR, dir_id, f"{conv_id}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            messages = json.load(f)
            log.info(f"加载对话: dir={dir_id}, conv={conv_id}, 消息数: {len(messages)}")
            return messages
    log.warning(f"对话不存在: dir={dir_id}, conv={conv_id}")
    return None

import os
import json
from modules import logger

log = logger.get_logger("Dolphin.conversation")

DATE_DIR = "date"
CONVERSATIONS_DIR = os.path.join(DATE_DIR, "conversations")

def save_conversation(messages, name):
    if not os.path.exists(CONVERSATIONS_DIR):
        os.makedirs(CONVERSATIONS_DIR)
    filepath = os.path.join(CONVERSATIONS_DIR, f"{name}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    log.info(f"保存对话: {name}, 消息数: {len(messages)}")

def load_conversation(name):
    filepath = os.path.join(CONVERSATIONS_DIR, f"{name}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            messages = json.load(f)
            log.info(f"加载对话: {name}, 消息数: {len(messages)}")
            return messages
    log.warning(f"对话不存在: {name}")
    return None

def list_conversations():
    if not os.path.exists(CONVERSATIONS_DIR):
        log.debug("对话目录不存在，返回空列表")
        return []
    conversations = []
    for filename in os.listdir(CONVERSATIONS_DIR):
        if filename.endswith('.json'):
            conversations.append(filename[:-5])
    log.debug(f"列出对话，共 {len(conversations)} 个")
    return conversations

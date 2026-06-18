import os
import json
from modules.logger import get_logger
from modules import bootstrap as app_paths
from modules.bootstrap import constants

log = get_logger("Dolphin.conversation")

CONVERSATIONS_DIR = app_paths.CONVERSATIONS_DIR

_FILE_AUTOCOMPLETE_TOOLS = constants.FILE_AUTOCOMPLETE_TOOLS


def _is_file_tool(tool_name):
    return any(kw in tool_name for kw in _FILE_AUTOCOMPLETE_TOOLS)


def _try_auto_complete_tool(tool_name, arguments, work_dir):
    file_path = arguments.get("file_path", "")
    if not file_path or not work_dir:
        return None

    full_path = os.path.join(work_dir, file_path)
    file_exists = os.path.isfile(full_path)

    if "create_file" in tool_name or "write_file" in tool_name:
        if file_exists:
            try:
                size = os.path.getsize(full_path)
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                total = len(lines)
                if total > 100:
                    lines = lines[:100]
                preview = "".join(lines)
                result = {
                    "success": True,
                    "file_path": file_path,
                    "size": size,
                    "total_lines": total,
                    "content_preview": preview,
                    "message": f"文件 {file_path} 创建/写入成功 ({size} 字节)",
                    "_recovered": True,
                    "_note": "此结果为对话恢复时自动补全，文件已存在"
                }
                if total > 100:
                    result["content_preview_note"] = f"仅显示前100行，共{total}行"
                return json.dumps(result, ensure_ascii=False)
            except Exception:
                pass
        return json.dumps({
            "success": True,
            "file_path": file_path,
            "message": f"文件 {file_path} 创建请求已记录",
            "_recovered": True,
            "_note": "此结果为对话恢复时自动补全，文件状态未知"
        }, ensure_ascii=False)

    if "read_file" in tool_name:
        if file_exists:
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                total = len(lines)
                if total > 200:
                    lines = lines[:200]
                content = "".join(lines)
                result = {
                    "success": True,
                    "file_path": file_path,
                    "content": content,
                    "total_lines": total,
                    "_recovered": True,
                    "_note": "此结果为对话恢复时从当前文件状态补全"
                }
                if total > 200:
                    result["content_note"] = f"仅显示前200行，共{total}行"
                return json.dumps(result, ensure_ascii=False)
            except Exception:
                pass
        return json.dumps({
            "error": f"文件不存在: {file_path}",
            "file_path": file_path,
            "_recovered": True,
            "_note": "此结果为对话恢复时自动补全"
        }, ensure_ascii=False)

    if "modify_file" in tool_name:
        if file_exists:
            try:
                size = os.path.getsize(full_path)
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                preview = "".join(lines[:30]) if lines else ""
                return json.dumps({
                    "success": True,
                    "file_path": file_path,
                    "size": size,
                    "total_lines": len(lines),
                    "content_preview": preview,
                    "message": f"文件 {file_path} 修改成功 ({size} 字节, {len(lines)} 行)",
                    "_recovered": True,
                    "_note": "此结果为对话恢复时从当前文件状态补全，修改可能已应用"
                }, ensure_ascii=False)
            except Exception:
                pass
        return json.dumps({
            "error": f"文件不存在: {file_path}",
            "_recovered": True,
            "_note": "此结果为对话恢复时自动补全"
        }, ensure_ascii=False)

    if "delete_file" in tool_name:
        if not file_exists:
            return json.dumps({
                "success": True,
                "file_path": file_path,
                "message": f"文件 {file_path} 不存在（可能已被删除）",
                "_recovered": True,
                "_note": "此结果为对话恢复时自动补全"
            }, ensure_ascii=False)
        return json.dumps({
            "error": f"文件 {file_path} 仍然存在（删除操作可能未执行）",
            "_recovered": True,
            "_note": "此结果为对话恢复时自动补全"
        }, ensure_ascii=False)

    return None


def _build_interrupted_response(tool_name, arguments):
    return json.dumps({
        "error": (
            f"对话在上次工具调用时意外中断，原始执行结果已丢失。"
            f"工具: {tool_name}，参数: {json.dumps(arguments, ensure_ascii=False)}。"
            f"请根据上下文重新评估当前状态，如有需要请重新执行此操作。"
        ),
        "_recovered": True,
        "_interrupted": True
    }, ensure_ascii=False)


def repair_conversation_messages(messages, work_dir=None):
    repaired = []
    repaired_count = 0

    for i, msg in enumerate(messages):
        repaired.append(msg)

        if msg.get("role") != "assistant":
            continue

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            continue

        tool_ids_with_responses = set()
        for j in range(i + 1, len(messages)):
            future = messages[j]
            if future.get("role") == "assistant":
                break
            if future.get("role") == "tool":
                tc_id = future.get("tool_call_id")
                if tc_id:
                    tool_ids_with_responses.add(tc_id)

        for tc in tool_calls:
            tc_id = tc.get("id")
            if tc_id in tool_ids_with_responses:
                continue

            repaired_count += 1
            fn = tc.get("function", {})
            tool_name = fn.get("name", "unknown")

            try:
                arguments = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                arguments = {}

            result = None
            if work_dir and _is_file_tool(tool_name):
                result = _try_auto_complete_tool(tool_name, arguments, work_dir)

            if result is None:
                result = _build_interrupted_response(tool_name, arguments)

            repaired.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result
            })
            log.warning(f"对话修复: 补全丢失的工具调用结果 [{tool_name}] -> {tc_id}")

    if repaired_count > 0:
        log.warning(f"对话修复完成: 共补全 {repaired_count} 个丢失的工具调用结果")

    return repaired


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

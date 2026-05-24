import json
from modules.chater import dpc_manager
from modules.logger import get_logger
from colorama import Fore, Style

log = get_logger("Dolphin.conversation_loader")


def load_and_activate(chat_instance, dir_id, conv_id, conv_name, work_dir):
    loaded = chat_instance.load_conversation(dir_id, conv_id)
    if not loaded:
        chat_instance.clear_history()
        chat_instance.save_conversation(dir_id, conv_id)
        log.info(f"初始化空对话文件: {conv_name} ({conv_id})")

    dpc_manager.set_current_by_id(work_dir, conv_id)

    log.info(f"加载对话: {conv_name} ({conv_id})")

    return {
        'conv_name': conv_name,
        'dir_id': dir_id,
        'conv_id': conv_id,
    }


def format_conversation_history(messages, show_thinking):
    if not messages:
        return ""

    lines = []
    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')
        if role == 'system':
            continue
        elif role == 'user':
            lines.append(f"您: {content}")
        elif role == 'assistant':
            if msg.get('reasoning_content'):
                if show_thinking:
                    lines.append(f"{Fore.LIGHTBLACK_EX}思考过程:{Style.RESET_ALL}")
                    lines.append(f"{Fore.LIGHTBLACK_EX}{msg['reasoning_content']}{Style.RESET_ALL}")
                    lines.append(f"{Fore.LIGHTBLACK_EX}--- 思考过程结束 ---{Style.RESET_ALL}")
                else:
                    lines.append(f"{Fore.LIGHTBLACK_EX}思考完成{Style.RESET_ALL}")
            if content:
                lines.append(f"AI: {content}")
            if msg.get('tool_calls'):
                lines.append(f"{Fore.BLUE}--工具调用:{Style.RESET_ALL}")
                for tc in msg['tool_calls']:
                    fn = tc['function']
                    lines.append(f"{Fore.BLUE}  - {fn['name']}{Style.RESET_ALL}")
                    args = fn.get('arguments', '')
                    if args:
                        try:
                            args_parsed = json.loads(args)
                            lines.append(f"{Fore.BLUE}    参数: {json.dumps(args_parsed, ensure_ascii=False, indent=4)}{Style.RESET_ALL}")
                        except (json.JSONDecodeError, TypeError):
                            lines.append(f"{Fore.BLUE}    参数: {args}{Style.RESET_ALL}")
        elif role == 'tool':
            tool_content = msg.get('content', '')
            if tool_content:
                lines.append(f"{Fore.GREEN}--结果:{Style.RESET_ALL}")
                lines.append(f"{Fore.GREEN}{tool_content}{Style.RESET_ALL}")

    return "\n".join(lines)

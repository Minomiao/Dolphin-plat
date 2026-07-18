"""主命令循环：解析用户输入并分发到各子模块。"""
import sys

from colorama import Fore, Style

from modules.logger import get_logger
from .state import ui, state
from .callback import chat_callback, clear_tool_pending, rollback_last_message
from .changes import handle_post_chat_changes
from .header import print_header, print_conversation_history
from .settings import settings_mode, model_settings, toggle_tools
from .conversation_ops import (
    open_work_directory, new_conversation, load_conversation, list_conversations
)
from .display import show_help, show_tools, show_skills

log = get_logger("Dolphin.main_loop")


def _pre_send_check():
    """发送消息前的必要检查。"""
    cmd = state.cmd
    missing = []
    if not state.current_config.get("api_key"):
        missing.append("API密钥")
    if not state.current_config.get("model"):
        missing.append("模型")
    return missing


async def main():
    """主命令循环。"""
    cmd = state.cmd
    config = state.config
    chat = state.chat
    screen_refresh = state.screen_refresh

    while True:
        try:
            ui.turn_first_output = True
            user_input = input("\n> ").strip()

            if not user_input:
                continue

            current_prefix = state.current_config.get('command_prefix', '/')
            if user_input.startswith(current_prefix):
                command = user_input[1:].strip()

                if command == cmd.get_command('help'):
                    show_help()
                    continue
                elif command == cmd.get_command('clear'):
                    state.chat_instance.clear_history()
                    screen_refresh.refresh(print_header, print_conversation_history, "对话历史已清空", show_history=False)
                    continue
                elif command == cmd.get_command('model'):
                    model_settings()
                    continue
                elif command == cmd.get_command('settings'):
                    settings_mode()
                    continue
                elif command == cmd.get_command('open'):
                    open_work_directory()
                    continue
                elif command == cmd.get_command('new'):
                    name = user_input[len(current_prefix) + len(command):].strip()
                    new_conversation(name)
                    continue
                elif command == cmd.get_command('list'):
                    list_conversations()
                    continue
                elif command == cmd.get_command('load'):
                    name = user_input[len(current_prefix) + len(command):].strip()
                    load_conversation(name)
                    continue
                elif command == cmd.get_command('back'):
                    continue
                elif command == cmd.get_command('exit'):
                    log.info("用户退出程序")
                    print("再见!")
                    break
                elif command == cmd.get_command('tools'):
                    show_tools()
                    continue
                elif command == cmd.get_command('skills'):
                    show_skills()
                    continue
                elif command == cmd.get_command('changes'):
                    from .changes import handle_pending_changes
                    handle_pending_changes()
                    continue
                elif command == cmd.get_command('thinking'):
                    state.show_thinking = not state.show_thinking
                    status = "开启" if state.show_thinking else "关闭"
                    print(f"思考过程显示已{status}")
                    continue
                elif command == cmd.get_command('effort'):
                    parts = user_input.split()
                    if len(parts) >= 2:
                        level = parts[1].lower()
                        if level in ['normal', 'fine', 'high']:
                            state.effort_level = level
                            state.chat_instance.effort_level = level
                            print(f"思考强度已设置为: {level}")
                        else:
                            print(f"无效的思考强度，可选: normal, fine, high")
                    else:
                        print(f"当前思考强度: {state.effort_level} (可选: normal, fine, high)")
                    continue
                elif command == cmd.get_command('toggle_tools'):
                    toggle_tools()
                    continue
                else:
                    print(f"未知命令: {command}")
                    continue

            # 发送消息前检查
            missing = _pre_send_check()
            if missing:
                missing_text = "、".join(missing)
                print(f"{Fore.RED}错误: 未设置{missing_text}，无法发送消息。输入 '{cmd.get_command('model')}' 进行配置。可前往模型服务官网申请 API key{Style.RESET_ALL}")
                log.warning(f"发送消息前检查失败: 缺少{missing_text}")
                continue

            try:
                await state.chat_instance.chat_stream(user_input)
                handle_post_chat_changes()
            except (state.AuthenticationError, state.RateLimitError,
                    state.APIConnectionError, state.APIError) as e:
                print(f"\n{Fore.RED}API 错误: {e}{Style.RESET_ALL}")
                log.error(f"API 错误: {e}", exc_info=True)
                rollback_last_message()
                clear_tool_pending()
            except Exception as e:
                print(f"\n{Fore.RED}错误: {e}{Style.RESET_ALL}")
                log.error(f"聊天错误: {e}", exc_info=True)
                clear_tool_pending()

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}已中断当前操作{Style.RESET_ALL}")
            clear_tool_pending()
            try:
                input("按 Enter 键继续...")
            except (EOFError, KeyboardInterrupt):
                print("\n再见!")
                break
        except EOFError:
            print("\n再见!")
            break
        except Exception as e:
            print(f"{Fore.RED}错误: {e}{Style.RESET_ALL}")
            log.error(f"主循环错误: {e}", exc_info=True)

from openai import OpenAI
from modules import config
from modules import commands as cmd
from modules import chat
from modules import logger
from modules import backup_manager
import os

# 导入 colorama 库
from colorama import init, Fore, Back, Style

# 初始化 colorama
init()

log = logger.setup_logger("Dolphin")

_SCREEN_ALT_ENTER = '\033[?1049h'
_SCREEN_ALT_EXIT = '\033[?1049l'

_using_alt_screen = False


def _supports_ansi():
    import sys as _sys
    if not _sys.stdout.isatty():
        return False
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            stdout_handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
                return False
            if mode.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING:
                return True
            new_mode = mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            return kernel32.SetConsoleMode(stdout_handle, new_mode) != 0
        except Exception:
            return False
    term = os.environ.get('TERM', '')
    return term not in ('', 'dumb')


def _enter_screen():
    global _using_alt_screen
    if _supports_ansi():
        print(_SCREEN_ALT_ENTER, end='', flush=True)
        _using_alt_screen = True


def _exit_screen():
    global _using_alt_screen
    if _using_alt_screen:
        print(_SCREEN_ALT_EXIT, end='', flush=True)

def settings_mode():
    global current_config, chat_instance
    log.info("进入设置模式")
    print("\n=== 设置模式 ===")
    print(f"输入 '{cmd.get_command('back')}' 返回主界面")
    print("其他配置可使用以下命令:")
    print(f"  {cmd.get_command('model')} - 切换模型和配置 API 密钥")
    print(f"  {cmd.get_command('open')}  - 切换工作目录")
    print()
    print(f"当前最大Token数: {current_config.get('max_tokens', 8192)}")
    print("推荐值: 8192 (适合大多数场景)")
    new_max_tokens = input("\n输入新的最大Token数 (留空保持当前值): ")
    if new_max_tokens == cmd.get_command('back'):
        log.info("用户取消设置，返回主界面")
        print("返回主界面")
        return
    try:
        new_max_tokens = int(new_max_tokens) if new_max_tokens else current_config.get('max_tokens', 8192)
    except ValueError:
        log.warning(f"无效的Token数: {new_max_tokens}")
        print("无效的Token数，保持当前值")
        new_max_tokens = current_config.get('max_tokens', 8192)
    
    current_prefix = current_config.get('command_prefix', '/')
    print(f"\n当前命令前缀: {current_prefix}")
    print("修改后将统一更改所有命令的唤起前缀 (例如 /help → .help)")
    new_prefix = input("输入新的命令前缀 (留空保持当前值): ")
    if new_prefix == cmd.get_command('back'):
        log.info("用户取消设置，返回主界面")
        print("返回主界面")
        return
    if new_prefix:
        current_config['command_prefix'] = new_prefix
        log.info(f"命令前缀已更改: {current_prefix} -> {new_prefix}")
    
    current_config['max_tokens'] = new_max_tokens
    
    config.save_config(current_config)
    cmd.save_commands()
    log.info(f"配置已保存: max_tokens={new_max_tokens}")
    print("\n配置已保存")
    
    global client
    client = OpenAI(
        api_key=current_config.get("api_key"),
        base_url=current_config.get("base_url")
    )
    chat_instance = chat.QuickAIChat(
        model=current_config.get('model'), 
        max_tokens=current_config.get('max_tokens', 8192),
        callback=chat_callback
    )
    log.info("客户端已更新")
    print("客户端已更新")

def handle_pending_changes():
    pending_count = backup_manager.get_pending_changes_count()
    if pending_count == 0:
        return
    
    print(f"\n{'='*50}")
    print(f"发现 {pending_count} 个待确认的文件更改")
    print(backup_manager.show_pending_changes())
    print(f"{'='*50}")
    
    while True:
        choice = input("\n是否应用这些更改? (y=应用/n=撤销/s=跳过): ").lower().strip()
        
        if choice == 'y':
            result = backup_manager.apply_all_changes()
            print(f"\n{result['message']}")
            for change in result.get('changes', []):
                print(f"  - {change['file']}: {change['status']}")
            break
        elif choice == 'n':
            result = backup_manager.revert_all_changes()
            print(f"\n{result['message']}")
            for change in result.get('changes', []):
                print(f"  - {change['file']}: {change['status']}")
            break
        elif choice == 's':
            print("跳过，更改将在下次对话时再次询问")
            break
        else:
            print("请输入 y (应用) / n (撤销) / s (跳过)")

def show_help():
    commands_config = cmd.load_commands()
    cmd_list = commands_config.get("commands", {})
    
    log.info("显示帮助信息")
    print("\n=== 命令帮助 ===")
    for cmd_key, cmd_info in cmd_list.items():
        cmd_input = cmd_info.get("input", "")
        cmd_description = cmd_info.get("description", "")
        print(f"{cmd_input:<12} - {cmd_description}")
    print("\n输入任何其他内容将发送给AI")

def show_tools():
    tools = chat_instance.list_available_tools()
    log.info(f"显示可用工具，共 {len(tools)} 个")
    if tools:
        print("\n=== 可用工具 ===")
        for tool in tools:
            print(f"  - {tool['name']}")
            print(f"    {tool['description']}")
    else:
        print("\n没有可用的工具")

def show_skills():
    log.info("显示技能管理")

    skills = chat_instance.list_skills()
    if not skills:
        print("\n没有可用的技能")
        return

    print("\n=== 技能管理 ===")
    for i, skill in enumerate(skills, 1):
        status = "启用" if skill.get('enabled', True) else "禁用"
        print(f"  {i}. {skill['name']} [{status}]")
        print(f"     {skill['description']}")

    print(f"输入 '{cmd.get_command('back')}' 返回主界面")
    while True:
        choice = input("输入编号切换状态: ").strip()
        if not choice or choice == cmd.get_command('back'):
            return

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(skills):
                print("无效的编号")
                continue
        except ValueError:
            print("无效的输入")
            continue

        skill = skills[idx]
        skill_name = skill['name']
        current_status = skill.get('enabled', True)
        target_status = not current_status

        if skill_name.startswith("plugin-"):
            result = chat_instance.plugin_loader.toggle_skill(skill_name, target_status)
        else:
            result = chat_instance.skill_mgr.toggle_skill(skill_name, target_status)

        if result.get('success'):
            new_status_text = "启用" if target_status else "禁用"
            print(f"  {idx + 1}. {skill['name']} [{new_status_text}]")
            skill['enabled'] = target_status
        else:
            print(f"错误: {result.get('error')}")

def toggle_tools():
    current_status = chat_instance.enable_tools
    new_status = not current_status
    chat_instance.enable_tool(new_status)
    status_text = "启用" if new_status else "禁用"
    log.info(f"工具状态已切换: {status_text}")
    print(f"工具已{status_text}")

def open_work_directory(path=None):
    global current_config, chat_instance, skill_mgr
    if not path:
        print(f"\n当前工作目录: {current_config.get('work_directory', 'workplace')}")
        path = input("输入要打开的工作目录: ")
        if not path:
            print("取消操作")
            return
    
    old_work_directory = current_config.get('work_directory', 'workplace')
    current_config['work_directory'] = path
    config.save_config(current_config)
    log.info(f"工作目录已更改: {old_work_directory} -> {path}")
    
    if path != old_work_directory:
        print(f"工作目录已更改，正在重新加载技能模块...")
        import importlib
        import modules.skill_manager as sm
        importlib.reload(sm)
        global skill_mgr
        skill_mgr = sm.get_skill_manager()
        chat_instance.skill_mgr = skill_mgr
        chat_instance._update_tools()
        print("技能模块已重新加载")
    
    print(f"工作目录已设置为: {path}")

def model_settings():
    global current_config, chat_instance
    log.info("进入模型设置")
    print("\n=== 模型设置 ===")
    print(f"输入 '{cmd.get_command('back')}' 返回主界面")
    print(f"当前 API 密钥: {'***' if current_config.get('api_key') else '未设置'}")
    print(f"当前模型: {current_config.get('model', 'deepseek-v4-flash')}")
    
    new_api_key = input("\nAPI 密钥 (留空保持当前值): ")
    if new_api_key == cmd.get_command('back'):
        log.info("用户取消模型设置，返回主界面")
        print("返回主界面")
        return
    new_api_key = new_api_key or current_config.get('api_key')
    
    print("\n可用模型:")
    from modules.config import get_available_models
    available_models = get_available_models()
    
    new_models = [m for m in available_models if not m["deprecated"]]
    deprecated_models = [m for m in available_models if m["deprecated"]]
    
    idx = 1
    choice_map = {}
    
    for model_info in new_models:
        print(f"{idx}. {model_info['name']} - {model_info['description']}")
        choice_map[str(idx)] = model_info["name"]
        idx += 1
    
    if deprecated_models:
        from modules.config import check_model_deprecation
        deprecation_msg = check_model_deprecation(deprecated_models[0]["name"])
        warning = ""
        if deprecation_msg:
            warning = f" ({deprecation_msg})"
        print(f"\n--- 以下模型即将/已废弃{warning} ---")
        for model_info in deprecated_models:
            print(f"{idx}. {model_info['name']} - {model_info['description']}")
            choice_map[str(idx)] = model_info["name"]
            idx += 1
    
    print(f"{idx}. 自定义模型")
    choice_map[str(idx)] = "__custom__"
    
    model_choice = input(f"\n请选择模型 (1-{idx}): ")
    if model_choice == cmd.get_command('back'):
        log.info("用户取消模型设置，返回主界面")
        print("返回主界面")
        return
    
    if model_choice in choice_map:
        if choice_map[model_choice] == "__custom__":
            new_model = input("请输入自定义模型名称: ")
            if new_model == cmd.get_command('back'):
                log.info("用户取消模型设置，返回主界面")
                print("返回主界面")
                return
            new_model = new_model or current_config.get('model', 'deepseek-v4-flash')
        else:
            new_model = choice_map[model_choice]
    else:
        log.warning(f"无效的模型选择: {model_choice}")
        print("无效选择，保持当前模型")
        new_model = current_config.get('model', 'deepseek-v4-flash')
    
    current_config['api_key'] = new_api_key
    current_config['model'] = new_model
    
    config.save_config(current_config)
    log.info(f"模型配置已保存: model={new_model}")
    print(f"\n模型已切换至: {new_model}")
    
    global client
    client = OpenAI(
        api_key=current_config.get("api_key"),
        base_url=current_config.get("base_url")
    )
    chat_instance = chat.QuickAIChat(
        model=current_config.get('model'), 
        max_tokens=current_config.get('max_tokens', 8192),
        callback=chat_callback
    )
    log.info("客户端已更新")
    print("客户端已更新")

def chat_callback(event_type, data):
    """处理聊天事件的回调函数"""
    if event_type == 'thinking':
        print(f"{Fore.LIGHTBLACK_EX}思考过程:{Style.RESET_ALL}\n{Fore.LIGHTBLACK_EX}{data['content']}{Style.RESET_ALL}\n{Fore.LIGHTBLACK_EX}--- 思考过程结束 ---{Style.RESET_ALL}\n")
    elif event_type == 'thinking_start':
        print(f"{Fore.LIGHTBLACK_EX}思考过程:{Style.RESET_ALL}")
    elif event_type == 'thinking_chunk':
        print(f"{Fore.LIGHTBLACK_EX}{data['content']}{Style.RESET_ALL}", end="", flush=True)
    elif event_type == 'thinking_end':
        print(f"\n{Fore.LIGHTBLACK_EX}--- 思考过程结束 ---{Style.RESET_ALL}")
    elif event_type == 'response_chunk':
        print(data['content'], end="", flush=True)
    elif event_type == 'response_end':
        print()
    elif event_type == 'tool_calls':
        print(f"{Fore.BLUE}--工具调用:{Style.RESET_ALL}")
        for call in data['calls']:
            print(f"{Fore.BLUE}  - {call['name']}{Style.RESET_ALL}")
            if call.get('arguments'):
                print(f"{Fore.BLUE}    参数: {call['arguments']}{Style.RESET_ALL}")
    elif event_type == 'tool_result':
        if data['formatted']:
            print(f"{Fore.GREEN}--结果:\n{data['formatted']}{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}--结果: {data['raw']}{Style.RESET_ALL}")
    elif event_type == 'user_output':
        label = data.get('label', '')
        content = data.get('content', data.get('content_str', ''))
        if label:
            print(f"{Fore.CYAN}[{label}]{Style.RESET_ALL} {content}")
        else:
            print(f"{Fore.CYAN}{content}{Style.RESET_ALL}")
    elif event_type == 'user_input_required':
        print(f"\n📝 需要输入:")
        print(f"  {data.get('prompt', '请输入信息')}")
        if data.get('default_value'):
            print(f"  默认值: {data.get('default_value')}")
        user_input = input("\n请输入: ").strip()
        if not user_input and data.get('default_value'):
            user_input = data.get('default_value')
        return user_input
    elif event_type == 'confirmation_required':
        print(f"\n⚠️  需要确认:")
        print(f"  操作: {data.get('action', 'unknown')}")
        if data.get('script_preview'):
            print(f"  脚本预览:")
            print(f"  {data.get('script_preview')}")
        if data.get('file_path'):
            print(f"  文件: {data.get('file_path')}")
        if data.get('work_directory'):
            print(f"  工作目录: {data.get('work_directory')}")
        if data.get('error'):
            print(f"  原因: {data.get('error')}")
        return input("\n是否确认此操作? (y/n): ").lower()
    elif event_type == 'operation_canceled':
        print("操作已取消")
    elif event_type == 'operation_confirmed':
        print("操作已确认，正在执行...")
    elif event_type == 'console_output':
        # 处理控制台输出
        content = data.get('content', '')
        level = data.get('level', 'info')
        if level == 'error':
            print(f"\n{Fore.RED}错误: {content}{Style.RESET_ALL}")
        elif level == 'warning':
            print(f"\n{Fore.YELLOW}警告: {content}{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.GREEN}信息: {content}{Style.RESET_ALL}")
    elif event_type == 'max_iterations_reached':
        print(f"\n⚠️  注意: 已达到最大工具调用迭代次数 ({data['iterations']} 次)")
        print("如果任务未完成，请继续对话以继续执行。")

async def main():
    global current_config, chat_instance, current_conversation
    
    while True:
        user_input = input("\n> ").strip()
        
        # 如果用户没有输入任何内容，直接继续等待新输入
        if not user_input:
            continue
        
        if user_input == cmd.get_command('quit'):
            handle_pending_changes()
            log.info("退出程序")
            break
        elif user_input == cmd.get_command('clear'):
            log.info("清空历史记录")
            chat_instance.clear_history()
            print("历史记录已清空")
            continue
        elif user_input == cmd.get_command('set'):
            try:
                _enter_screen()
                settings_mode()
            finally:
                _exit_screen()
            continue
        elif user_input == cmd.get_command('model'):
            try:
                _enter_screen()
                model_settings()
            finally:
                _exit_screen()
            continue
        elif user_input.startswith(cmd.get_command('open')):
            open_cmd = cmd.get_command('open')
            parts = user_input[len(open_cmd):].strip()
            open_work_directory(parts if parts else None)
            continue
        elif user_input == cmd.get_command('help'):
            show_help()
            continue
        elif user_input == cmd.get_command('new'):
            new_name = input("请输入新对话名称: ")
            if new_name:
                if current_conversation == "main" and chat_instance.messages:
                    save_choice = input("是否保存当前main对话? (y/n): ").lower()
                    if save_choice == 'y':
                        save_name = input("请输入保存名称: ") or current_conversation
                        chat_instance.save_conversation(save_name)
                        log.info(f"对话已保存: {save_name}")
                        print(f"对话已保存为: {save_name}")
                chat_instance.clear_history()
                current_conversation = new_name
                log.info(f"切换到新对话: {new_name}")
                print(f"已切换到新对话: {new_name}")
            continue
        elif user_input.startswith(cmd.get_command('load')):
            # 提取加载名称参数
            parts = user_input.split(' ', 1)
            if len(parts) > 1:
                load_name = parts[1].strip()
            else:
                load_name = input("请输入要加载的对话名称: ")
            if load_name:
                if chat_instance.load_conversation(load_name):
                    current_conversation = load_name
                    log.info(f"加载对话: {load_name}")
                    print(f"已加载对话: {load_name}")
                    
                    # 显示加载的对话内容
                    if chat_instance.messages:
                        print("\n=== 对话历史 ===")
                        for msg in chat_instance.messages:
                            if msg['role'] == 'user':
                                print(f"您: {msg['content']}")
                            elif msg['role'] == 'assistant':
                                print(f"AI: {msg['content']}")
                            elif msg['role'] == 'tool':
                                print(f"工具: {msg.get('name', 'unknown')}")
                                if 'tool_call_id' in msg:
                                    print(f"  调用ID: {msg['tool_call_id']}")
                                if 'arguments' in msg:
                                    print(f"  参数: {msg['arguments']}")
                            elif msg['role'] == 'tool_response':
                                print(f"工具响应: {msg.get('tool_call_id', 'unknown')}")
                                if 'content' in msg:
                                    print(f"  内容: {msg['content']}")
                else:
                    log.warning(f"对话不存在: {load_name}")
                    print(f"对话 '{load_name}' 不存在")
            continue
        elif user_input.startswith(cmd.get_command('saveas')):
            # 提取保存名称参数
            save_as_command = cmd.get_command('saveas')
            if len(user_input) > len(save_as_command):
                save_name = user_input[len(save_as_command):].strip()
            else:
                save_name = input("请输入保存名称: ")
            if save_name:
                chat_instance.save_conversation(save_name)
                log.info(f"对话已保存: {save_name}")
                print(f"对话已保存为: {save_name}")
                if current_conversation == "main":
                    chat_instance.clear_history()
                    log.info("main对话已清空")
                    print("main对话已清空")
                else:
                    current_conversation = "main"
                    log.info("切换到main对话")
                    print("已切换到main对话")
            continue
        elif user_input == cmd.get_command('list'):
            conversations = chat_instance.list_conversations()
            log.info(f"列出所有对话，共 {len(conversations)} 个")
            if conversations:
                print("\n=== 所有对话 ===")
                for conv in conversations:
                    print(f"  - {conv}")
            else:
                print("没有找到任何对话")
            continue
        elif user_input == cmd.get_command('tools'):
            show_tools()
            continue
        elif user_input == cmd.get_command('skills'):
            try:
                _enter_screen()
                show_skills()
            finally:
                _exit_screen()
            continue
        elif user_input == cmd.get_command('toggle'):
            toggle_tools()
            continue
        
        prefix = cmd._get_prefix()
        if user_input.startswith(prefix):
            suggestion = cmd._fuzzy_match_keyword(user_input)
            if suggestion:
                print(f"{Fore.RED}错误: 未知命令 '{user_input}'。您可能想输入 '{suggestion}'。输入 '{cmd.get_command('help')}' 查看可用命令{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}错误: 未知命令 '{user_input}'。输入 '{cmd.get_command('help')}' 查看可用命令{Style.RESET_ALL}")
            log.warning(f"未知命令: {user_input}")
            continue
        
        log.info(f"用户输入: {user_input}")
        await chat_instance.chat_stream(user_input)
        
        # 每次对话结束后检查是否有待确认的文件更改
        handle_pending_changes()

def _progress_bar(percent, label):
    bar_width = 25
    filled = int(bar_width * percent / 100)
    bar = "#" * filled + "-" * (bar_width - filled)
    print(f"\r  [{bar}] {percent:3d}%  {label}", end="", flush=True)
    if percent >= 100:
        print()

_DEEPSLEEPING = "d-e-e-p-s-l-e-e-p-i-n-g"

def _build_dolphin_art():
    D = [
        " ████╗   ",
        " ██╔═██╗ ",
        " ██║ ██║ ",
        " ██╠═██║ ",
        " ████╝   ",
    ]
    O = [
        "  ████╗  ",
        " ██╔═██╗ ",
        " ██║ ██║ ",
        " ██╠═██║ ",
        "  ████╝  ",
    ]
    L = [
        " ██╗     ",
        " ██║     ",
        " ██║     ",
        " ██║     ",
        " ██████╗ ",
    ]
    P = [
        " █████╗  ",
        " ██╔═██╗ ",
        " █████╔╝ ",
        " ██╔══╝  ",
        " ██║     ",
    ]
    H = [
        " ██╗ ██╗ ",
        " ██║ ██║ ",
        " ██████║ ",
        " ██╔═██║ ",
        " ██║ ██║ ",
    ]
    I = [
        " ██╗ ",
        " ██║ ",
        " ██║ ",
        " ██║ ",
        " ██║ ",
    ]
    N = [
        " ███╗   ██╗ ",
        " ██╔██╗ ██║ ",
        " ██║╚██╗██║ ",
        " ██║ ╚████║ ",
        " ██║  ╚███║ ",
    ]
    letters = [D, O, L, P, H, I, N]
    lines = []
    for row in range(5):
        lines.append("".join(L[row] for L in letters))
    return "\n".join(lines)

_DOLPHIN_ART = _build_dolphin_art()

def _print_dolphin():
    print(Fore.LIGHTBLUE_EX + _DOLPHIN_ART + Style.RESET_ALL)

def _show_splash():
    _print_dolphin()
    print()

if __name__ == "__main__":
    import asyncio
    import time
    
    _show_splash()
    
    _progress_bar(5, _DEEPSLEEPING[:1])
    time.sleep(0.1)
    current_config = config.load_config()
    _progress_bar(20, _DEEPSLEEPING[:3])
    time.sleep(0.1)
    
    cmd._validate_commands()
    _progress_bar(35, _DEEPSLEEPING[:7])
    time.sleep(0.1)
    
    deprecation_warning = config.check_model_deprecation(current_config.get('model', 'deepseek-v4-flash'))
    if deprecation_warning:
        log.warning(deprecation_warning)
    
    WORKPLACE_DIR = current_config.get('work_directory', 'workplace')
    if not os.path.exists(WORKPLACE_DIR):
        os.makedirs(WORKPLACE_DIR)
        log.info(f"创建工作目录: {WORKPLACE_DIR}")
    _progress_bar(50, _DEEPSLEEPING[:11])
    time.sleep(0.1)
    
    chat_instance = chat.QuickAIChat(
        model=current_config.get('model', 'deepseek-v4-flash'), 
        max_tokens=current_config.get('max_tokens', 8192),
        callback=chat_callback
    )
    _progress_bar(85, _DEEPSLEEPING[:17])
    time.sleep(0.1)
    
    current_conversation = "main"
    
    log.info("Dolphin 启动")
    log.info(f"当前配置: model={current_config.get('model')}, max_tokens={current_config.get('max_tokens', 8192)}, conversation={current_conversation}, work_directory={WORKPLACE_DIR}")
    _progress_bar(100, _DEEPSLEEPING)
    time.sleep(0.3)
    os.system('cls' if os.name == 'nt' else 'clear')
    
    _print_dolphin()
    print("=" * 50)
    if deprecation_warning:
        print(f"{Fore.YELLOW}警告: {deprecation_warning}{Style.RESET_ALL}")
    print(f"输入 '{cmd.get_command('help')}' 获取命令帮助")
    print("=" * 50)
    
    asyncio.run(main())

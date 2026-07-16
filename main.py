import os
import sys
import time
import asyncio

from modules import bootstrap

# 入口文件确定项目根目录（兼容 PyInstaller 打包）
if getattr(sys, 'frozen', False):
    bootstrap.init(os.path.dirname(os.path.abspath(sys.executable)))
else:
    bootstrap.init(os.path.dirname(os.path.abspath(__file__)))

from openai import OpenAI, AuthenticationError, RateLimitError, APIConnectionError, APIError
from modules.main_server import config
from modules.CLIserver import commands as cmd
from modules.chater import chat, conversation_loader
from modules.chater.conversation_loader import format_user_output_line
from modules.CLIserver import screen_refresh
from modules.logger import setup_logger, get_logger
from modules.functions import backup_manager

# 导入 colorama 库
from colorama import init, Fore, Back, Style

# 初始化 colorama
init()

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn
from rich import box

_console = Console()

log = setup_logger("Dolphin")

_SCREEN_ALT_ENTER = '\033[?1049h'
_SCREEN_ALT_EXIT = '\033[?1049l'


_SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']


class _UIState:
    """封装 UI 运行时状态，避免全局变量散布"""
    def __init__(self):
        self.using_alt_screen = False
        self.thinking_start_time = 0.0
        self.turn_first_output = True
        self.progress = None
        self._tool_pending = False
        self._spinner_task = None


class _AppState:
    """封装应用业务状态，避免全局变量散布"""
    def __init__(self):
        self.current_config = None
        self.chat_instance = None
        self.skill_mgr = None
        self.current_conversation = None
        self.current_dir_id = None
        self.current_conv_id = None
        self.client = None
        self.show_thinking = False


ui = _UIState()
state = _AppState()


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
    if _supports_ansi():
        print(_SCREEN_ALT_ENTER + '\033[H\033[2J', end='', flush=True)
        ui.using_alt_screen = True


def _exit_screen():
    if ui.using_alt_screen:
        print(_SCREEN_ALT_EXIT, end='', flush=True)

def _rollback_last_message():
    if not state.chat_instance or not state.chat_instance.messages:
        return

    msgs = state.chat_instance.messages
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].get("role") == "user":
            del msgs[i:]
            if state.current_dir_id and state.current_conv_id:
                from modules.chater import conversation
                conversation.save_conversation(msgs, state.current_dir_id, state.current_conv_id)
            log.debug("API 错误后已回退用户消息及其后的 assistant/tool 消息")
            return

    log.debug("未找到用户消息，未执行回退")

def settings_mode():
    log.info("进入设置模式")
    print("\n=== 设置模式 ===")
    print(f"输入 '{cmd.get_command('back')}' 返回主界面")
    print("其他配置可使用以下命令:")
    print(f"  {cmd.get_command('model')} - 切换模型和配置 API 密钥")
    print(f"  {cmd.get_command('open')}  - 切换工作目录")
    print()
    print(f"当前最大Token数: {state.current_config.get('max_tokens', 18000)}")
    print("推荐值: 18000 (适合大多数场景)")
    new_max_tokens = input("\n输入新的最大Token数 (留空保持当前值): ")
    if new_max_tokens == cmd.get_command('back'):
        log.info("用户取消设置，返回主界面")
        print("返回主界面")
        return
    if new_max_tokens:
        try:
            new_max_tokens = int(new_max_tokens)
            if new_max_tokens < 1:
                log.warning(f"Token数过小: {new_max_tokens}")
                print("Token数至少为 1，保持当前值")
                new_max_tokens = state.current_config.get('max_tokens', 18000)
            elif new_max_tokens > 200000:
                log.warning(f"Token数过大: {new_max_tokens}")
                print("Token数最大不超过 200000，保持当前值")
                new_max_tokens = state.current_config.get('max_tokens', 18000)
        except ValueError:
            log.warning(f"无效的Token数: {new_max_tokens}")
            print("请输入有效数字，保持当前值")
            new_max_tokens = state.current_config.get('max_tokens', 18000)
    else:
        new_max_tokens = state.current_config.get('max_tokens', 18000)
    
    current_prefix = state.current_config.get('command_prefix', '/')
    print(f"\n当前命令前缀: {current_prefix}")
    print("修改后将统一更改所有命令的唤起前缀 (例如 /help → .help)")
    new_prefix = input("输入新的命令前缀 (留空保持当前值, 最长10字符): ")
    if new_prefix == cmd.get_command('back'):
        log.info("用户取消设置，返回主界面")
        print("返回主界面")
        return
    new_prefix = new_prefix.strip()
    if new_prefix:
        if len(new_prefix) > 10:
            log.warning(f"命令前缀过长: {len(new_prefix)}字符")
            print(f"命令前缀最长 10 个字符，已截断为: {new_prefix[:10]}")
            new_prefix = new_prefix[:10]
        state.current_config['command_prefix'] = new_prefix
        log.info(f"命令前缀已更改: {current_prefix} -> {new_prefix}")
    
    state.current_config['max_tokens'] = new_max_tokens
    
    config.save_config(state.current_config)
    cmd.save_commands()
    log.info(f"配置已保存: max_tokens={new_max_tokens}")
    print("\n配置已保存")
    
    state.client = OpenAI(
        api_key=state.current_config.get("api_key"),
        base_url=state.current_config.get("base_url")
    )
    state.chat_instance = chat.QuickAIChat(
        model=state.current_config.get('model'), 
        max_tokens=state.current_config.get('max_tokens', 18000),
        callback=chat_callback
    )
    state.chat_instance.effort_level = state.effort_level
    log.info("客户端已更新")
    print("客户端已更新")

def handle_pending_changes():
    """处理待确认的文件变更（使用 Rich Live Display）"""
    bm = backup_manager.get_backup_manager()
    pending_count = bm.get_pending_changes_count()
    if pending_count == 0:
        return

    # 进入独立屏幕
    _enter_screen()
    try:
        # 显示变更确认界面
        _show_changes_screen(bm, pending_count)
    finally:
        # 退出独立屏幕
        _exit_screen()


def _get_last_assistant_output():
    """获取最后一段 AI 输出内容"""
    try:
        if not hasattr(state, 'chat_instance') or not state.chat_instance:
            return None

        messages = state.chat_instance.messages
        if not messages:
            return None

        # 从后往前查找最后一条 assistant 消息
        for msg in reversed(messages):
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                if content and content.strip():
                    return content.strip()

        return None
    except Exception as e:
        log.debug(f"获取最后 AI 输出失败: {e}")
        return None


def _show_changes_screen(bm, pending_count):
    """显示变更确认界面（动态更新）"""
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()

    # 构建标题
    header_text = Text.assemble(
        "文件变更确认 (",
        (str(pending_count), "bold cyan"),
        " 个待处理)",
    )

    # 获取最后一段对话内容
    last_output = _get_last_assistant_output()

    # 构建变更列表
    pending_list = bm.get_pending_changes_list()
    table = _build_changes_table(pending_list)

    # 构建操作提示
    footer_text = Text.from_markup(
        "[bold]操作:[/bold] "
        "[green]y[/green]=应用全部 | "
        "[red]n[/red]=撤销全部 | "
        "[yellow]s[/yellow]=跳过"
    )

    # 显示界面（简化布局，避免空白）
    console.print()
    console.print(Panel(header_text, border_style="cyan"))

    # 显示最后一段对话输出
    if last_output:
        # 限制显示长度，避免界面过长
        display_text = last_output[:300] + "..." if len(last_output) > 300 else last_output
        console.print(Panel(
            display_text,
            title="最近对话",
            border_style="dim",
            padding=(0, 1)
        ))

    console.print(table)  # 直接显示表格，不使用 Panel 包裹
    console.print(Panel(footer_text, border_style="dim"))
    console.print()

    # 处理用户输入
    _process_changes_input(bm, console)


def _build_changes_table(pending_list):
    """构建变更列表表格"""
    from rich.table import Table
    from rich.text import Text

    table = Table(show_header=True, header_style="bold cyan", border_style="dim", padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("操作", width=8)
    table.add_column("文件路径", width=60)

    action_style_map = {
        "create": ("green", "创建"),
        "delete": ("red", "删除"),
        "modify": ("yellow", "修改"),
    }

    for i, change in enumerate(pending_list, 1):
        action = change.get("action", "unknown")
        style, label = action_style_map.get(action, ("white", action))

        table.add_row(
            str(i),
            Text(label, style=style),
            change.get("file_path", "unknown"),
        )

    return table


def _process_changes_input(bm, console):
    """处理用户输入"""
    from rich.text import Text

    while True:
        try:
            choice = input("\n请选择操作: ").lower().strip()

            if choice == 'y':
                result = bm.apply_all_changes()
                _show_operation_result(console, result, "应用")
                break
            elif choice == 'n':
                # 二次确认撤销操作
                confirm = input("⚠️  确认撤销所有更改？此操作不可恢复 (yes/no): ").lower().strip()
                if confirm == 'yes':
                    result = bm.revert_all_changes()
                    _show_operation_result(console, result, "撤销")
                    break
                else:
                    console.print("[yellow]已取消撤销操作[/yellow]")
            elif choice == 's':
                console.print("[yellow]已跳过，下次对话时再次确认[/yellow]")
                time.sleep(1)
                break
            else:
                console.print("[red]无效输入，请使用 y/n/s[/red]")
        except KeyboardInterrupt:
            console.print("\n[dim]已取消操作[/dim]")
            break


def _show_operation_result(console, result, action_name):
    """显示操作结果"""
    from rich.panel import Panel
    from rich.text import Text

    # 构建结果消息
    if result.get('success'):
        message = Text.assemble(
            f"{action_name}成功: ",
            (result.get('message', ''), 'green'),
        )
    else:
        message = Text.assemble(
            f"{action_name}失败: ",
            (result.get('message', ''), 'red'),
        )

    # 显示结果面板
    console.print(Panel(message, border_style="green" if result.get('success') else "red"))

    # 显示详细变更列表
    changes = result.get('changes', [])
    if changes:
        console.print(f"\n{action_name}详情:")
        for change in changes:
            file_path = change.get('file', 'unknown')
            status = change.get('status', 'unknown')
            status_color = "green" if "success" in status or "applied" in status or "reverted" in status else "red"
            console.print(f"  [{status_color}]✓[/{status_color}] {file_path}: {status}")

    # 等待用户查看结果
    input("\n按 Enter 键继续...")

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

def _print_header():
    deprecation_warning = config.check_model_deprecation(
        state.current_config.get('model', 'deepseek-v4-flash'))
    work_dir = state.current_config.get('work_directory', 'workplace')

    dolphin = Text(_DOLPHIN_ART, style="bright_blue")

    info = Text()
    if deprecation_warning:
        info.append(f"{deprecation_warning}\n", style="yellow")
    info.append("输入 ", style="dim")
    info.append(f"'{cmd.get_command('help')}'", style="bold white")
    info.append(" 获取命令帮助\n", style="dim")
    info.append("工作目录: ", style="dim")
    info.append(work_dir, style="white")

    panel = Panel(
        Group(dolphin, "", info),
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    _console.print(panel)

def _print_conversation_history():
    output = conversation_loader.format_conversation_history(
        state.chat_instance.messages, state.show_thinking)
    if output:
        print(output)

def show_tools():
    tools = state.chat_instance.list_available_tools()
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

    skills = state.chat_instance.list_skills()
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
            result = state.chat_instance.plugin_loader.toggle_skill(skill_name, target_status)
        else:
            result = state.chat_instance.skill_mgr.toggle_skill(skill_name, target_status)

        if result.get('success'):
            new_status_text = "启用" if target_status else "禁用"
            print(f"  {idx + 1}. {skill['name']} [{new_status_text}]")
            skill['enabled'] = target_status
        else:
            print(f"错误: {result.get('error')}")

def toggle_tools():
    current_status = state.chat_instance.enable_tools
    new_status = not current_status
    state.chat_instance.enable_tool(new_status)
    status_text = "启用" if new_status else "禁用"
    log.info(f"工具状态已切换: {status_text}")
    print(f"工具已{status_text}")

def open_work_directory(path=None, silent=False):
    if not path:
        cur = state.current_config.get('work_directory', 'workplace')
        print(f"\n当前工作目录: {cur}")
        path = input("输入要打开的工作目录: ")
        if not path:
            print("取消操作")
            return
    
    # 相对路径基于项目根目录解析为绝对路径
    if not os.path.isabs(path):
        path = os.path.normpath(os.path.join(bootstrap.PROJECT_ROOT, path))
    
    old_work_directory = state.current_config.get('work_directory', 'workplace')
    state.current_config['work_directory'] = path
    config.save_config(state.current_config)
    log.info(f"工作目录已更改: {old_work_directory} -> {path}")
    
    if path != old_work_directory:
        print(f"工作目录已更改，正在重新加载技能模块...")
        import importlib
        import modules.loader.skill_manager as sm
        importlib.reload(sm)
        state.skill_mgr = sm.get_skill_manager()
        state.skill_mgr.set_work_dir(path)
        state.chat_instance.skill_mgr = state.skill_mgr
        if state.chat_instance.plugin_loader:
            state.chat_instance.plugin_loader.set_work_dir(path)
        state.chat_instance._update_tools()
        print("技能模块已重新加载")
    
    from modules.chater import dpc_manager
    
    if state.chat_instance.messages and state.current_dir_id and state.current_conv_id:
        state.chat_instance.save_conversation(state.current_dir_id, state.current_conv_id)
        log.info(f"自动保存旧对话: {state.current_conversation}")
    
    dir_id = dpc_manager.ensure_dir_id(path)
    conv_id, conv_name = dpc_manager.get_current(path)
    
    if conv_id and conv_name:
        result = conversation_loader.load_and_activate(
            state.chat_instance, dir_id, conv_id, conv_name, path)
        if result:
            state.current_conversation = result['conv_name']
            state.current_dir_id = result['dir_id']
            state.current_conv_id = result['conv_id']
            if not silent:
                screen_refresh.refresh(_print_header, _print_conversation_history, f"已自动加载对话: {conv_name}")
            return
    
    if conv_id:
        log.warning(f".dpc 指向的对话不存在，将创建新对话")
    
    state.chat_instance.clear_history()
    
    conv_name = os.path.basename(path.rstrip('/\\'))
    if not conv_name:
        conv_name = "default"
    existing_names = [c["name"] for c in dpc_manager.get_conversations(path)]
    base_name = conv_name
    counter = 1
    while conv_name in existing_names:
        conv_name = f"{base_name}_{counter}"
        counter += 1
    
    from modules.chater import conversation
    dir_id, new_conv_id = conversation.init_conversation(dir_id, None, conv_name, path)
    state.current_conversation = conv_name
    state.current_dir_id = dir_id
    state.current_conv_id = new_conv_id
    log.info(f"为工作目录创建新对话: {conv_name} ({new_conv_id})")
    if not silent:
        screen_refresh.refresh(_print_header, _print_conversation_history, f"已创建新对话: {conv_name}", show_history=False)

def model_settings():
    log.info("进入模型设置")
    print("=== 模型设置 ===")
    print(f"输入 '{cmd.get_command('back')}' 返回主界面")
    print(f"当前模型: {state.current_config.get('model', 'deepseek-v4-flash')}")
    
    print("\n可用模型:")
    from modules.main_server.config import get_available_models
    available_models = get_available_models()
    
    new_models = [m for m in available_models if not m["deprecated"]]
    deprecated_models = [m for m in available_models if m["deprecated"]]
    
    idx = 1
    choice_map = {}
    
    for model_info in new_models:
        print(f"{idx}. {model_info['name']}")
        choice_map[str(idx)] = model_info["name"]
        idx += 1
    
    if deprecated_models:
        print(f"\n--- 已废弃模型 ---")
        for model_info in deprecated_models:
            date = model_info.get("deprecation_date", "")
            date_str = f" (废弃: {date})" if date else ""
            print(f"{idx}. {model_info['name']}{date_str}")
            choice_map[str(idx)] = model_info["name"]
            idx += 1
    
    model_choice = input(f"\n请选择模型 (1-{idx - 1}): ")
    if model_choice == cmd.get_command('back'):
        log.info("用户取消模型设置，返回主界面")
        print("返回主界面")
        return
    
    if model_choice in choice_map:
        new_model = choice_map[model_choice]
    else:
        log.warning(f"无效的模型选择: {model_choice}")
        print("无效选择，保持当前模型")
        new_model = state.current_config.get('model', 'deepseek-v4-flash')
    
    print(f"\n当前 API 密钥: {'***' if state.current_config.get('api_key') else '未设置'}")
    new_api_key = input("API 密钥 (留空保持当前值): ")
    if new_api_key == cmd.get_command('back'):
        log.info("用户取消模型设置，返回主界面")
        print("返回主界面")
        return
    new_api_key = new_api_key or state.current_config.get('api_key')
    
    state.current_config['api_key'] = new_api_key
    state.current_config['model'] = new_model
    
    config.save_config(state.current_config)
    log.info(f"模型配置已保存: model={new_model}")
    print(f"\n模型已切换至: {new_model}")
    
    state.client = OpenAI(
        api_key=state.current_config.get("api_key"),
        base_url=state.current_config.get("base_url")
    )
    state.chat_instance = chat.QuickAIChat(
        model=state.current_config.get('model'), 
        max_tokens=state.current_config.get('max_tokens', 18000),
        callback=chat_callback
    )
    state.chat_instance.effort_level = state.effort_level
    log.info("客户端已更新")
    print("客户端已更新")


async def _run_spinner(prefix: str):
    i = 0
    while True:
        frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
        sys.stdout.write(f"\r\033[K{Fore.CYAN}[{prefix}]{Style.RESET_ALL} {frame}")
        sys.stdout.flush()
        i += 1
        await asyncio.sleep(0.12)


def _clear_tool_pending():
    if ui._spinner_task and not ui._spinner_task.done():
        ui._spinner_task.cancel()
        ui._spinner_task = None
    ui._tool_pending = False


def chat_callback(event_type, data):
    """处理聊天事件的回调函数"""
    if event_type == 'thinking':
        if ui.turn_first_output:
            print()
            ui.turn_first_output = False
        if state.show_thinking:
            print(f"{Fore.LIGHTBLACK_EX}[思考过程]{Style.RESET_ALL}\n{Fore.LIGHTBLACK_EX}{data['content']}{Style.RESET_ALL}\n{Fore.LIGHTBLACK_EX}--- 思考过程结束 ---{Style.RESET_ALL}\n")
    elif event_type == 'tool_start':
        _clear_tool_pending()
        ui._tool_pending = True
        ui._spinner_task = asyncio.ensure_future(_run_spinner(data['name']))
    elif event_type == 'thinking_start':
        if ui.turn_first_output:
            print()
            ui.turn_first_output = False
        if state.show_thinking:
            print(f"{Fore.LIGHTBLACK_EX}[思考过程]{Style.RESET_ALL}")
        else:
            ui.thinking_start_time = time.time()
            print(f"\r\033[K{Fore.LIGHTBLACK_EX}正在思考中 - 0s{Style.RESET_ALL}", end="", flush=True)
    elif event_type == 'thinking_chunk':
        if state.show_thinking:
            print(f"{Fore.LIGHTBLACK_EX}{data['content']}{Style.RESET_ALL}", end="", flush=True)
        else:
            elapsed = int(time.time() - ui.thinking_start_time)
            print(f"\r\033[K{Fore.LIGHTBLACK_EX}正在思考中 - {elapsed}s{Style.RESET_ALL}", end="", flush=True)
    elif event_type == 'thinking_end':
        if state.show_thinking:
            print(f"\n{Fore.LIGHTBLACK_EX}--- 思考过程结束 ---{Style.RESET_ALL}")
        else:
            elapsed = int(time.time() - ui.thinking_start_time)
            print(f"\r\033[K{Fore.LIGHTBLACK_EX}[思考完成 {elapsed}s]{Style.RESET_ALL}")
    elif event_type == 'response_chunk':
        if ui.turn_first_output:
            print()
            ui.turn_first_output = False
        print(data['content'], end="", flush=True)
    elif event_type == 'response_end':
        print()
    elif event_type == 'tool_calls':
        _clear_tool_pending()
        sys.stdout.write("\n")
        sys.stdout.flush()
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
        _clear_tool_pending()
        line = format_user_output_line(data)
        sys.stdout.write(f"\r\033[K{line}\n")
        sys.stdout.flush()
    elif event_type == 'user_input_required':
        _clear_tool_pending()
        sys.stdout.write("\n")
        sys.stdout.flush()
        print(f"{Fore.YELLOW}[需要输入]{Style.RESET_ALL}")
        print(f"  {data.get('prompt', '请输入信息')}")
        if data.get('default_value'):
            print(f"  默认值: {data.get('default_value')}")
        user_input = input("\n请输入: ").strip()
        if not user_input and data.get('default_value'):
            user_input = data.get('default_value')
        return user_input
    elif event_type == 'confirmation_required':
        _clear_tool_pending()
        sys.stdout.write("\n")
        sys.stdout.flush()
        print(f"{Fore.YELLOW}[需要确认]{Style.RESET_ALL}")
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
        current_iterations = data.get('iterations', 0)
        hard_limit = data.get('hard_limit', 100)
        remaining = hard_limit - current_iterations
        print(f"\n{Fore.YELLOW}工具调用已达 {current_iterations} 次 (上限 {hard_limit} 次，剩余 {remaining} 次){Style.RESET_ALL}")
        return input("是否继续对话? (y/n): ").lower()
    elif event_type == 'context_usage':
        ratio = data.get('usage_ratio', 0)
        level = data.get('level')  # None 表示无告警
        turn_completion = data.get('turn_completion_tokens', 0)
        
        pct = f"{ratio:.0%}"
        
        # 圆形进度条：根据百分比选择不同填充程度
        # ○ ◔ ◑ ◕ ● (0% -> 100%)
        if ratio < 0.25:
            circle = "○"
        elif ratio < 0.5:
            circle = "◔"
        elif ratio < 0.75:
            circle = "◑"
        elif ratio < 0.95:
            circle = "◕"
        else:
            circle = "●"
        
        # 告警提示
        if level == 'critical':
            print(f"\n{Fore.RED}上下文即将耗尽 ({pct})，建议 {cmd.get_command('clear')} 清空历史{Style.RESET_ALL}")
        elif level == 'high':
            print(f"\n{Fore.YELLOW}上下文使用率较高 ({pct})，建议 {cmd.get_command('clear')} 清空历史{Style.RESET_ALL}")
        elif level == 'warn':
            print(f"\n{Fore.LIGHTBLACK_EX}上下文使用率 {pct}{Style.RESET_ALL}")
        
        # 本轮只显示 completion_tokens，圆形进度条显示百分比
        print(f"{Fore.LIGHTBLACK_EX} {turn_completion} token | {circle} {pct}{Style.RESET_ALL}")

async def main():
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
            state.chat_instance.clear_history()
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
        elif user_input.startswith(cmd.get_command('new')):
            new_cmd = cmd.get_command('new')
            new_name = user_input[len(new_cmd):].strip()
            if not new_name:
                new_name = input("请输入新对话名称: ")
            if new_name:
                if state.current_conversation == "main" and state.chat_instance.messages:
                    save_choice = input("是否保存当前main对话? (y/n): ").lower()
                    if save_choice == 'y':
                        save_name = input("请输入保存名称: ") or state.current_conversation
                        from modules.chater import dpc_manager
                        work_dir = state.current_config.get('work_directory', 'workplace')
                        save_dir_id = dpc_manager.ensure_dir_id(work_dir)
                        save_conv_id = dpc_manager.add_conversation(work_dir, save_name)
                        state.chat_instance.save_conversation(save_dir_id, save_conv_id)
                        log.info(f"对话已保存: {save_name}")
                        print(f"对话已保存为: {save_name}")
                state.chat_instance.clear_history()
                from modules.chater import conversation
                work_dir = state.current_config.get('work_directory', 'workplace')
                dir_id, conv_id = conversation.init_conversation(None, None, new_name, work_dir)
                state.current_conversation = new_name
                state.current_dir_id = dir_id
                state.current_conv_id = conv_id
                log.info(f"切换到新对话: {new_name} ({conv_id})")
                screen_refresh.refresh(_print_header, _print_conversation_history, f"已切换到新对话: {new_name}", show_history=False)
            continue
        elif user_input.startswith(cmd.get_command('load')):
            parts = user_input.split(' ', 1)
            if len(parts) > 1:
                load_name = parts[1].strip()
            else:
                load_name = input("请输入要加载的对话名称: ")
            if load_name:
                from modules.chater import dpc_manager
                work_dir = state.current_config.get('work_directory', 'workplace')
                dir_id = dpc_manager.ensure_dir_id(work_dir)
                load_conv_id = dpc_manager.get_id_by_name(work_dir, load_name)
                result = conversation_loader.load_and_activate(
                    state.chat_instance, dir_id, load_conv_id, load_name, work_dir)
                if result:
                    state.current_conversation = result['conv_name']
                    state.current_dir_id = result['dir_id']
                    state.current_conv_id = result['conv_id']
                    
                    screen_refresh.refresh(_print_header, _print_conversation_history, f"已加载对话: {load_name}")
                else:
                    log.warning(f"对话不存在: {load_name}")
                    print(f"对话 '{load_name}' 不存在")
            continue
        elif user_input == cmd.get_command('list'):
            from modules.chater import dpc_manager
            work_dir = state.current_config.get('work_directory', 'workplace')
            dpc_convs = dpc_manager.get_conversations(work_dir)
            log.info(f"列出对话（当前目录: {work_dir}），共 {len(dpc_convs)} 个")
            if dpc_convs:
                print(f"\n=== 当前目录 '{work_dir}' 的对话 ===")
                for conv in dpc_convs:
                    marker = " *" if conv["id"] == state.current_conv_id else "  "
                    print(f"  {marker} {conv['name']}")
            else:
                print(f"当前目录 '{work_dir}' 没有关联的对话")
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
        elif user_input.startswith(cmd.get_command('showthinking')):
            showthink_cmd = cmd.get_command('showthinking')
            parts = user_input[len(showthink_cmd):].strip()
            changed = False
            if parts == 'on':
                state.show_thinking = True
                state.current_config['show_thinking'] = True
                config.save_config(state.current_config)
                changed = True
            elif parts == 'off':
                state.show_thinking = False
                state.current_config['show_thinking'] = False
                config.save_config(state.current_config)
                changed = True
            else:
                choice = input("开启思考过程显示? (on/off): ").strip().lower()
                if choice == 'on':
                    state.show_thinking = True
                    state.current_config['show_thinking'] = True
                    config.save_config(state.current_config)
                    changed = True
                elif choice == 'off':
                    state.show_thinking = False
                    state.current_config['show_thinking'] = False
                    config.save_config(state.current_config)
                    changed = True
                else:
                    print(f"{Fore.RED}无效输入，请输入 on 或 off{Style.RESET_ALL}")
            if changed:
                screen_refresh.refresh(_print_header, _print_conversation_history, f"思考过程显示: {'开启' if state.show_thinking else '关闭'}")
            continue
        elif user_input.startswith(cmd.get_command('effort')):
            effort_cmd = cmd.get_command('effort')
            level = user_input[len(effort_cmd):].strip().lower()
            level_label = {"fine": "精简", "normal": "标准", "high": "深度"}
            if not level:
                current = state.effort_level
                print(f"当前思考深度: {level_label.get(current, current)}")
                continue
            valid_levels = ["fine", "normal", "high"]
            if level not in valid_levels:
                print(f"{Fore.RED}无效的思考深度: '{level}'。可选: fine / normal / high{Style.RESET_ALL}")
                continue
            state.effort_level = level
            state.chat_instance.effort_level = level
            state.current_config['effort_level'] = level
            config.save_config(state.current_config)
            log.info(f"思考深度已切换: {level}")
            print(f"思考深度已切换为: {level_label.get(level, level)}")
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
        
        missing = []
        if not state.current_config.get('api_key'):
            missing.append("API 密钥")
        if not state.current_config.get('model'):
            missing.append("模型")
        if missing:
            missing_text = "、".join(missing)
            print(f"{Fore.RED}错误: 未设置{missing_text}，无法发送消息。输入 '{cmd.get_command('model')}' 进行配置。可前往 DeepSeek 官网申请 API key{Style.RESET_ALL}")
            log.warning(f"发送消息前检查失败: 缺少{missing_text}")
            continue

        log.info(f"用户输入: {user_input}")
        ui.turn_first_output = True
        state.chat_instance.set_save_target(state.current_dir_id, state.current_conv_id)
        try:
            await state.chat_instance.chat_stream(user_input)
        except AuthenticationError:
            print(f"{Fore.RED}错误: API 密钥无效或已过期。输入 '{cmd.get_command('model')}' 重新配置 API 密钥{Style.RESET_ALL}")
            log.error("API 认证失败: 密钥无效或已过期")
            _rollback_last_message()
        except RateLimitError:
            print(f"{Fore.RED}错误: API 调用频率过高或余额不足，请稍后重试或检查账户余额{Style.RESET_ALL}")
            log.error("API 限流: 频率过高或余额不足")
            _rollback_last_message()
        except APIConnectionError:
            print(f"{Fore.RED}错误: 无法连接到 API 服务器，请检查网络连接或稍后重试{Style.RESET_ALL}")
            log.error("API 连接失败: 网络问题或服务器不可达")
            _rollback_last_message()
        except APIError as e:
            print(f"{Fore.RED}错误: API 服务异常 ({e.status_code if hasattr(e, 'status_code') else 'unknown'})，请稍后重试{Style.RESET_ALL}")
            log.error(f"API 错误: {e}")
            _rollback_last_message()
        except Exception as e:
            print(f"{Fore.RED}错误: 请求失败，请稍后重试{Style.RESET_ALL}")
            log.error(f"未知错误: {e}")
            _rollback_last_message()
        
        # 每次对话结束后检查是否有待确认的文件更改
        handle_pending_changes()

def _progress_bar(percent, label):
    if ui.progress is None:
        ui.progress = Progress(
            BarColumn(bar_width=25, style="dim", complete_style="cyan", finished_style="cyan"),
            TextColumn("[bright_blue]{task.percentage:>3.0f}%"),
            TextColumn("{task.description}"),
        )
        ui.progress.start()
        ui.progress.add_task("", total=100)
        ui.progress.console.print()
    ui.progress.tasks[0].completed = percent
    ui.progress.tasks[0].description = label
    ui.progress.refresh()
    if percent >= 100:
        ui.progress.stop()
        ui.progress = None

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
        " ██╗  ",
        " ██║  ",
        " ██║  ",
        " ██║  ",
        " ██║  ",
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
    _console.print(Text(_DOLPHIN_ART, style="bright_blue"))

def _show_splash():
    _print_dolphin()
    print()

if __name__ == "__main__":
    import asyncio
    import time
    
    _show_splash()
    
    _progress_bar(5, _DEEPSLEEPING[:1])
    time.sleep(0.1)
    state.current_config = config.load_config()
    state.show_thinking = state.current_config.get('show_thinking', False)
    state.effort_level = state.current_config.get('effort_level', 'fine')
    if 'effort_level' not in state.current_config:
        state.current_config['effort_level'] = 'fine'
        config.save_config(state.current_config)
    _progress_bar(20, _DEEPSLEEPING[:3])
    time.sleep(0.1)
    
    cmd._validate_commands()
    _progress_bar(35, _DEEPSLEEPING[:7])
    time.sleep(0.1)
    
    deprecation_warning = config.check_model_deprecation(state.current_config.get('model', 'deepseek-v4-flash'))
    if deprecation_warning:
        log.warning(deprecation_warning)
    
    WORKPLACE_DIR = state.current_config.get('work_directory', 'workplace')
    # 相对路径基于项目根目录解析为绝对路径
    if not os.path.isabs(WORKPLACE_DIR):
        WORKPLACE_DIR = os.path.join(bootstrap.PROJECT_ROOT, WORKPLACE_DIR)
    if not os.path.exists(WORKPLACE_DIR):
        WORKPLACE_DIR = os.path.join(bootstrap.PROJECT_ROOT, 'workplace')
        log.warning(f"工作目录不存在，回退到默认目录: {WORKPLACE_DIR}")
        state.current_config['work_directory'] = WORKPLACE_DIR
        config.save_config(state.current_config)
    if not os.path.exists(WORKPLACE_DIR):
        os.makedirs(WORKPLACE_DIR)
        log.info(f"创建工作目录: {WORKPLACE_DIR}")
    _progress_bar(50, _DEEPSLEEPING[:11])
    time.sleep(0.1)

    # 嵌入模型下载 + ONNX 转换（仅在 web_search 启用时执行）
    if state.current_config.get('skills', {}).get('web_search', False):
        from modules.bootstrap.model_downloader import is_model_downloaded, download_model
        download_ok = is_model_downloaded()  # 已存在则视为成功

        if not download_ok:
            model_task = None
            model_progress = None
            try:
                model_progress = Progress(
                    BarColumn(bar_width=15, style="dim", complete_style="green", finished_style="green"),
                    TextColumn("[green]{task.percentage:>3.0f}%"),
                    TextColumn("{task.description}"),
                )
                model_progress.start()
                model_task = model_progress.add_task("嵌入模型", total=100)

                def _on_model_progress(ratio: float, desc: str):
                    if model_task is not None:
                        model_progress.tasks[0].completed = int(ratio * 100)
                        model_progress.tasks[0].description = desc
                        model_progress.refresh()

                download_ok = download_model(progress_callback=_on_model_progress)

                model_progress.tasks[0].completed = 100
                model_progress.tasks[0].description = "嵌入模型下载完成" if download_ok else "嵌入模型下载失败"
                model_progress.refresh()

                if not download_ok:
                    _console.print("[yellow]联网搜索将使用未过滤结果[/yellow]")
            except Exception as e:
                download_ok = False
                if model_task is not None and model_progress is not None:
                    model_progress.tasks[0].completed = 100
                    model_progress.tasks[0].description = "嵌入模型下载失败"
                    model_progress.refresh()
                log.warning(f"模型下载过程异常: {e}")

        if download_ok:
            from modules.bootstrap.onnx_converter import is_onnx_converted, convert_to_onnx
            if not is_onnx_converted():
                onnx_task = None
                onnx_progress = None
                try:
                    onnx_progress = Progress(
                        BarColumn(bar_width=15, style="dim", complete_style="cyan", finished_style="cyan"),
                        TextColumn("[cyan]{task.percentage:>3.0f}%"),
                        TextColumn("{task.description}"),
                    )
                    onnx_progress.start()
                    onnx_task = onnx_progress.add_task("ONNX 转换", total=100)

                    def _on_onnx_progress(ratio: float, desc: str):
                        if onnx_task is not None:
                            onnx_progress.tasks[0].completed = int(ratio * 100)
                            onnx_progress.tasks[0].description = desc
                            onnx_progress.refresh()

                    convert_to_onnx(progress_callback=_on_onnx_progress)

                    onnx_progress.tasks[0].completed = 100
                    onnx_progress.tasks[0].description = "ONNX 转换完成"
                    onnx_progress.refresh()
                except Exception as e:
                    if onnx_task is not None and onnx_progress is not None:
                        onnx_progress.tasks[0].completed = 100
                        onnx_progress.tasks[0].description = "ONNX 转换失败"
                        onnx_progress.refresh()
                    log.warning(f"ONNX 转换过程异常: {e}")

        time.sleep(0.5)

    state.chat_instance = chat.QuickAIChat(
        model=state.current_config.get('model', 'deepseek-v4-flash'), 
        max_tokens=state.current_config.get('max_tokens', 18000),
        callback=chat_callback
    )
    state.chat_instance.effort_level = state.effort_level
    _progress_bar(85, _DEEPSLEEPING[:17])
    time.sleep(0.1)
    
    state.current_conversation = "main"
    state.current_dir_id = None
    state.current_conv_id = None
    
    log.info("Dolphin 启动")
    log.info(f"当前配置: model={state.current_config.get('model')}, max_tokens={state.current_config.get('max_tokens', 18000)}, effort={state.effort_level}, conversation={state.current_conversation}, work_directory={WORKPLACE_DIR}")
    _progress_bar(100, _DEEPSLEEPING)
    time.sleep(0.3)
    screen_refresh.clear_screen()
    
    _print_header()
    
    open_work_directory(WORKPLACE_DIR, silent=True)
    
    if state.chat_instance.messages:
        _print_conversation_history()
    
    asyncio.run(main())

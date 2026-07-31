"""设置模式、模型设置和工具切换界面。"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from modules.logger import get_logger
from .state import state
from .screen_refresh import create_header_panel, create_footer_panel

log = get_logger("Dolphin.settings")
_console = Console()


def _rebuild_client_and_chat():
    """根据当前配置重建 OpenAI 客户端和 chat 实例。"""
    config = state.config
    chat = state.chat

    # 保留旧实例的消息，避免对话历史丢失
    old_messages = []
    if state.chat_instance is not None:
        old_messages = state.chat_instance.messages

    state.client = state.OpenAI(
        api_key=state.current_config.get("api_key"),
        base_url=state.current_config.get("base_url")
    )
    state.chat_instance = chat.DolphinChat(
        model=state.current_config.get('model'),
        max_tokens=state.current_config.get('max_tokens', 18000),
        callback=_chat_callback_proxy
    )
    state.chat_instance.effort_level = state.effort_level
    state.chat_instance.messages = old_messages
    log.info("客户端已更新")
    print("客户端已更新")


def _chat_callback_proxy(event_type, data):
    """延迟解析的回调代理，避免循环导入。"""
    from .callback import chat_callback
    return chat_callback(event_type, data)


def settings_mode():
    """进入设置界面。"""
    cmd = state.cmd
    config = state.config
    log.info("进入设置模式")

    def _render():
        while True:
            current_max_tokens = state.current_config.get('max_tokens', 18000)
            current_prefix = state.current_config.get('command_prefix', '/')

            # 构建当前配置表格
            table = Table(show_header=True, header_style="bold cyan", border_style="dim", padding=(0, 2))
            table.add_column("配置项", style="bold white", width=15)
            table.add_column("当前值", style="dim")
            table.add_row("最大 Token 数", str(current_max_tokens))
            table.add_row("命令前缀", current_prefix)

            # 渲染界面
            _console.print()
            _console.print(create_header_panel("设置模式", "配置 Dolphin 的运行参数"))
            _console.print()
            _console.print(table)
            _console.print()
            _console.print("[bold]操作选项:[/bold]")
            _console.print("  [cyan]1[/cyan] - 修改最大 Token 数")
            _console.print("  [cyan]2[/cyan] - 修改命令前缀")
            _console.print(f"  [dim]{cmd.get_command_keyword('back')}[/dim] - 返回主界面")
            _console.print()
            _console.print(create_footer_panel("输入对应选项进行配置"))

            choice = input("\n> ").strip()

            if choice == cmd.get_command_keyword('back') or not choice:
                _rebuild_client_and_chat()
                return

            if choice == '1':
                # 修改最大 Token 数
                _console.print()
                _console.print(Panel(Text("当前值: " + str(current_max_tokens) + "\n推荐值: 18000 (适合大多数场景)\n范围: 1-200000"), title="最大 Token 数", border_style="cyan"))
                new_value = input("输入新的最大 Token 数 (留空保持当前值): ").strip()

                if not new_value:
                    continue

                try:
                    new_max_tokens = int(new_value)
                    if new_max_tokens < 1:
                        _console.print("[red]Token 数至少为 1[/red]")
                        input("按 Enter 键继续...")
                        continue
                    elif new_max_tokens > 200000:
                        _console.print("[red]Token 数最大不超过 200000[/red]")
                        input("按 Enter 键继续...")
                        continue
                    state.current_config['max_tokens'] = new_max_tokens
                    config.save_config(state.current_config)
                    log.info(f"最大 Token 数已更改: {new_max_tokens}")
                    _console.print(f"[green]已更新: {new_max_tokens}[/green]")
                    input("按 Enter 键继续...")
                except ValueError:
                    _console.print("[red]请输入有效数字[/red]")
                    input("按 Enter 键继续...")

            elif choice == '2':
                # 修改命令前缀
                _console.print()
                _console.print(Panel(Text(f"当前前缀: {current_prefix}\n修改后将统一更改所有命令的唤起前缀\n例如: /help → .help"), title="命令前缀", border_style="cyan"))
                new_prefix = input("输入新的命令前缀 (最长10字符): ").strip()

                if not new_prefix:
                    continue

                if len(new_prefix) > 10:
                    new_prefix = new_prefix[:10]
                    _console.print(f"[yellow]命令前缀已截断为: {new_prefix}[/yellow]")

                state.current_config['command_prefix'] = new_prefix
                config.save_config(state.current_config)
                cmd.save_commands()
                log.info(f"命令前缀已更改: {current_prefix} -> {new_prefix}")
                _console.print(f"[green]已更新: {new_prefix}[/green]")
                input("按 Enter 键继续...")

            else:
                _console.print("[red]无效选项[/red]")
                input("按 Enter 键继续...")

    from .screen_refresh import enter_screen
    enter_screen(_render,
                 command_input=cmd.get_command('set'),
                 command_info=f"╰─{cmd.get_command_description('set')}")


def _apply_model_config(model_info):
    """将模型专属配置写入 current_config 并保存。"""
    # 自定义模型有专属的 base_url 和 api_key
    if model_info.get("custom"):
        if model_info.get("base_url"):
            state.current_config["base_url"] = model_info["base_url"]
        if model_info.get("api_key"):
            state.current_config["api_key"] = model_info["api_key"]


def model_settings():
    """模型设置界面。"""
    cmd = state.cmd
    config = state.config
    log.info("进入模型设置")

    from modules.main_server.config import (
        get_available_models, add_custom_model, remove_custom_model,
        get_custom_model
    )

    def _render():
        current_model = state.current_config.get('model', 'deepseek-v4-flash')

        while True:
            available_models = get_available_models()

            # 构建模型列表表格
            table = Table(show_header=True, header_style="bold cyan", border_style="dim", padding=(0, 2))
            table.add_column("#", style="dim", width=4)
            table.add_column("模型名称", style="bold white", width=30)
            table.add_column("描述", style="dim", width=20)
            table.add_column("状态", width=12)

            choice_map = {}
            custom_indices = set()
            idx = 1

            for model_info in available_models:
                marker = "✓" if model_info['name'] == current_model else ""
                desc = model_info.get('description', '')
                name_display = model_info['name']
                if model_info.get("custom"):
                    name_display = f"* {name_display}"
                    custom_indices.add(str(idx))
                table.add_row(str(idx), name_display, desc, Text(marker, style="green"))
                choice_map[str(idx)] = model_info
                idx += 1

            # 渲染界面
            _console.print()
            _console.print(create_header_panel("模型设置", f"当前模型: {current_model}"))
            _console.print()
            _console.print(table)
            _console.print()
            _console.print("[bold]操作选项:[/bold]")
            _console.print(f"  [cyan]1-{idx-1}[/cyan] - 选择模型")
            _console.print(f"  [cyan]k[/cyan] - 修改 API 密钥")
            _console.print(f"  [cyan]a[/cyan] - 添加自定义模型")
            if custom_indices:
                _console.print(f"  [cyan]d[/cyan] - 删除自定义模型")
            _console.print(f"  [dim]{cmd.get_command_keyword('back')}[/dim] - 返回主界面")
            _console.print("  ([dim]*[/dim] 标记表示自定义模型)")
            _console.print()
            api_key = state.current_config.get('api_key', '')
            _console.print(create_footer_panel(f"API 密钥: {'***' + api_key[-4:] if len(api_key) > 4 else ('已设置' if api_key else '未设置')}"))

            choice = input("\n> ").strip()

            if choice == cmd.get_command_keyword('back') or not choice:
                return

            if choice == 'k':
                # 修改 API 密钥
                _console.print()
                new_api_key = input("API 密钥 (留空保持当前值): ").strip()
                if new_api_key:
                    state.current_config['api_key'] = new_api_key
                    config.save_config(state.current_config)
                    log.info("API 密钥已更新")
                    _console.print("[green]API 密钥已更新[/green]")
                    _rebuild_client_and_chat()
                    input("按 Enter 键继续...")
                continue

            if choice == 'a':
                # 添加自定义模型
                _add_custom_model_flow()
                continue

            if choice == 'd':
                # 删除自定义模型
                _delete_custom_model_flow(custom_indices, choice_map)
                continue

            if choice not in choice_map:
                _console.print("[red]无效选择[/red]")
                input("按 Enter 键继续...")
                continue

            model_info = choice_map[choice]
            new_model = model_info["name"]
            state.current_config['model'] = new_model
            _apply_model_config(model_info)
            config.save_config(state.current_config)
            log.info(f"模型已切换: {new_model}")
            _rebuild_client_and_chat()
            _console.print(f"[green]已切换至: {new_model}[/green]")
            input("按 Enter 键继续...")
            return

    from .screen_refresh import enter_screen
    enter_screen(_render,
                 command_input=cmd.get_command('model'),
                 command_info=f"╰─{cmd.get_command_description('model')}")


def _add_custom_model_flow():
    """自定义模型添加流程。"""
    from modules.main_server.config import add_custom_model

    _console.print()
    _console.print(create_header_panel("添加自定义模型", "输入新模型的配置信息"))

    name = input("模型名称 (如 gpt-4o): ").strip()
    if not name:
        _console.print("[red]模型名称不能为空[/red]")
        input("按 Enter 键继续...")
        return

    description = input("模型描述 (如 OpenAI GPT-4o): ").strip()
    if not description:
        description = name

    base_url = input("API 地址 (如 https://api.openai.com/v1): ").strip()
    if not base_url:
        _console.print("[red]API 地址不能为空[/red]")
        input("按 Enter 键继续...")
        return

    api_key = input("API 密钥: ").strip()
    if not api_key:
        _console.print("[red]API 密钥不能为空[/red]")
        input("按 Enter 键继续...")
        return

    context_str = input("上下文窗口大小 (留空默认 128000): ").strip()
    context_window = 128000
    if context_str:
        try:
            context_window = int(context_str)
        except ValueError:
            _console.print("[yellow]输入无效，使用默认值 128000[/yellow]")

    success, error = add_custom_model(name, description, base_url, api_key, context_window)
    if success:
        _console.print(f"[green]自定义模型 '{name}' 已添加[/green]")
    else:
        _console.print(f"[red]{error}[/red]")
    input("按 Enter 键继续...")


def _delete_custom_model_flow(custom_indices, choice_map):
    """自定义模型删除流程。"""
    from modules.main_server.config import remove_custom_model

    _console.print()
    _console.print(create_header_panel("删除自定义模型", "选择要删除的自定义模型"))
    _console.print(f"[bold]可删除的模型序号:[/bold] {', '.join(sorted(custom_indices))}")

    idx_input = input("输入要删除的模型序号 (留空取消): ").strip()
    if not idx_input or idx_input not in custom_indices:
        return

    model_info = choice_map[idx_input]
    name = model_info["name"]

    # 如果当前正在使用该模型，切回默认模型
    if state.current_config.get('model') == name:
        state.current_config['model'] = 'deepseek-v4-flash'

    success, error = remove_custom_model(name)
    if success:
        _console.print(f"[green]自定义模型 '{name}' 已删除[/green]")
    else:
        _console.print(f"[red]{error}[/red]")
    input("按 Enter 键继续...")


def toggle_tools():
    """切换工具启用/禁用状态。"""
    current_status = state.chat_instance.enable_tools
    new_status = not current_status
    state.chat_instance.enable_tool(new_status)
    status_text = "启用" if new_status else "禁用"
    log.info(f"工具状态已切换: {status_text}")
    print(f"工具已{status_text}")
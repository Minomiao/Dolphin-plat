"""文件变更确认界面。"""
import time

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from colorama import Fore, Style

from modules.logger import get_logger
from .state import state
from .callback import flush_context_usage

log = get_logger("Dolphin.changes")


def _get_last_assistant_output():
    """获取最后一段 AI 输出内容。"""
    try:
        if not hasattr(state, 'chat_instance') or not state.chat_instance:
            return None

        messages = state.chat_instance.messages
        if not messages:
            return None

        for msg in reversed(messages):
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                if content and content.strip():
                    return content.strip()

        return None
    except Exception as e:
        log.debug(f"获取最后 AI 输出失败: {e}")
        return None


def _build_changes_table(pending_list):
    """构建变更列表表格。"""
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


def _show_operation_result(console, result, action_name):
    """显示操作结果。"""
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

    console.print(Panel(message, border_style="green" if result.get('success') else "red"))

    changes = result.get('changes', [])
    if changes:
        console.print(f"\n{action_name}详情:")
        for change in changes:
            file_path = change.get('file', 'unknown')
            status = change.get('status', 'unknown')
            status_color = "green" if "success" in status or "applied" in status or "reverted" in status else "red"
            console.print(f"  [{status_color}]✓[/{status_color}] {file_path}: {status}")

    input("\n按 Enter 键继续...")


def _process_changes_input(bm, console):
    """处理用户输入。"""
    while True:
        try:
            choice = input("\n请选择操作: ").lower().strip()

            if choice == 'y':
                result = bm.apply_all_changes()
                _show_operation_result(console, result, "应用")
                break
            elif choice == 'n':
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


def _show_changes_screen(bm, pending_count):
    """显示变更确认界面。"""
    console = Console()

    header_text = Text.assemble(
        "文件变更确认 (",
        (str(pending_count), "bold cyan"),
        " 个待处理)",
    )

    last_output = _get_last_assistant_output()

    pending_list = bm.get_pending_changes_list()
    table = _build_changes_table(pending_list)

    footer_text = Text.from_markup(
        "[bold]操作:[/bold] "
        "[green]y[/green]=应用全部 | "
        "[red]n[/red]=撤销全部 | "
        "[yellow]s[/yellow]=跳过"
    )

    console.print()
    console.print(Panel(header_text, border_style="cyan"))

    if last_output:
        display_text = last_output[:300] + "..." if len(last_output) > 300 else last_output
        console.print(Panel(
            display_text,
            title="最近对话",
            border_style="dim",
            padding=(0, 1)
        ))

    console.print(table)
    console.print(Panel(footer_text, border_style="dim"))
    console.print()

    _process_changes_input(bm, console)


def handle_pending_changes():
    """处理待确认的文件变更。"""
    backup_manager = state.backup_manager
    screen_refresh = state.screen_refresh
    from .header import print_header, print_conversation_history

    bm = backup_manager.get_backup_manager()
    pending_count = bm.get_pending_changes_count()
    if pending_count == 0:
        return

    screen_refresh.clear_screen()
    _show_changes_screen(bm, pending_count)
    screen_refresh.refresh(print_header, print_conversation_history)


def handle_post_chat_changes():
    """每次对话结束后检查待确认变更并刷新 token 用量回显。"""
    handle_pending_changes()
    flush_context_usage()

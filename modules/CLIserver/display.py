"""帮助、工具、技能显示界面。"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from modules.logger import get_logger
from .state import state
from .screen_refresh import clear_screen, create_header_panel, create_footer_panel

log = get_logger("Dolphin.display")
_console = Console()


def show_help():
    """显示命令帮助界面。"""
    def _render():
        cmd = state.cmd
        commands_config = cmd.load_commands()
        cmd_list = commands_config.get("commands", {})

        log.info("显示帮助信息")

        # 构建表格
        table = Table(show_header=True, header_style="bold cyan", border_style="dim", padding=(0, 2))
        table.add_column("命令", style="bold white", width=15)
        table.add_column("描述", style="dim")

        for cmd_key, cmd_info in cmd_list.items():
            cmd_input = cmd_info.get("input", "")
            cmd_description = cmd_info.get("description", "")
            table.add_row(cmd_input, cmd_description)

        # 渲染界面
        _console.print()
        _console.print(create_header_panel("命令帮助", "查看所有可用命令及其用法"))
        _console.print()
        _console.print(table)
        _console.print()
        _console.print(create_footer_panel("按 Enter 键返回主界面"))
        input()

    from .screen_refresh import enter_screen
    enter_screen(_render)


def show_tools():
    """显示可用工具界面。"""
    def _render():
        tools = state.chat_instance.list_available_tools()
        log.info(f"显示可用工具，共 {len(tools)} 个")

        _console.print()
        _console.print(create_header_panel("可用工具", f"共 {len(tools)} 个工具"))

        if tools:
            table = Table(show_header=True, header_style="bold cyan", border_style="dim", padding=(0, 2))
            table.add_column("#", style="dim", width=4)
            table.add_column("工具名称", style="bold white", width=20)
            table.add_column("描述", style="dim")

            for i, tool in enumerate(tools, 1):
                table.add_row(str(i), tool['name'], tool.get('description', ''))

            _console.print()
            _console.print(table)
        else:
            _console.print()
            _console.print(Panel(Text("没有可用的工具", style="yellow"), border_style="yellow"))

        _console.print()
        _console.print(create_footer_panel("按 Enter 键返回主界面"))
        input()

    from .screen_refresh import enter_screen
    enter_screen(_render)


def show_skills():
    """显示技能管理界面。"""
    cmd = state.cmd
    log.info("显示技能管理")

    skills = state.chat_instance.list_skills()
    if not skills:
        print("\n没有可用的技能")
        return

    def _render():
        while True:
            # 构建表格
            table = Table(show_header=True, header_style="bold cyan", border_style="dim", padding=(0, 2))
            table.add_column("#", style="dim", width=4)
            table.add_column("技能名称", style="bold white", width=25)
            table.add_column("状态", width=8)
            table.add_column("描述", style="dim")

            for i, skill in enumerate(skills, 1):
                status = "启用" if skill.get('enabled', True) else "禁用"
                status_style = "green" if skill.get('enabled', True) else "red"
                table.add_row(
                    str(i),
                    skill['name'],
                    Text(status, style=status_style),
                    skill.get('description', '')
                )

            # 渲染界面
            _console.print()
            _console.print(create_header_panel("技能管理", f"共 {len(skills)} 个技能，输入编号切换状态"))
            _console.print()
            _console.print(table)
            _console.print()
            _console.print(create_footer_panel(f"输入编号切换状态 | 输入 '{cmd.get_command_keyword('back')}' 返回主界面"))

            choice = input("\n> ").strip()
            if not choice or choice == cmd.get_command_keyword('back'):
                return

            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(skills):
                    _console.print("[red]无效的编号[/red]")
                    input("按 Enter 键继续...")
                    continue
            except ValueError:
                _console.print("[red]无效的输入[/red]")
                input("按 Enter 键继续...")
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
                _console.print(f"[green]{skill_name}[/green] 已{new_status_text}")
                skill['enabled'] = target_status
            else:
                _console.print(f"[red]错误: {result.get('error')}[/red]")
            input("按 Enter 键继续...")

    from .screen_refresh import enter_screen
    enter_screen(_render)
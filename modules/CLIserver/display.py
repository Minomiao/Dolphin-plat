"""帮助、工具、技能显示。"""
from colorama import Fore, Style

from modules.logger import get_logger
from .state import state

log = get_logger("Dolphin.display")


def show_help():
    """显示命令帮助。"""
    cmd = state.cmd
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
    """显示可用工具。"""
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
    """显示技能管理。"""
    cmd = state.cmd
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

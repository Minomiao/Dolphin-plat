from openai import OpenAI
from modules import config
from modules import commands as cmd
from modules import chat
from modules import logger
import os

log = logger.setup_logger("QuickAI")

def settings_mode():
    global current_config, chat_instance, commands_config
    log.info("进入设置模式")
    print("\n=== 设置模式 ===")
    print(f"输入 '{cmd.get_command('back')}' 返回主界面")
    print("当前配置:")
    print(f"API密钥: {'***' if current_config.get('api_key') else '未设置'}")
    print(f"模型: {current_config.get('model', 'deepseek-chat')}")
    print(f"工作目录: {current_config.get('work_directory', 'workplace')}")
    print("\n输入新的配置 (留空保持当前值):")
    
    new_api_key = input("API密钥: ")
    if new_api_key == cmd.get_command('back'):
        log.info("用户取消设置，返回主界面")
        print("返回主界面")
        return
    new_api_key = new_api_key or current_config.get('api_key')
    
    print("\n可用模型:")
    print("1. deepseek-chat")
    print("2. deepseek-coder")
    print("3. deepseek-reasoner")
    print("4. gpt-3.5-turbo")
    print("5. gpt-4")
    print("6. 自定义模型")
    
    model_choice = input("\n请选择模型 (1-6): ")
    if model_choice == cmd.get_command('back'):
        log.info("用户取消设置，返回主界面")
        print("返回主界面")
        return
    
    model_map = {
        "1": "deepseek-chat",
        "2": "deepseek-coder",
        "3": "deepseek-reasoner",
        "4": "gpt-3.5-turbo",
        "5": "gpt-4"
    }
    
    if model_choice in model_map:
        new_model = model_map[model_choice]
    elif model_choice == "6":
        new_model = input("请输入自定义模型名称: ")
        if new_model == cmd.get_command('back'):
            log.info("用户取消设置，返回主界面")
            print("返回主界面")
            return
        new_model = new_model or current_config.get('model', 'deepseek-chat')
    else:
        log.warning(f"无效的模型选择: {model_choice}")
        print("无效选择，保持当前模型")
        new_model = current_config.get('model', 'deepseek-chat')
    
    print(f"\n当前工作目录: {current_config.get('work_directory', 'workplace')}")
    new_work_directory = input("输入新的工作目录 (留空保持当前值): ")
    if new_work_directory == cmd.get_command('back'):
        log.info("用户取消设置，返回主界面")
        print("返回主界面")
        return
    new_work_directory = new_work_directory or current_config.get('work_directory', 'workplace')
    
    print("\n是否要修改命令配置? (y/n)")
    modify_commands = input().lower()
    if modify_commands == 'y':
        cmd_list = commands_config.get("commands", {})
        for cmd_key in cmd_list.keys():
            current_input = cmd_list[cmd_key].get('input', '')
            new_input = input(f"{cmd_key} 命令输入 (当前: {current_input}): ")
            if new_input == cmd.get_command('back'):
                log.info("用户取消设置，返回主界面")
                print("返回主界面")
                return
            if new_input:
                log.info(f"修改命令 {cmd_key} 输入: {current_input} -> {new_input}")
                commands_config["commands"][cmd_key]["input"] = new_input
    
    current_config['api_key'] = new_api_key
    current_config['model'] = new_model
    current_config['work_directory'] = new_work_directory
    
    config.save_config(current_config)
    cmd.save_commands(commands_config)
    log.info(f"配置已保存: model={new_model}, work_directory={new_work_directory}")
    print("\n配置已保存")
    
    if new_work_directory != current_config.get('work_directory', 'workplace'):
        print(f"工作目录已更改，正在重新加载技能模块...")
        import importlib
        import modules.skill_manager as sm
        importlib.reload(sm)
        global skill_mgr
        skill_mgr = sm.get_skill_manager()
        chat_instance.skill_mgr = skill_mgr
        chat_instance._update_tools()
        print("技能模块已重新加载")
    
    global client
    client = OpenAI(
        api_key=current_config.get("api_key"),
        base_url=current_config.get("base_url")
    )
    chat_instance = chat.QuickAIChat(model=current_config.get('model'))
    log.info("客户端已更新")
    print("客户端已更新")

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
    skills = chat_instance.list_skills()
    log.info(f"显示可用技能，共 {len(skills)} 个")
    if skills:
        print("\n=== 可用技能 ===")
        for skill in skills:
            print(f"  - {skill['name']}")
            print(f"    描述: {skill['description']}")
            print(f"    函数: {', '.join(skill['functions'])}")
    else:
        print("\n没有可用的技能")

def toggle_tools():
    current_status = chat_instance.enable_tools
    new_status = not current_status
    chat_instance.enable_tool(new_status)
    status_text = "启用" if new_status else "禁用"
    log.info(f"工具状态已切换: {status_text}")
    print(f"工具已{status_text}")

def manage_skills():
    from modules import config
    skills = chat_instance.list_skills()
    
    print("\n=== 技能管理 ===")
    if skills:
        for i, skill in enumerate(skills, 1):
            status = "启用" if skill.get('enabled', True) else "禁用"
            print(f"{i}. {skill['name']} - {skill['description']} [{status}]")
            print(f"   函数: {', '.join(skill['functions'])}")
    else:
        print("没有可用的技能")
        return
    
    # 逐个询问用户是否修改技能状态
    print("\n=== 技能状态设置 ===")
    print("现在将逐个询问每个技能的状态设置")
    print("输入 'y' 确认当前状态，或输入 'n' 切换状态，或输入 's' 跳过")
    
    updated_skills = []
    
    for skill in skills:
        skill_name = skill['name']
        current_status = skill.get('enabled', True)
        status_text = "启用" if current_status else "禁用"
        
        print(f"\n技能: {skill_name}")
        print(f"描述: {skill['description']}")
        print(f"当前状态: {status_text}")
        print(f"包含函数: {', '.join(skill['functions'])}")
        
        while True:
            choice = input(f"是否保持{status_text}状态? (y/n/s): ").lower()
            if choice in ['y', 'n', 's']:
                break
            print("请输入有效的选项: y (保持) / n (切换) / s (跳过)")
        
        if choice == 's':
            print(f"跳过技能 {skill_name}")
            continue
        elif choice == 'n':
            new_status = not current_status
            result = chat_instance.skill_mgr.toggle_skill(skill_name, new_status)
            if result.get('success'):
                new_status_text = "启用" if new_status else "禁用"
                print(f"技能 '{skill_name}' 已{new_status_text}")
                updated_skills.append(skill_name)
            else:
                print(f"错误: {result.get('error')}")
        else:  # choice == 'y'
            print(f"保持技能 '{skill_name}' {status_text}状态")
    
    # 显示更新结果
    if updated_skills:
        print(f"\n=== 更新完成 ===")
        print(f"已更新 {len(updated_skills)} 个技能的状态")
        for skill_name in updated_skills:
            skills_config = config.load_config().get('skills', {})
            status = "启用" if skills_config.get(skill_name, True) else "禁用"
            print(f"- {skill_name}: {status}")
    else:
        print("\n=== 操作完成 ===")
        print("没有更新任何技能的状态")
    
    # 提供额外的修改选项
    print("\n=== 额外选项 ===")
    print("1. 查看当前技能状态")
    print("2. 返回主菜单")
    
    while True:
        choice = input("请选择: ")
        if choice == '1':
            skills = chat_instance.list_skills()
            print("\n=== 当前技能状态 ===")
            for i, skill in enumerate(skills, 1):
                status = "启用" if skill.get('enabled', True) else "禁用"
                print(f"{i}. {skill['name']} - [{status}]")
        elif choice == '2':
            break
        else:
            print("请输入有效的选项: 1 (查看状态) / 2 (返回)")
    
    print("退出技能管理")

if __name__ == "__main__":
    current_config = config.load_config()
    commands_config = cmd.load_commands()
    
    WORKPLACE_DIR = current_config.get('work_directory', 'workplace')
    if not os.path.exists(WORKPLACE_DIR):
        os.makedirs(WORKPLACE_DIR)
        log.info(f"创建工作目录: {WORKPLACE_DIR}")
    
    chat_instance = chat.QuickAIChat(model=current_config.get('model', 'deepseek-chat'))
    current_conversation = "main"
    
    log.info("QuickAI 启动")
    log.info(f"当前配置: model={current_config.get('model')}, conversation={current_conversation}, work_directory={WORKPLACE_DIR}")
    print("QuickAI 聊天助手")
    print(f"输入 '{cmd.get_command('help')}' 获取命令帮助")
    print("=" * 50)
    
    while True:
        user_input = input("\n您: ")
        
        if user_input == cmd.get_command('quit'):
            log.info("用户退出程序")
            print("再见!")
            break
        elif user_input == cmd.get_command('clear'):
            log.info("清空历史记录")
            chat_instance.clear_history()
            print("历史记录已清空")
            continue
        elif user_input == cmd.get_command('set'):
            settings_mode()
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
        elif user_input == cmd.get_command('load'):
            load_name = input("请输入要加载的对话名称: ")
            if load_name:
                if chat_instance.load_conversation(load_name):
                    current_conversation = load_name
                    log.info(f"加载对话: {load_name}")
                    print(f"已加载对话: {load_name}")
                else:
                    log.warning(f"对话不存在: {load_name}")
                    print(f"对话 '{load_name}' 不存在")
            continue
        elif user_input == cmd.get_command('save_as'):
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
            show_skills()
            continue
        elif user_input == cmd.get_command('toggle'):
            toggle_tools()
            continue
        elif user_input == cmd.get_command('skill'):
            manage_skills()
            continue
        
        log.info(f"用户输入: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")
        chat_instance.chat_stream(user_input)

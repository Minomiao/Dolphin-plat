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

def settings_mode():
    global current_config, chat_instance, commands_config
    log.info("进入设置模式")
    print("\n=== 设置模式 ===")
    print(f"输入 '{cmd.get_command('back')}' 返回主界面")
    print("当前配置:")
    print(f"API密钥: {'***' if current_config.get('api_key') else '未设置'}")
    print(f"模型: {current_config.get('model', 'deepseek-v4-flash')}")
    print(f"工作目录: {current_config.get('work_directory', 'workplace')}")
    print(f"最大Token数: {current_config.get('max_tokens', 8192)}")
    print("\n输入新的配置 (留空保持当前值):")
    
    new_api_key = input("API密钥: ")
    if new_api_key == cmd.get_command('back'):
        log.info("用户取消设置，返回主界面")
        print("返回主界面")
        return
    new_api_key = new_api_key or current_config.get('api_key')
    
    print("\n可用模型:")
    
    from modules.config import get_available_models, MODEL_REGISTRY
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
        deprecation_msg = config.check_model_deprecation(deprecated_models[0]["name"])
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
        log.info("用户取消设置，返回主界面")
        print("返回主界面")
        return
    
    if model_choice in choice_map:
        if choice_map[model_choice] == "__custom__":
            new_model = input("请输入自定义模型名称: ")
            if new_model == cmd.get_command('back'):
                log.info("用户取消设置，返回主界面")
                print("返回主界面")
                return
            new_model = new_model or current_config.get('model', 'deepseek-v4-flash')
        else:
            new_model = choice_map[model_choice]
    else:
        log.warning(f"无效的模型选择: {model_choice}")
        print("无效选择，保持当前模型")
        new_model = current_config.get('model', 'deepseek-v4-flash')
    
    print(f"\n当前工作目录: {current_config.get('work_directory', 'workplace')}")
    new_work_directory = input("输入新的工作目录 (留空保持当前值): ")
    if new_work_directory == cmd.get_command('back'):
        log.info("用户取消设置，返回主界面")
        print("返回主界面")
        return
    new_work_directory = new_work_directory or current_config.get('work_directory', 'workplace')
    
    print(f"\n当前最大Token数: {current_config.get('max_tokens', 8192)}")
    print("推荐值: 8192 (适合大多数场景)")
    new_max_tokens = input("输入新的最大Token数 (留空保持当前值): ")
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
    current_config['max_tokens'] = new_max_tokens
    
    config.save_config(current_config)
    cmd.save_commands(commands_config)
    log.info(f"配置已保存: model={new_model}, work_directory={new_work_directory}, max_tokens={new_max_tokens}")
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
            # 检查是否是插件技能
            if skill_name.startswith("plugin-"):
                result = chat_instance.plugin_loader.toggle_skill(skill_name, new_status)
            else:
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
            # 检查是否是插件技能
            if skill_name.startswith("plugin-"):
                original_skill_name = skill_name[8:]
                plugins_config = config.load_config().get('plugins', {})
                status = "启用" if plugins_config.get(original_skill_name, True) else "禁用"
            else:
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

def chat_callback(event_type, data):
    """处理聊天事件的回调函数"""
    if event_type == 'thinking':
        print(f"思考过程:\n{Fore.LIGHTBLACK_EX}{data['content']}{Style.RESET_ALL}\n{Fore.LIGHTBLACK_EX}--- 思考过程结束 ---{Style.RESET_ALL}\n")
    elif event_type == 'thinking_start':
        print("思考过程:")
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
    global current_config, commands_config, chat_instance, current_conversation
    
    while True:
        user_input = input("\n您: ").strip()
        
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
            show_skills()
            continue
        elif user_input == cmd.get_command('toggle'):
            toggle_tools()
            continue
        elif user_input == cmd.get_command('skill'):
            manage_skills()
            continue
        
        log.info(f"用户输入: {user_input}")
        await chat_instance.chat_stream(user_input)
        
        # 每次对话结束后检查是否有待确认的文件更改
        handle_pending_changes()

if __name__ == "__main__":
    import asyncio
    
    current_config = config.load_config()
    commands_config = cmd.load_commands()
    
    deprecation_warning = config.check_model_deprecation(current_config.get('model', 'deepseek-v4-flash'))
    if deprecation_warning:
        log.warning(deprecation_warning)
        print(f"{Fore.YELLOW}警告: {deprecation_warning}{Style.RESET_ALL}")
    
    WORKPLACE_DIR = current_config.get('work_directory', 'workplace')
    if not os.path.exists(WORKPLACE_DIR):
        os.makedirs(WORKPLACE_DIR)
        log.info(f"创建工作目录: {WORKPLACE_DIR}")
    
    chat_instance = chat.QuickAIChat(
        model=current_config.get('model', 'deepseek-v4-flash'), 
        max_tokens=current_config.get('max_tokens', 8192),
        callback=chat_callback
    )
    current_conversation = "main"
    
    log.info("Dolphin 启动")
    log.info(f"当前配置: model={current_config.get('model')}, max_tokens={current_config.get('max_tokens', 8192)}, conversation={current_conversation}, work_directory={WORKPLACE_DIR}")
    print("Dolphin 聊天助手")
    print(f"输入 '{cmd.get_command('help')}' 获取命令帮助")
    print("=" * 50)
    
    # 运行异步主函数
    asyncio.run(main())

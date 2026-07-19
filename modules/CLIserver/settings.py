"""设置模式、模型设置和工具切换。"""
from colorama import Fore, Style

from modules.logger import get_logger
from .state import state

log = get_logger("Dolphin.settings")


def _rebuild_client_and_chat():
    """根据当前配置重建 OpenAI 客户端和 chat 实例。"""
    config = state.config
    chat = state.chat
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
    log.info("客户端已更新")
    print("客户端已更新")


def _chat_callback_proxy(event_type, data):
    """延迟解析的回调代理，避免循环导入。"""
    from .callback import chat_callback
    return chat_callback(event_type, data)


def settings_mode():
    """进入设置模式。"""
    cmd = state.cmd
    config = state.config
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
    if new_max_tokens == cmd.get_command_keyword('back'):
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
    if new_prefix == cmd.get_command_keyword('back'):
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

    _rebuild_client_and_chat()


def model_settings():
    """模型设置。"""
    cmd = state.cmd
    config = state.config
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
    if model_choice == cmd.get_command_keyword('back'):
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
    if new_api_key == cmd.get_command_keyword('back'):
        log.info("用户取消模型设置，返回主界面")
        print("返回主界面")
        return
    new_api_key = new_api_key or state.current_config.get('api_key')

    state.current_config['api_key'] = new_api_key
    state.current_config['model'] = new_model

    config.save_config(state.current_config)
    log.info(f"模型配置已保存: model={new_model}")
    print(f"\n模型已切换至: {new_model}")

    _rebuild_client_and_chat()


def toggle_tools():
    """切换工具启用/禁用状态。"""
    current_status = state.chat_instance.enable_tools
    new_status = not current_status
    state.chat_instance.enable_tool(new_status)
    status_text = "启用" if new_status else "禁用"
    log.info(f"工具状态已切换: {status_text}")
    print(f"工具已{status_text}")

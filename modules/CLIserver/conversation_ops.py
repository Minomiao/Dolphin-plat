"""对话管理操作：打开工作目录、新建/加载/列出对话。"""
import os
import importlib

from colorama import Fore, Style

from modules import bootstrap
from modules.logger import get_logger
from .state import state

log = get_logger("Dolphin.conversation_ops")


def _chat_callback_proxy(event_type, data):
    """延迟解析的回调代理，避免循环导入。"""
    from .callback import chat_callback
    return chat_callback(event_type, data)


def open_work_directory(path=None, silent=False):
    """打开/切换工作目录。"""
    cmd = state.cmd
    config = state.config
    conversation_loader = state.conversation_loader
    screen_refresh = state.screen_refresh

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

    from .header import print_header, print_conversation_history

    if conv_id and conv_name:
        result = conversation_loader.load_and_activate(
            state.chat_instance, dir_id, conv_id, conv_name, path)
        if result:
            state.current_conversation = result['conv_name']
            state.current_dir_id = result['dir_id']
            state.current_conv_id = result['conv_id']
            state.chat_instance.set_save_target(result['dir_id'], result['conv_id'])
            if not silent:
                screen_refresh.refresh(print_header, print_conversation_history, f"已自动加载对话: {conv_name}")
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
    state.chat_instance.set_save_target(dir_id, new_conv_id)
    log.info(f"为工作目录创建新对话: {conv_name} ({new_conv_id})")
    if not silent:
        screen_refresh.refresh(print_header, print_conversation_history, f"已创建新对话: {conv_name}", show_history=False)


def new_conversation(new_name):
    """新建对话。"""
    cmd = state.cmd
    config = state.config
    conversation_loader = state.conversation_loader
    screen_refresh = state.screen_refresh

    if not new_name:
        new_name = input("请输入新对话名称: ")
    if not new_name:
        return

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
    state.chat_instance.set_save_target(dir_id, conv_id)
    log.info(f"切换到新对话: {new_name} ({conv_id})")

    from .header import print_header, print_conversation_history
    screen_refresh.refresh(print_header, print_conversation_history, f"已切换到新对话: {new_name}", show_history=False)


def load_conversation(load_name):
    """加载旧对话。"""
    cmd = state.cmd
    config = state.config
    conversation_loader = state.conversation_loader
    screen_refresh = state.screen_refresh

    if not load_name:
        load_name = input("请输入要加载的对话名称: ")
    if not load_name:
        return

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
        state.chat_instance.set_save_target(result['dir_id'], result['conv_id'])

        from .header import print_header, print_conversation_history
        screen_refresh.refresh(print_header, print_conversation_history, f"已加载对话: {load_name}")
    else:
        log.warning(f"对话不存在: {load_name}")
        print(f"对话 '{load_name}' 不存在")


def list_conversations():
    """列出当前目录的所有对话。"""
    config = state.config
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

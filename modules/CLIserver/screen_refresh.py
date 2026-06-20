"""
统一的终端清屏/重绘模块。
将项目中散布的 os.system('cls') + _print_header() + _print_conversation_history()
模式收拢为单次调用，支持 清屏 -> 头 -> 消息 -> 对话历史 的连贯渲染。
"""

import os
from modules.logger import get_logger

log = get_logger("Dolphin.screen_refresh")


def clear_screen():
    """跨平台清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def refresh(header_fn, history_fn=None, message=None, show_history=True):
    """
    统一终端重绘。

    参数:
        header_fn:   callable, 无参, 负责绘制页面头部 (如 _print_header)
        history_fn:  callable, 无参, 负责绘制对话历史 (如 _print_conversation_history)
        message:     str | None, 在头部之后、历史之前印出的通告消息
        show_history: bool, 是否调用 history_fn
    """
    clear_screen()
    header_fn()
    if message:
        print(message)
    if show_history and history_fn:
        history_fn()


def refresh_with_header(header_fn, message=None, show_history=True, history_fn=None):
    """
    便捷入口: 清屏后依次打印 头部、消息、对话历史。
    与 refresh() 功能相同，只是参数顺序略作调整以突出 header。
    """
    return refresh(
        header_fn=header_fn,
        history_fn=history_fn,
        message=message,
        show_history=show_history,
    )


def reprint_history(history_fn, header_fn=None):
    """
    只重印头部和对话历史，不清屏（用于追加输出后补印）。
    """
    if header_fn:
        header_fn()
    if history_fn:
        history_fn()

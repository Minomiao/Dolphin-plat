"""终端屏幕控制：ANSI 支持检测与备选屏幕切换。"""
import os
import sys

from modules.bootstrap import constants
from modules.logger import get_logger
from .state import ui

log = get_logger("Dolphin.terminal")

_SCREEN_ALT_ENTER = constants.SCREEN_ALT_ENTER
_SCREEN_ALT_EXIT = constants.SCREEN_ALT_EXIT


def supports_ansi():
    """检测当前终端是否支持 ANSI 转义序列。"""
    if not sys.stdout.isatty():
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
        except Exception as e:
            log.debug(f"ANSI 检测失败: {e}")
            return False
    term = os.environ.get('TERM', '')
    return term not in ('', 'dumb')


def enter_screen():
    """进入终端备选屏幕。"""
    if supports_ansi():
        print(_SCREEN_ALT_ENTER + '\033[H\033[2J', end='', flush=True)
        ui.using_alt_screen = True


def exit_screen():
    """退出终端备选屏幕。"""
    if ui.using_alt_screen:
        print(_SCREEN_ALT_EXIT, end='', flush=True)

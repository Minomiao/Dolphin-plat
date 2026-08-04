"""原始终端按键读取：支持方向键。

Windows 使用控制台输入 API (ReadConsoleInputW)，其他平台回退到
ANSI 转义序列解析。
"""

import os
import sys

from modules.logger import get_logger

log = get_logger("Dolphin.console_input")

KEY_UP = "up"
KEY_DOWN = "down"
KEY_ENTER = "enter"
KEY_ESC = "escape"

_STD_INPUT_HANDLE = -10


def is_available():
    """判断当前是否支持交互式控制台输入（非管道重定向）。"""
    if not sys.stdin.isatty():
        return False
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.GetStdHandle.restype = ctypes.c_void_p
            handle = kernel32.GetStdHandle(_STD_INPUT_HANDLE)
            return bool(handle) and handle != -1
        except Exception as e:
            log.debug(f"控制台输入检测失败: {e}")
            return False
    return True


def flush():
    """清空控制台输入缓冲区，丢弃进入界面前的残留按键。"""
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.GetStdHandle.restype = ctypes.c_void_p
            handle = kernel32.GetStdHandle(_STD_INPUT_HANDLE)
            if handle and handle != -1:
                kernel32.FlushConsoleInputBuffer(handle)
        except Exception as e:
            log.debug(f"清空控制台输入失败: {e}")


def read_key():
    """读取一个按键事件。

    Returns:
        KEY_UP / KEY_DOWN / KEY_ENTER / KEY_ESC，失败时返回 None
    """
    if os.name == 'nt':
        return _read_key_windows()
    return _read_key_unix()


def _read_key_windows():
    """通过 Windows 控制台输入 API 读取按键事件。"""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32

    class KEY_EVENT_RECORD(ctypes.Structure):
        _fields_ = [
            ("bKeyDown", wintypes.BOOL),
            ("wRepeatCount", wintypes.WORD),
            ("wVirtualKeyCode", wintypes.WORD),
            ("wVirtualScanCode", wintypes.WORD),
            ("UnicodeChar", wintypes.WCHAR),
            ("dwControlKeyState", wintypes.DWORD),
        ]

    class INPUT_RECORD(ctypes.Structure):
        _fields_ = [
            ("EventType", wintypes.WORD),
            ("Padding", wintypes.WORD),
            ("KeyEvent", KEY_EVENT_RECORD),
        ]

    KEY_EVENT = 0x0001
    VK_UP = 0x26
    VK_DOWN = 0x28
    VK_RETURN = 0x0D
    VK_ESCAPE = 0x1B
    RIGHT_CTRL_PRESSED = 0x0004
    LEFT_CTRL_PRESSED = 0x0008

    kernel32.GetStdHandle.restype = ctypes.c_void_p
    handle = kernel32.GetStdHandle(_STD_INPUT_HANDLE)
    if not handle or handle == -1:
        return None

    record = INPUT_RECORD()
    num_read = wintypes.DWORD()
    while True:
        if not kernel32.ReadConsoleInputW(handle, ctypes.byref(record), 1, ctypes.byref(num_read)):
            log.debug("ReadConsoleInputW 失败")
            return None
        if num_read.value == 0:
            continue

        if record.EventType == KEY_EVENT and record.KeyEvent.bKeyDown:
            vk = record.KeyEvent.wVirtualKeyCode
            ctrl_state = record.KeyEvent.dwControlKeyState
            if vk == VK_UP:
                return KEY_UP
            if vk == VK_DOWN:
                return KEY_DOWN
            if vk == VK_RETURN:
                return KEY_ENTER
            if vk == VK_ESCAPE:
                return KEY_ESC
            if vk == ord('C') and ctrl_state & (RIGHT_CTRL_PRESSED | LEFT_CTRL_PRESSED):
                return KEY_ESC


def _read_key_unix():
    """通过 ANSI 转义序列读取按键事件（非 Windows 回退）。"""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)

        first = _read_bytes(fd, 1)
        if not first:
            return None
        if first in (b'\r', b'\n'):
            return KEY_ENTER
        if first != b'\x1b':
            return None

        second = _read_bytes(fd, 1, timeout=0.1)
        if second is None:
            return KEY_ESC
        if second != b'[':
            return None
        third = _read_bytes(fd, 1, timeout=0.1)
        if third is None:
            return None
        if third == b'A':
            return KEY_UP
        if third == b'B':
            return KEY_DOWN
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _read_bytes(fd, count, timeout=None):
    """带超时读取 count 个字节；timeout 为 None 时阻塞等待。"""
    import select

    chunks = []
    remaining = count
    while remaining > 0:
        if timeout is not None:
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                break
        data = os.read(fd, remaining)
        if not data:
            break
        chunks.append(data)
        remaining -= len(data)
    return b''.join(chunks)

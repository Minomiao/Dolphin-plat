"""
程序启动引导模块。
由 main.py 在启动之初调用 bootstrap.init(root_path) 完成路径初始化。
支持 PyInstaller 打包后的路径解析。
"""
from .paths import compute

PROJECT_ROOT = None
DATE_DIR = None
LOG_DIR = None
CONVERSATIONS_DIR = None
PROMPT_DIR = None
PROMPT_FILE = None
CONFIG_FILE = None
ENV_FILE = None
COMMANDS_FILE = None
BACKUP_DIR = None


def init(root_path: str):
    """由 main.py 调用，传入项目根目录绝对路径。"""
    global PROJECT_ROOT, DATE_DIR, LOG_DIR
    global CONVERSATIONS_DIR, PROMPT_DIR, PROMPT_FILE
    global CONFIG_FILE, ENV_FILE, COMMANDS_FILE

    if PROJECT_ROOT is not None:
        return

    globals().update(compute(root_path))

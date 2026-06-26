import logging
import os
from datetime import datetime
from modules import bootstrap as app_paths

_dpc_initialized = False


def _init_date_dpc():
    global _dpc_initialized
    if _dpc_initialized:
        return
    _dpc_initialized = True
    try:
        from modules.chater import dpc_manager
        dpc_manager.ensure_restriction(app_paths.DATE_DIR, ["*"])
    except Exception as e:
        logging.getLogger("Dolphin.logger").error(f"DPC 初始化失败: {e}")


def setup_logger(name="Dolphin", level=logging.DEBUG):
    if not os.path.exists(app_paths.LOG_DIR):
        os.makedirs(app_paths.LOG_DIR)

    _init_date_dpc()

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    log_filename = datetime.now().strftime("%Y-%m-%d") + ".log"
    log_filepath = os.path.join(app_paths.LOG_DIR, log_filename)

    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setLevel(level)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger


_thinking_logger = None

def get_thinking_logger():
    """获取思考过程专用日志 Logger"""
    global _thinking_logger
    if _thinking_logger is None:
        if not os.path.exists(app_paths.LOG_DIR):
            os.makedirs(app_paths.LOG_DIR)

        _thinking_logger = logging.getLogger("Dolphin.thinking")
        _thinking_logger.setLevel(logging.DEBUG)

        think_filename = "think_" + datetime.now().strftime("%Y-%m-%d") + ".log"
        think_filepath = os.path.join(app_paths.LOG_DIR, think_filename)

        think_handler = logging.FileHandler(think_filepath, encoding='utf-8')
        think_handler.setLevel(logging.DEBUG)
        think_handler.setFormatter(logging.Formatter('[%(asctime)s] 思考过程:\n%(message)s'))

        _thinking_logger.addHandler(think_handler)

    return _thinking_logger

def get_logger(name="QuickAI"):
    return logging.getLogger(name)


def log_thinking(content: str):
    """记录思考过程到专用日志文件"""
    if not content:
        return
    logger = get_thinking_logger()
    logger.debug(content)

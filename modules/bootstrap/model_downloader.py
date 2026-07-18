"""
嵌入模型下载与管理模块。
负责检查、下载、验证 bge-small-zh-v1.5 模型到本地 models/ 目录。
由 main.py 在启动流程中调用。
"""
import os

from modules import bootstrap as app_paths
from modules.logger import get_logger

log = get_logger("Dolphin.model_downloader")

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
MODEL_DIR_NAME = "bge-small-zh-v1.5"
HF_MIRROR = "https://hf-mirror.com"


def get_model_dir() -> str:
    """返回模型存放的本地绝对路径。"""
    return os.path.join(app_paths.PROJECT_ROOT, "models", MODEL_DIR_NAME)


def is_model_downloaded() -> bool:
    """检查模型是否已下载完成（通过 config 标记 + 文件存在性双重验证）。"""
    from modules.main_server import config
    cfg = config.load_config()
    if not cfg.get("embedding_model_downloaded", False):
        return False

    model_dir = get_model_dir()
    if not os.path.isdir(model_dir):
        return False

    # 如果 ONNX 已转换且 ONNX 文件确实存在，不检查原始权重文件
    if cfg.get("onnx_converted", False):
        onnx_path = os.path.join(app_paths.MODELS_DIR, "onnx", MODEL_DIR_NAME, "model.onnx")
        return os.path.isfile(onnx_path)

    safetensors = os.path.join(model_dir, "model.safetensors")
    if not os.path.isfile(safetensors):
        return False

    return True


def _mark_downloaded(success: bool):
    """通过 config.py 记录模型下载状态。"""
    try:
        from modules.main_server import config
        cfg = config.load_config()
        cfg["embedding_model_downloaded"] = success
        config.save_config(cfg)
        log.info(f"模型下载状态已记录: {success}")
    except Exception as e:
        log.warning(f"记录模型下载状态失败: {e}")


def download_model(progress_callback=None) -> bool:
    """
    下载嵌入模型到本地 models/ 目录。

    Args:
        progress_callback: 可选的回调函数，接收 (progress: float, description: str)。
            progress 范围 0.0 ~ 1.0。

    Returns:
        True 表示下载成功，False 表示失败。
    """
    if is_model_downloaded():
        log.info("模型已存在，跳过下载")
        return True

    model_dir = get_model_dir()

    try:
        os.environ["HF_ENDPOINT"] = HF_MIRROR
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

        if progress_callback:
            progress_callback(0.1, "正在加载下载工具...")

        from huggingface_hub import snapshot_download

        if progress_callback:
            progress_callback(0.2, "正在下载嵌入模型...")

        from huggingface_hub import hf_hub_download, list_repo_files

        # 获取所有文件列表
        files = list_repo_files(MODEL_NAME)
        total = len(files)

        os.makedirs(model_dir, exist_ok=True)

        for i, filename in enumerate(files):
            hf_hub_download(
                repo_id=MODEL_NAME,
                filename=filename,
                local_dir=model_dir,
            )
            if progress_callback:
                ratio = 0.2 + 0.7 * ((i + 1) / total)
                progress_callback(ratio, f"正在下载嵌入模型... ({i + 1}/{total})")

        log.info(f"完成下载 {MODEL_NAME} 所有 {total} 个文件")

        if progress_callback:
            progress_callback(0.95, "正在验证模型文件...")

        # 验证关键文件
        safetensors = os.path.join(model_dir, "model.safetensors")
        if not os.path.isfile(safetensors):
            raise FileNotFoundError("model.safetensors 不存在，下载可能不完整")

        _mark_downloaded(True)

        if progress_callback:
            progress_callback(1.0, "嵌入模型下载完成")

        log.info(f"嵌入模型下载成功: {model_dir}")
        return True

    except Exception as e:
        log.error(f"嵌入模型下载失败: {e}")

        # 清理不完整的下载
        if os.path.isdir(model_dir):
            try:
                import shutil
                shutil.rmtree(model_dir)
                log.info("已清理不完整的模型文件")
            except Exception:
                pass

        _mark_downloaded(False)

        if progress_callback:
            progress_callback(1.0, "嵌入模型下载失败")

        return False

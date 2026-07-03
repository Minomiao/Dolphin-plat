"""
ONNX 模型转换模块。
负责将 bge-small-zh-v1.5 从 safetensors 转换为 ONNX 格式，
由 main.py 在启动流程中于模型下载完成后调用。
"""
import os
import warnings

from modules import bootstrap as app_paths
from modules.logger import get_logger

log = get_logger("Dolphin.onnx_converter")

MODEL_DIR_NAME = "bge-small-zh-v1.5"
ONNX_DIR_NAME = "onnx"
ONNX_FILENAME = "model.onnx"


def _get_model_dir() -> str:
    """返回原始模型存放的本地绝对路径。"""
    return os.path.join(app_paths.MODELS_DIR, MODEL_DIR_NAME)


def _get_onnx_dir() -> str:
    """返回 ONNX 模型存放的本地绝对路径。"""
    return os.path.join(app_paths.MODELS_DIR, ONNX_DIR_NAME, MODEL_DIR_NAME)


def _get_onnx_path() -> str:
    """返回 ONNX 模型文件路径。"""
    return os.path.join(_get_onnx_dir(), ONNX_FILENAME)


def is_onnx_converted() -> bool:
    """检查 ONNX 模型是否已转换（config 标记 + 文件存在性双重验证）。"""
    from modules.main_server import config
    try:
        if not config.load_config().get("onnx_converted", False):
            return False
    except Exception:
        return False

    # 二次验证：ONNX 文件是否存在
    onnx_path = _get_onnx_path()
    if not os.path.isfile(onnx_path):
        return False

    return True


def _mark_converted(success: bool):
    """通过 config.py 记录 ONNX 转换状态。"""
    try:
        from modules.main_server import config
        cfg = config.load_config()
        cfg["onnx_converted"] = success
        config.save_config(cfg)
        log.info(f"ONNX 转换状态已记录: {success}")
    except Exception as e:
        log.warning(f"记录 ONNX 转换状态失败: {e}")


def _cleanup_original_weights(model_dir: str):
    """转换成功后删除原始权重文件，节省磁盘空间。"""
    removed = []
    for filename in ("model.safetensors", "pytorch_model.bin"):
        filepath = os.path.join(model_dir, filename)
        if os.path.isfile(filepath):
            try:
                os.remove(filepath)
                removed.append(filename)
            except Exception as e:
                log.warning(f"删除 {filename} 失败: {e}")

    if removed:
        log.info(f"已清理原始权重文件: {', '.join(removed)}")


def convert_to_onnx(progress_callback=None) -> bool:
    """
    将嵌入模型从 safetensors 转换为 ONNX 格式。

    Args:
        progress_callback: 可选的回调函数，接收 (progress: float, description: str)。
            progress 范围 0.0 ~ 1.0。

    Returns:
        True 表示转换成功，False 表示失败。
    """
    if is_onnx_converted():
        log.info("ONNX 模型已存在，跳过转换")
        return True

    model_dir = _get_model_dir()
    onnx_dir = _get_onnx_dir()
    onnx_path = _get_onnx_path()

    try:
        if progress_callback:
            progress_callback(0.1, "正在加载模型...")

        # 抑制 transformers / torch 的警告输出
        os.environ.setdefault("TQDM_DISABLE", "1")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

        import torch
        import torch.nn as nn
        from sentence_transformers import SentenceTransformer
        from transformers import AutoTokenizer

        # 加载模型
        model = SentenceTransformer(model_dir)
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        bert = model._first_module().auto_model

        if progress_callback:
            progress_callback(0.2, "正在导出 ONNX...")

        os.makedirs(onnx_dir, exist_ok=True)

        # 包装 BertModel，仅输出 last_hidden_state
        class BertONNXWrapper(nn.Module):
            def __init__(self, bert_model):
                super().__init__()
                self.bert = bert_model

            def forward(self, input_ids, attention_mask):
                outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
                return outputs.last_hidden_state

        wrapper = BertONNXWrapper(bert)
        wrapper.eval()

        # 构造导出用的示例输入
        texts = ["test sentence for export"]
        encoded = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")

        # 抑制导出过程中的所有警告
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            torch.onnx.export(
                wrapper,
                (encoded['input_ids'], encoded['attention_mask']),
                onnx_path,
                input_names=['input_ids', 'attention_mask'],
                output_names=['last_hidden_state'],
                dynamic_axes={
                    'input_ids': {0: 'batch', 1: 'sequence'},
                    'attention_mask': {0: 'batch', 1: 'sequence'},
                    'last_hidden_state': {0: 'batch', 1: 'sequence'},
                },
                opset_version=14,
                dynamo=False,
            )

        size_mb = os.path.getsize(onnx_path) / 1024 / 1024
        log.info(f"ONNX 导出完成，文件大小: {size_mb:.1f}MB")

        if progress_callback:
            progress_callback(0.8, "导出完成，正在清理...")

        # 转换成功，清理原始权重
        _cleanup_original_weights(model_dir)

        _mark_converted(True)

        if progress_callback:
            progress_callback(1.0, "ONNX 转换完成")

        return True

    except Exception as e:
        log.error(f"ONNX 转换失败: {e}")

        # 清理不完整的 ONNX 文件
        if os.path.isfile(onnx_path):
            try:
                os.remove(onnx_path)
                log.info("已清理不完整的 ONNX 文件")
            except Exception:
                pass

        _mark_converted(False)

        if progress_callback:
            progress_callback(1.0, "ONNX 转换失败")

        return False

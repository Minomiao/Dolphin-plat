"""
嵌入模型管理模块。
封装 bge-small-zh-v1.5 的加载和编码。
优先使用 ONNX Runtime，回退到 SentenceTransformer (torch)。
仅负责向量化。
路径通过 bootstrap paths 获取。
"""
import os
import threading
from typing import List, Dict, Any, Optional

# 抑制 sentence-transformers / transformers 的 tqdm 输出
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

from modules import bootstrap as app_paths
from modules.logger import get_logger

log = get_logger("Dolphin.embedding")

MODEL_DIR_NAME = "bge-small-zh-v1.5"
ONNX_DIR_NAME = "onnx"
ONNX_FILENAME = "model.onnx"


def _is_onnx_available() -> bool:
    """检查 ONNX 模型是否就绪。"""
    from modules.main_server import config
    cfg = config.load_config()
    if not cfg.get("onnx_converted", False):
        return False
    onnx_path = os.path.join(app_paths.MODELS_DIR, ONNX_DIR_NAME, MODEL_DIR_NAME, ONNX_FILENAME)
    return os.path.isfile(onnx_path)


class EmbeddingModel:
    """嵌入模型单例，懒加载 + 线程安全，ONNX 优先。"""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._model = None       # SentenceTransformer (torch 回退)
        self._session = None     # onnxruntime.InferenceSession
        self._tokenizer = None   # transformers.AutoTokenizer
        self._use_onnx = False
        self._ready = False

    @classmethod
    def get_instance(cls) -> "EmbeddingModel":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_ready(self) -> bool:
        """模型是否已成功加载。"""
        return self._ready

    def _ensure_loaded(self) -> bool:
        """确保模型已加载，返回是否成功。ONNX 优先。"""
        if self._ready:
            return True

        if _is_onnx_available():
            return self._load_onnx()
        else:
            return self._load_torch()

    def _load_onnx(self) -> bool:
        """加载 ONNX Runtime 模型。"""
        onnx_path = os.path.join(app_paths.MODELS_DIR, ONNX_DIR_NAME, MODEL_DIR_NAME, ONNX_FILENAME)
        model_dir = os.path.join(app_paths.MODELS_DIR, MODEL_DIR_NAME)

        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer

            self._session = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider'])
            self._tokenizer = AutoTokenizer.from_pretrained(model_dir)
            self._use_onnx = True
            self._ready = True
            log.info("ONNX 模型加载完成")
            return True
        except Exception as e:
            log.warning(f"ONNX 加载失败: {e}，回退 torch")
            return self._load_torch()

    def _load_torch(self) -> bool:
        """加载 SentenceTransformer (torch) 模型。"""
        model_dir = os.path.join(app_paths.MODELS_DIR, MODEL_DIR_NAME)
        if not os.path.isdir(model_dir):
            log.warning(f"模型目录不存在: {model_dir}")
            return False

        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_dir)
            self._use_onnx = False
            self._ready = True
            log.info("torch 模型加载完成")
            return True
        except Exception as e:
            log.error(f"模型加载失败: {e}")
            return False

    def encode(self, texts: List[str]):
        """
        将文本编码为向量。

        Args:
            texts: 文本列表

        Returns:
            numpy array, shape (n, 512)，L2 归一化。模型不可用时返回 None。
        """
        if not self._ensure_loaded():
            log.warning("嵌入模型不可用，encode 返回 None")
            return None

        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return None

        if self._use_onnx:
            import numpy as np
            encoded = self._tokenizer(texts, padding=True, truncation=True, return_tensors="np")
            outputs = self._session.run(
                None,
                {'input_ids': encoded['input_ids'], 'attention_mask': encoded['attention_mask']}
            )
            last_hidden = outputs[0]          # [batch, seq_len, 512]
            cls_emb = last_hidden[:, 0, :]     # [batch, 512]
            norm = np.linalg.norm(cls_emb, axis=1, keepdims=True)
            return cls_emb / np.maximum(norm, 1e-9)
        else:
            import numpy as np
            embs = self._model.encode(texts, normalize_embeddings=True)
            return np.array(embs)

"""
Phase 1 — Embedding 模型（单例，预加载）
"""
from sentence_transformers import SentenceTransformer
import numpy as np

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from . import config
        print(f"📥 首次加载 Embedding 模型: {config.EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
        dim = _embedding_model.get_sentence_embedding_dimension()
        print(f"✅ 模型加载完成，向量维度: {dim}")
    return _embedding_model


def encode_texts(texts: list[str], normalize: bool = True) -> np.ndarray:
    model = get_embedding_model()
    return model.encode(texts, normalize_embeddings=normalize, show_progress_bar=False)

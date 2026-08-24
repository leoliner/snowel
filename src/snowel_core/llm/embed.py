# src/snowel_core/llm/embed.py
import hashlib
import sqlite3

from ..storage import config


class EmbeddingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def name(self) -> str: ...
    dim: int = 0


class DeterministicEmbed(EmbeddingProvider):
    """零依赖确定性嵌入（默认）：sha256 派生定长向量，测试与离线兜底。"""
    dim = 64

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def name(self) -> str:
        return "deterministic-hash-64"

    @staticmethod
    def _vec(text: str) -> list[float]:
        out: list[float] = []
        seed = text.encode("utf-8")
        while len(out) < DeterministicEmbed.dim:
            seed = hashlib.sha256(seed).digest()
            out.extend(b / 255.0 for b in seed)
        return out[:DeterministicEmbed.dim]


def get_provider(conn: sqlite3.Connection) -> EmbeddingProvider:
    kind = config.get(conn, "embedding.provider", "deterministic")
    if kind == "deterministic":
        return DeterministicEmbed()
    if kind == "fastembed":
        try:
            from fastembed import TextEmbedding  # extras: snowel-core[embed]
        except ImportError as e:
            raise ImportError(
                "embedding.provider=fastembed 需要 pip install snowel-core[embed]"
            ) from e

        class FastembedProvider(EmbeddingProvider):
            dim = 512  # bge-small-zh-v1.5

            def __init__(self):
                self._m = TextEmbedding("BAAI/bge-small-zh-v1.5")

            def embed(self, texts):
                return [list(map(float, v)) for v in self._m.embed(texts)]

            def name(self):
                return "fastembed:bge-small-zh-v1.5"

        return FastembedProvider()
    raise ValueError(f"未知 embedding.provider：{kind}")

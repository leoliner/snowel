# src/snowel_core/llm/backend.py
import sqlite3

from ..storage import config


class GenerationBackend:
    def generate(self, prompt: str, *, model: str | None = None,
                 system: str | None = None) -> str: ...


class LitellmBackend(GenerationBackend):
    """litellm 适配（铁律 2：LLM 调用唯一实现处之一）。惰性 import 供无网测试。"""

    def __init__(self, default_model: str = "gpt-4o-mini"):
        self.default_model = default_model

    @classmethod
    def for_conn(cls, conn: sqlite3.Connection) -> "LitellmBackend":
        return cls(config.get(conn, "llm.model", "gpt-4o-mini"))

    def generate(self, prompt: str, *, model: str | None = None,
                 system: str | None = None) -> str:
        import litellm
        resp = litellm.completion(
            model=model or self.default_model,
            messages=[*([{"role": "system", "content": system}] if system else []),
                      {"role": "user", "content": prompt}])
        return resp["choices"][0]["message"]["content"]

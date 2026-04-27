"""
LLM inference client for Nexus.
Connects to a local llama.cpp server via HTTP.
Model-agnostic — works with any model served by llama.cpp, Ollama, or compatible API.
"""
import re
import json
import urllib.request
from typing import Any


class LLMClient:
    def __init__(self, base_url: str = "http://localhost:8384"):
        self._base_url = base_url.rstrip("/")

    def format_prompt(self, system: str, user: str, history: list[dict[str, str]] | None = None) -> str:
        parts = [f"<|im_start|>system\n{system}<|im_end|>"]
        for msg in history or []:
            role = msg["role"]
            content = msg["content"]
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        parts.append(f"<|im_start|>user\n{user}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)

    @staticmethod
    def parse_response(raw: str) -> str:
        cleaned = re.sub(r"<\|[^>]+\|>", "", raw)
        return cleaned.strip()

    async def infer(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> str:
        payload = json.dumps({
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": ["<|im_end|>", "<|end|>"],
        }).encode()
        req = urllib.request.Request(
            f"{self._base_url}/completion",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                return self.parse_response(data.get("content", ""))
        except Exception as e:
            return f"[Inference error: {e}]"

    async def chat(self, system: str, user: str, history: list[dict[str, str]] | None = None,
                   max_tokens: int = 1024, temperature: float = 0.7) -> str:
        prompt = self.format_prompt(system, user, history)
        return await self.infer(prompt, max_tokens, temperature)

    def health(self) -> bool:
        try:
            req = urllib.request.Request(f"{self._base_url}/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

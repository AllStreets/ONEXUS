"""
LocalProvider — inference via a local llama.cpp-compatible HTTP server.
Converts OpenAI-style messages to ChatML format for the /completion endpoint.
"""
import re
import json
import urllib.request
from nexus.inference.provider import InferenceProvider


class LocalProvider(InferenceProvider):
    name = "local"

    def __init__(self, base_url: str = "http://localhost:8384"):
        self._base_url = base_url.rstrip("/")

    def _messages_to_chatml(self, messages: list[dict]) -> str:
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)

    @staticmethod
    def _parse_response(raw: str) -> str:
        cleaned = re.sub(r"<\|[^>]+\|>", "", raw)
        return cleaned.strip()

    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        prompt = self._messages_to_chatml(messages)
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
                return self._parse_response(data.get("content", ""))
        except Exception as e:
            return f"[Inference error: {e}]"

    async def health(self) -> bool:
        try:
            req = urllib.request.Request(f"{self._base_url}/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

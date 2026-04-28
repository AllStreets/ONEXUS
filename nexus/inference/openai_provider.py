"""
OpenAIProvider — inference via the OpenAI API.
Uses the openai Python SDK. Messages format is native (no conversion needed).
"""
from openai import OpenAI
from nexus.inference.provider import InferenceProvider


class OpenAIProvider(InferenceProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._client = OpenAI(api_key=api_key)
        self._model = model

    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[Inference error: {e}]"

    async def health(self) -> bool:
        try:
            self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False

"""
OpenAIProvider — inference via the OpenAI API.
Uses the openai Python SDK. Messages format is native (no conversion needed).
"""
from openai import OpenAI
from nexus.inference.provider import InferenceProvider


class OpenAIProvider(InferenceProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._api_key = api_key
        self._client = OpenAI(api_key=api_key)
        self._model = model

    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        try:
            kwargs: dict = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
            }
            # Newer OpenAI models (o1, o3, gpt-4.1) require max_completion_tokens
            # instead of max_tokens. Try the new param first, fall back to legacy.
            try:
                kwargs["max_completion_tokens"] = max_tokens
                response = self._client.chat.completions.create(**kwargs)
            except Exception:
                del kwargs["max_completion_tokens"]
                kwargs["max_tokens"] = max_tokens
                response = self._client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            return f"[Inference error: {e}]"

    async def health(self) -> bool:
        try:
            # List models is free and confirms the API key works
            self._client.models.list()
            return True
        except Exception:
            return False

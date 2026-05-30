"""
AnthropicProvider — inference via the Anthropic (Claude) API.
Uses the anthropic Python SDK. Separates system message from user messages
per Anthropic's API contract.
"""
from anthropic import Anthropic
from nexus.inference.provider import InferenceProvider


class AnthropicProvider(InferenceProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._api_key = api_key
        self._client = Anthropic(api_key=api_key)
        self._model = model

    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        try:
            system_msg = None
            non_system = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    non_system.append(msg)

            kwargs: dict = {
                "model": self._model,
                "messages": non_system,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if system_msg:
                kwargs["system"] = system_msg

            response = self._client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            return f"[Inference error: {e}]"

    async def health(self) -> bool:
        try:
            # Count tokens is free and confirms the API key works
            self._client.messages.count_tokens(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            try:
                # Fallback: minimal completion if count_tokens unavailable
                self._client.messages.create(
                    model=self._model,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                )
                return True
            except Exception:
                return False

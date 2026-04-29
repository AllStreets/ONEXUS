"""
LLM inference client for Nexus.
Delegates to a ProviderRouter for multi-provider support.
Backward-compatible: accepts base_url for local-only setups.
"""
from nexus.inference.provider import InferenceProvider
from nexus.inference.router import ProviderRouter
from nexus.inference.local import LocalProvider


class LLMClient:
    def __init__(
        self,
        router: ProviderRouter | None = None,
        base_url: str = "http://localhost:8384",
    ):
        if router is not None:
            self._router = router
        else:
            self._router = ProviderRouter(default="local")
            self._router.register(LocalProvider(base_url=base_url))

    async def infer(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        provider: str | None = None,
    ) -> str:
        """Infer from a raw prompt string. Wraps in a user message for the router."""
        messages = [{"role": "user", "content": prompt}]
        return await self._router.infer(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            provider=provider,
        )

    async def chat(
        self,
        system: str,
        user: str,
        history: list[dict[str, str]] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        provider: str | None = None,
    ) -> str:
        """Build a messages list from system/user/history and route."""
        messages: list[dict] = [{"role": "system", "content": system}]
        for msg in history or []:
            messages.append(msg)
        messages.append({"role": "user", "content": user})
        return await self._router.infer(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            provider=provider,
        )

    async def health(self) -> bool:
        """Health check — checks if the default local provider is up."""
        local = self._router.providers.get("local")
        if local and isinstance(local, LocalProvider):
            return await local.health()
        return True

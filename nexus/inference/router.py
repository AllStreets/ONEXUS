"""
ProviderRouter — selects and delegates to a named InferenceProvider.
Supports per-request provider selection with fallback to the default.
"""
from nexus.inference.provider import InferenceProvider, ProviderUnavailable


class ProviderRouter:
    def __init__(self, default: str = "local"):
        self._default = default
        self._providers: dict[str, InferenceProvider] = {}

    @property
    def providers(self) -> dict[str, InferenceProvider]:
        return dict(self._providers)

    def register(self, provider: InferenceProvider) -> None:
        self._providers[provider.name] = provider

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    async def infer(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        provider: str | None = None,
    ) -> str:
        target_name = provider or self._default

        target = self._providers.get(target_name)
        if target is None:
            raise ProviderUnavailable(target_name)

        if await target.health():
            return await target.infer(messages, max_tokens=max_tokens, temperature=temperature)

        if target_name != self._default:
            fallback = self._providers.get(self._default)
            if fallback and await fallback.health():
                return await fallback.infer(messages, max_tokens=max_tokens, temperature=temperature)

        raise ProviderUnavailable(target_name)

    async def health(self) -> dict[str, bool]:
        return {name: await p.health() for name, p in self._providers.items()}

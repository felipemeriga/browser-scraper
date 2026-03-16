from browser_agent.providers.base import BaseProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> BaseProvider | None:
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def validate(self, provider: str, action: str) -> bool:
        p = self.get(provider)
        if p is None:
            return False
        return action in p.actions


registry = ProviderRegistry()

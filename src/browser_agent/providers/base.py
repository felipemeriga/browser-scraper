from abc import ABC, abstractmethod

from pydantic import BaseModel

from browser_agent.jobs.models import ProviderResult


class BaseProvider(ABC):
    name: str
    actions: list[str]

    @abstractmethod
    async def execute(
        self, action: str, params: BaseModel | None = None
    ) -> ProviderResult:
        """Run browser_use agent to perform the provider-specific task."""
        ...

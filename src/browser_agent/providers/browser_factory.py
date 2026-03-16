from pathlib import Path

from browser_use import Browser, ChatOpenAI

from browser_agent.config import settings


def create_browser(downloads_path: Path | None = None) -> Browser:
    return Browser(
        headless=settings.browser_headless,
        downloads_path=str(downloads_path) if downloads_path else None,
    )


def create_llm() -> ChatOpenAI:
    return ChatOpenAI(model=settings.llm_model)

from pydantic import BaseModel

from browser_agent.config import settings
from browser_agent.jobs.models import ProviderResult
from browser_agent.providers.base import BaseProvider
from browser_agent.providers.browser_factory import create_browser, create_llm


class ClaroProvider(BaseProvider):
    name = "claro"
    actions = ["fetch-bill"]

    async def execute(
        self, action: str, params: BaseModel | None = None
    ) -> ProviderResult:
        from browser_use import Agent

        downloads_path = settings.downloads_dir / "claro"
        downloads_path.mkdir(parents=True, exist_ok=True)

        browser = create_browser(downloads_path)
        try:
            agent = Agent(
                task=(
                    f"Go to the Claro website (https://www.claro.com.br/). "
                    f"Log in with username '{settings.claro_username}' "
                    f"and password '{settings.claro_password}'. "
                    f"Navigate to the bills/invoices section (Minha Claro). "
                    f"Find and download the most recent phone bill as PDF. "
                    f"After downloading, extract the bill amount and due date. "
                    f"Return the amount and due date as the final result."
                ),
                llm=create_llm(),
                browser=browser,
            )
            history = await agent.run(max_steps=30)

            result_text = history.final_result() or ""
            downloaded_files = list(downloads_path.glob("*.pdf"))
            file_path = str(downloaded_files[-1]) if downloaded_files else None

            return ProviderResult(
                status="success" if history.is_successful() else "failure",
                file_path=file_path,
                extracted_data={"raw_result": result_text},
                error=None if history.is_successful() else result_text,
            )
        finally:
            await browser.close()

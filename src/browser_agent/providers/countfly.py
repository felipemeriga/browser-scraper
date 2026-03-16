from pydantic import BaseModel

from browser_agent.api.schemas import EmitInvoiceParams
from browser_agent.config import settings
from browser_agent.jobs.models import ProviderResult
from browser_agent.providers.base import BaseProvider
from browser_agent.providers.browser_factory import create_browser, create_llm


class CountflyProvider(BaseProvider):
    name = "countfly"
    actions = ["emit-invoice"]

    async def execute(
        self, action: str, params: BaseModel | None = None
    ) -> ProviderResult:
        from browser_use import Agent

        if not isinstance(params, EmitInvoiceParams):
            return ProviderResult(
                status="failure",
                error="emit-invoice requires amount and description",
            )

        downloads_path = settings.downloads_dir / "countfly"
        downloads_path.mkdir(parents=True, exist_ok=True)

        browser = create_browser(downloads_path)
        try:
            agent = Agent(
                task=(
                    f"Go to Countfly (https://app.countfly.com/dashboard). "
                    f"Log in with username '{settings.countfly_username}' "
                    f"and password '{settings.countfly_password}'. "
                    f"Navigate to the invoice emission section. "
                    f"Create a new invoice with amount R$ {params.amount:.2f} "
                    f"and description '{params.description}'. "
                    f"Confirm and emit the invoice. "
                    f"Download the invoice receipt if available. "
                    f"Return confirmation details as the final result."
                ),
                llm=create_llm(),
                browser=browser,
                use_vision=settings.use_vision,
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

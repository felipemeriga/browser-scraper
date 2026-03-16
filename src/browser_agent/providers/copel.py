from pydantic import BaseModel

from browser_agent.api.schemas import FetchBillParams
from browser_agent.config import settings
from browser_agent.jobs.models import ProviderResult
from browser_agent.providers.base import BaseProvider
from browser_agent.providers.browser_factory import create_browser, create_llm


class CopelProvider(BaseProvider):
    name = "copel"
    actions = ["fetch-bill"]

    async def execute(
        self, action: str, params: BaseModel | None = None
    ) -> ProviderResult:
        from browser_use import Agent

        if not isinstance(params, FetchBillParams):
            return ProviderResult(
                status="failure",
                error="fetch-bill requires reference_month (MM/YYYY)",
            )

        downloads_path = settings.downloads_dir / "copel"
        downloads_path.mkdir(parents=True, exist_ok=True)

        browser = create_browser(downloads_path)
        try:
            agent = Agent(
                task=(
                    "Go to the Copel login page at "
                    "https://www.copel.com/avaweb/paginaLogin/login.jsf. "
                    f"Log in with username '{settings.copel_username}' "
                    f"and password '{settings.copel_password}'. "
                    "After logging in, navigate to the "
                    "'Segunda Via Online' option. "
                    "In the reference month field, enter "
                    f"'{params.reference_month}' (MM/YYYY format). "
                    "Submit the search. "
                    "In the results, find and click the '2 via' link. "
                    "A dialog will open with the bill details and "
                    "an orange button 'Fazer download da 2ª via'. "
                    "IMPORTANT: Do NOT click outside the dialog or "
                    "navigate away. If a popup appears asking "
                    "'Deseja realmente sair do aplicativo?', "
                    "click 'Não' to dismiss it and try again. "
                    "To download, use JavaScript to click the "
                    "download button directly — find the button "
                    "element and use element.click() via the "
                    "browser console if a normal click does not "
                    "trigger the download. "
                    "A loading indicator will appear — wait for it "
                    "to finish and the PDF file to be downloaded. "
                    "After the download completes, extract the bill "
                    "amount and due date from the page. "
                    "Return the amount and due date as the final "
                    "result."
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

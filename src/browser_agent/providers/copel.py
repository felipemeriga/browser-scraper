from pydantic import BaseModel

from browser_agent.api.schemas import FetchBillParams
from browser_agent.config import settings
from browser_agent.jobs.models import ProviderResult
from browser_agent.providers.base import BaseProvider


class CopelProvider(BaseProvider):
    name = "copel"
    actions = ["fetch-bill"]

    async def execute(
        self, action: str, params: BaseModel | None = None
    ) -> ProviderResult:
        from playwright.async_api import async_playwright

        if not isinstance(params, FetchBillParams):
            return ProviderResult(
                status="failure",
                error="fetch-bill requires reference_month (MM/YYYY)",
            )

        downloads_path = settings.downloads_dir / "copel"
        downloads_path.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.browser_headless)
            context = await browser.new_context(
                accept_downloads=True,
            )
            page = await context.new_page()

            try:
                # Step 1: Navigate to login page
                await page.goto(
                    "https://www.copel.com/avaweb/paginaLogin/login.jsf",
                    wait_until="networkidle",
                )

                # Step 2: Login
                await page.get_by_placeholder("CNPJ ou CPF").fill(
                    settings.copel_username
                )
                await page.get_by_placeholder("Senha").fill(settings.copel_password)
                await page.get_by_text("Entrar").click()
                await page.wait_for_load_state("networkidle")

                # Step 3: Click "Segunda via online" icon/link
                segunda_via = page.get_by_text("Segunda via online", exact=False)
                await segunda_via.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)

                # Step 4: Enter reference month
                month_input = (
                    page.locator("input")
                    .filter(has_text="")
                    .locator('[placeholder*="MM"], [name*="mes"], [id*="mes"]')
                )
                if await month_input.count() == 0:
                    # Fallback: find any visible text input
                    month_input = page.locator('input[type="text"]').first
                await month_input.fill(params.reference_month)

                # Step 5: Submit search
                submit_btn = page.locator(
                    'button:has-text("Pesquisar"), '
                    'button:has-text("Buscar"), '
                    'input[type="submit"]'
                )
                await submit_btn.click()
                await page.wait_for_load_state("networkidle")

                # Step 6: Click "2 via" link
                segunda_via_link = page.get_by_text("2 via").first
                await segunda_via_link.click()
                await page.wait_for_timeout(2000)

                # Step 7: Click the orange download button in dialog
                download_btn = page.get_by_text("Fazer download da 2ª via")
                async with page.expect_download(timeout=60000) as download_info:
                    await download_btn.click()

                # Step 8: Save the downloaded file
                download = await download_info.value
                file_name = download.suggested_filename or (
                    f"copel_{params.reference_month.replace('/', '-')}.pdf"
                )
                file_path = str(downloads_path / file_name)
                await download.save_as(file_path)

                # Step 9: Extract bill info from the page
                amount_text = ""
                due_date_text = ""
                try:
                    valor = page.locator(
                        "text=/Valor.*R\\$/, text=/R\\$\\s*[\\d,.]/"
                    ).first
                    amount_text = await valor.text_content() or ""
                except Exception:
                    pass
                try:
                    vencimento = page.locator("text=/Vencimento/").first
                    due_date_text = await vencimento.text_content() or ""
                except Exception:
                    pass

                return ProviderResult(
                    status="success",
                    file_path=file_path,
                    extracted_data={
                        "amount": amount_text.strip(),
                        "due_date": due_date_text.strip(),
                        "reference_month": params.reference_month,
                    },
                )

            except Exception as e:
                return ProviderResult(
                    status="failure",
                    error=str(e),
                )
            finally:
                await context.close()
                await browser.close()

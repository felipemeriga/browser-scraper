import re

from pydantic import BaseModel

from browser_agent.api.schemas import ClaroFetchBillParams
from browser_agent.config import settings
from browser_agent.jobs.models import ProviderResult
from browser_agent.providers.base import BaseProvider

MONTH_NAMES = {
    "01": "Janeiro",
    "02": "Fevereiro",
    "03": "Março",
    "04": "Abril",
    "05": "Maio",
    "06": "Junho",
    "07": "Julho",
    "08": "Agosto",
    "09": "Setembro",
    "10": "Outubro",
    "11": "Novembro",
    "12": "Dezembro",
}


class ClaroProvider(BaseProvider):
    name = "claro"
    actions = ["fetch-bill"]

    async def execute(
        self, action: str, params: BaseModel | None = None
    ) -> ProviderResult:
        from playwright.async_api import async_playwright

        if not isinstance(params, ClaroFetchBillParams):
            return ProviderResult(
                status="failure",
                error=(
                    "fetch-bill requires reference_month (MM/YYYY) "
                    "and optional product_type (movel|residencial)"
                ),
            )

        downloads_path = settings.downloads_dir / "claro"
        downloads_path.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.browser_headless)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            try:
                # Step 1: Navigate to login page
                await page.goto(
                    "https://minhaclaro.claro.com.br/acesso-rapido/",
                    wait_until="networkidle",
                )

                # Step 2: Click "Entrar" button to open login form
                await page.get_by_text("Entrar").first.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)

                # Step 3: Fill CPF (label-based input, not placeholder)
                cpf_input = page.get_by_label("CPF, celular ou outro dado")
                await cpf_input.fill(settings.claro_username)

                # Step 4: Click "Continuar"
                await page.locator(
                    "button.mdn-Button--primary:has-text('Continuar')"
                ).click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)

                # Step 5: Fill password (label-based input)
                await page.get_by_label("Senha").fill(settings.claro_password)

                # Step 6: Click "Entrar" to login (button starts disabled, wait for it)
                entrar_btn = page.locator(
                    "button.mdn-Button--primary:has-text('Entrar')"
                )
                await entrar_btn.wait_for(state="attached", timeout=10000)
                await page.wait_for_function(
                    "() => !document.querySelector("
                    '"button.mdn-Button--primary").disabled',
                    timeout=10000,
                )
                await entrar_btn.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(3000)

                # Step 7: Select product (movel or residencial)
                if params.product_type == "movel":
                    product_link = page.locator('a[href*="area-logada/movel"]').first
                else:
                    product_link = page.locator(
                        'a[href*="area-logada/residencial"]'
                    ).first
                await product_link.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(3000)

                # Step 8: Click "Ver faturas"
                await page.get_by_text("Ver faturas").first.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)

                # Step 9: Select the month tab
                month_num = params.reference_month[:2]
                year = params.reference_month[3:]
                month_name = MONTH_NAMES.get(month_num, "")
                tab_text = f"{month_name} {year}"

                month_tab = page.locator(
                    f"div.tab-item p.tab-item-date:has-text('{tab_text}')"
                ).first
                await month_tab.click()
                await page.wait_for_timeout(2000)

                # Step 10: Extract bill info
                amount_text = ""
                due_date_text = ""
                try:
                    amount_el = page.locator("text=/R\\$\\s*[\\d.,]+/").first
                    amount_text = await amount_el.text_content() or ""
                except Exception:
                    pass
                try:
                    due_el = page.locator("text=/Vencimento/").first
                    due_date_text = await due_el.text_content() or ""
                except Exception:
                    pass

                # Step 11: Click "Segunda via da fatura" to download
                segunda_via = page.get_by_text("Segunda via da fatura").first
                async with page.expect_download(timeout=60000) as download_info:
                    await segunda_via.click()

                # Step 12: Save the downloaded file
                download = await download_info.value
                due_date_clean = (
                    re.sub(
                        r"[^\d]",
                        "-",
                        re.search(r"\d{2}/\d{2}/\d{4}", due_date_text).group(),
                    )
                    if re.search(r"\d{2}/\d{2}/\d{4}", due_date_text)
                    else params.reference_month.replace("/", "-")
                )

                product = params.product_type
                file_name = f"claro_{product}_venc_{due_date_clean}.pdf"
                file_path = str(downloads_path / file_name)
                await download.save_as(file_path)

                return ProviderResult(
                    status="success",
                    file_path=file_path,
                    extracted_data={
                        "amount": amount_text.strip(),
                        "due_date": due_date_text.strip(),
                        "reference_month": params.reference_month,
                        "product_type": params.product_type,
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

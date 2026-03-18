import asyncio
import logging

from pydantic import BaseModel

from browser_agent.api.schemas import ClaroFetchBillParams
from browser_agent.config import settings
from browser_agent.jobs.models import ProviderResult
from browser_agent.providers.base import BaseProvider

logger = logging.getLogger(__name__)


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
                error="fetch-bill requires optional product_type (movel|residencial)",
            )

        downloads_path = settings.downloads_dir / "claro"
        downloads_path.mkdir(parents=True, exist_ok=True)
        debug_path = downloads_path / "debug"
        debug_path.mkdir(parents=True, exist_ok=True)

        async def log_step(page, step_name, frame=None):
            """Log current state: URL, frames, screenshot."""
            logger.info(f"=== STEP: {step_name} ===")
            logger.info(f"  Page URL: {page.url}")
            logger.info(f"  Frames ({len(page.frames)}):")
            for i, f in enumerate(page.frames):
                logger.info(f"    [{i}] {f.url}")
            # Screenshot
            try:
                screenshot_file = str(debug_path / f"{step_name}.png")
                await page.screenshot(path=screenshot_file, full_page=True)
                logger.info(f"  Screenshot: {screenshot_file}")
            except Exception as e:
                logger.info(f"  Screenshot failed: {e}")
            # Log HTML snippet around target element if frame given
            if frame:
                try:
                    html = await frame.evaluate(
                        "() => document.body.innerHTML.substring(0, 2000)"
                    )
                    logger.info(f"  Frame HTML (first 2000 chars): {html}")
                except Exception:
                    pass

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.browser_headless)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            try:
                # Step 1: Navigate to login page
                await page.goto(
                    "https://minhaclaro.claro.com.br/acesso-rapido/",
                    wait_until="load",
                )
                await log_step(page, "01_login_page")

                # Step 2: Click "Entrar" button to open login form
                await page.get_by_text("Entrar").first.click()
                await page.wait_for_load_state("load")
                await page.wait_for_timeout(1000)
                await log_step(page, "02_after_entrar")

                # Step 3: Fill CPF
                cpf_input = page.get_by_label("CPF, celular ou outro dado")
                await cpf_input.wait_for(state="visible", timeout=10000)
                await cpf_input.fill(settings.claro_username)

                # Step 4: Click "Continuar" (button starts disabled)
                continuar_btn = page.locator(
                    "button.mdn-Button--primary:has-text('Continuar')"
                )
                await page.wait_for_function(
                    "() => {"
                    "const b = document.querySelector("
                    '"button.mdn-Button--primary");'
                    "return b && !b.disabled;"
                    "}",
                    timeout=10000,
                )
                await continuar_btn.click()
                await page.wait_for_load_state("load")
                await page.wait_for_timeout(1000)
                await log_step(page, "03_after_continuar")

                # Step 5: Fill password
                password_input = page.locator("input[type='password']")
                await password_input.wait_for(state="visible", timeout=10000)
                await password_input.fill(settings.claro_password)

                # Step 6: Click "Entrar" to login (button starts disabled)
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
                await page.wait_for_load_state("load")
                await page.wait_for_timeout(2000)
                await log_step(page, "04_after_login")

                # Check for login error
                login_error = page.locator(".mdn-Alert--danger:has-text('inválidos')")
                if await login_error.count() > 0:
                    return ProviderResult(
                        status="failure",
                        error="Login failed: invalid username/password",
                    )

                # Step 7: Select product (movel or residencial)
                if params.product_type == "movel":
                    product_link = page.locator(
                        'a[href="/minha/area-logada/movel"]'
                    ).first
                else:
                    # Multiple residencial products may exist (some
                    # cancelled). Pick the last one (active).
                    product_links = page.locator(
                        'a[href="/minha/area-logada/residencial"]'
                    )
                    count = await product_links.count()
                    product_link = product_links.nth(count - 1)
                await product_link.wait_for(state="visible", timeout=20000)
                await product_link.click()
                await page.wait_for_load_state("load")
                await page.wait_for_timeout(5000)
                await log_step(page, "05_after_product")

                # Set up download listener (catches downloads from
                # any page/popup including blob URLs)
                download_future = asyncio.get_event_loop().create_future()

                def on_download(dl):
                    logger.info(f"  DOWNLOAD EVENT: {dl.url[:100]}...")
                    if not download_future.done():
                        download_future.set_result(dl)

                context.on(
                    "page", lambda new_page: new_page.on("download", on_download)
                )
                page.on("download", on_download)

                if params.product_type == "residencial":
                    # === RESIDENCIAL FLOW ===

                    # Dismiss onboarding modal if present
                    # ("O Minha Claro está de cara nova!" with
                    # "Vamos começar" button)
                    try:
                        modal_btn = page.locator(
                            "button:has-text('Vamos começar')"
                        ).first
                        if await modal_btn.is_visible(timeout=5000):
                            await modal_btn.click()
                            await page.wait_for_timeout(1000)
                    except Exception:
                        pass
                    # Also try closing any X button on modals
                    try:
                        close_btn = page.locator(
                            "[data-headlessui-state='open'] "
                            "button[aria-label='close'], "
                            "[data-headlessui-state='open'] "
                            "button:has(.mdn-Icon-fechar)"
                        ).first
                        if await close_btn.is_visible(timeout=2000):
                            await close_btn.click()
                            await page.wait_for_timeout(1000)
                    except Exception:
                        pass

                    # Click "Consultar faturas"
                    consultar = page.locator(
                        "a[href*='financeiro/fatura-interativa']"
                    ).first
                    await consultar.wait_for(state="visible", timeout=30000)
                    await consultar.click()
                    await page.wait_for_timeout(8000)
                    await log_step(page, "06_after_consultar_faturas")

                    # Find the faturas frame
                    # (minhaclaroresidencial.claro.com.br)
                    faturas_frame = None
                    for frame in page.frames:
                        if "fatura-interativa" in frame.url:
                            faturas_frame = frame
                            break

                    if faturas_frame is None:
                        # Might have navigated the main page
                        faturas_frame = page.main_frame

                    # Click "Segunda via da fatura" shortcut card
                    segunda_via = faturas_frame.locator(
                        ".mdn-Shortcut:has-text('Segunda via da fatura')"
                    ).first
                    await segunda_via.wait_for(state="visible", timeout=30000)
                    await segunda_via.click()
                    await page.wait_for_timeout(3000)
                    await log_step(page, "07_after_segunda_via")

                    # Click "Fazer Download da fatura"
                    download_btn = faturas_frame.locator(
                        "button:has-text('Fazer Download da fatura')"
                    ).first
                    await download_btn.wait_for(state="visible", timeout=30000)
                    await download_btn.click()

                else:
                    # === MÓVEL FLOW ===

                    # Click "Ver faturas" button inside iframe
                    iframe = page.frame_locator("iframe").first
                    ver_faturas = iframe.locator("button:has-text('Ver faturas')").first
                    try:
                        await ver_faturas.wait_for(state="visible", timeout=30000)
                        await ver_faturas.click()
                    except Exception:
                        await page.evaluate(
                            """() => {
                                const frames = document.querySelectorAll('iframe');
                                for (const f of frames) {
                                    try {
                                        const btn = f.contentDocument.querySelector(
                                            "button[data-tag='clique:ver-faturas']"
                                        );
                                        if (btn) { btn.click(); return true; }
                                    } catch(e) {}
                                }
                                return false;
                            }"""
                        )

                    await page.wait_for_timeout(8000)
                    await log_step(page, "06_after_ver_faturas")

                    # Find #goToSegundaViaFatura — one per month tab
                    # (oldest first), click the LAST one (most recent)
                    clicked = False
                    for i, frame in enumerate(page.frames):
                        try:
                            els = frame.locator("#goToSegundaViaFatura")
                            count = await els.count()
                            if count == 0:
                                continue
                            target_el = els.nth(count - 1)
                            dd = await target_el.get_attribute("data-due-date")
                            logger.info(f"  Using LAST ({count - 1}) due-date={dd}")
                            await target_el.dispatch_event("click")
                            clicked = True
                            break
                        except Exception as e:
                            logger.info(f"  Frame [{i}] error: {e}")
                            continue

                    if not clicked:
                        return ProviderResult(
                            status="failure",
                            error="Could not find download link",
                        )

                await log_step(page, "08_after_download_click")

                # Wait for download from any page
                download = await asyncio.wait_for(download_future, timeout=30)

                # Save the downloaded file
                logger.info(
                    f"Download URL: {download.url[:100]}... "
                    f"filename: {download.suggested_filename}"
                )
                from datetime import datetime

                now = datetime.now()
                month_label = now.strftime("%m-%Y")
                product = params.product_type
                file_name = f"claro_{product}_{month_label}.pdf"
                file_path = str(downloads_path / file_name)
                await download.save_as(file_path)

                return ProviderResult(
                    status="success",
                    file_path=file_path,
                    extracted_data={
                        "product_type": params.product_type,
                    },
                )

            except Exception as e:
                await log_step(page, "error_state")
                return ProviderResult(
                    status="failure",
                    error=str(e),
                )
            finally:
                await context.close()
                await browser.close()

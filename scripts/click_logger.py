"""
Launch a browser and log every click with the element's HTML.
Usage: python scripts/click_logger.py [url]
"""

import asyncio
import sys

from playwright.async_api import async_playwright


async def main():
    url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://minhaclaro.claro.com.br/acesso-rapido/"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        # Track which pages/frames we've seen
        all_pages = []

        async def inject_logger(frame):
            try:
                await frame.evaluate("""() => {
                    if (window.__clickLoggerInstalled) return;
                    window.__clickLoggerInstalled = true;
                    document.addEventListener('click', (e) => {
                        const el = e.target;
                        const info = {
                            tag: el.tagName,
                            id: el.id,
                            classes: String(el.className),
                            text: el.textContent?.trim().substring(0, 100),
                            href: el.href || el.getAttribute('href'),
                            type: el.type,
                            role: el.getAttribute('role'),
                            'data-attrs': Object.fromEntries(
                                [...el.attributes]
                                    .filter(a => a.name.startsWith('data-'))
                                    .map(a => [a.name, a.value])
                            ),
                            outerHTML: el.outerHTML.substring(0, 500),
                            parentHTML: el.parentElement
                                ? el.parentElement.outerHTML.substring(0, 800)
                                : '',
                            frameUrl: window.location.href,
                        };
                        console.log('CLICK_LOG:' + JSON.stringify(info, null, 2));
                    }, true);
                }""")
            except Exception:
                pass

        def on_console(msg):
            if "CLICK_LOG:" in msg.text:
                print(f"\n{'=' * 60}\n{msg.text}\n{'=' * 60}")

        def on_download(download):
            print(f"\n{'#' * 60}")
            print(f"DOWNLOAD: {download.url}")
            print(f"Suggested filename: {download.suggested_filename}")
            print(f"{'#' * 60}\n")

        async def setup_page(p):
            p.on("console", on_console)
            p.on("download", on_download)
            p.on("frameattached", lambda f: asyncio.ensure_future(inject_logger(f)))
            p.on("framenavigated", lambda f: asyncio.ensure_future(inject_logger(f)))
            all_pages.append(p)

        # Handle new pages (popups, new tabs)
        context.on("page", lambda p: asyncio.ensure_future(setup_new_page(p)))

        async def setup_new_page(p):
            await p.wait_for_load_state("load")
            await setup_page(p)
            for frame in p.frames:
                await inject_logger(frame)
            print(f"\n>>> New page opened: {p.url}")

        await setup_page(page)
        await page.goto(url, wait_until="load")

        # Initial injection
        for frame in page.frames:
            await inject_logger(frame)

        print(f"\nBrowser opened at: {url}")
        print("Click on any element — its HTML will be logged here.")
        print("Downloads will also be logged.")
        print("Press Ctrl+C to exit.\n")

        # Re-inject logger into all frames periodically
        try:
            while True:
                await asyncio.sleep(2)
                for p in all_pages:
                    try:
                        for frame in p.frames:
                            await inject_logger(frame)
                    except Exception:
                        pass
                # Also print current frames for debugging
        except KeyboardInterrupt:
            print("\nClosing browser...")
        finally:
            await browser.close()


asyncio.run(main())

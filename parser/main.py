import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # без GUI
        page = await browser.new_page()
        page.set_default_timeout(5000)
        await page.goto("https://www.the-unmatched.club/tools/matchups")

        elements = await page.query_selector_all('button[data-button-root]')
        await elements[1].click()
        elements = await page.query_selector_all('div[data-cmdk-item]')
        heroes = [await element.inner_text() for element in elements]
    
        data = dict()

        for hero in heroes[0:1]:
            print(hero)
            selector = f'div[data-cmdk-item][data-value="{hero}"]'
            await page.click(selector)

            enemies = await page.query_selector_all('.card-content.svelte-7yksa3')
            for enemy in enemies:
                text = await enemy.inner_text()
                print(text)

            # enemies = await page.query_selector_all('.absolute.z-\\[2\\].top-0.right-0.flex.gap-2.text-sm.text-white.bg-gray-900\\/60.p-1.rounded-bl-lg')
            # for enemy in enemies:
            #     text = await enemy.inner_text()
            #     data[f'{hero}'][''] = text.split('\n')[0]
                # element = await page.wait_for_selector('div.absolute.z-\\[2\\].left-0.right-0.bottom-0.pb-2.px-2.text-white.bg-gray-900\\/90')
            #     text = await enemy.inner_text()
            #     vs_name = text.split('\n')[0]
            #     print(vs_name)

            await page.click(f'button[role="combobox"]:has-text("{hero}")')

        await browser.close()

asyncio.run(main())
import asyncio
import json
from collections import defaultdict

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

        data = defaultdict(lambda: defaultdict(dict))

        for hero in heroes:
            selector = f'div[data-cmdk-item][data-value="{hero}"]'
            element = await page.wait_for_selector(selector)
            await element.click()

            selector = await page.wait_for_selector('.absolute.z-\\[2\\].top-0.right-0.flex.gap-2.text-sm.text-white.bg-gray-900\\/60.p-1.rounded-bl-lg')
            enemies = await page.query_selector_all('.card-content.svelte-7yksa3')
            for num, enemy in enumerate(enemies):
                text = await enemy.inner_text()
                values = text.split('\n')
                games, percent, enemy_name = values[0], values[1], values[2]
                data[hero][enemy_name]['games'] = int(games)
                data[hero][enemy_name]['percent'] = float(percent.rstrip('%')) / 100

            await page.click(f'button[role="combobox"]:has-text("{hero}")')

        await browser.close()
        with open('winrates.json', 'w') as fp:
            json.dump(data, fp)

asyncio.run(main())
from playwright.async_api import async_playwright
import asyncio
from random import randint
import os
import time

async def get_website_text_only_async(url):
    """
    Asynchronously capture website text.

    Args:
        url: The website URL to process

    Returns:
        String of page text
    """

    page_text = ""

    # Initialize Playwright
    async with async_playwright() as playwright:
        # Launch browser
        browser = await playwright.chromium.launch(headless=False)
        context_options = {"viewport": {'width': 1920, 'height': 1920}}
        context = await browser.new_context(**context_options)

        # Create a new page
        page = await context.new_page()

        try:
            # Navigate to website with a shorter timeout
            print(f"🔗 Navigating to website for text only extraction...{url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=3000)

            # Wait for a reasonable time for most content to load
            await page.wait_for_load_state("load", timeout=3000)

            # Try to wait for any major content
            try:
                await page.wait_for_selector("h1, article, .main-content, .content, main", state="visible", timeout=3000)
            except:
                print("⚠️ Couldn't find main content element, continuing anyway...")

            # Give a little extra time for any JavaScript rendering
            await asyncio.sleep(1)

            # Scroll down gradually if we're capturing for GIF
            top = 0
            for i in range(3):
                top += 300
                await page.evaluate(f"window.scrollTo({{top: {top}, behavior: 'smooth'}})")
                await asyncio.sleep(0.125)

            # Wait at the scrolled position
            await asyncio.sleep(0.25)

            # Scroll back up
            await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")

            await asyncio.sleep(0.25)
            # Extract all human-readable text from the page
            body_element = await page.query_selector('body')
            if body_element:
                page_text = await body_element.inner_text()

                # Clean up the text
                import re
                page_text = re.sub(r'\n{3,}', '\n\n', page_text)
                page_text = re.sub(r'\s{2,}', ' ', page_text)
                print(f"📄 Extracted {len(page_text)} characters of text")

        except Exception as e:
            print(f"❌ Error during page processing for text extraction: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Close the page and context
            try:
                await page.close()
                await context.close()

            except Exception as e:
                print(f"❌ Error during cleanup: {e}")
                import traceback
                traceback.print_exc()

            # Close the browser
            await browser.close()
            print("🚪 Browser closed")

    return page_text


async def process_urls_text_only(urls, max_concurrent=3):
    """Process multiple URLs concurrently with a limit on concurrent tasks."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(url):
        async with semaphore:
            return await get_website_text_only_async(url)

    tasks = [process_with_semaphore(url) for url in urls]
    return await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Example list of URLs to process
    urls_to_process = [
        ("https://www.whalesync.com"),
        ("https://www.whalesync.com/pricing"),
        ("https://www.github.com"),
        ("https://www.github.com/pricing"),
        # Add more URLs as needed
    ]

    # Run the async function
    results = asyncio.run(process_urls_text_only(urls_to_process, max_concurrent=3))
    print(results)

    # Print results
    for i, url in enumerate(urls_to_process):
        page_text = results[i]
        print(f"\nResults for {url}:")
        print(f"Page text excerpt: {page_text[:300]}\nTotal page length: {len(page_text)}" if page_text else "No page text extracted")

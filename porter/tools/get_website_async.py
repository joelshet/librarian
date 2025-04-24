from playwright.async_api import async_playwright
import asyncio
from random import randint
import os
import time

async def get_website_async(url, name="test"):
    """
    Asynchronously capture website data including screenshots.

    Args:
        url: The website URL to process
        name: Unique identifier for file naming (e.g., row_id)

    Returns:
        Tuple of (video_path, screenshot_path, title, h1_text, description, page_text)
    """
    # Create directories if they don't exist
    for dir_path in ["screenshots"]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    # Initialize variables to be returned with consistent naming
    screenshot_path = f"screenshots/{name}.jpg"
    title = ""
    h1_text = ""
    description = ""
    page_text = ""

    print(f"🌐 Processing website: {url}")

    # Initialize Playwright
    async with async_playwright() as playwright:
        # Launch browser
        browser = await playwright.chromium.launch(headless=False)
        # browser = await playwright.chromium.launch(args=['--hide-scrollbars'])

        # Create a context
        context_options = {
            "viewport": {'width': 1920, 'height': 1920}
        }

        context = await browser.new_context(**context_options)

        # Create a new page
        page = await context.new_page()

        try:
            # Navigate to website with a shorter timeout
            print(f"🔗 Navigating to website...{url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=5000)

            # Wait for a reasonable time for most content to load
            print("⌛ Waiting for initial render...")
            await page.wait_for_load_state("load", timeout=5000)

            # Try to wait for any major content
            try:
                await page.wait_for_selector("h1, article, .main-content, .content, main",
                                            state="visible",
                                            timeout=5000)
            except:
                print("⚠️ Couldn't find main content element, continuing anyway...")

            # Give a little extra time for any JavaScript rendering
            print("⏳ Allowing time for JS rendering...")
            await asyncio.sleep(2)

            print("✅ Page appears to be ready")

            # Get title using various methods with fallbacks
            title = await page.title()

            # If title is empty, try Open Graph and Twitter Card titles
            if not title:
                # Try Open Graph title
                og_title = await page.query_selector('meta[property="og:title"]')
                if og_title:
                    title = await og_title.get_attribute('content') or ""
                    print(f"🔍 Using og:title: {title}")

                # If still empty, try Twitter Card title
                if not title:
                    twitter_title = await page.query_selector('meta[name="twitter:title"]')
                    if twitter_title:
                        title = await twitter_title.get_attribute('content') or ""
                        print(f"🔍 Using twitter:title: {title}")

            print(f"📝 Final page title: {title}")

            # Get first H1 from website
            h1_element = await page.query_selector('h1')
            if h1_element:
                h1_text = await h1_element.inner_text()
                print(f"📝 H1: {h1_text}")

            # Get description with fallbacks
            meta_description = await page.query_selector('meta[name="description"]')
            if meta_description:
                description = await meta_description.get_attribute('content') or ""
                print(f"📝 Using meta description")

            # If description is empty, try Open Graph description
            if not description:
                og_description = await page.query_selector('meta[property="og:description"]')
                if og_description:
                    description = await og_description.get_attribute('content') or ""
                    print(f"📝 Using og:description")

            # If still empty, try Twitter Card description
            if not description:
                twitter_description = await page.query_selector('meta[name="twitter:description"]')
                if twitter_description:
                    description = await twitter_description.get_attribute('content') or ""
                    print(f"📝 Using twitter:description")

            if description:
                print(f"📝 Description: {description[:50]}..." if len(description) > 50 else f"📝 Description: {description}")
            else:
                print("⚠️ No description found")

            # Extract all human-readable text from the page
            body_element = await page.query_selector('body')
            if body_element:
                page_text = await body_element.inner_text()

                # Clean up the text
                import re
                page_text = re.sub(r'\n{3,}', '\n\n', page_text)
                page_text = re.sub(r'\s{2,}', ' ', page_text)
                print(f"📄 Extracted {len(page_text)} characters of text")

            # Take screenshot
            await page.screenshot(path=screenshot_path)
            print(f"📸 Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"❌ Error during page processing: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Close the page and context
            try:
                await page.close()
                print("🚪 Page closed")
                await context.close()
                print("🚪 Context closed")

            except Exception as e:
                print(f"❌ Error during cleanup: {e}")
                import traceback
                traceback.print_exc()

            # Close the browser
            await browser.close()
            print("🚪 Browser closed")

    print(f"✅ Website processing complete for {url}")
    return screenshot_path, title, h1_text, description, page_text


async def process_urls(urls_with_names, max_concurrent=3):
    """Process multiple URLs concurrently with a limit on concurrent tasks."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(url, name):
        async with semaphore:
            return await get_website_async(url, name)

    tasks = [process_with_semaphore(url, name)
             for url, name in urls_with_names]
    return await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Example list of URLs to process
    urls_to_process = [
        ("https://www.whalesync.com", "whalesync", False),
        ("https://www.google.com", "google", False),
        ("https://www.github.com", "github", True),
        ("https://www.microsoft.com", "microsoft", False),
        ("https://www.python.org", "python", False),
        # Add more URLs as needed
    ]

    # Run the async function
    results = asyncio.run(process_urls(urls_to_process, max_concurrent=3))

    # Print results
    for i, (url, name, _) in enumerate(urls_to_process):
        screenshot_path, title, h1, description, page_text = results[i]
        print(f"\nResults for {name} ({url}):")
        print(f"Video: {video_path}")
        print(f"Screenshot: {screenshot_path}")
        print(f"Title: {title}")
        print(f"H1: {h1}")
        print(f"Description: {description}")
        print(f"Page text excerpt: {page_text[:100]}..." if page_text else "No page text extracted")

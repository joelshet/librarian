from playwright.async_api import async_playwright
import asyncio
from random import randint
import os
import time

async def get_website_async(url, name="test", GIF=False):
    """
    Asynchronously capture website data including screenshots and optionally video for GIF creation.

    Args:
        url: The website URL to process
        name: Unique identifier for file naming (e.g., row_id)
        GIF: Boolean - whether to record and save video for GIF creation

    Returns:
        Tuple of (video_path, screenshot_path, title, h1_text, description, page_text)
    """
    # Create directories if they don't exist
    for dir_path in ["videos", "screenshots"]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    # Initialize variables to be returned with consistent naming
    video_path = f"videos/{name}.webm"
    screenshot_path = f"screenshots/{name}.jpg"
    title = ""
    h1_text = ""
    description = ""
    page_text = ""

    print(f"🌐 Processing website: {url}" + (" (with video for GIF)" if GIF else ""))

    # Initialize Playwright
    async with async_playwright() as playwright:
        # Launch browser
        browser = await playwright.chromium.launch(headless=False)
        # browser = await playwright.chromium.launch(args=['--hide-scrollbars'])

        # Create a context with video recording enabled only if GIF is True
        context_options = {
            "viewport": {'width': 1920, 'height': 1920}
        }

        if GIF:
            context_options["record_video_dir"] = "videos/"

        context = await browser.new_context(**context_options)

        # Create a new page
        page = await context.new_page()
        video = None

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

            # Scroll down gradually if we're capturing for GIF
            if GIF:
                print("📜 Performing scroll actions for video...")
                top = 0
                for i in range(3):
                    top += 300
                    await page.evaluate(f"window.scrollTo({{top: {top}, behavior: 'smooth'}})")
                    await asyncio.sleep(randint(50,100)/100)

                # Wait at the scrolled position
                await asyncio.sleep(1)

                # Scroll back up
                print("📜 Scrolling back up naturally...")
                await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")

                await asyncio.sleep(2)

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

            # Get the page's video object before closing
            if GIF:
                video = page.video
                print("🎥 Captured video for GIF creation")

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

                # Now save the video after the page is closed
                if GIF and video:
                    print(f"💾 Saving video to {video_path}...")
                    await video.save_as(video_path)
                    print(f"✅ Video saved to {video_path}")
                elif video:
                    # If we don't need the video, delete it immediately
                    await video.delete()
                    print(f"🗑️ Deleted video recording (not needed)")

            except Exception as e:
                print(f"❌ Error during cleanup: {e}")
                import traceback
                traceback.print_exc()

            # Close the browser
            await browser.close()
            print("🚪 Browser closed")

    print(f"✅ Website processing complete for {url}")
    return video_path, screenshot_path, title, h1_text, description, page_text


async def process_urls(urls_with_names, max_concurrent=3):
    """Process multiple URLs concurrently with a limit on concurrent tasks."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(url, name, GIF=False):
        async with semaphore:
            return await get_website_async(url, name, GIF)

    tasks = [process_with_semaphore(url, name, GIF)
             for url, name, GIF in urls_with_names]
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
        video_path, screenshot_path, title, h1, description, page_text = results[i]
        print(f"\nResults for {name} ({url}):")
        print(f"Video: {video_path}")
        print(f"Screenshot: {screenshot_path}")
        print(f"Title: {title}")
        print(f"H1: {h1}")
        print(f"Description: {description}")
        print(f"Page text excerpt: {page_text[:100]}..." if page_text else "No page text extracted")

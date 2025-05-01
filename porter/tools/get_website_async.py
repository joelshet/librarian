from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
import asyncio
import os
import re
import traceback

# --- Configuration ---
SCREENSHOTS_DIR = "screenshots"
DEFAULT_VIEWPORT = {'width': 1920, 'height': 1920}
NAVIGATION_TIMEOUT = 15000 # Increased timeout slightly
LOAD_STATE_TIMEOUT = 15000 # Increased timeout slightly
SELECTOR_TIMEOUT = 7000 # Increased timeout slightly
JS_RENDER_DELAY = 2 # seconds

async def get_website_async(browser: Browser, context: BrowserContext, url: str, name: str = "test"):
    """
    Asynchronously capture website data using a shared browser instance.

    Args:
        browser: The shared Playwright Browser instance.
        url: The website URL to process.
        name: Unique identifier for file naming (e.g., row_id).

    Returns:
        Tuple of (screenshot_path, title, h1_text, description, page_text)
        Returns (None, "", "", "", "") on major errors during context/page setup or processing.
    """
    # Create directories if they don't exist
    if not os.path.exists(SCREENSHOTS_DIR):
        try:
            os.makedirs(SCREENSHOTS_DIR)
        except FileExistsError:
            pass

    screenshot_path = os.path.join(SCREENSHOTS_DIR, f"{name}.jpg")
    title = ""
    h1_text = ""
    description = ""
    page_text = ""

    page: Page | None = None

    print(f"[{name}] 🌐 Processing website: {url}")

    try:
        # Create a NEW context for isolation per task
        # context = await browser.new_context(viewport=DEFAULT_VIEWPORT)
        page = await context.new_page()

        # Navigate to website
        print(f"[{name}] 🔗 Navigating to website...")
        # wait_until="domcontentloaded" is often faster but might miss dynamically loaded content
        # wait_until="load" waits for more resources
        # wait_until="networkidle" waits until network activity subsides (can be slow/unreliable)
        await page.goto(url, wait_until="load", timeout=NAVIGATION_TIMEOUT)
        print(f"[{name}]  navigated.")

        # Give time for dynamic content loading if necessary
        print(f"[{name}] ⏳ Allowing time for JS rendering...")
        await asyncio.sleep(JS_RENDER_DELAY)

        print(f"[{name}] ✅ Page appears to be ready for scraping")

        # --- Scrape Data ---

        # Get title using various methods with fallbacks
        title = await page.title()
        if not title:
            og_title = await page.locator('meta[property="og:title"]').get_attribute('content')
            if og_title:
                title = og_title
                print(f"[{name}] 🔍 Using og:title")
            else:
                twitter_title = await page.locator('meta[name="twitter:title"]').get_attribute('content')
                if twitter_title:
                    title = twitter_title
                    print(f"[{name}] 🔍 Using twitter:title")
        title = title.strip() if title else "" # Ensure it's a string and stripped
        print(f"[{name}] 📝 Final page title: {title}")

        # Get first H1 from website
        try:
            # Use locator which waits automatically to some extent
            h1_element = page.locator('h1').first
            # Explicitly wait for visibility if needed, but locator often handles it
            # await h1_element.wait_for(state="visible", timeout=SELECTOR_TIMEOUT / 2)
            h1_text = await h1_element.inner_text(timeout=SELECTOR_TIMEOUT) # Timeout on the action
            h1_text = h1_text.strip()
            print(f"[{name}] 📝 H1: {h1_text}")
        except Exception:
            print(f"[{name}] ⚠️ No H1 found or visible.")
            h1_text = ""

        # Get description with fallbacks
        meta_desc = await page.locator('meta[name="description"]').get_attribute('content')
        if meta_desc:
            description = meta_desc
            print(f"[{name}] 📝 Using meta description")
        else:
            og_desc = await page.locator('meta[property="og:description"]').get_attribute('content')
            if og_desc:
                description = og_desc
                print(f"[{name}] 📝 Using og:description")
            else:
                twitter_desc = await page.locator('meta[name="twitter:description"]').get_attribute('content')
                if twitter_desc:
                    description = twitter_desc
                    print(f"[{name}] 📝 Using twitter:description")

        description = description.strip() if description else "" # Ensure string and stripped
        if description:
            print(f"[{name}] 📝 Description: {description[:50]}...")
        else:
            print(f"[{name}] ⚠️ No description found")

        # Extract all human-readable text from the page
        try:
            body_element = page.locator('body')
            # await body_element.wait_for(state="visible", timeout=SELECTOR_TIMEOUT) # Wait if needed
            page_text = await body_element.inner_text(timeout=LOAD_STATE_TIMEOUT) # Give ample timeout

            # Clean up the text (basic cleaning)
            page_text = re.sub(r'<script.*?/script>', '', page_text, flags=re.DOTALL | re.IGNORECASE)
            page_text = re.sub(r'<style.*?/style>', '', page_text, flags=re.DOTALL | re.IGNORECASE)
            page_text = re.sub(r'<.*?>', ' ', page_text) # Remove HTML tags crudely
            page_text = re.sub(r'\n{3,}', '\n\n', page_text) # Consolidate newlines
            page_text = re.sub(r'\s{2,}', ' ', page_text) # Consolidate whitespace
            page_text = page_text.strip()
            print(f"[{name}] 📄 Extracted {len(page_text)} characters of text")
        except Exception as e:
            print(f"[{name}] ⚠️ Could not extract body text: {e}")
            page_text = ""


        # Take screenshot
        print(f"[{name}] 📸 Taking screenshot...")
        await page.screenshot(path=screenshot_path, full_page=True) # Consider full_page
        print(f"[{name}] 📸 Screenshot saved to {screenshot_path}")

    except Exception as e:
        print(f"❌ [{name}] Error during page processing for {url}: {e}")
        # Comment out traceback for cleaner concurrent logs unless debugging
        # traceback.print_exc()
        # Return None for screenshot path to indicate failure
        return None, "", "", "", ""

    finally:
        # Clean up context and page for this specific task
        if page:
            try:
                await page.close()
                print(f"[{name}] 🚪 Page closed")
            except Exception as e:
                print(f"❌ [{name}] Error closing page: {e}")

    print(f"✅ [{name}] Website processing complete for {url}")
    return screenshot_path, title, h1_text, description, page_text

# Updated to accept browser instance
async def process_urls(browser: Browser, context, urls_with_names, max_concurrent=3):
    """Process multiple URLs concurrently using a shared browser."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(url, name):
        # Pass the shared browser instance down
        async with semaphore:
            # Add retry logic here if needed
            result = await get_website_async(browser, context, url, name)
            return result

    tasks = [process_with_semaphore(url, name)
             for url, name in urls_with_names]
    results = await asyncio.gather(*tasks, return_exceptions=False) # Set return_exceptions=True to debug gather issues
    return results

# --- Main Execution Block ---
async def main():
    # Define URLs here
    urls_to_process = [
        # ("https://httpbin.org/delay/5", "httpbin_delay"), # Test timeouts
        ("https://www.whalesync.com", "whalesync"),
        ("https://www.google.com", "google"),
        ("https://github.com", "github"),
        ("https://www.microsoft.com", "microsoft"),
        ("https://www.python.org", "python"),
        ("https://example.com", "example"),
        ("https://playwright.dev/python", "playwright_py"),
        # Add more URLs as needed (name, url)
    ]

    # Launch Playwright and Browser ONCE
    async with async_playwright() as p:
        browser = None # Initialize browser variable
        try:
            print("🚀 Launching browser...")
            # Use headless=True for production/CI, False for debugging layout
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport=DEFAULT_VIEWPORT)
            # browser = await p.firefox.launch(headless=True)
            # browser = await p.webkit.launch(headless=True)
            print(f"✅ Browser launched! Type: {browser.browser_type.name}")

            # Run the processing function, passing the shared browser
            results = await process_urls(browser, context, urls_to_process, max_concurrent=3)

            # Print results cleanly
            print("\n--- Processing Summary ---")
            for i, (url, name) in enumerate(urls_to_process):
                if i < len(results): # Ensure results list matches input length
                    screenshot_path, title, h1, description, page_text = results[i]
                    print(f"\nResults for {name} ({url}):")
                    if screenshot_path: # Check if processing was successful
                         print(f"  Screenshot: {screenshot_path}")
                         print(f"  Title: {title}")
                         print(f"  H1: {h1}")
                         print(f"  Description: {description[:100]}{'...' if len(description) > 100 else ''}")
                         print(f"  Page text excerpt: {page_text[:100]}{'...' if len(page_text) > 100 else ''}")
                    else:
                        print("  Processing failed (see error logs above).")
                else:
                     print(f"\nResult missing for {name} ({url})")

        except Exception as e:
            print(f"❌ An error occurred during the main process: {e}")
            traceback.print_exc()
        finally:
            if browser:
                print("🚪 Closing browser...")
                await browser.close()
                print("✅ Browser closed.")
            print("🏁 Main process finished.")


if __name__ == "__main__":
    # Create screenshots directory if it doesn't exist before starting
    if not os.path.exists(SCREENSHOTS_DIR):
        os.makedirs(SCREENSHOTS_DIR)

    # Run the async main function
    asyncio.run(main())

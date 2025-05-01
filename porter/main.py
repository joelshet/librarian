import os
import re
import asyncio
import string
import argparse
import logging
from dotenv import load_dotenv
from pyairtable import Api
from pyairtable.formulas import match, OR

from playwright.async_api import async_playwright, Playwright, Browser

from tools.get_website_async import get_website_async
from tools.crop_image import crop_image_async
from tools.simple_ai_async import get_validated_response_async

from library.prompts import prompt_library

# Parse command line arguments
parser = argparse.ArgumentParser(description="Airtable Async Website Processor")
parser.add_argument("--debug", action="store_true", help="Enable GIF creation for all processed websites")
parser.add_argument("--delay", default=5, help="Delay between checking for rows to process (default 5 seconds)")
args = parser.parse_args()

DEBUG = args.debug
SLEEP_INTERVAL = args.delay
HEADLESS_MODE = False

# Load environment variables
load_dotenv()
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

airtable_api = Api(AIRTABLE_API_KEY)

# Load configuration variables
CONCURRENCY = int(os.getenv("PROCESSING_CONCURRENCY", 3))
SLEEP_INTERVAL = int(os.getenv("PROCESSING_INTERVAL_SECONDS", 5))
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "screenshots")
DEFAULT_VIEWPORT = {'width': 1920, 'height': 1920}

def setup_logging(debug: bool = False):
    """Configure logging"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

async def process_row(browser: Browser, context, row, table, semaphore):
    row_id = row["id"]
    fields = row.get("fields", {})
    url = fields.get("URL", "No URL")
    pricing_url = fields.get("Pricing URL", None)
    status = fields.get("Status", "Unknown")

    async with semaphore:
        try:
            if status == "Todo" and url:
                await handle_website(browser, context, row, table, row_id, url, fields, pricing_url)
            elif status == "Toai":
                await handle_ai_processing(table, row_id, fields)

        except Exception as e:
            logging.info(f"❌ Error processing row {row_id}: {e}")
            import traceback
            traceback.print_exc()

async def handle_website(browser: Browser, context, row, table, row_id, url, fields, pricing_url):
    screenshot_path = f"screenshots/{row_id}.png"
    os.makedirs("screenshots", exist_ok=True)

    await update_table(table, row_id, {"Status": "In progress"})

    try:
        screenshot_path, title, h1, description, page_text = await get_website_async(browser, context, url, name=row_id)
        logging.info(f"✅ Website data fetched for {url}, Title: {title[:50]}..." if title and len(title) > 50 else f"🔤 Title: {title}")

        await crop_image_async(screenshot_path, screenshot_path)
        await upload_attachment(table, row_id, "Screenshot", screenshot_path)

        if os.path.exists(screenshot_path):
            try:
                os.remove(screenshot_path)
                logging.info(f"🗑️ Deleted local screenshot after successful upload: {screenshot_path}")
            except Exception as e:
                logging.error(f"🔥 Failed to delete screenshot {screenshot_path} after upload: {e}")

        logging.info(f"📎 Screenshot uploaded for {row_id} from {screenshot_path}")

        updates = {
            "Title": title,
            "H1": h1,
            "Meta_Description": description,
            "URL_Content": page_text,
            "Status": "Toai"
        }

        if pricing_url:
            image_path, title, h1, description, pricing_page_text = await get_website_async(browser, context, pricing_url, name=row_id)
            updates["Pricing_URL_Content"] = pricing_page_text

            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    logging.debug(f"🗑️ Deleted local image of pricing_url after successful upload: {image_path}")
                except Exception as e:
                    logging.error(f"🔥 Failed to delete image of pricing_url: {image_path} after upload: {e}")


        await update_table(table, row_id, updates)

    except Exception as e:
        handle_error(row, table, row_id, screenshot_path, e)

async def handle_ai_processing(table, row_id, fields):
    logging.info(f"🤖 Starting AI processing for row {row_id}")
    try:
        logging.debug(f"Attempting to get schema...")
        schema = await get_table_schema(table)
        logging.debug(f"{schema}")

        ai_tasks, ai_field_names = [], []

        for field in schema.fields:
            if field.name.startswith("AI_") and field.name not in fields:
                if field.name in prompt_library:
                    base_prompt = prompt_library[field.name]
                elif schema.field(field.name) and schema.field(field.name).description:
                    base_prompt = schema.field(field.name).description
                else:
                    logging.error(f"Base prompt not found")
                    continue

                logging.debug(f"{base_prompt=}")

                placeholders = re.findall(r'{([^{}]+)}', base_prompt)
                template_str_converted = re.sub(r'{([^{}]+)}', r'${\1}', base_prompt)

                modified_fields = {key: value for key, value in fields.items()}
                for placeholder in placeholders:
                    if ' ' in placeholder:
                        template_str_converted = template_str_converted.replace(
                            '${' + placeholder + '}',
                            '${' + placeholder.replace(' ', '_') + '}'
                        )

                template = string.Template(template_str_converted)
                prompt = template.safe_substitute(modified_fields)
                logging.debug(f"{prompt=}")

                ai_tasks.append(get_validated_response_async(prompt))
                ai_field_names.append(field.name)

        if ai_tasks:
            logging.info(f"⚡ Processing {len(ai_tasks)} AI requests in parallel...")
            ai_responses = await asyncio.gather(*ai_tasks)
            logging.info(f"✅ All AI responses received")

            for field_name, response in zip(ai_field_names, ai_responses):
                if response:
                    await update_table(table, row_id, {field_name: response})
                else:
                    logging.info(f"⚠️ No response for field '{field_name}'")

        logging.info(f"🏁 Setting status to 'Done' for row {row_id}")
        await update_table(table, row_id, {"Status": "Done"})

    except Exception as e:
        logging.error(f"❌ Error processing AI for row {row_id}: {e}")

def handle_error(row, table, row_id, screenshot_path, error):
    logging.info(f"❌ Error processing website data: {error}")
    if os.path.exists(screenshot_path):
        try:
            os.remove(screenshot_path)
            logging.info(f"🗑️ Cleaned up file after error: {screenshot_path}")
        except:
            pass
    raise

# Helper functions to make Airtable operations awaitable
async def get_rows_to_process(table):
    loop = asyncio.get_event_loop()
    # rows = await loop.run_in_executor(None, table.all)
    formula = OR(match({"Status": "Todo"}), match({"Status": "Toai"}))
    rows = await loop.run_in_executor(None, lambda: table.all(formula=formula))
    return rows

async def update_table(table, row_id, fields):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: table.update(row_id, fields))
    return result

async def upload_attachment(table, row_id, field_name, file_path):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: table.upload_attachment(row_id, field_name, file_path))
    return result

async def get_table_schema(table):
    logging.debug(f"Getting table schema...")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, table.schema)

async def main_async():
    logging.info("\n🔄 Starting new processing cycle")
    logging.info("="*60)

    table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
    rows = await get_rows_to_process(table)
    logging.info(f"📊 Found {len(rows)} rows with status 'Todo' or 'Toai'.")

    status_counts = {status: sum(1 for row in rows if row.get("fields", {}).get("Status") == status) for status in set(row.get("fields", {}).get("Status", "Unknown") for row in rows)}
    logging.info(f"📊 Status breakdown: {status_counts}")

    if rows:
        async with async_playwright() as p: # Manages Playwright start/stop
            browser: Browser | None = None
            # Check if browser exists and is connected, otherwise launch/relaunch
            if browser is None or not browser.is_connected():
                logging.warning("Browser not found or disconnected. Launching/Relaunching...")
                if browser: # Attempt to close previous instance if it exists
                    try:
                        await browser.close()
                    except Exception as close_err:
                        logging.error(f"Error closing previous browser instance: {close_err}")
                try:
                    browser = await p.chromium.launch(headless=HEADLESS_MODE)
                    logging.info(f"✅ Browser launched! Type: {browser.browser_type.name}, Headless: {HEADLESS_MODE}")
                except Exception as launch_err:
                    logging.critical(f"❌ FATAL: Failed to launch browser: {launch_err}. Stopping.")
                    raise

            # Run the main processing cycle with the active browser
            context = await browser.new_context(viewport=DEFAULT_VIEWPORT)

            semaphore = asyncio.Semaphore(3)
            tasks = [process_row(browser, context, row, table, semaphore) for row in rows]

            if tasks:
                logging.info(f"🚀 Starting processing of {len(tasks)} rows...")
                await asyncio.gather(*tasks)
                logging.info(f"✅ All {len(tasks)} rows processed")
            else:
                logging.info("ℹ️ No rows to process")

            logging.info("="*60)
            logging.info("🏁 Processing cycle complete\n")

async def run_continuously():
    logging.info("🔄 Starting continuous processing loop with shared browser")
    async with async_playwright() as p: # Manages Playwright start/stop
        browser: Browser | None = None
        while True:
            try:
                await main_async()
                await asyncio.sleep(SLEEP_INTERVAL)

            except Exception as e:
                logging.info(f"❌ Error in main processing cycle: {e}")
                import traceback
                traceback.print_exc()

            # Cleanup when loop exits (e.g., on fatal error or KeyboardInterrupt)
            if browser and browser.is_connected():
                logging.info("🚪 Closing browser on exit...")
                await browser.close()
            logging.info("🛑 Continuous processing loop stopped.")


if __name__ == "__main__":
    setup_logging(debug=DEBUG)
    logging.info("🚀 Starting Airtable Async Processor")
    logging.info("="*60)
    logging.info(f"📋 Using table: {AIRTABLE_TABLE_NAME}")
    logging.info(f"⏱️ Check interval: 5 seconds")
    logging.info(f"🔄 Concurrency: 3 simultaneous rows")
    logging.info("="*60)

    try:
        asyncio.run(run_continuously())
    except KeyboardInterrupt:
        logging.info("\n🛑 Process interrupted by user. Shutting down...")
    except Exception as e:
        logging.info(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

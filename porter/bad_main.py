import os
import re
import asyncio
import string
import argparse
import logging
import traceback # Import traceback at the top
from dotenv import load_dotenv
from pyairtable import Api
from pyairtable.formulas import match, OR
# --- Import Playwright types ---
from playwright.async_api import async_playwright, Playwright, Browser

# --- Assuming get_website_async is already updated ---
# Ensure this function now accepts 'browser' as the first argument
from tools.get_website_async import get_website_async
from tools.crop_image import crop_image_async
from tools.simple_ai_async import get_validated_response_async

from library.prompts import prompt_library

# Parse command line arguments
parser = argparse.ArgumentParser(description="Airtable Async Website Processor")
parser.add_argument("--debug", action="store_true", help="Enable debug logging and potentially non-headless browser")
args = parser.parse_args()

DEBUG = args.debug

# Load environment variables
load_dotenv()
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

airtable_api = Api(AIRTABLE_API_KEY)

# Load configuration variables
CONCURRENCY = int(os.getenv("PROCESSING_CONCURRENCY", 3)) # For row processing, not browser tabs
SLEEP_INTERVAL = int(os.getenv("PROCESSING_INTERVAL_SECONDS", 5))
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "screenshots")
# Option for headless mode, potentially overridden by --debug
HEADLESS_MODE = False


def setup_logging(debug: bool = False):
    """Configure logging"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s', # Added funcName
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # Quieten noisy libraries if needed
    logging.getLogger("pyairtable").setLevel(logging.WARNING)
    # logging.getLogger("playwright").setLevel(logging.WARNING) # Uncomment if Playwright logs are too verbose

# --- MODIFIED FUNCTION SIGNATURES ---

async def process_row(browser: Browser, row, table, semaphore): # Added browser
    """Processes a single Airtable row, handling web scraping or AI tasks."""
    row_id = row["id"]
    fields = row.get("fields", {})
    url = fields.get("URL", "No URL")
    pricing_url = fields.get("Pricing URL", None)
    status = fields.get("Status", "Unknown")

    async with semaphore: # Limits concurrent row processing logic
        logging.debug(f"Acquired semaphore for row {row_id}, Status: {status}")
        try:
            if status == "Todo" and url:
                # Pass browser instance down
                await handle_website(browser, row, table, row_id, url, fields, pricing_url)
            elif status == "Toai":
                # AI processing doesn't need the browser directly here
                await handle_ai_processing(table, row_id, fields)
            else:
                logging.debug(f"Row {row_id} with status '{status}' does not require immediate action.")

        except Exception as e:
            logging.error(f"❌ Error processing row {row_id}: {e}", exc_info=not DEBUG) # Log stack trace unless debugging
            if DEBUG:
                 traceback.print_exc() # Print trace if debugging
            # Optionally update Airtable status to 'Error' here
            # await update_table(table, row_id, {"Status": "Error", "Error Details": str(e)[:1000]})
        finally:
            logging.debug(f"Released semaphore for row {row_id}")


async def handle_website(browser: Browser, row, table, row_id, url, fields, pricing_url): # Added browser
    """Handles the web scraping part for a given row using the shared browser."""
    logging.info(f"[{row_id}] 🚀 Starting web processing for URL: {url}")
    # Define screenshot path using SCREENSHOT_DIR
    screenshot_filename = f"{row_id}.jpg" # Use jpg as per get_website_async
    screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_filename)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True) # Ensure directory exists

    await update_table(table, row_id, {"Status": "In progress"})
    generated_screenshot_path: str | None = None # To track actual generated path
    generated_pricing_image_path: str | None = None

    try:
        # --- Call get_website_async with the shared browser ---
        generated_screenshot_path, title, h1, description, page_text = await get_website_async(
            browser, url, name=row_id # Pass browser instance
        )

        if generated_screenshot_path is None:
             raise ValueError("get_website_async failed to return a screenshot path.")

        logging.info(f"[{row_id}] ✅ Website data fetched. Title: {title[:50]}")

        # Crop the image in place (if needed and successful)
        # crop_successful = await crop_image_async(generated_screenshot_path, generated_screenshot_path)
        # if not crop_successful:
        #    logging.warning(f"[{row_id}] Cropping failed for {generated_screenshot_path}, uploading original.")

        # Upload the generated screenshot
        await upload_attachment(table, row_id, "Screenshot", generated_screenshot_path)
        logging.info(f"[{row_id}] 📎 Screenshot uploaded from {generated_screenshot_path}")

        # Delete local file *after* successful upload
        if os.path.exists(generated_screenshot_path):
            try:
                os.remove(generated_screenshot_path)
                logging.info(f"[{row_id}] 🗑️ Deleted local screenshot: {generated_screenshot_path}")
            except Exception as e:
                logging.error(f"[{row_id}] 🔥 Failed to delete screenshot {generated_screenshot_path}: {e}")

        updates = {
            "Title": title,
            "H1": h1,
            "Meta_Description": description,
            "URL_Content": page_text,
            # Status will be updated below
        }

        # Process Pricing URL if it exists
        if pricing_url:
            logging.info(f"[{row_id}] 💲 Processing Pricing URL: {pricing_url}")
            pricing_image_name = f"{row_id}_pricing"
            # --- Call get_website_async again for the pricing URL ---
            generated_pricing_image_path, _, _, _, pricing_page_text = await get_website_async(
                 browser, pricing_url, name=pricing_image_name # Pass same browser
            )

            if generated_pricing_image_path:
                updates["Pricing_URL_Content"] = pricing_page_text
                logging.info(f"[{row_id}] ✅ Pricing page text extracted.")
                 # Optional: Upload pricing page screenshot?
                 # await upload_attachment(table, row_id, "Pricing Screenshot", generated_pricing_image_path)

                # Delete local pricing image
                if os.path.exists(generated_pricing_image_path):
                    try:
                        os.remove(generated_pricing_image_path)
                        logging.info(f"[{row_id}] 🗑️ Deleted local pricing image: {generated_pricing_image_path}")
                    except Exception as e:
                        logging.error(f"[{row_id}] 🔥 Failed to delete pricing image {generated_pricing_image_path}: {e}")
            else:
                 logging.warning(f"[{row_id}] Processing pricing URL {pricing_url} did not yield an image/content.")
                 updates["Pricing_URL_Content"] = f"Error processing pricing URL: {pricing_url}"


        updates["Status"] = "Toai" # Set status after successful web processing
        await update_table(table, row_id, updates)
        logging.info(f"[{row_id}] ✔️ Web processing successful. Status set to 'Toai'.")

    except Exception as e:
        logging.error(f"[{row_id}] ❌ Error during web processing for {url}: {e}", exc_info=not DEBUG)
        if DEBUG:
             traceback.print_exc()
        # Clean up generated files on error
        if generated_screenshot_path and os.path.exists(generated_screenshot_path):
            try:
                os.remove(generated_screenshot_path)
                logging.info(f"[{row_id}] 🗑️ Cleaned up screenshot after error: {generated_screenshot_path}")
            except Exception as del_e:
                 logging.error(f"[{row_id}] 🔥 Failed to cleanup screenshot {generated_screenshot_path} after error: {del_e}")
        if generated_pricing_image_path and os.path.exists(generated_pricing_image_path):
             try:
                 os.remove(generated_pricing_image_path)
                 logging.info(f"[{row_id}] 🗑️ Cleaned up pricing image after error: {generated_pricing_image_path}")
             except Exception as del_e:
                 logging.error(f"[{row_id}] 🔥 Failed to cleanup pricing image {generated_pricing_image_path} after error: {del_e}")
        # Update status to Error
        await update_table(table, row_id, {"Status": "Error", "Error Details": f"Web processing failed: {str(e)[:1000]}"})
        # Do not re-raise here if process_row catches it, let the loop continue


async def handle_ai_processing(table, row_id, fields):
    """Handles the AI processing for a given row."""
    logging.info(f"[{row_id}] 🤖 Starting AI processing")
    await update_table(table, row_id, {"Status": "AI in progress"}) # Optional intermediate status
    try:
        # logging.debug(f"Attempting to get schema...") # Can be noisy
        schema = await get_table_schema(table)
        # logging.debug(f"{schema}") # Very verbose

        ai_tasks, ai_field_names = [], []

        for field in schema.fields:
            # Process fields starting with "AI_" that are currently empty
            if field.name.startswith("AI_") and field.name not in fields:
                base_prompt = ""
                # Prioritize prompt from library, fallback to field description
                if field.name in prompt_library:
                    base_prompt = prompt_library[field.name]
                    logging.debug(f"[{row_id}] Found prompt for '{field.name}' in library.")
                elif field.description:
                    base_prompt = field.description
                    logging.debug(f"[{row_id}] Using description as prompt for '{field.name}'.")
                else:
                    logging.warning(f"[{row_id}] No prompt or description found for field '{field.name}'. Skipping.")
                    continue

                # Simple placeholder substitution (replace {Field Name} with field value)
                prompt = base_prompt
                placeholders = re.findall(r'{([^{}]+)}', prompt)
                valid_substitution = True
                for placeholder in placeholders:
                    if placeholder in fields and fields[placeholder] is not None:
                        prompt = prompt.replace(f'{{{placeholder}}}', str(fields[placeholder]))
                    else:
                        logging.warning(f"[{row_id}] Placeholder '{{{placeholder}}}' for '{field.name}' not found in row fields or is null. Skipping field.")
                        valid_substitution = False
                        break # Stop processing this field if a placeholder is missing

                if not valid_substitution:
                    continue

                logging.debug(f"[{row_id}] Final prompt for '{field.name}': {prompt[:100]}...")

                # Add task to run AI prompt
                ai_tasks.append(get_validated_response_async(prompt))
                ai_field_names.append(field.name)

        if ai_tasks:
            logging.info(f"[{row_id}] ⚡ Requesting {len(ai_tasks)} AI fields in parallel...")
            # Use asyncio.gather with return_exceptions=True to handle individual AI errors
            ai_responses = await asyncio.gather(*ai_tasks, return_exceptions=True)
            logging.info(f"[{row_id}] ✅ All AI responses/exceptions received.")

            ai_updates = {}
            has_errors = False
            for field_name, response_or_exc in zip(ai_field_names, ai_responses):
                if isinstance(response_or_exc, Exception):
                    logging.error(f"[{row_id}] ❌ AI Error for field '{field_name}': {response_or_exc}")
                    ai_updates[field_name] = f"AI Error: {response_or_exc}" # Record error in field
                    has_errors = True
                elif response_or_exc:
                    logging.info(f"[{row_id}] ✨ AI Result for '{field.name}': {str(response_or_exc)[:50]}...")
                    ai_updates[field_name] = response_or_exc
                else:
                    logging.warning(f"[{row_id}] ⚠️ Empty AI response for field '{field_name}'.")
                    # Optionally set empty string or a specific note
                    # ai_updates[field_name] = ""

            if ai_updates:
                await update_table(table, row_id, ai_updates)

        # Set status based on whether AI processing encountered errors or finished all tasks
        final_status = "Error" if has_errors else "Done"
        logging.info(f"[{row_id}] 🏁 Setting final status to '{final_status}'.")
        await update_table(table, row_id, {"Status": final_status})

    except Exception as e:
        logging.error(f"[{row_id}] ❌ Unexpected error during AI processing setup for row {row_id}: {e}", exc_info=not DEBUG)
        if DEBUG:
            traceback.print_exc()
        await update_table(table, row_id, {"Status": "Error", "Error Details": f"AI setup failed: {str(e)[:1000]}"})

# Helper functions (keep async wrappers for Airtable sync calls)
async def get_rows_to_process(table):
    loop = asyncio.get_event_loop()
    formula = OR(match({"Status": "Todo"}), match({"Status": "Toai"}))
    logging.info(f"Fetching rows with formula: {formula}")
    rows = await loop.run_in_executor(None, lambda: table.all(formula=formula, fields=["URL", "Pricing URL", "Status"])) # Specify needed fields
    return rows

async def update_table(table, row_id, fields):
    logging.debug(f"[{row_id}] Updating table with fields: {list(fields.keys())}")
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, lambda: table.update(row_id, fields, typecast=True)) # Enable typecast
        logging.debug(f"[{row_id}] Update result: {result['id']}")
        return result
    except Exception as e:
        logging.error(f"[{row_id}] Failed to update Airtable: {e}")
        # Decide how to handle Airtable update errors (retry? log?)
        raise # Re-raise for now

async def upload_attachment(table, row_id, field_name, file_path):
    logging.debug(f"[{row_id}] Uploading attachment '{os.path.basename(file_path)}' to field '{field_name}'")
    loop = asyncio.get_event_loop()
    if not os.path.exists(file_path):
         logging.error(f"[{row_id}] Cannot upload attachment, file does not exist: {file_path}")
         return None # Or raise error
    try:
        # Check file size? Airtable has limits.
        result = await loop.run_in_executor(None, lambda: table.upload_attachment(row_id, field_name, file_path))
        # The result might just be the record update, not specific attachment info in pyairtable v1.x
        # In v2.x table.update({field_name: [{"url": "file://"+file_path}]}) might be used. Check pyairtable docs.
        logging.debug(f"[{row_id}] Attachment upload result ID: {result['id']}")
        return result
    except Exception as e:
        logging.error(f"[{row_id}] Failed to upload attachment {file_path} to {field_name}: {e}")
        raise # Re-raise

async def get_table_schema(table):
    logging.debug(f"Getting table schema...")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, table.schema)


async def main_async(browser: Browser): # Added browser parameter
    """Main processing cycle for one batch of rows."""
    logging.info("\n🔄 Starting new processing cycle")
    logging.info("="*60)

    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_NAME:
         logging.critical("Airtable API Key, Base ID, or Table Name not configured. Exiting.")
         return # Exit cycle if config missing

    try:
        table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
        rows = await get_rows_to_process(table)
        logging.info(f"📊 Found {len(rows)} rows with status 'Todo' or 'Toai'.")

        if not rows:
             logging.info("ℹ️ No rows to process in this cycle.")
             logging.info("="*60)
             return # Nothing to do

        status_counts = {}
        for row in rows:
            status = row.get("fields", {}).get("Status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        logging.info(f"📊 Status breakdown: {status_counts}")

        # Use the concurrency limit from environment variables
        semaphore = asyncio.Semaphore(CONCURRENCY)
        # --- Pass browser instance when creating tasks ---
        tasks = [process_row(browser, row, table, semaphore) for row in rows]

        logging.info(f"🚀 Starting processing of {len(tasks)} rows with concurrency={CONCURRENCY}...")
        await asyncio.gather(*tasks)
        logging.info(f"✅ All {len(tasks)} row tasks for this cycle have been processed (check logs for errors).")

    except Exception as e:
         logging.error(f"❌ Unhandled error in main_async cycle: {e}", exc_info=not DEBUG)
         if DEBUG:
              traceback.print_exc()

    logging.info("="*60)
    logging.info("🏁 Processing cycle complete\n")


async def run_continuously():
    """Runs the main processing logic in a loop, managing the browser lifecycle."""
    logging.info("🔄 Starting continuous processing loop with shared browser")
    async with async_playwright() as p: # Manages Playwright start/stop
        browser: Browser | None = None
        while True:
            cycle_start_time = asyncio.get_event_loop().time()
            try:
                # Check if browser exists and is connected, otherwise launch/relaunch
                if browser is None or not browser.is_connected():
                    logging.warning("Browser not found or disconnected. Launching/Relaunching...")
                    if browser: # Attempt to close previoous instance if it exists
                        try:
                           await browser.close()
                        except Exception as close_err:
                           logging.error(f"Error closing previous browser instance: {close_err}")
                    try:
                        browser = await p.chromium.launch(
                             headless=HEADLESS_MODE,
                             args=['--no-sandbox', '--disable-setuid-sandbox'] # Common args for containers/CI
                        )
                        logging.info(f"✅ Browser launched! Type: {browser.browser_type.name}, Headless: {HEADLESS_MODE}")
                    except Exception as launch_err:
                         logging.critical(f"❌ FATAL: Failed to launch browser: {launch_err}. Stopping.")
                         break # Exit the loop if browser cannot be launched

                # Run the main processing cycle with the active browser
                await main_async(browser)

            except Exception as e:
                # Catch unexpected errors from main_async or browser management
                logging.error(f"❌ Error in main processing loop: {e}", exc_info=not DEBUG)
                if DEBUG:
                    traceback.print_exc()
                # Optional: Decide if error warrants closing browser for next cycle
                # if browser:
                #    await browser.close()
                #    browser = None

            cycle_end_time = asyncio.get_event_loop().time()
            cycle_duration = cycle_end_time - cycle_start_time
            logging.info(f"Cycle took {cycle_duration:.2f} seconds.")

            # Wait before starting the next cycle
            logging.info(f"⏳ Waiting {SLEEP_INTERVAL} seconds before next cycle...")
            await asyncio.sleep(SLEEP_INTERVAL)

        # Cleanup when loop exits (e.g., on fatal error or KeyboardInterrupt)
        if browser and browser.is_connected():
            logging.info("🚪 Closing browser on exit...")
            await browser.close()
        logging.info("🛑 Continuous processing loop stopped.")


if __name__ == "__main__":
    setup_logging(debug=DEBUG)
    logging.info("🚀 Starting Airtable Async Processor")
    logging.info("="*60)
    logging.info(f"📋 Airtable Base: {AIRTABLE_BASE_ID}, Table: {AIRTABLE_TABLE_NAME}")
    logging.info(f"⏱️ Check interval: {SLEEP_INTERVAL} seconds")
    logging.info(f"🔄 Row Processing Concurrency: {CONCURRENCY}")
    logging.info(f"👁️ Headless Mode: {HEADLESS_MODE}")
    logging.info(f"💾 Screenshot Dir: {SCREENSHOT_DIR}")
    logging.info("="*60)

    # Create screenshot directory if it doesn't exist
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    try:
        asyncio.run(run_continuously())
    except KeyboardInterrupt:
        logging.info("\n🛑 Process interrupted by user. Shutting down gracefully...")
    except Exception as e:
        # Catch errors during initial asyncio.run setup if any
        logging.critical(f"\n❌ Fatal error during startup or shutdown: {e}", exc_info=True)
        traceback.print_exc()
    finally:
        logging.info("🏁 Airtable Async Processor finished.")

import os
import re
import asyncio
import string
import argparse
import logging
from dotenv import load_dotenv
from pyairtable import Api
from pyairtable.formulas import match, OR

from tools.get_website_async import get_website_async
from tools.crop_image import crop_image_async
from tools.simple_ai_async import get_ai_response_async

# Parse command line arguments
parser = argparse.ArgumentParser(description="Airtable Async Website Processor")
parser.add_argument("--debug", action="store_true", help="Enable GIF creation for all processed websites")
args = parser.parse_args()

DEBUG = args.debug

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

def setup_logging(debug: bool = False):
    """Configure logging"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

async def process_row(row, table, semaphore):
    row_id = row["id"]
    fields = row.get("fields", {})
    url = fields.get("URL", "No URL")
    pricing_url = fields.get("Pricing URL", None)
    status = fields.get("Status", "Unknown")

    async with semaphore:
        try:
            if status == "Todo" and url:
                await handle_website(row, table, row_id, url, fields, pricing_url)
            elif status == "Toai":
                await handle_ai_processing(table, row_id, fields)

        except Exception as e:
            logging.info(f"❌ Error processing row {row_id}: {e}")
            import traceback
            traceback.print_exc()

async def handle_website(row, table, row_id, url, fields, pricing_url):
    screenshot_path = f"screenshots/{row_id}.png"
    os.makedirs("screenshots", exist_ok=True)

    await update_table(table, row_id, {"Status": "In progress"})
    try:
        screenshot_path, title, h1, description, page_text = await get_website_async(url, name=row_id)
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
            "Meta Description": description,
            "URL Content": page_text,
            "Status": "Toai"
        }

        if pricing_url:
            image_path, title, h1, description, pricing_page_text = await get_website_async(pricing_url, name=row_id)
            updates["Pricing URL Content"] = pricing_page_text

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
        schema = await get_table_schema(table)
        ai_tasks, ai_field_names = [], []

        for field in schema.fields:
            if field.name.startswith("AI_") and field.name not in fields:
                description = schema.field(field.name).description
                placeholders = re.findall(r'{([^{}]+)}', description)
                template_str_converted = re.sub(r'{([^{}]+)}', r'${\1}', description)

                modified_fields = {key: value for key, value in fields.items()}
                for placeholder in placeholders:
                    if ' ' in placeholder:
                        template_str_converted = template_str_converted.replace(
                            '${' + placeholder + '}',
                            '${' + placeholder.replace(' ', '_') + '}'
                        )

                template = string.Template(template_str_converted)
                prompt = template.safe_substitute(modified_fields)

                ai_tasks.append(get_ai_response_async(prompt))
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

    semaphore = asyncio.Semaphore(3)
    tasks = [process_row(row, table, semaphore) for row in rows]

    if tasks:
        logging.info(f"🚀 Starting processing of {len(tasks)} rows...")
        await asyncio.gather(*tasks)
        logging.info(f"✅ All {len(tasks)} rows processed")
    else:
        logging.info("ℹ️ No rows to process")

    logging.info("="*60)
    logging.info("🏁 Processing cycle complete\n")

async def run_continuously():
    logging.info("🔄 Starting continuous processing loop")
    while True:
        try:
            await main_async()
        except Exception as e:
            logging.info(f"❌ Error in main processing cycle: {e}")
            import traceback
            traceback.print_exc()

        logging.info("⏳ Waiting before next cycle...")
        await asyncio.sleep(5)

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

import os
import re
import asyncio
import string
import argparse
from dotenv import load_dotenv
from pyairtable import Api

from get_website_async import get_website_async
from get_website_text_only_async import get_website_text_only_async
from crop_image import crop_image_async
from movie_to_gif import crop_and_convert_to_gif_async
from simple_ai_async import get_ai_response_async

# Parse command line arguments
parser = argparse.ArgumentParser(description="Airtable Async Website Processor")
parser.add_argument("--gif", action="store_true", help="Enable GIF creation for all processed websites")
args = parser.parse_args()

# Global flag for GIF creation
ENABLE_GIFS = args.gif

# Load environment variables
load_dotenv()

# Airtable Configuration
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

airtable_api = Api(AIRTABLE_API_KEY)

async def process_row(row, table, semaphore):
    """Process a single Airtable row asynchronously"""
    row_id = row["id"]
    fields = row.get("fields", {})
    url = fields.get("URL", "No URL")
    pricing_url = fields.get("Pricing URL", None)
    status = fields.get("Status", "Unknown")

    # Create directories if they don't exist
    for dir_path in ["videos", "screenshots", "gifs"]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    # Define consistent file paths based on row_id
    video_path = f"videos/{row_id}.webm"
    screenshot_path = f"screenshots/{row_id}.png"
    gif_path = f"gifs/{row_id}.gif"

    async with semaphore:  # Limit concurrent tasks
        try:
            if all([status == "Todo", url]):
                print(f"🚀 Starting website processing for {url}")
                await update_table(table, row_id, {"Status": "In progress"})
                print(f"⏳ Updated status to 'In progress' for {url}")

                # Determine if we should record video for GIF creation
                should_record_video = ENABLE_GIFS and "GIF" not in fields
                print(f"🎬 Video recording: {'Enabled' if should_record_video else 'Disabled'}")

                # Get website data asynchronously
                print(f"📥 Fetching website data for {url}...")

                try:
                    video_path, image_path, title, h1, description, page_text = await get_website_async(
                        url,
                        name=row_id,
                        GIF=should_record_video
                    )

                    # Update paths if returned paths are different
                    if image_path != screenshot_path:
                        print(f"ℹ️ Screenshot path changed from {screenshot_path} to {image_path}")
                        screenshot_path = image_path

                    print(f"✅ Website data fetched for {url}\tTitle: {title[:50]}..." if title and len(title) > 50 else f"🔤 Title: {title}")

                    # Handle screenshot
                    if "Screenshot" not in fields:
                        print(f"🖼️ Cropping screenshot for {url}...")
                        await crop_image_async(screenshot_path, screenshot_path)
                        print(f"📤 Uploading screenshot to Airtable for {url}..., {screenshot_path=}")
                        await upload_attachment(table, row_id, "Screenshot", screenshot_path)
                        print(f"✅ Screenshot uploaded for {url}")

                    # Handle thumbnails
                    if "Thumbnail" not in fields:
                        print(f"🖼️ Cropping thumbnail for {url}...")
                        await crop_image_async(screenshot_path, screenshot_path)
                        try:
                            thumb_path = f"screenshots/{row_id}_thumb.jpg"
                            print(thumb_path)
                            await upload_attachment(table, row_id, "Thumbnail", thumb_path)
                        except:
                            print(f"Failed to upload thumbnail for {url}")

                    # Handle GIF creation if enabled
                    if should_record_video:
                        print(f"🎬 Creating GIF from video for {url}...")
                        success = await crop_and_convert_to_gif_async(video_path, gif_path)

                        if success:
                            print(f"📤 Uploading GIF to Airtable for {url}...")
                            await upload_attachment(table, row_id, "GIF", gif_path)
                            print(f"✅ GIF uploaded for {url}")

                    # Delete the video file if it exists
                    if os.path.exists(video_path):
                        try:
                            os.remove(video_path)
                            print(f"🗑️ Deleted video file: {video_path}")
                        except Exception as e:
                            print(f"⚠️ Could not delete video file {video_path}: {e}")

                    # Update the fields
                    print(f"📝 Updating fields in Airtable for {url}...")
                    updates = {
                        "Title": title,
                        "H1": h1,
                        "Description": description,
                        "Page Text": page_text,
                        "Status": "Toai"
                    }
                    await update_table(table, row_id, updates)
                    print(f"✅ Fields updated for {url}, status set to 'Toai'")

                    if pricing_url:
                        pricing_page_text = await get_website_text_only_async(pricing_url)
                        await update_table(table, row_id, {"Pricing Page Text": pricing_page_text})

                except Exception as e:
                    print(f"❌ Error processing website data for {url}: {e}")
                    # Clean up files in case of error
                    for path in [video_path, screenshot_path]:
                        if os.path.exists(path):
                            try:
                                os.remove(path)
                                print(f"🗑️ Cleaned up file after error: {path}")
                            except:
                                pass

                    # Update status to indicate error
                    await update_table(table, row_id, {"Status": "Error"})
                    print(f"⚠️ Status set to 'Error' for {url}")
                    raise  # Re-raise so the outer try/except can log it

            elif status == "Toai":
                print(f"🤖 Starting AI processing for row {row_id}")
                try:
                    print(f"📚 Getting AI fields and prompts from table schema...")
                    schema = await get_table_schema(table)

                    ai_tasks = []
                    ai_field_names = []
                    ai_field_count = 0

                    for this_field in schema.fields:
                        if all([this_field.name.startswith("AI"), this_field.name not in fields]):
                            ai_field_count += 1
                            this_field_description = schema.field(this_field.name).description
                            print(f"🧠 Preparing AI prompt for field: {this_field.name}")

                            placeholders = re.findall(r'{([^{}]+)}', this_field_description)

                            # Convert standard format to Template format
                            template_str_converted = re.sub(r'{([^{}]+)}', r'${\1}', this_field_description)

                            # Create a modified fields dictionary with underscores instead of spaces in keys
                            modified_fields = {}
                            for key, value in fields.items():
                                # Add both the original key and a version with spaces replaced by underscores
                                modified_fields[key] = value
                                if ' ' in key:
                                    modified_fields[key.replace(' ', '_')] = value

                            # Also handle spaces in the template placeholders
                            for placeholder in placeholders:
                                if ' ' in placeholder:
                                    template_str_converted = template_str_converted.replace(
                                        '${' + placeholder + '}',
                                        '${' + placeholder.replace(' ', '_') + '}'
                                    )

                            template = string.Template(template_str_converted)
                            prompt = template.safe_substitute(modified_fields)
                            print(f"📋 Generated prompt for {this_field.name} ({len(prompt)} chars)")

                            # Create async task for AI response
                            ai_tasks.append(get_ai_response_async(prompt))
                            ai_field_names.append(this_field.name)

                    # Process all AI requests concurrently
                    if ai_tasks:
                        print(f"⚡ Processing {len(ai_tasks)} AI requests in parallel...")
                        ai_responses = await asyncio.gather(*ai_tasks)
                        print(f"✅ All AI responses received")

                        # Update each field with its corresponding response
                        for field_name, response in zip(ai_field_names, ai_responses):
                            if response:
                                print(f"📝 Updating field '{field_name}' with AI response ({len(response)} chars)")
                                await update_table(table, row_id, {field_name: response})
                            else:
                                print(f"⚠️ No response for field '{field_name}'")
                    else:
                        print(f"ℹ️ No AI fields to process for row {row_id}")

                    print(f"🏁 Setting status to 'Done' for row {row_id}")
                    await update_table(table, row_id, {"Status": "Done"})
                    print(f"✅ Row {row_id} completed successfully")

                except Exception as e:
                    print(f"❌ Error processing AI for row {row_id}: {e}")

            # else:
                # print(f"⏭️ Skipping row {row_id} - Status: {status}")

        except Exception as e:
            print(f"❌ Error processing row {row_id}: {e}")
            import traceback
            traceback.print_exc()  # Print the full stack trace

        finally:
            # Final cleanup - ensure files are removed if they exist
            if "Status" in fields and fields["Status"] in ["Done", "Error"]:
                for path in [video_path]:  # Only delete video, keep screenshots and GIFs
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                            print(f"🗑️ Final cleanup: Deleted {path}")
                        except Exception as cleanup_error:
                            print(f"⚠️ Could not delete {path} during cleanup: {cleanup_error}")

        # print(f"🔚 Finished processing row {row_id}\n" + "-"*50)

# Helper functions to make Airtable operations awaitable
async def get_all_rows(table):
    """Get all rows from the Airtable table"""
    print("📊 Fetching all rows from Airtable...")
    # Run in a separate thread since pyairtable is not async
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, table.all)
    print(f"📋 Retrieved {len(rows)} rows from Airtable")
    return rows

async def update_table(table, row_id, fields):
    """Update Airtable row asynchronously"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: table.update(row_id, fields))
    return result

async def upload_attachment(table, row_id, field_name, file_path):
    """Upload attachment to Airtable asynchronously"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: table.upload_attachment(row_id, field_name, file_path))
    return result

async def get_table_schema(table):
    """Get the table schema asynchronously"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, table.schema)

async def main_async():
    """Main async function to process all rows"""
    print("\n🔄 Starting new processing cycle")
    print("="*60)

    table = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

    # Get all rows
    rows = await get_all_rows(table)

    # Count rows by status
    status_counts = {}
    for row in rows:
        status = row.get("fields", {}).get("Status", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    print(f"📊 Status breakdown: {status_counts}")

    # Create a semaphore to limit concurrent executions
    semaphore = asyncio.Semaphore(3)  # Process up to 3 rows at a time
    print(f"⚙️ Using concurrency limit of 3 simultaneous tasks")

    # Create tasks for each row
    tasks = [process_row(row, table, semaphore) for row in rows]

    if tasks:
        print(f"🚀 Starting processing of {len(tasks)} rows...")
        # Run all tasks concurrently and wait for them to complete
        await asyncio.gather(*tasks)
        print(f"✅ All {len(tasks)} rows processed")
    else:
        print("ℹ️ No rows to process")

    print("="*60)
    print("🏁 Processing cycle complete\n")

async def run_continuously():
    """Run the main function in a continuous loop with a pause between iterations"""
    print("🔄 Starting continuous processing loop")
    while True:
        try:
            await main_async()
        except Exception as e:
            print(f"❌ Error in main processing cycle: {e}")
            import traceback
            traceback.print_exc()

        print("⏳ Waiting before next cycle...")
        await asyncio.sleep(5)  # Wait 5 seconds before checking again

# Main entry point
if __name__ == "__main__":
    print("🚀 Starting Airtable Async Processor")
    print("="*60)
    print(f"📋 Using table: {AIRTABLE_TABLE_NAME}")
    print(f"⏱️ Check interval: 5 seconds")
    print(f"🔄 Concurrency: 3 simultaneous rows")
    print(f"🎬 GIF creation: {'Enabled' if ENABLE_GIFS else 'Disabled'}")
    print("="*60)

    try:
        asyncio.run(run_continuously())
    except KeyboardInterrupt:
        print("\n🛑 Process interrupted by user. Shutting down...")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

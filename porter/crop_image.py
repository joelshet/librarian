from PIL import Image
import asyncio

def crop_image(image_path, output_path, left=0, upper=0, right=1920, lower=1200):
    """
    Synchronous function to crop an image.

    Args:
        image_path: Path to the source image
        output_path: Path where the cropped image will be saved
        left, upper, right, lower: Crop coordinates

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        img = Image.open(image_path)
        cropped_img = img.crop((left, upper, right, lower))
        # cropped_img.thumbnail((1600,1000))
        cropped_img.save(output_path)
        thumb_output_path = output_path.split('.')[0]+"_thumb.jpg"
        cropped_img.thumbnail((800,500))
        cropped_img.save(thumb_output_path)

        return True

    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return False
    except Exception as e:
        print(f"An error occurred while cropping image: {e}")
        return False

async def crop_image_async(image_path, output_path, left=0, upper=0, right=1920, lower=1200):
    """
    Asynchronous wrapper for crop_image.
    Runs the synchronous image cropping function in a separate thread to avoid blocking.

    Args:
        Same as crop_image

    Returns:
        bool: True if successful, False otherwise
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: crop_image(image_path, output_path, left, upper, right, lower)
    )

# Example usage:
image_path = "screenshot.png"
output_path = "cropped_screenshot.png"

if __name__ == "__main__":
    # Synchronous usage
    if crop_image(image_path, output_path):
        print(f"Image cropped and saved to {output_path}")
    else:
        print("Image cropping failed.")

    # Async usage example (uncomment to use)
    """
    import asyncio

    async def main():
        if await crop_image_async(image_path, output_path):
            print(f"Image cropped asynchronously and saved to {output_path}")
        else:
            print("Async image cropping failed.")

    asyncio.run(main())
    """

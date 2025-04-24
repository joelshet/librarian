import asyncio
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.fx.Crop import Crop

def crop_and_convert_to_gif(input_video_path, output_gif_path, width=800, height=500):
    """
    Synchronous function to crop a video to specified dimensions and convert it to GIF using MoviePy 2.x.

    Args:
        input_video_path (str): Path to the input video file
        output_gif_path (str): Path for the output GIF file
        width (int): Target width (default: 800)
        height (int): Target height (default: 500)
    """
    try:
        # Load the video file
        video = VideoFileClip(input_video_path).subclipped(4, 7)

        # Crop parameters: x1, y1, width, height (not x2, y2 as in v1)
        cropped_video = Crop(x1=0, y1=0, width=width, height=height).apply(video)

        # Convert to GIF
        cropped_video.write_gif(output_gif_path, fps=10)

        # Close the video objects to release resources
        video.close()

        print(f"Successfully converted {input_video_path} to {output_gif_path}")
        return True
    except Exception as e:
        print(f"Error processing video: {e}")
        return False

async def crop_and_convert_to_gif_async(input_video_path, output_gif_path, width=800, height=500):
    """
    Asynchronous function to crop a video to specified dimensions and convert it to GIF.
    Runs the synchronous function in a thread pool to avoid blocking the event loop.

    Args:
        input_video_path (str): Path to the input video file
        output_gif_path (str): Path for the output GIF file
        width (int): Target width (default: 800)
        height (int): Target height (default: 500)

    Returns:
        bool: True if successful, False otherwise
    """
    print(f"🎬 Starting async conversion of {input_video_path} to GIF...")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: crop_and_convert_to_gif(input_video_path, output_gif_path, width, height)
    )
    if result:
        print(f"✅ Async GIF conversion complete: {output_gif_path}")
    else:
        print(f"❌ Async GIF conversion failed for: {input_video_path}")
    return result

# Example usage
if __name__ == "__main__":
    input_path = "test.webm"   # Replace with your video path
    output_path = "output.gif" # Replace with your desired output path

    # Synchronous usage
    # crop_and_convert_to_gif(input_path, output_path)

    # Async usage
    async def run_test():
        print("Starting async test...")
        await crop_and_convert_to_gif_async(input_path, output_path)
        print("Test complete!")

    asyncio.run(run_test())

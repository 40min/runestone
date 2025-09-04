from pathlib import Path
from runestone.cli import process
from runestone.core.console import setup_console
from runestone.core.processor import RunestoneProcessor

# Setup console
console = setup_console()

def main():
    console.print("Hello from runestone!")

    # Create processor instance with your configuration
    processor = RunestoneProcessor(
        provider="openai",  # or "gemini" 
        api_key=None,  # Will use environment variables
        model_name=None,  # Will use defaults
        verbose=False
    )
    
    # Process the image
    image_path = Path("/Users/40min/Downloads/ref.jpeg")
    result = processor.process_image(image_path)
    
    # Display results
    processor.display_results_console(result)


if __name__ == "__main__":
    main()

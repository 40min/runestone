from runestone.cli import process
from src.runestone.core.console_config import setup_console

# Setup console
console = setup_console()

def main():
    console.print("Hello from runestone!")
    process("/Users/40min/Downloads/ref.jpeg")


if __name__ == "__main__":
    main()

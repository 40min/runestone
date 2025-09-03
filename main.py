from src.runestone.core.logging_config import setup_logging, get_logger

# Setup logging
setup_logging()

# Get logger for this module
logger = get_logger(__name__)

def main():
    logger.info("Hello from runestone!")


if __name__ == "__main__":
    main()

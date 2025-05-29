import logging
import os
from config import LOG_FILE


class Logger:
    _instance = None  # Singleton instance

    @staticmethod
    def get_logger(stage=''):
        """Returns a global logger instance."""
        if Logger._instance is None:
            Logger._instance = logging.getLogger("root")
            Logger._instance.setLevel(logging.INFO)

            # Remove existing handlers to prevent duplicates
            Logger._instance.handlers.clear()

            # Create file and console handlers
            file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
            stream_handler = logging.StreamHandler()

            # Updated log format with filename
            log_format = "%(asctime)s | %(filename)-20s | %(levelname)-7s | %(message)s"
            formatter = logging.Formatter(log_format)

            file_handler.setFormatter(formatter)
            stream_handler.setFormatter(formatter)

            # Add handlers
            Logger._instance.addHandler(file_handler)
            Logger._instance.addHandler(stream_handler)

            # Optional stage-based level
            if stage == "production":
                Logger._instance.setLevel(logging.ERROR)

        return Logger._instance

# Example usage
log = Logger.get_logger()
log.info("Global logger initialized!")

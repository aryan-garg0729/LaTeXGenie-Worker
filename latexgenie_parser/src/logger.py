import logging
import os
from pathlib import Path
from config import BASE_DIR

# Ensure logs directory exists
LOGS_DIR = Path(BASE_DIR) / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / "log_file.log"

class Logger:
    _instance = None  # Singleton instance

    @staticmethod
    def get_logger(stage=''):
        """Returns a global logger instance."""
        if Logger._instance is None:
            Logger._instance = logging.getLogger("root")
            Logger._instance.setLevel(logging.INFO)
            Logger._instance.handlers.clear()

            file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
            stream_handler = logging.StreamHandler()

            # Get unique instance/container identifier
            # instance_id = str(os.getpid())

            instance_id = (
                os.environ.get("HOSTNAME") or
                os.environ.get("INSTANCE_ID") or
                os.environ.get("CONTAINER_NAME") or
                "unknown-instance"
            )

            # Enhanced log format: timestamp | instance | filename:line | level | message
            log_format = (
                "%(asctime)s | %(instance_id)-18s | %(filename)-20s:%(lineno)d | "
                "%(levelname)-7s | %(message)s"
            )

            class ContextFilter(logging.Filter):
                def filter(self, record):
                    record.instance_id = instance_id
                    return True

            formatter = logging.Formatter(log_format)
            file_handler.setFormatter(formatter)
            stream_handler.setFormatter(formatter)

            # Add instance id filter
            file_handler.addFilter(ContextFilter())
            stream_handler.addFilter(ContextFilter())

            Logger._instance.addHandler(file_handler)
            Logger._instance.addHandler(stream_handler)

            if stage == "production":
                Logger._instance.setLevel(logging.ERROR)

        return Logger._instance

# Example usage
log = Logger.get_logger()
log.info("Global logger initialized!")

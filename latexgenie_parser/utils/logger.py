import logging
from pathlib import Path
from config import BASE_DIR

# === Ensure logs directory exists ===
LOGS_DIR = Path(BASE_DIR) / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "log_file.log"


# === Console log colors ===
class LogColors:
    RESET = "\033[0m"
    GREY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    LEVEL_COLORS = {
        logging.DEBUG: GREY,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: MAGENTA,
    }


# === Formatter with color for console ===
class ColoredFormatter(logging.Formatter):
    def format(self, record):
        color = LogColors.LEVEL_COLORS.get(record.levelno, LogColors.WHITE)
        message = super().format(record)
        return f"{color}{message}{LogColors.RESET}"


# === Singleton Logger ===
class Logger:
    _instance = None

    @staticmethod
    def get_logger():
        if Logger._instance:
            return Logger._instance

        logger = logging.getLogger("global_logger")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Prevent propagation to root

        if not logger.handlers:
            # === File handler ===
            file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
            file_formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)

            # === Console handler ===
            console_handler = logging.StreamHandler()
            console_formatter = ColoredFormatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%H:%M:%S"
            )
            console_handler.setFormatter(console_formatter)

            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

        Logger._instance = logger
        return logger

log = Logger.get_logger()
log.info("Global Logger initialized")
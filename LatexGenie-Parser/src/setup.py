from pathlib import Path
from config import DATA_DIR, LOGS_DIR, OUTPUT_IMAGES_DIR, GENIE_OUTPUT_DIR, HEADER_PARSER_DIR

# Define folder paths



def create_folders():
    for folder in [DATA_DIR, LOGS_DIR, OUTPUT_IMAGES_DIR, GENIE_OUTPUT_DIR, HEADER_PARSER_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
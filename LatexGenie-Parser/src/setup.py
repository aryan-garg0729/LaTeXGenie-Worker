from config import DATA_DIR, OUTPUT_IMAGES_DIR, GENIE_OUTPUT_DIR, HEADER_PARSER_DIR


def create_folders():
    for folder in [DATA_DIR, OUTPUT_IMAGES_DIR, GENIE_OUTPUT_DIR, HEADER_PARSER_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
import os
from pathlib import Path

#DIRECTORIES
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) #/mnt/piyush/LaTeXGenie-Worker
PARSER_DIR = Path(BASE_DIR) / 'LatexGenie-Parser'
OUTPUT_IMAGES_DIR = Path(BASE_DIR) / "output/images"
GENIE_OUTPUT_DIR = Path(BASE_DIR) / "genie_output"
HEADER_PARSER_DIR = Path(PARSER_DIR) / "parsers/data"
DATA_DIR = Path(BASE_DIR) / "data"
LOGS_DIR = Path(BASE_DIR) / "logs"

#FILES
LOG_FILE = Path(LOGS_DIR) / "log_file.log"

#URLS
COLAB_URL = 'https://b8d7-34-34-95-167.ngrok-free.app'

xml_output_path = "structure_output.xml"
reference_txt_file = "references.txt"
reference_bib_file = "references.bib"
output_inline_html = "src/reference/data/output_inline.html"
dummy_md = "src/reference/data/dummy.md"
citation_map_json = "src/reference/data/citation_map.json"
CONTAINER_NAME = "grobid-server"
output_tex = "output/output.tex"
output_bib = "output/references.bib"
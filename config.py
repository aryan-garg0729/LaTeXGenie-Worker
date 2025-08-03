import os
from pathlib import Path

# DIRECTORIES
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PARSER_DIR = BASE_DIR / 'latexgenie_parser'
OUTPUT_IMAGES_DIR = BASE_DIR / "output/images"
GENIE_OUTPUT_DIR = BASE_DIR / "genie_output"
HEADER_PARSER_DIR = PARSER_DIR / "header_reference_genie/data"
DATA_DIR = BASE_DIR / "data"

# URLS
CONTAINER_NAME = "grobid-server"
# GROBID_BASE_URL = "http://localhost:8070"
GROBID_BASE_URL = "http://grobid:8070"
COLAB_URL = 'https://b8d7-34-34-95-167.ngrok-free.app'

# FILES
DATA_AUTO_DIR = DATA_DIR / "output/input/auto"
KNOWLEDGE_JSON = DATA_AUTO_DIR / "input_content_list.json"
ORIGINAL_PDF = DATA_AUTO_DIR / "input_origin.pdf"
OUTPUT_TEX = "output/output.tex"
OUTPUT_BIB = "output/references.bib"
INTERM_OUTPUT_IMAGES = DATA_AUTO_DIR / "images"
REFERENCES_TXT = HEADER_PARSER_DIR / "references.txt"
XML_OUTPUT = HEADER_PARSER_DIR / "pdf_structure_xml.xml"
OUTPUT_INLINE_HTML = HEADER_PARSER_DIR / "output_inline.html"
DUMMY_MD = HEADER_PARSER_DIR / "dummy.md"
CITATION_MAP_JSON = HEADER_PARSER_DIR / "citation_map.json"
CSL_DIR = PARSER_DIR / "header_reference_genie/csl"
GENIE_OUTPUT_ZIP = GENIE_OUTPUT_DIR / "output.zip"

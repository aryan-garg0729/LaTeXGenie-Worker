import os
from pathlib import Path

#DIRECTORIES
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
PARSER_DIR = Path(BASE_DIR) / 'latexgenie_parser'
OUTPUT_IMAGES_DIR = Path(BASE_DIR) / "output/images"
GENIE_OUTPUT_DIR = Path(BASE_DIR) / "genie_output"
HEADER_PARSER_DIR = Path(PARSER_DIR) / "parsers/data"
DATA_DIR = Path(BASE_DIR) / "data"



#URLS
CONTAINER_NAME = "grobid-server"
COLAB_URL = 'https://b8d7-34-34-95-167.ngrok-free.app'

#FILES
KNOWLEDGE_JSON = "data/output/input/auto/input_content_list.json"
ORIGINAL_PDF = "data/output/input/auto/input_origin.pdf"
OUTPUT_TEX = "output/output.tex"
OUTPUT_BIB = "output/references.bib"
INTERM_OUTPUT_IMAGES = "data/output/input/auto/images"
REFERENCES_TXT = "latexgenie_parser/parsers/data/references.txt"
XML_OUTPUT = "latexgenie_parser/parsers/data/pdf_structure_xml.xml"
OUTPUT_INLINE_HTML = "latexgenie_parser/parsers/data/output_inline.html"
DUMMY_MD = "latexgenie_parser/parsers/data/dummy.md"
CITATION_MAP_JSON = "latexgenie_parser/parsers/data/citation_map.json"
CSL_DIR = "latexgenie_parser/parsers/csl"

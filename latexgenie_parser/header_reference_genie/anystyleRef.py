import subprocess
import os
import re
from config import REFERENCES_TXT
from latexgenie_parser.utils.logger import Logger

log = Logger.get_logger()

def read_file(filepath, mode="r", encoding="utf-8"):
    with open(filepath, mode, encoding=encoding) as f:
        return f.read()


def write_file(filepath, content, mode="w", encoding="utf-8"):
    with open(filepath, mode, encoding=encoding) as f:
        f.write(content)


def escape_special_chars(text):
    text = text.replace("\\", "\\\\")        # Escape backslashes
    text = text.replace("'''", "\\'\\'\\'")  # Escape triple single quotes
    text = text.replace("$", "")  # Escape single quotes
    return text


def format_references(input_text):
    lines = input_text.strip().split('\n')
    formatted_refs = []

    for idx, line in enumerate(lines, start=1):
        # Remove everything until the first alphabet character
        cleaned = re.sub(r'^[^A-Za-z]*', '', line)
        if cleaned:
            escaped = escape_special_chars(cleaned.strip())
            formatted_refs.append(f"[{idx}] {escaped}")

    return '\n'.join(formatted_refs)


def generate_bib(input_file, output_dir="output"):
    try:
        # subprocess.run([
        #     "docker", "run", "--rm", "-v", f"{os.getcwd()}:/data",
        #     "cokoapps/anystyle:2.0.0",
        #     "anystyle", "-f", "bib", "--overwrite", "parse",
        #     f"/data/{input_file}", f"/data/{output_dir}/"
        # ], check=True)
        subprocess.run([
            "anystyle", "-f", "bib", "--overwrite", "parse",
            f"{input_file}", f"{output_dir}"
        ], check=True)

        log.info(f"✅ Bib file saved")

    except subprocess.CalledProcessError as e:
        log.info(f"❌ Error: {e}")


def get_bib_file(references=""):
    try:
        reference_txt_file = REFERENCES_TXT

        # Step 1: Format references (optional but recommended)
        formatted = format_references(references)
        write_file(reference_txt_file, formatted)
        log.info(f"✅ Formatted references saved to {REFERENCES_TXT}")

        # Step 2: Generate BibTeX
        generate_bib(reference_txt_file)
    except Exception as e:
        log.info(f"Error in Bib Generation {e}")
    finally:
        if os.path.exists(reference_txt_file):
            os.remove(reference_txt_file)
            log.info(f"'{reference_txt_file}' File deleted.")
        else:
            log.info(f"'{reference_txt_file}' File not found.")

    
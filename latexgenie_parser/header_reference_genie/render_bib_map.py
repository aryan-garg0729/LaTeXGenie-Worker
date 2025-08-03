import re
import subprocess
import json
import os
from bs4 import BeautifulSoup
from latexgenie_parser.utils.logger import Logger
from config import DUMMY_MD,CITATION_MAP_JSON,OUTPUT_INLINE_HTML,CSL_DIR
log = Logger.get_logger()


csl_files = [
    f"{CSL_DIR}/apa.csl",
    f"{CSL_DIR}/mla.csl",
    f"{CSL_DIR}/chicago.csl",
    f"{CSL_DIR}/elsevier-harvard.csl",
]
def extract_bib_keys(bib_file):
    with open(bib_file, "r", encoding="utf-8") as f:
        content = f.read()
    return re.findall(r'@\w+\{([^,]+),', content)

def ieee_mapping(bib_path,mapping):
    
    with open(bib_path, "r", encoding="utf-8") as f:
        entries = f.read().split("@")
        for entry in entries:
            if not entry.strip():
                continue
            match_key = re.search(r"{([^,]+),", entry)
            match_number = re.search(r"citation-number\s*=\s*{?(\d+)}?", entry)
            if match_key and match_number:
                key = match_key.group(1).strip()
                number = match_number.group(1).strip()
                mapping[f"[{number}]"] = key
    return mapping



def generate_inline_citation_map(bib_file, output_json="src/reference/data/citation_map.json"):
    keys = extract_bib_keys(bib_file)
    if not keys:
        raise ValueError("No citation keys found in the .bib file.")

    # Write inline citations in one markdown file
    with open(DUMMY_MD, "w", encoding="utf-8") as f:
        f.write("# Inline Citations\n\n")
        for key in keys:
            f.write(f"[@{key}]\n\n")

    inline_map = {}

    for csl_file in csl_files:

        # Run Pandoc to HTML with citeproc
        subprocess.run([
            "pandoc",
            DUMMY_MD,
            "--citeproc",
            f"--bibliography={bib_file}",
            f"--csl={csl_file}",
            "-t", "html",
            "-o", OUTPUT_INLINE_HTML
        ], check=True)

        # Parse HTML and extract spans with data-cites
        with open(OUTPUT_INLINE_HTML, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        
        for span in soup.find_all("span", attrs={"data-cites": True}):
            cites = span["data-cites"].split()
            rendered = span.get_text(strip=True)
            if len(cites) == 1:
                inline_map[rendered] = cites[0]
            else:
                # Multiple keys in one citation — skip or handle later
                for c in cites:
                    inline_map[rendered] = c  # Overwrites but fine if used solo
    
    # create ieee style
    inline_map = ieee_mapping(bib_file, inline_map)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(inline_map, f, indent=2, ensure_ascii=False)

    log.info(f" Saved {len(inline_map)} inline citation formats to {output_json}")
    return inline_map

def citation_map(bib_file, output_json=CITATION_MAP_JSON):
    try:
        return generate_inline_citation_map(bib_file, output_json)
    except Exception as e:
        log.error(f"❌ Error: {e}")
        return {}
    finally:
        if os.path.exists(OUTPUT_INLINE_HTML):
            os.remove(OUTPUT_INLINE_HTML)
            log.info(f"'{OUTPUT_INLINE_HTML}' File deleted.")
        else:
            log.warning(f"'{OUTPUT_INLINE_HTML}' File not found.")

        if os.path.exists(DUMMY_MD):
            os.remove(DUMMY_MD)
            log.info(f"'{DUMMY_MD}' File deleted.")
        else:
            log.warning(f"'{DUMMY_MD}' File not found.")

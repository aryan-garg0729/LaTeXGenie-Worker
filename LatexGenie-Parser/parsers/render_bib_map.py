import re
import subprocess
import json
import os
from bs4 import BeautifulSoup
from src.logger import Logger

log = Logger.get_logger()

output_inline_html = "parsers/data/output_inline.html"
dummy_md = "parsers/data/dummy.md"
citation_map_json="parsers/data/citation_map.json"
csl_files = [
    "parsers/csl/apa.csl",
    "parsers/csl/mla.csl",
    "parsers/csl/chicago.csl",
    "parsers/csl/elsevier-harvard.csl",
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
    with open(dummy_md, "w", encoding="utf-8") as f:
        f.write("# Inline Citations\n\n")
        for key in keys:
            f.write(f"[@{key}]\n\n")

    inline_map = {}

    for csl_file in csl_files:

        # Run Pandoc to HTML with citeproc
        subprocess.run([
            "pandoc",
            dummy_md,
            "--citeproc",
            f"--bibliography={bib_file}",
            f"--csl={csl_file}",
            "-t", "html",
            "-o", output_inline_html
        ], check=True)

        # Parse HTML and extract spans with data-cites
        with open(output_inline_html, "r", encoding="utf-8") as f:
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

def citation_map(bib_file, output_json=citation_map_json):
    try:
        return generate_inline_citation_map(bib_file, output_json)
    except Exception as e:
        log.error(f"❌ Error: {e}")
        return {}
    finally:
        if os.path.exists(output_inline_html):
            os.remove(output_inline_html)
            log.info(f"'{output_inline_html}' File deleted.")
        else:
            log.warning(f"'{output_inline_html}' File not found.")

        if os.path.exists(dummy_md):
            os.remove(dummy_md)
            log.info(f"'{dummy_md}' File deleted.")
        else:
            log.warning(f"'{dummy_md}' File not found.")

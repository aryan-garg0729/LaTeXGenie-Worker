from config import COLAB_URL, OUTPUT_IMAGES_DIR, GENIE_OUTPUT_DIR,KNOWLEDGE_JSON,ORIGINAL_PDF,OUTPUT_BIB,OUTPUT_TEX,INTERM_OUTPUT_IMAGES
GENIE_OUTPUT_ZIP = f"{GENIE_OUTPUT_DIR}/output.zip"
import os
import json
import re
import itertools
import requests
import shutil
import zipfile
import argparse
import google.generativeai as genai
from bs4 import BeautifulSoup
from latexgenie_parser.utils.logger import Logger
from latexgenie_parser.header_reference_genie.anystyleRef import get_bib_file
from latexgenie_parser.header_reference_genie.render_bib_map import citation_map
from latexgenie_parser.header_reference_genie.citegenie import fuzzy_match_citations
from latexgenie_parser.utils.broken_char import BROKEN_COMBINATIONS, replace_broken
from latexgenie_parser.header_reference_genie.metadata_extractor import generate_header_and_references

log = Logger.get_logger()

# --- HTML table to LaTeX conversion logic ---

def llm_aided_latex(text):
    print("llm called")
    # === CONFIGURATION ===
    API_KEY = "AIzaSyDXiX89zV3uMBz5LSfcYzYIy8zaftsFq5Q"  # Replace with your API key

    # === SETUP ===
    genai.configure(api_key=API_KEY)

    # Use Gemini Pro (for text-based tasks)
    model = genai.GenerativeModel('gemma-3-27b-it',generation_config={
            "temperature": 0.7,
    })
    
    prompt = f"""You are a text analysis expert trained to structure scientific and technical content for LaTeX documents.

    Given an input chunk of text from a research paper or technical document, identify and wrap the relevant parts using **appropriate LaTeX environments**:

    - Use `\\begin{{itemize}}...\\end{{itemize}}` for **list items** (bulleted or numbered steps, \\item).
    - Use `\\begin{{algorithm}}[H]...\\end{{algorithm}}` with `\\begin{{algorithmic}}` inside for **algorithmic pseudocode**.
    - Use `\\begin{{lstlisting}}...\\end{{lstlisting}}` for **source code** blocks (Python, C++, LaTeX, etc.).
    - Leave all **plain explanatory text** as-is.
    - Maintain correct LaTeX syntax and indentation.
    - Do not hallucinate structure — only wrap what is clearly list/code/algorithm.


    Example Input:
    To compute the factorial of a number n:
    If n is 0, return 1.
    Otherwise, return n * factorial(n - 1).

    This is an example of a recursive algorithm. Below is a Python implementation:
    def factorial(n):
    if n == 0:
    return 1
    else:
    return n * factorial(n - 1)

    Example Output:
    To compute the factorial of a number \\( n \\):

    \\begin{{itemize}}
    \\item If \\( n = 0 \\), return 1.
    \\item Otherwise, return \\( n \\times \\text{{factorial}}(n - 1) \\).
    \\end{{itemize}}

    This is an example of a recursive algorithm.

    \\begin{{algorithm}}[H]
    \\caption{{Recursive Factorial}}
    \\begin{{algorithmic}}
    \\IF{{$n = 0$}}
    \\STATE return 1
    \\ELSE
    \\STATE return $n \\times \\text{{factorial}}(n - 1)$
    \\ENDIF
    \\end{{algorithmic}}
    \\end{{algorithm}}

    \\begin{{lstlisting}}[language=Python]
    def factorial(n):
        if n == 0:
            return 1
        else:
            return n * factorial(n - 1)
    \\end{{lstlisting}}

    Now process the following input in the same way:
    {text}

    Latex output:
    """
    response = model.generate_content(prompt)
    return response.text

def html_table_to_2d_array(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    rows = table.find_all("tr")

    max_cols = 0
    structured_rows = []

    for row in rows:
        cells = row.find_all(["td", "th"])
        col_count = sum(int(cell.get("colspan", 1)) for cell in cells)
        max_cols = max(max_cols, col_count)
        structured_rows.append(cells)

    grid = [[None] * max_cols for _ in range(len(rows))]

    for row_idx, cells in enumerate(structured_rows):
        col_idx = 0
        for cell in cells:
            while col_idx < max_cols and grid[row_idx][col_idx] is not None:
                col_idx += 1

            rowspan = int(cell.get("rowspan", 1))
            colspan = int(cell.get("colspan", 1))
            grid[row_idx][col_idx] = cell.get_text(strip=True)

            for r, c in itertools.product(range(rowspan), range(colspan)):
                if r == 0 and c == 0:
                    continue
                new_row = row_idx + r
                new_col = col_idx + c
                if new_row >= len(grid):
                    grid.extend([[None] * max_cols for _ in range(new_row - len(grid) + 1)])
                if r > 0:
                    grid[new_row][new_col] = "up"
                else:
                    grid[new_row][new_col] = "left"

            col_idx += colspan

    return grid

def array_to_latex(grid):
    if not grid or not grid[0]:
        return "\\begin{tabular}{|c|}\\hline\nEmpty Table\\\\\\hline\n\\end{tabular}"

    num_cols = len(grid[0])
    latex = "\\begin{tabular}{|" + "|".join(["c"] * num_cols) + "|}\\hline\n"

    for row_idx, row in enumerate(grid):
        cells = []
        col_idx = 0
        skip_hline = any(cell == "up" for cell in row)

        while col_idx < num_cols:
            cell = row[col_idx]
            if cell is None:
                cells.append("")
                col_idx += 1
                continue
            elif cell == "up":
                cells.append(" ")
                col_idx += 1
                continue
            elif cell == "left":
                col_idx += 1
                continue
            else:
                colspan = 1
                while col_idx + colspan < num_cols and row[col_idx + colspan] == "left":
                    colspan += 1

                rowspan = 1
                while row_idx + rowspan < len(grid) and grid[row_idx + rowspan][col_idx] == "up":
                    rowspan += 1

                ch = "|" if col_idx == 0 else ""
                if rowspan > 1 and colspan > 1:
                    cell_text = f"\\multicolumn{{{colspan}}}{{{ch}c|}}{{\\multirow{{{rowspan}}}{{*}}{{{escape_latex(cell)}}}}}"
                elif rowspan > 1:
                    cell_text = f"\\multirow{{{rowspan}}}{{*}}{{{escape_latex(cell)}}}"
                elif colspan > 1:
                    cell_text = f"\\multicolumn{{{colspan}}}{{{ch}c|}}{{{escape_latex(cell)}}}"
                else:
                    cell_text = escape_latex(cell)

                cells.append(cell_text)
                col_idx += colspan

        latex += " & ".join(cells) + " \\\\ "

        if row_idx + 1 < len(grid) and "up" not in grid[row_idx + 1]:
            latex += "\\hline\n"
        elif row_idx + 1 == len(grid):
            latex += "\\hline\n"
        else:
            start_col, last_col = 0, num_cols - 1
            while start_col < num_cols and grid[row_idx + 1][start_col] == "up":
                start_col += 1
            while last_col > 0 and grid[row_idx + 1][last_col] == "up":
                last_col -= 1
            if start_col <= last_col:
                latex += f"\\cline{{{start_col + 1}-{last_col + 1}}}\n"

    latex += "\\end{tabular}"
    return latex

def convert_html_table_to_latex(html):
    try:
        array = html_table_to_2d_array(html)
        return array_to_latex(array)
    except Exception as e:
        return f"\\begin{{verbatim}}\n{html}\n\\end{{verbatim}}"

def is_code_like(text):
    return False  # Stub for now

# def extract_authors_affiliations(text):
#     return f"\\author{{\n\\IEEEauthorblockN{{{escape_latex(text)}}}\n}}"

# --- Utility functions ---

def escape_latex(text):
    replacements = {
        '\\': r'\textbackslash{}',
        '{': r'\{',
        '}': r'\}',
        '$': r'\$',
        '&': r'\&',
        '#': r'\#',
        '%': r'\%',
        '_': r'\_',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }

    def replacer(part):
        if part.startswith('<!>') and part.endswith('<!>'):
            return part  # preserve inline LaTeX
        return ''.join(replacements.get(c, c) for c in part)

    parts = re.split(r'(<!>.*?<!>)', text)
    escaped = ''.join(replacer(part) for part in parts)
    return escaped.replace('<!>', '$')


def generate_imports(document_type='article', column='one', citation_style=None):
    document_classes = {
        "article": {
            "one": r"\documentclass[11pt, onecolumn]{article}",
            "two": r"\documentclass[11pt, twocolumn]{article}"
        },
        "report": {
            "one": r"\documentclass[11pt, onecolumn]{report}",
            "two": r"\documentclass[11pt, twocolumn]{report}"
        },
        "book": {
            "one": r"\documentclass[11pt, onecolumn]{book}",
            "two": r"\documentclass[11pt, twocolumn]{book}"
        }
    }

    latex_imports = [
        r"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%",
        r"%%%%%   This LaTeX file was generated by LaTeXGenie  %%%%%",
        r"%%%%%      — your AI-powered writing assistant —     %%%%%",
        r"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%",
        r"",
        document_classes[document_type][column],
        r"% Encoding and language",
        r"\usepackage[utf8]{inputenc}  % UTF-8 input encoding",
        r"\usepackage[english]{babel}  % English language support",
        r"",
        r"% Optional citation styles (uncomment if needed)",
        r"% Bibliography",
        r"\usepackage[backend=biber, style=ieee]{biblatex}  % IEEE style" if citation_style == 'ieee' else r"%\usepackage[backend=biber, style=ieee]{biblatex}  % IEEE style",
        r"\usepackage[backend=biber, style=apa]{biblatex}  % APA style" if citation_style == 'apa' else r"%\usepackage[backend=biber, style=apa]{biblatex}  % APA style",
        r"%\usepackage[backend=biber, style=mla]{biblatex}  % MLA style",
        r"%\usepackage[backend=biber, style=authoryear]{biblatex}  % Harvard style",
        r"%\usepackage[backend=biber, style=chicago-authordate]{biblatex}  % Chicago style",
        r"\addbibresource{references.bib}  % Reference to .bib file",
        r"",
        r"% Graphics",
        r"\usepackage{graphicx}  % Insert images",
        r"\usepackage[dvipsnames]{xcolor}  % Color support",
        r"",
        r"% Math (if needed)",
        r"\usepackage{amsmath, amssymb, amsfonts}  % Math support",
        r"",
        r"% Tables",
        r"\usepackage{booktabs}  % Nicer tables",
        r"\usepackage{tabularx}  % Flexible tables",
        r"\usepackage{makecell}  % Better cell formatting",
        r"",
        r"% Lists and formatting",
        r"\usepackage{enumitem}  % Customizable lists",
        r"\usepackage{comment}  % Comment blocks",
        r"",
        r"% URLs and hyperlinks",
        r"\usepackage{hyperref}  % Clickable links",
        r"\usepackage{url}  % URLs in text",
        r"",
        r"% Misc",
        r"\usepackage{fancyhdr}  % Custom headers/footers",
        r"\usepackage{lmodern}  % Improved font rendering",
        r"",
        r"\begin{document}"
    ]

    return latex_imports


def json_to_latex(data, column,references):
    latex_parts = []

    title = ""
    # references = []
    i = 0

    title_set = False
    in_references = False
    
    while i < len(data):
        obj = data[i]
        obj_type = obj.get("type")
        text = obj.get("text", "").strip() if obj_type == "text" else ""
        text = replace_broken(text, BROKEN_COMBINATIONS) if obj_type == "text" else text
        level = obj.get("text_level", None)

        # TITLE
        if obj_type == "text" and level == 1 and not title_set:
            title = escape_latex(text)
            latex_parts.append(f"\\title{{{title}}}")  # Use as title visually
            latex_parts.append("\\maketitle")
            title_set = True
            i += 1
            continue

        # REFERENCES
        if obj_type == "text":
            if not in_references and re.match(r"(?i)^((references?)|(bibliography)|(reference list))[\s:]*$", text):
                in_references = True
                latex_parts.append(r"\section*{References}")
                i += 1
                continue
            if in_references:
                i += 1
                continue

            # NORMAL TEXT
            escaped_text = escape_latex(text).replace('\n', r'\\')
            if level == 1:
                latex_parts.append(f"\\section*{{{escaped_text}}}")
            elif level == 2:
                latex_parts.append(f"\\subsection*{{{escaped_text}}}")
            elif level == 3:
                latex_parts.append(f"\\subsubsection*{{{escaped_text}}}")
            elif level == 4:
                latex_parts.append(f"\\paragraph*{{{escaped_text}}}")
            elif level == 5:
                latex_parts.append(f"\\subparagraph*{{{escaped_text}}}")
            else:
                latex_parts.append(escaped_text)
            i += 1
            continue

        # IMAGES
        if obj_type == "image":
            path = obj.get("img_path")
            caption = " ".join(obj.get("img_caption", []))
            column_width = r"\columnwidth" if column == "two" else r"0.65\columnwidth"
            latex_parts.append(
                "\\begin{figure}[htbp]\n"
                f"\\centering\n"
                f"\\includegraphics[width={column_width}, keepaspectratio]{{{path}}}\n"
                f"\\caption*{{{escape_latex(caption)}}}\n"
                "\\end{figure}"
            )
            i += 1
            continue

        # EQUATIONS
        if obj_type == "equation":
            equation = obj.get("text", "").strip().strip('$')
            latex_parts.append(f"\\begin{{equation}}\n{equation}\n\\end{{equation}}")
            i += 1
            continue

        # TABLES
        if obj_type == "table":
            caption = " ".join(obj.get("table_caption", []))
            footnotes = obj.get("table_footnote", [])
            html_body = obj.get("table_body", "")
            table_latex = convert_html_table_to_latex(html_body)

            escaped_caption = escape_latex(caption)
            escaped_footnotes = [escape_latex(fn) for fn in footnotes]

            tablenotes_block = ""
            if escaped_footnotes:
                tablenotes_block = (
                    "\\begin{tablenotes}\n\\footnotesize\n"
                    + "\n".join([f"\\item {note}" for note in escaped_footnotes]) +
                    "\n\\end{tablenotes}"
                )

            latex_parts.append(
                "\\begin{table}[htbp]\n"
                "\\centering\n"
                "\\begin{threeparttable}\n"
                f"\\caption*{{{escaped_caption}}}\n"
                f"{table_latex}\n"
                f"{tablenotes_block}\n"
                "\\end{threeparttable}\n"
                "\\end{table}"
            )
            i += 1
            continue

        i += 1

    latex_parts.append(r"\FloatBarrier")
    if references:
        for ref in references:
            latex_parts.append(f"\\noindent {escape_latex(ref)}\\\\")
    latex_parts.append(r"\end{document}")

    return "\n\n".join(latex_parts), title


def knowledge_extractor(args):
    # Replace this with your actual public ngrok URL from Colab
    

    # Local path to your test PDF
    pdf_path = args.pdf_path
    zip_path = 'output.zip'
    unzip_dir = 'unzipped_output'

    # Endpoint to hit
    url = f'{COLAB_URL}/convert'

    # Upload and download
    with open(pdf_path, 'rb') as f:
        files = {'file': (pdf_path, f, 'application/pdf')}
        log.info("Uploading...")
        response = requests.post(url, files=files)

        if response.status_code == 200:
            with open(zip_path, 'wb') as out_file:
                out_file.write(response.content)
            log.info("✅ Downloaded output.zip successfully.")
        else:
            log.error(f"❌ Request failed with status code {response.status_code}")
        

    # remove old unzipped folder
    safe_remove_dir(unzip_dir)
    # Unzip the downloaded file
    os.makedirs(unzip_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(unzip_dir)

    log.info("✅ Unzipped output.zip successfully.")



def convert_pdf():

    input_path = 'data/input.pdf'
    output_dir = 'data/output'

    os.system(f'rm -rf {output_dir}')

    os.system(f'python latexgenie_core/magic_pdf/tools/cli.py -p {input_path} -o {output_dir}')


    return True



def safe_remove_dir(path):
    if not os.path.exists(path):
        return f"Path does not exist: {path}"
    if not os.path.isdir(path):
        return f"Path is not a directory: {path}"
    try:
        shutil.rmtree(path)
        return f"Successfully removed directory and all contents: {path}"
    except Exception as e:
        return f"Error removing directory: {e}"


def handler(args):
    convert_pdf()
    try:
        # open the required file
        try:
            with open(KNOWLEDGE_JSON, "r", encoding="utf-8") as f:
                miner_data = json.load(f)
        except FileNotFoundError:
            log.error(f"Knowledge JSON file not found: {KNOWLEDGE_JSON}")
            return
        except json.JSONDecodeError as e:
            log.error(f"Error decoding JSON: {e}")
            return
        
        try:
            _ , references = generate_header_and_references(
                journal_type=args.journal,
                pdf_path=ORIGINAL_PDF,
                title="",
                only_ref=True
            )
        except Exception as e:
            log.error(f"Error in generate_header_and_references: {e}")
            return

        try:
            latex_output, title = json_to_latex(miner_data, args.column,references)
            print(latex_output)
        except Exception as e:
            log.error(f"Error in json_to_latex: {e}")
            return

        try:
            latex_imports = generate_imports(args.journal, args.column, citation_style='apa')
            latex_output = "\n".join(latex_imports) + "\n\n" + latex_output
        except Exception as e:
            log.error(f"Error in citation processing: {e}")
            return

        try:
            with open(OUTPUT_TEX, "w", encoding="utf-8") as f:
                f.write(latex_output)
        except Exception as e:
            log.error(f"Error writing LaTeX output: {e}")
            return

        # Copy images to output folder
        try:
            safe_remove_dir(OUTPUT_IMAGES_DIR)
            os.makedirs(OUTPUT_IMAGES_DIR, exist_ok=True)
            if os.path.exists(INTERM_OUTPUT_IMAGES):
                for file in os.listdir(INTERM_OUTPUT_IMAGES):
                    if file.endswith(".png") or file.endswith(".jpg"):
                        src_path = os.path.join(INTERM_OUTPUT_IMAGES, file)
                        dest_path = os.path.join(OUTPUT_IMAGES_DIR, file)
                        with open(src_path, "rb") as src_file:
                            with open(dest_path, "wb") as dest_file:
                                dest_file.write(src_file.read())
        except Exception as e:
            log.error(f"Error copying images: {e}")
            return

        # Zip the output folder
        try:
            safe_remove_dir(GENIE_OUTPUT_DIR)
            os.makedirs(GENIE_OUTPUT_DIR, exist_ok=True)
            with zipfile.ZipFile(GENIE_OUTPUT_ZIP, "w") as zipf:
                for root, dirs, files in os.walk("output"):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, os.path.relpath(file_path, "output"))
        except Exception as e:
            log.error(f"Error zipping output: {e}")
            return

    except Exception as e:
        log.error(f"Unexpected error in handler: {e}")


def run_pipeline(pdf_path: str, column: str = "one", journal: str = "report"):
    VALID_COLUMNS = {"one"}
    VALID_JOURNALS = {"article", "report", "book"}

    try:
        if column not in VALID_COLUMNS:
            raise ValueError(f"Invalid column: {column}")
        if journal not in VALID_JOURNALS:
            raise ValueError(f"Invalid journal: {journal}")

        args = argparse.Namespace(pdf_path=pdf_path, column=column, journal=journal)

        log.info(r"%%%% Starting JSON to LaTeX conversion... %%%%")
        handler(args)
        log.info(r"%%%% LaTeX file generated: output.tex %%%%")
        return GENIE_OUTPUT_ZIP

    except ValueError as ve:
        log.error(f"ValueError: {ve}")
        raise
    except Exception as e:
        log.error(f"Unexpected error in run_pipeline: {e}")
        raise


# run_pipeline("input.pdf")

# # --- Main script execution ---
# if __name__ == "__main__":
#     # Parse command-line arguments
#     parser = argparse.ArgumentParser(description="Convert JSON to LaTeX with optional column format.")
#     parser.add_argument("-c","--column", choices=["one", "two"], default="one", help="Column format: 'one' or 'two'")
#     parser.add_argument("-j","--journal", choices=["elsevier", "ieee","ieee_thanks_journal"], default="elsevier", help="Journal type: 'elsevier' or 'ieee'")
#     parser.add_argument("-p","--pdf", help="Provide the pdf path")
#     args = parser.parse_args()

#     # Check if pdf path is provided
#     # if args.pdf is None or not args.pdf.strip():
#     #     log.warning("pdf path not found")
#     #     exit()

#     # miner U logics
#     log.info(r"%%%% Starting JSON to LaTeX conversion... %%%%")
    
#     handler(args)

#     log.info(r"%%%% LaTeX file generated: output.tex %%%%")

import sys
import os
import json
import re
import itertools
import requests
import shutil
import zipfile
import argparse
from bs4 import BeautifulSoup
# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..","..")))
from src.logger import Logger
from parsers.anystyleRef import get_bib_file
from parsers.render_bib_map import citation_map
from parsers.citegenie import fuzzy_match_citations
from utils.broken_char import generate_broken_combinations, replace_broken
from parsers.header_parser import generate_header_and_references

log = Logger.get_logger()

broken_combinations = generate_broken_combinations()
# --- HTML table to LaTeX conversion logic ---

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


def generate_imports(journal,column,citation_style='apa'):
    journal_column = {
        "elsevier": {
            "one": r"\documentclass[final,1p,times,authoryear]{elsarticle}  % Elsevier journal class, one-column layout",
            "two": r"\documentclass[final,5p,times,authoryear]{elsarticle}  % Elsevier journal class, one-column layout"
        },
        "ieee": {
            "one": r"\documentclass[journal, onecolumn]{IEEEtran}",
            "two": r"\documentclass[journal]{IEEEtran}"
        },
        "ieee_thanks_journal": {
            "one": r"\documentclass[journal, onecolumn]{IEEEtran}",
            "two": r"\documentclass[journal]{IEEEtran}"
        }
    }

    latex_imports = [
        r"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%",
        r"%%%%%   This LaTeX file was generated by LaTeXGenie  %%%%%",
        r"%%%%% — your AI-powered academic writing assistant — %%%%%",
        r"%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%",
        r"",
        journal_column[journal][column],
        r"% Encoding and language",
        r"\usepackage[utf8]{inputenc}  % UTF-8 support for input text",
        r"\usepackage[english]{babel}  % English language support",
        r"\usepackage[autostyle, english = american]{csquotes}  % Context-aware quotation handling",
        r"",
        r"% Bibliography",
        r"% Conditional citation styles - uncomment the one you need",
        r"\usepackage[backend=biber, style=ieee]{biblatex}  % IEEE style" if citation_style=='ieee'else r"%\usepackage[backend=biber, style=ieee]{biblatex}  % IEEE style",
        
        r"\usepackage[backend=biber, style=apa]{biblatex}  % APA style" if citation_style=='apa' else  r"%\usepackage[backend=biber, style=apa]{biblatex}  % APA style",
        r"%\usepackage[backend=biber, style=mla]{biblatex}  % MLA style",
        r"%\usepackage[backend=biber, style=authoryear]{biblatex}  % Harvard style",
        r"%\usepackage[backend=biber, style=chicago-authordate]{biblatex}  % Chicago style",
        r"\addbibresource{references.bib}  % Reference to .bib file",
        r"",
        r"% Graphics and color",
        r"\usepackage{graphicx}  % Include graphics/images",
        r"\usepackage{epsfig}  % EPS image support",
        r"\usepackage[dvipsnames, table, xcdraw]{xcolor}  % Extended color and table support",
        r"",
        r"% Math and symbols",
        r"\usepackage[centertags]{amsmath}  % AMS math with centered equation tags",
        r"\usepackage{amssymb}  % Additional math symbols",
        r"\usepackage{amsfonts}  % AMS math fonts",
        r"\usepackage{amsthm}  % Theorem environments",
        r"",
        r"% Tables",
        r"\usepackage{booktabs}  % Improved table rules",
        r"\usepackage{multirow}  % Table cells spanning multiple rows",
        r"\usepackage{tabularx}  % Tables with adjustable-width columns",
        r"\usepackage{threeparttable}  % Tables with notes below",
        r"\usepackage{longtable}  % Tables spanning multiple pages",
        r"\usepackage{makecell}  % Enhanced cell formatting",
        r"",
        r"% Figures and floats",
        r"\usepackage{caption}  % Customization of captions",
        r"\usepackage{subfig}  % Use only this for subfigures",
        r"\usepackage{float, lscape}  % Float placement and landscape (legacy)",
        r"\usepackage{pdflscape}  % Use this instead of lscape",
        r"",
        r"% Layout and headers",
        r"\usepackage{fancyhdr}  % Custom headers and footers",
        r"\usepackage{afterpage}  % Execute command after current page",
        r"\usepackage{lmodern}  % Enhanced font rendering",
        r"",
        r"% Lists and formatting",
        r"\usepackage{enumerate}  % Enhanced enumerate environments",
        r"\usepackage{comment}  % Enables comment blocks",
        r"",
        r"% Algorithms",
        r"\usepackage{algorithm}  % Floating algorithm environment",
        r"\usepackage{algpseudocode}  % Pseudocode for algorithms",
        r"\usepackage{algorithmicx}  % Algorithmic package base",
        r"",
        r"% Hyperlinks and URLs",
        r"\usepackage{hyperref}  % Clickable links and references",
        r"\usepackage{url}  % Optional, hyperref usually handles it",
        r"",
        r"% Misc",
        r"\usepackage{lineno}  % For line numbers, optional",
        r"\usepackage{placeins}  %For FloatBarrier",
        r"",
        r"",
        r"\begin{document}"
    ]
    return latex_imports


# --- Main JSON to LaTeX parser ---
def json_to_latex(data,column):
    latex_parts = []

    title_set = author_set = abstract_set = keywords_set = False
    in_references = False
    title=""
    section = False
    references = []
    i = 0

    while i < len(data):
        obj = data[i]
        obj_type = obj.get("type")
        text = obj.get("text", "").strip() if obj_type == "text" else ""

        text = replace_broken(text, broken_combinations) if obj_type=="text" else text
        
        level = obj.get("text_level", None)

        if obj_type == "text" and level == 1 and not title_set:
            # latex_parts.append(f"\\title{{{escape_latex(text)}}}")
            title_set = True
            title = escape_latex(text)
            i += 1
            continue

        if obj_type == "text" and title_set and not author_set:
            # latex_parts.append(extract_authors_affiliations(text))
            # latex_parts.append(r"\maketitle")
            author_set = True
            i += 1
            continue

        if obj_type == "text" and not abstract_set and re.match(r"(?i)^abstract[\s:]*", text):
            # lines = [escape_latex(re.sub(r"(?i)^abstract[\s:]*", "", text).strip())]
            i += 1
            while i < len(data) and data[i].get("type") == "text" and data[i].get("text_level") is None:
                # lines.append(escape_latex(data[i]["text"].strip()))
                i += 1
            # latex_parts.append(r"\begin{abstract}")
            # latex_parts.append(" ".join(lines))
            # latex_parts.append(r"\end{abstract}")
            abstract_set = True
            continue

        if obj_type == "text" and not keywords_set and re.match(r"(?i)^keywords?[\s:]*", text):
            # lines = [escape_latex(re.sub(r"(?i)^keywords?[\s:]*", "", text).strip())]
            i += 1
            while i < len(data) and data[i].get("type") == "text" and data[i].get("text_level") is None:
                # lines.append(escape_latex(data[i]["text"].strip()))
                i += 1
            # latex_parts.append(r"\begin{IEEEkeywords}")
            # latex_parts.append(", ".join(lines))
            # latex_parts.append(r"\end{IEEEkeywords}")
            keywords_set = True
            continue

        if obj_type == "text":
            if not in_references and re.match(r"(?i)^(?:\d+[\.\)]?\s*)?(references?|bibliography|reference list)[\s:]*$"
, text):
                in_references = True
                i += 1
                continue
            if in_references:
                if references and text and text[0].islower():
                    references[-1] += " " + text
                else:
                    references.append(text)
                i += 1
                continue

            if is_code_like(text):
                latex_parts.append(r"\begin{verbatim}")
                latex_parts.append(text)
                latex_parts.append(r"\end{verbatim}")
                i += 1
                continue

            escaped_text = escape_latex(text).replace('\n', '\\\\')

            if level == 1 and not title_set:
                latex_parts.append(f"\\title{{{escaped_text}}}")
                title_set = True
            elif level == 1 or level == 2:
                section = True
                latex_parts.append(f"\\section*{{{escaped_text}}}")
            elif level == 3:
                section = True
                latex_parts.append(f"\\subsection*{{{escaped_text}}}")
            elif level == 4:
                section = True
                latex_parts.append(f"\\subsubsection*{{{escaped_text}}}")
            elif level == 5:
                section = True
                latex_parts.append(f"\\paragraph*{{{escaped_text}}}")
            elif section:
                latex_parts.append(escaped_text)
            i += 1
            continue

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

        # --- Equation ---
        if obj_type == "equation":
            equation = obj.get("text", "").strip()
            # Remove $$ if present
            equation = equation.strip('$').strip()
            latex_parts.append(f"\\begin{{equation}}\n{equation}\n\\end{{equation}}")

        if obj_type == "table":
            table_width = r"\textwidth"
            caption = " ".join(obj.get("table_caption", []))
            foot_notes = obj.get("table_footnote", [])
            html_body = obj.get("table_body", "")
            table_latex = convert_html_table_to_latex(html_body)

            escaped_caption = escape_latex(caption)
            escaped_footnotes = [escape_latex(fn) for fn in foot_notes]

            tablenotes_block = ""
            if escaped_footnotes:
                tablenotes_block = (
                    "\\begin{tablenotes}\n"
                    "\\footnotesize\n"
                    + "\n".join([f"\\item {note}" for note in escaped_footnotes]) + "\n"
                    "\\end{tablenotes}\n"
                )

            latex_parts.append(
                "\\begin{table*}[t]\n"
                "\\centering\n"
                "\\begin{threeparttable}\n"
                f"\\caption*{{{escaped_caption}}}\n"
                f"{table_latex}\n"
                f"{tablenotes_block}"
                "\\end{threeparttable}\n"
                "\\end{table*}"
            )
            i += 1
            continue

        i += 1
    latex_parts.append(r"\FloatBarrier")
    latex_parts.append(r"\printbibliography")
    latex_parts.append(r"\end{document}")
    
    return "\n\n".join(latex_parts), title, references

def knowledge_extractor(args):
    # Replace this with your actual public ngrok URL from Colab
    COLAB_URL = 'https://b8d7-34-34-95-167.ngrok-free.app'

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

    input_path = 'LaTeXGenie-Worker/data/input.pdf'
    output_dir = 'LaTeXGenie-Worker/data/output'

    os.system(f'rm -rf {output_dir}')

    os.system(f'python LaTeXGenie-Worker/LaTeXGenie-Core/magic_pdf/tools/cli.py -p {input_path} -o {output_dir}')


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
    # knowledge_extractor(args)
    convert_pdf()

    # open the required file
    with open("LaTeXGenie-Worker/data/output/input/auto/input_content_list.json", "r", encoding="utf-8") as f:
        miner_data = json.load(f)

    latex_output, title, _ = json_to_latex(miner_data, args.column)

    # generate header and references from the grobid
    # journal_type = "elsevier"
    pdf_path = "LaTeXGenie-Worker/data/output/input/auto/input_origin.pdf"
    header , references = generate_header_and_references(journal_type=args.journal,pdf_path=pdf_path, title=title)
    # header , references = generate_header_and_references(journal_type=args.journal,pdf_path=args.pdf,title=title)
    
    header = replace_broken(header, broken_combinations)

    #generate Bib file 
    total_ref = len(references)
    references = "\n".join(references)
    references = replace_broken(references, broken_combinations)
    get_bib_file(references)

    # create mapping rendered : key
    mapping = citation_map("output/references.bib")

    # add citations
    latex_output,citation_style = fuzzy_match_citations(latex_output, mapping,total_ref, threshold=80) 

    # generate final latex
    latex_imports = generate_imports(args.journal, args.column,citation_style = citation_style)
    latex_imports.append(header)
    latex_output = "\n".join(latex_imports) + "\n\n" + latex_output
    

    # write final latex output to file
    with open("output/output.tex", "w", encoding="utf-8") as f:
        f.write(latex_output)

    # copy images to output folder
    safe_remove_dir("output/images")
    os.makedirs("output/images", exist_ok=True)
    
    if os.path.exists('LaTeXGenie-Worker/data/output/input/auto/images'):
        for file in os.listdir("LaTeXGenie-Worker/data/output/input/auto/images"):
            if file.endswith(".png") or file.endswith(".jpg"):
                src_path = os.path.join("LaTeXGenie-Worker/data/output/input/auto/images", file)
                dest_path = os.path.join("output/images", file)
                with open(src_path, "rb") as src_file:
                    with open(dest_path, "wb") as dest_file:
                        dest_file.write(src_file.read())
    
    # zip the output folder
    safe_remove_dir("genie_output")
    os.makedirs("genie_output", exist_ok=True)
    with zipfile.ZipFile("genie_output/output.zip", "w") as zipf:
        for root, dirs, files in os.walk("output"):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, "output"))


def run_pipeline(pdf_path: str, column: str = "one", journal: str = "elsevier"):
    VALID_COLUMNS = {"one", "two"}
    VALID_JOURNALS = {"elsevier", "ieee", "ieee_thanks_journal"}

    if column not in VALID_COLUMNS:
        raise ValueError(f"Invalid column: {column}")
    if journal not in VALID_JOURNALS:
        raise ValueError(f"Invalid journal: {journal}")

    args = argparse.Namespace(pdf_path=pdf_path, column=column, journal=journal)

    log.info(r"%%%% Starting JSON to LaTeX conversion... %%%%")
    handler(args)
    log.info(r"%%%% LaTeX file generated: output.tex %%%%")
    return "genie_output/output.zip"

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

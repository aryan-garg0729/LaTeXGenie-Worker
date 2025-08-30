import re
from typing import List, Dict, Any, Tuple
from latexgenie_parser.src.latex_generator.table_converter import convert_html_table_to_latex, escape_latex
from latexgenie_parser.utils.broken_char import replace_broken, BROKEN_COMBINATIONS



def is_code_like(text: str) -> bool:
    return False  # Stub for now

def json_to_latex(data: List[Dict[str, Any]], column: str, start_index: int = 0) -> Tuple[str, List[str]]:
    latex_parts = []
    in_references = False
    references = []
    section = False
    i = start_index

    while i < len(data):
        obj = data[i]
        obj_type = obj.get("type")
        text = obj.get("text", "").strip() if obj_type == "text" else ""
        text = replace_broken(text, BROKEN_COMBINATIONS) if obj_type == "text" else text
        level = obj.get("text_level", None)

        if obj_type == "text":
            if not in_references and re.match(r"(?i)^(\d+[.\)]?\s*)?(references?|bibliography|reference list)[\s:]*$", text):
                in_references = True
                i += 1
                continue

            if in_references:
                if references and text and text[0].islower():
                    references[-1] += " " + text
                else:
                    references.extend(text.split('\n'))
                i += 1
                continue

            if is_code_like(text):
                latex_parts.append(r"\begin{verbatim}")
                latex_parts.append(text)
                latex_parts.append(r"\\end{verbatim}")
                i += 1
                continue

            escaped_text = escape_latex(text).replace('\n', r'\\')

            if level == 1:
                section = True
                latex_parts.append(f"\section*{{{escaped_text}}}")
            elif level == 2:
                section = True
                latex_parts.append(f"\subsection*{{{escaped_text}}}")
            elif level == 3:
                section = True
                latex_parts.append(f"\subsubsection*{{{escaped_text}}}")
            elif level == 4:
                section = True
                latex_parts.append(f"\paragraph*{{{escaped_text}}}")
            elif level == 5:
                section = True
                latex_parts.append(f"\subparagraph*{{{escaped_text}}}")
            else:
                latex_parts.append(escaped_text)

            i += 1
            continue

        if obj_type == "image":
            path = obj.get("img_path")
            caption = " ".join(obj.get("img_caption", []))
            column_width = r"\columnwidth" if column == "two" else r"0.65\columnwidth"
            latex_parts.append(
                "\\begin{figure}[htbp]\n"
                f"\centering\n"
                f"\includegraphics[width={column_width}, keepaspectratio]{{{path}}}\n"
                f"\caption*{{{escape_latex(caption)}}}\n"
                "\end{figure}"
            )
            i += 1
            continue

        if obj_type == "equation":
            equation = obj.get("text", "").strip().strip('$')
            latex_parts.append(f"\\begin{{equation}}{equation}\end{{equation}}")
            i += 1
            continue

        # if obj_type == "table":
        #     table_width = r"\\textwidth"
        #     caption = " ".join(obj.get("table_caption", []))
        #     foot_notes = obj.get("table_footnote", [])
        #     html_body = obj.get("table_body", "")
        #     table_latex = convert_html_table_to_latex(html_body)

        #     escaped_caption = escape_latex(caption)
        #     escaped_footnotes = [escape_latex(fn) for fn in foot_notes]

        #     tablenotes_block = ""
        #     if escaped_footnotes:
        #         tablenotes_block = (
        #             "\\begin{tablenotes}\n"
        #             "\\footnotesize\n"
        #             + "\n".join([f"\item {note}" for note in escaped_footnotes]) + "\n"
        #             "\end{tablenotes}\n"
        #         )

        #     latex_parts.append(
        #         "\\begin{table*}[t]\n"
        #         "\centering\n"
        #         "\\begin{threeparttable}\n"
        #         f"\caption*{{{escaped_caption}}}\n"
        #         f"{table_latex}\n"
        #         f"{tablenotes_block}"
        #         "\end{threeparttable}\n"
        #         "\end{table*}"
        #     )
        #     i += 1
        #     continue
        if obj_type == "table":
            caption = " ".join(obj.get("table_caption", []))
            html_body = obj.get("table_body", "")

            # === Extract row function ===
            def extract_rows(html: str) -> List[List[str]]:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                return [
                    [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    for tr in soup.find_all("tr")
                ]

            all_rows = extract_rows(html_body)
            col_count = len(all_rows[0]) if all_rows else 0
            j = i + 1

            while j < len(data):
                next_obj = data[j]
                if next_obj.get("type") != "table":
                    break

                next_caption = next_obj.get("table_caption", [])
                # next_footnotes = next_obj.get("table_footnote", [])
                next_body = next_obj.get("table_body", "")
                next_rows = extract_rows(next_body)

                if next_caption:
                    break  # treat as start of new logical table

                if not next_rows or len(next_rows[0]) != col_count:
                    break  # column mismatch

                all_rows.extend(next_rows)
                j += 1

            # Look at the last table in the merged range for footnotes
            last_footnotes = data[j - 1].get("table_footnote", [])
            escaped_footnotes = [escape_latex(fn) for fn in last_footnotes]

            # === Convert merged rows to HTML again ===
            merged_html = "<table>\n" + "\n".join(
                "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in all_rows
            ) + "\n</table>"

            table_latex = convert_html_table_to_latex(merged_html)
            escaped_caption = escape_latex(caption)

            tablenotes_block = ""
            if escaped_footnotes:
                tablenotes_block = (
                    "\\begin{tablenotes}\n"
                    "\\footnotesize\n"
                    + "\n".join([f"\item {note}" for note in escaped_footnotes]) + "\n"
                    "\end{tablenotes}\n"
                )

            latex_parts.append(
                "\\begin{table*}[t]\n"
                "\centering\n"
                "\\begin{threeparttable}\n"
                f"\caption*{{{escaped_caption}}}\n"
                f"{table_latex}\n"
                f"{tablenotes_block}"
                "\end{threeparttable}\n"
                "\end{table*}"
            )

            i = j  # skip all merged table chunks
            continue

        i += 1

    latex_parts.append(r"\FloatBarrier")
    latex_parts.append(r"\printbibliography")
    latex_parts.append(r"\end{document}")

    return "\n\n".join(latex_parts), references

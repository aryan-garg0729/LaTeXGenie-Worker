import re
import itertools
from bs4 import BeautifulSoup
from typing import List, Optional
from utils.broken_char import escape_latex


def html_table_to_2d_array(html: str) -> List[List[Optional[str]]]:
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

def array_to_latex(grid: List[List[Optional[str]]]) -> str:
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

def convert_html_table_to_latex(html: str) -> str:
    try:
        array = html_table_to_2d_array(html)
        return array_to_latex(array)
    except Exception as e:
        return f"\\begin{{verbatim}}\n{html}\n\\end{{verbatim}}"

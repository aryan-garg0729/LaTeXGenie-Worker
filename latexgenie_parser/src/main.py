import json
import argparse
from config import *
from latexgenie_parser.utils.logger import Logger
from latexgenie_parser.header_reference_genie.anystyleRef import get_bib_file
from latexgenie_parser.header_reference_genie.render_bib_map import citation_map
from latexgenie_parser.header_reference_genie.citegenie import fuzzy_match_citations
from latexgenie_parser.utils.broken_char import BROKEN_COMBINATIONS, replace_broken
from latexgenie_parser.src.tools.intelligent_doc_matcher import generate_header, generate_references
from latexgenie_parser.src.latex_generator.content_generator import json_to_latex
from latexgenie_parser.src.latex_generator.latex_template import generate_imports
from latexgenie_parser.utils.file_utils import copy_images, zip_output
from latexgenie_parser.src.tools.pdf_knowledge import convert_pdf

log = Logger.get_logger()

class LatexPipeline:
    def __init__(self, args):
        self.args = args
        self.log = Logger.get_logger()

    def run(self):
        try:
            success = convert_pdf()
            if not success:
                self.log.error("knowledge not extracted !!")
                return

            miner_data = self._load_knowledge_json()

            header, main_text_pointer = self._generate_header()

            latex_output, ref = json_to_latex(miner_data, self.args.column, main_text_pointer)

            references = self._generate_references(ref)
            get_bib_file(references)

            mapping = citation_map(OUTPUT_BIB)
            latex_output, citation_style = fuzzy_match_citations(latex_output, mapping, len(references), threshold=80)

            latex_imports = generate_imports(self.args.journal, self.args.column, citation_style=citation_style)
            latex_imports.append(header)

            final_latex = "\n".join(latex_imports) + "\n\n" + latex_output
            self._save_latex_output(final_latex)

            copy_images(INTERM_OUTPUT_IMAGES, OUTPUT_IMAGES_DIR)
            zip_output("output", GENIE_OUTPUT_ZIP)

        except Exception as e:
            self.log.error(f"An error occurred during the pipeline execution: {e}")

    def _load_knowledge_json(self):
        try:
            with open(KNOWLEDGE_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self.log.error(f"Knowledge JSON file not found: {KNOWLEDGE_JSON}")
            raise
        except json.JSONDecodeError as e:
            self.log.error(f"Error decoding JSON: {e}")
            raise

    def _generate_header(self):
        try:
            header, main_text_pointer = generate_header(
                journal_type=self.args.journal,
                pdf_path=ORIGINAL_PDF
            )
            return replace_broken(header, BROKEN_COMBINATIONS), main_text_pointer
        except Exception as e:
            self.log.error(f"Error in generate_headers: {e}")
            raise

    def _generate_references(self, ref):
        try:
            references = generate_references(ref, ORIGINAL_PDF)
            references = "\n".join(references)
            return replace_broken(references, BROKEN_COMBINATIONS)
        except Exception as e:
            self.log.error(f"Error in generate_references: {e}")
            raise

    def _save_latex_output(self, content):
        try:
            with open(OUTPUT_TEX, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            self.log.error(f"Error writing LaTeX output: {e}")
            raise

def handler(args):
    pipeline = LatexPipeline(args)
    pipeline.run()

def run_pipeline(pdf_path: str, column: str = "one", journal: str = "elsevier"):
    VALID_COLUMNS = {"one", "two"}
    VALID_JOURNALS = {"elsevier", "ieee", "ieee_thanks_journal"}

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
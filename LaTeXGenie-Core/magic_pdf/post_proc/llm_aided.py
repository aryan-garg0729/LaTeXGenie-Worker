# Copyright (c) Opendatalab. All rights reserved.
import json
from loguru import logger
from magic_pdf.dict2md.ocr_mkcontent import merge_para_with_text
import google.generativeai as genai
import ast


#@todo: Some formulas end with "\", which will cause the "$" at the end to be escaped, which also needs to be fixed
formula_optimize_prompt = """Please follow the guidelines below to correct errors in LaTeX formulas to ensure that the formulas can be rendered and match the original content:

1. Fix rendering or compilation errors:
    - Some syntax errors such as mismatched/missing/extra tokens. Your task is to fix these syntax errors and make sure corrected results conform to latex math syntax principles.
    - Errors that cannot be compiled or rendered due to reasons such as keywords not supported by KaTeX

2. Keep the original information:
   - Preserve all important information from the original formula
   - Do not add any new information that was not in the original formula

IMPORTANT: Please return only the corrected formula without any description, explanation or metadata.

LaTeX recognition result:
$FORMULA

Your corrected result:
"""

text_optimize_prompt = f"""Please follow the guidelines below to correct errors caused by OCR and ensure that the text is coherent and consistent with the original content:

1. Fix spelling errors and mistakes caused by OCR:
   - Fixed common OCR errors (e.g. 'rn' was misread as 'm')
   - Use context and common sense to make corrections
   - Only fix obvious errors, do not modify content unnecessarily
   - Do not add extra periods or other unnecessary punctuation

2. Keep the original structure:
   - Keep all titles and subtitles

3. Keep the original content:
   - Preserve all important information from the original text
   - Do not add any new information that was not in the original text
   - Preserve line breaks between paragraphs

4. Maintain consistency:
   - Ensure that the content is smoothly connected to the previous content
   - Properly handle text that starts or ends in the middle of a sentence
   
5. Modified internal formula:
   - Remove extra spaces before and after the formula in the line
   - Fixed OCR errors in formulas
   - Ensure that formulas can be rendered by KaTeX
   
6. Modified full-width symbols
    - Corrected full-width punctuation marks to half-width punctuation marks
    - Corrected full-width letters to half-width letters
    - Corrected full-width numbers to half-width numbers

IMPORTANT: Please return only the corrected text, preserving all original formatting including line breaks. Do not include any introduction, explanation, or metadata.

Previous context:

Current chunk to process:

Corrected text:
"""

def llm_aided_formula(pdf_info_dict, formula_aided_config):
    pass

def llm_aided_text(pdf_info_dict, text_aided_config):
    pass


def llm_aided_title(pdf_info_dict, title_aided_config):
    genai.configure(api_key=title_aided_config["api_key"])
    client = genai.GenerativeModel(title_aided_config["model"],generation_config={
        "temperature": 0.7, 
    })
    title_dict = {}
    origin_title_list = []
    i = 0
    for page_num, page in pdf_info_dict.items():
        blocks = page["para_blocks"]
        for block in blocks:
            if block["type"] == "title":
                origin_title_list.append(block)
                title_text = merge_para_with_text(block)
                page_line_height_list = []
                for line in block['lines']:
                    bbox = line['bbox']
                    page_line_height_list.append(int(bbox[3] - bbox[1]))
                if len(page_line_height_list) > 0:
                    line_avg_height = sum(page_line_height_list) / len(page_line_height_list)
                else:
                    line_avg_height = int(block['bbox'][3] - block['bbox'][1])
                title_dict[f"{i}"] = [title_text, line_avg_height, int(page_num[5:])+1]
                i += 1
    # logger.info(f"Title list: {title_dict}")

    title_optimize_prompt = f"""The input content is a dictionary consisting of all the titles in a document. Please optimize the title results according to the following guidelines so that the results conform to the hierarchy of a normal document:

1. Each value in the dictionary is a list containing the following elements:
    - Title text
    - The text line height is the average line height of the block containing the title
    - The page number where the title is located

2. Keep the original content:
    - All elements in the input dictionary are valid and no element in the dictionary can be deleted
    - Please make sure that the number of elements in the output dictionary is the same as the number of input elements.

3. Keep the key-value correspondence in the dictionary unchanged

4. Optimize the hierarchy:
    - Add proper hierarchy to each heading element
    - Headings with larger line heights are generally higher-level headings
    - The titles must be in a continuous sequence from the beginning to the end, and no levels can be skipped.
    - The maximum number of title levels is 4. Do not add too many levels.
    - The optimized title only retains the integer representing the level of the title, and does not retain other information
    
5. Reasonableness check and fine-tuning:
    - After completing the initial classification, carefully check the rationality of the classification results
    - Fine-tune unreasonable classifications based on context and logical order
    - Ensure that the final classification results are consistent with the actual structure and logic of the document
    - The dictionary may contain body text that is mistaken for a title. You can exclude them by marking them with a level of 0.
    
IMPORTANT: 
Please directly return the optimized dictionary consisting of title levels in the format of {{title id:title level}}, as follows:
{{0:1,1:2,2:2,3:3}}
There is no need to format the dictionary or return any other information.
Must output in plain text only. Example output:  {{0:1,1:2,2:2,3:3}} 
Outputs like ```python\n {{0:1,1:2,2:2,3:3}}``` or ```text\n {{0:1,1:2,2:2,3:3}}``` etc are not needed

Input title list:
{title_dict}

Corrected title list:
"""

    retry_count = 0
    max_retries = 3
    dict_completion = None

    while retry_count < max_retries:
        try:
            completion = client.generate_content(title_optimize_prompt)
            # print(f"Title completion git wali: {completion.text}")
            dict_completion = ast.literal_eval(completion.text)
            # logger.info(f"len(dict_completion): {len(dict_completion)}, len(title_dict): {len(title_dict)}")

            if len(dict_completion) == len(title_dict):
                for i, origin_title_block in enumerate(origin_title_list):
                    origin_title_block["level"] = int(dict_completion[i])
                break
            else:
                logger.warning("The number of titles in the optimized result is not equal to the number of titles in the input.")
                retry_count += 1
        except Exception as e:
            logger.exception(e)
            retry_count += 1

    if dict_completion is None:
        logger.error("Failed to decode dict after maximum retries.")



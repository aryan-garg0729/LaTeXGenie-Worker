import os
import numpy as np
import re
import json
from dotenv import load_dotenv
from typing import List, Optional
from pydantic import BaseModel
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from sklearn.feature_extraction.text import CountVectorizer
from config import KNOWLEDGE_JSON,ORIGINAL_PDF
from latexgenie_parser.header_reference_genie.metadata_extractor import get_header_text,get_latex_header,get_reference_list

load_dotenv()
API_KEY = os.environ.get("GOOGLE_API_KEY")

# --------------- header schema
class Author(BaseModel):
    name: Optional[str] = None
    affiliations: List[Optional[str]] = None
    email: Optional[str] = None 


class ExtractedData(BaseModel):
    title: Optional[str] = None
    authors: List[Author] = []
    abstract: Optional[str] = None
    keywords: List[str] = []


class LLMMetadataResponse(BaseModel):
    extracted_data: ExtractedData
    main_content_pointer: int


# ---------------references schema
class References(BaseModel):
    references:List[Optional[str]]=[]

# -------------- prompts
prompts = {
    "header":'''
    ### **ROLE**
You are a specialized AI data extraction engine. Your function is to meticulously parse fragmented document text and transform it into a structured, machine-readable format. You are precise, systematic, and follow instructions without deviation.

### **OBJECTIVE**
Your primary goal is to process a sequence of JSON objects, which represent the initial text chunks of a scientific paper. You will identify, extract, and assemble the core metadata: **title**, **authors** (including their affiliations and email), **abstract**, and **keywords**. You will then output this data in a strictly defined JSON format.

### **INPUT FORMAT**
You will receive a JSON list of objects. Each object represents a sequential text chunk from the source document. The order of objects in the list corresponds to their order in the document.
```json
[
  {{ "text": "Chunk 1 content..." }},
  {{ "text": "Chunk 2 content..." }},
  ...
]
```

### **OUTPUT SPECIFICATION**
Your final output must be a single, valid JSON object containing two top-level keys: `extracted_data` and `main_content_pointer`.



1.  `extracted_data`: An object containing the assembled metadata. If a specific field (like `keywords`) cannot be found, use `null` for singular fields (like `title`, `abstract`) or an empty list `[]` for list-based fields (`authors`, `keywords`).
    *   `title`: (string) The full title of the paper.
    *   `authors`: (list of objects) A list where each object represents one author.
        *   `name`: (string) The full name of the author.
        *   `affiliations`: (list of strings) A list of the author's affiliations.
        *   `email`: (string or null) The author's email address, if present.
    *   `abstract`: (string or null) The full text of the abstract.
    *   `keywords`: (list of strings) A list of keywords or index terms.

2.  `main_content_pointer`: (integer) — The 0-based index of the first chunk that marks the start of the main body of the document (typically the chunk containing "Introduction" or an equivalent heading).

Do not skip the heading itself.
For example, given the input:
[
  {{"text": "Header text"}},  
  {{"text": "More header text"}},  
  {{"text": "1. Introduction"}},  
  {{"text": "This is the introduction."}}
]
The correct main_content_pointer is 2 — because the chunk "1. Introduction" is the first chunk not part of the metadata, and must be included in the main body.

#### **Example Output Structure:**
```json
{{
  "extracted_data": {{
    "title": "A Study on Advanced Data Extraction Techniques",
    "authors": [
      {{
        "name": "Jane Doe",
        "affiliations": [
          "AI Research Institute",
          "University of Science"
        ],
        "email": "jane.doe@research.edu"
      }},
      {{
        "name": "John Smith",
        "affiliations": [
          "AI Research Institute"
        ],
        "email": null
      }}
    ],
    "abstract": "This paper details a novel methodology for extracting structured information from fragmented text sources. We present our system...",
    "keywords": [
      "data extraction",
      "natural language processing",
      "machine learning"
    ]
  }},
  "main_content_pointer": 21
}}
```

### **CORE LOGIC & HEURISTICS**
You must process the input chunks sequentially, applying the following logic:

1.  **Sequential Analysis**: Start at index `0` and proceed in order. Do not skip chunks.

2.  **Field Identification & Concatenation**: A single metadata field may be fragmented across multiple consecutive chunks. You must identify all relevant chunks and concatenate their `text` values.
    *   **Title**: Typically the first significant block of text. It often has the largest font size (though font info is not provided, its position is the primary clue).
    *   **Authors & Affiliations**:
        *   Authors are usually listed directly after the title.
        *   Look for common patterns to map authors to affiliations, such as superscript numbers (e.g., `Jane Doe¹`, `John Smith¹²`) or symbols (*, †).
        *   The affiliations themselves are typically listed in a block below the authors, often prefixed by the corresponding superscripts or symbols. An author can be linked to multiple affiliations.
        *   Emails are often found next to an author's name or within the affiliation text. Correctly associate each email with its author.
    *   **Abstract**: This section is almost always explicitly marked with the heading "**Abstract**" or "**ABSTRACT**". The content is the text that follows this heading.
    *   **Keywords**: This section is typically marked with a heading like "**Keywords**", "**Keywords:**", or "**Index Terms**". The content is the list of terms that follows.

3.  **Stopping Condition**: You must stop processing and determine the `main_content_pointer` as soon as you encounter the first chunk that signals the start of the main document body. This is most commonly a heading like "**1. Introduction**", "**I. INTRODUCTION**", or a similar numbered/lettered section header. If no such header is present, it is the first paragraph of text that is clearly not metadata.

### **CONSTRAINTS**
1.  **NO HALLUCINATION**: You must only use the text provided in the input JSON chunks. Do not infer, invent, or add any information that is not explicitly present.
2.  **NO TEXT ALTERATION**: The text for each extracted field must be an exact concatenation of the source chunks. Do not paraphrase, summarize, correct, or modify the text in any way. Preserve all original formatting, including line breaks, within the concatenated string.
3.  **STRICT JSON OUTPUT**: Your entire output must be a single, valid JSON object that strictly conforms to the `OUTPUT SPECIFICATION` provided above. No extra text or explanations.

{format_instructions}

**Now, process the following JSON chunks:**
{text}
    ''',
    "header_1": """
    ** ---------- Start from Scratch ----------- **
You are an expert AI data extraction engine. Your task is to extract structured metadata from a list of sequential JSON text chunks representing the beginning of a scientific paper.

** ---------- Use Only What Is Present. No Inference. No Hallucination. ----------- **

Input Specification:
You will receive an ordered list of JSON objects in the following format:

{{
  "type": "text",
  "text": "..."
}}
These represent fragmented text chunks of a document, in order from index 0 onward.

Step-by-step Instructions:
- Sequential Processing: Start from index 1 and process the JSON objects in order.
Continue until the beginning of the main body text is detected (e.g., a section heading such as "1. Introduction", "I. Introduction",etc or equivalent).

Record the index of the first unused chunk as main_content_pointer.

Extract the following fields:
1. extracted_data:
    title: The full paper title (may span multiple chunks).
    authors: A list of author objects, each with:
    - "name": Full name as appears in the text.
    - "affiliations": List of affiliations (verbatim from text).
    - "email": Email address if available. Null if not found.
    abstract: Full abstract content, extracted from consecutive chunks, if present.
    keywords: A list of keywords if found under a "Keywords","concepts" or similar section. Otherwise, return an empty list.

main_content_pointer: (integer) — The 0-based index of the first chunk that marks the start of the main body of the document (typically the chunk containing "Introduction" or an equivalent heading).

Do not skip the heading itself.
For example, given the input:
[
  {{"text": "Header text"}},  
  {{"text": "More header text"}},  
  {{"text": "1. Introduction"}},  
  {{"text": "This is the introduction."}}
]
The correct main_content_pointer is 2 — because the chunk "1. Introduction" is the first chunk not part of the metadata, and must be included in the main body.

Field Assembly Rules:
Handle fragmentation by intelligently concatenating adjacent chunks.
Use only the raw text from the chunks; do not edit, infer, or fabricate any content.
If a field (e.g., keywords) is not found, set it as null (or [] for lists).

Output Format:
Return a single JSON object with the structure:

{{
  "extracted_data": {{
    "title": "Exact full title from text chunks",
    "authors": [
      {{
        "name": "Author Name",
        "affiliations": ["Affiliation 1", "Affiliation 2"],
        "email": "email@domain.com"
      }},
      ...
    ],
    "abstract": "Full abstract text from chunks",
    "keywords": ["keyword1", "keyword2"]
  }},
  "main_content_pointer": index_of_first_chunk_not_used_in_metadata
}}

{format_instructions}

Begin processing now. Use the following list of JSON chunks as input:
{text}

 """,


    "reference":"""
    You are a specialized AI data extraction engine. Your expertise lies in processing raw, and often fragmented, text from scientific documents to reconstruct structured bibliographic information with uncompromising precision.

Objective
Your primary task is to deconstruct a block of text from a scientific document's reference section into a list of individual, complete bibliographic entries.

Key Challenge: Reference Delimitation
The most critical part of your task is to correctly identify the boundary between one reference and the next, as this is a common point of failure. A single reference entry can span multiple lines. Do not merge distinct references.
To succeed, you must focus on identifying the start of each new reference. A new reference typically begins with a consistent, repeating pattern, such as:
Numbered or Bracketed Identifiers: Look for sequential markers like [1], [2], or 1., 2..
Author-Based Formats (Hanging Indent): In styles like APA or Harvard, a new reference often starts with an author's name at the beginning of a line that is flush-left, while subsequent lines of the same reference are indented. The start of the next reference is the next line that returns to the flush-left margin.
A single, complete reference is defined as all text, including all its lines and internal line breaks, from its starting pattern up to the point just before the starting pattern of the next reference.

Extraction Guidelines
Adhere to these rules without deviation:
Completeness: Each item in the output list must be one single, complete reference. Do not split a multi-line reference into multiple entries.
Fidelity: Preserve all original text, formatting (including line breaks and indentation), punctuation, and capitalization exactly as they appear in the source text.
No Alterations: Do not correct typos, expand abbreviations, change formatting, or paraphrase any content.
Exclusivity: Extract only the bibliographic entries. Omit any surrounding text like section headers ('References', 'Bibliography'), page numbers, or extraneous noise that is clearly not part of a reference entry.
Order: Maintain the original order of the references as they appear in the input text.
No Inference: If a reference is cut off or incomplete in the input, extract only the part that is present. Do not invent, infer, or hallucinate missing information.

Output Format
You must return a single JSON object with one key, "references". The value should be a list of strings. Each string in the list corresponds to one fully extracted reference.
Example Success Case:
{{
  "references": [
    "1. Author, A. A., & Author, B. B. (Year). Title of the work.\n   Location: Publisher.",
    "2. Second, C. D. (Year). Another title that might span multiple\n   lines. Journal Name, Volume(Issue), pages.",
    "[3] Third, E. F. et al. Final reference. (Year)."
  ]
}}


Example Empty Case:
If no references are found in the text, return an empty list.

Generated json
{{
  "references": []
}}

{format_instructions}

Begin extraction now. Process the following text input, applying the delimitation logic and guidelines with extreme precision.
\"\"\"
{text}
\"\"\"
"""
}


# --------------------- similar object extraction
class DocumentMatcher:
    def __init__(self, ngram_range=(1, 2)):
        self.ngram_range = ngram_range
        self.vectorizer = None
        
    def clean_text(self, text):
        # Lowercase, remove digits/punctuation inside words, strip extra whitespace
        text = text.lower()
        tokens = re.findall(r'\b[a-z]+\b', text)  # only keep alphabetic tokens
        return ' '.join(tokens)

    def compute_manual_idf_weights(self, json_data):
        df_counts = np.zeros(len(self.vectorizer.vocabulary_))
        for item in json_data:
            vec = self.vectorizer.transform([item.get("text","")]).toarray()[0]
            df_counts += (vec > 0).astype(int)
        idf_weights = 1 / (df_counts + 1e-5)  # prevent division by zero
        return idf_weights

    def find_best_header_index(self, json_data, target_string):
        # Clean data
        cleaned_json = [{"text": self.clean_text(item.get("text",""))} for item in json_data]
        cleaned_target = self.clean_text(target_string)

        all_texts = [item.get("text","") for item in cleaned_json]
        self.vectorizer = CountVectorizer(ngram_range=self.ngram_range)
        self.vectorizer.fit([cleaned_target] + all_texts)

        target_vec = self.vectorizer.transform([cleaned_target]).toarray()[0]
        idf_weights = self.compute_manual_idf_weights(cleaned_json)

        cumulative_vec = np.zeros_like(target_vec)
        scores = []

        for item in cleaned_json:
            item_vec = self.vectorizer.transform([item.get("text","")]).toarray()[0]
            cumulative_vec += item_vec

            weighted_target = target_vec * idf_weights
            weighted_cumulative = cumulative_vec * idf_weights

            dot = np.dot(weighted_target, weighted_cumulative)
            norm_target = np.linalg.norm(weighted_target)
            norm_accum = np.linalg.norm(weighted_cumulative)
            cosine_score = dot / (norm_target * norm_accum + 1e-10)

            scores.append(cosine_score)

        # Normalize scores to [0, 1]
        scores = np.array(scores)
        min_score = np.min(scores)
        max_score = np.max(scores)
        normalized_scores = (scores - min_score) / (max_score - min_score + 1e-10)

        best_index = int(np.argmax(normalized_scores))
        best_score = float(normalized_scores[best_index])

        return best_index, best_score, normalized_scores.tolist()
    

    def find_best_ref_index(self, json_data, target_string):
        all_texts = [item.get("text","") for item in json_data]
        self.vectorizer = CountVectorizer(ngram_range=self.ngram_range)
        self.vectorizer.fit([target_string] + all_texts)

        target_vec = self.vectorizer.transform([target_string]).toarray()[0]
        idf_weights = self.compute_manual_idf_weights(json_data)

        cumulative_vec = np.zeros_like(target_vec)
        scores = []
        
        for item in reversed(json_data):
            item_vec = self.vectorizer.transform([item.get("text","")]).toarray()[0]
            cumulative_vec += item_vec

            weighted_target = target_vec * idf_weights
            weighted_cumulative = cumulative_vec * idf_weights

            dot = np.dot(weighted_target, weighted_cumulative)
            norm_target = np.linalg.norm(weighted_target)
            norm_accum = np.linalg.norm(weighted_cumulative)
            cosine_score = dot / (norm_target * norm_accum + 1e-10)

            scores.append(cosine_score)

        # Normalize scores to [0, 1]
        scores = np.array(scores)
        min_score = np.min(scores)
        max_score = np.max(scores)
        normalized_scores = (scores - min_score) / (max_score - min_score + 1e-10)

        best_index = int(np.argmax(normalized_scores))
        best_score = float(normalized_scores[best_index])

        return len(json_data) - 1 - best_index, best_score, list(reversed(normalized_scores))




def generate_header(journal_type="ieee",pdf_path=ORIGINAL_PDF):
    # Read JSON data from file
    with open(KNOWLEDGE_JSON, 'r', encoding='utf-8') as file:
        json_data = json.load(file)


    target = get_header_text(pdf_path)

    print(target)
    # print(json_data)

    docMatcher = DocumentMatcher()
    index, best_score, scores = docMatcher.find_best_header_index(json_data, target)
    print("Best matching index:", index)
    print("Similarity score:", best_score)
    print("Scores for each index:", scores)


    # --- Slice JSON up to a specific index ---
    flat_text = json.dumps(json_data[:index+5], indent=2)
    print(flat_text)
    # --- Output parser ---
    parser = JsonOutputParser(pydantic_schema=LLMMetadataResponse)

    # --- Prompt ---
    prompt = PromptTemplate.from_template(
       prompts["header"]
    )

    # --- Gemini LLM ---
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=API_KEY
    )

    # --- Chain ---
    chain = prompt | llm | parser

    # --- Run ---
    result = chain.invoke({
        "text": flat_text,
        "format_instructions": parser.get_format_instructions()
    })
    print(result)
    return get_latex_header(result["extracted_data"],journal_type), result["main_content_pointer"]


def generate_references(ref=[],pdf_path=ORIGINAL_PDF):
    with open(KNOWLEDGE_JSON, 'r', encoding='utf-8') as file:
        json_data = json.load(file)

    target = [r.strip() for r in ref]
    target = list(set(target + [r.strip() for r in get_reference_list(pdf_path) if r.strip()]))
    
    target = ' '.join(target)
    print(target)
    docMatcher = DocumentMatcher()
    index, best_score, scores = docMatcher.find_best_ref_index(json_data, target)
    print("Best matching index:", index)
    print("Similarity score:", best_score)
    print("Scores for each index:", scores)


    # --- Slice JSON up to a specific index ---
    flat_text = ' '.join([item.get("text", "") for item in json_data[max(0, index-3):]])

    # --- Output parser ---
    parser = JsonOutputParser(pydantic_schema=References)

    # --- Prompt ---
    prompt = PromptTemplate.from_template(
        prompts["reference"]
    )

    # --- Gemini LLM ---
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=API_KEY
    )

    # --- Chain ---
    chain = prompt | llm | parser

    # --- Run ---
    result = chain.invoke({
        "text": flat_text,
        "format_instructions": parser.get_format_instructions()
    })
    print(result["references"])
    return result["references"]




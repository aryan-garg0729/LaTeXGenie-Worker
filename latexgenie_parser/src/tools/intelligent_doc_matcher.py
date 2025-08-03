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
    "header": """
    ROLE:
    You are an expert AI data extraction engine. Your specialty is processing fragmented document data and structuring it into a coherent format. You are precise, methodical, and strictly follow instructions.

    TASK:
    You will be given a list of JSON objects, which represent sequential chunks of a document's text. Your task is to analyze these chunks from the beginning to identify and extract the core metadata of a scientific paper: title, {{authors, affiliations, email with direct index mapping}}, abstract, and keywords.

    A single piece of information (like the title or a list of authors) may be fragmented across multiple consecutive JSON objects. You must intelligently identify all the chunks that constitute a single field and concatenate their text content.

    You must process the objects sequentially starting from index 0. Once you have identified all the metadata and have reached the main body of the text (e.g., a section like "1. Introduction"), you should stop processing.

    Your final output must be a single JSON object containing two main keys:

    extracted_data: An object containing the assembled metadata containing all data from used objects.

    main_content_pointer: An integer representing the index of object from where main content starts or end of list (starting from 0).

    RULES AND CONSTRAINTS:

    NO HALLUCINATION: You must only use the text provided in the input JSON chunks. If a field (e.g., keywords) is not present, you must use null or an empty list ([]) for that key in your output. Do not invent any information.

    NO TEXT ALTERATION: The text for each field must be an exact concatenation of the text from the source chunks. Do not paraphrase, summarize, correct, or change the text in any way.

    USE ALL RELEVANT CHUNKS: You must process chunks from index 0 up to the point where the metadata ends. Do not skip any chunks in this range. The last_used_index must be the final index you drew information from.

    HANDLE FRAGMENTATION: Correctly identify and merge text from multiple consecutive objects to form complete fields. For example, if the title is split between objects at index 0 and 1, your title field should be the combined text of both.

    STRUCTURED OUTPUT: Your final output must be a single, valid JSON object following the specified format precisely.
    sample:{{
            "extracted_data": {{
                "title": "Machine Learning Approaches for Natural Language Processing",
                "authors": [
                    {{
                        "name": "John Smith",
                        "affiliations": ["Department of Computer Science", "University of Technology"],
                        "email": "john.smith@university.edu"
                    }},
                ],
                "abstract": "This paper presents novel approaches to natural language processing using advanced machine learning techniques...",
                "keywords": ["machine learning", "natural language processing"]
            }},
            "main_content_pointer": 15
        }}

    {format_instructions}

    Now, process the following JSON chunks:
    {text}
    """,
    "reference":"""
    ROLE:
    You are an expert AI data extraction engine. Your specialty is processing fragmented document data and structuring it into a coherent format. You are precise, methodical, and strictly follow instructions.

    TASK:
    You will be given a list of JSON objects, which represent sequential chunks of a document's text. Your task is to analyze these chunks from the beginning to identify and extract the references and biblographic text of a scientific paper.

    A single reference may be fragmented across multiple consecutive JSON objects. You must intelligently identify all the chunks that constitute a single field and concatenate their text content.

    Your final output must be a single JSON object containing:
    references: A list containing the references **with each reference as separated**.


    RULES AND CONSTRAINTS:

    NO HALLUCINATION: You must only use the text provided in the input JSON chunks.references are not present, you must return empty list ([]) for that key in your output. Do not invent any information.

    NO TEXT ALTERATION: The text for each field must be an exact concatenation of the text from the source chunks. Do not paraphrase, summarize, correct, or change the text in any way.

    HANDLE FRAGMENTATION: Correctly identify and merge text from multiple consecutive objects to form complete fields. For example, if a reference is split between objects at index 0 and 1, your reference item should be the combined text of both.

    STRUCTURED OUTPUT: Your final output must be a single, valid JSON object following the specified format precisely.

    {format_instructions}

    Now, process the following JSON chunks:
    {text}
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

    docMatcher = DocumentMatcher()
    index, best_score, scores = docMatcher.find_best_header_index(json_data, target)
    print("Best matching index:", index)
    print("Similarity score:", best_score)
    print("Scores for each index:", scores)


    # --- Slice JSON up to a specific index ---
    flat_text = json.dumps(json_data[:index+5], indent=2)

    # --- Output parser ---
    parser = JsonOutputParser(pydantic_schema=LLMMetadataResponse)

    # --- Prompt ---
    prompt = PromptTemplate.from_template(
       prompts["header"]
    )

    # --- Gemini LLM ---
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=API_KEY,
        temperature=0
    )

    # --- Chain ---
    chain = prompt | llm | parser

    # --- Run ---
    result = chain.invoke({
        "text": flat_text,
        "format_instructions": parser.get_format_instructions()
    })
    print(result["extracted_data"])
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
    flat_text = json.dumps(json_data[max(0, index-3):], indent=2)

    # --- Output parser ---
    parser = JsonOutputParser(pydantic_schema=References)

    # --- Prompt ---
    prompt = PromptTemplate.from_template(
        prompts["reference"]
    )

    # --- Gemini LLM ---
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=API_KEY,
        temperature=0
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



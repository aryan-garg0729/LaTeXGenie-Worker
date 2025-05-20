
import requests
import re
import json
import nltk
import random
from tqdm import tqdm
from nltk.tokenize import sent_tokenize, word_tokenize
from urllib.parse import quote

# Uncomment this once if needed
# nltk.download("punkt")

# === CONFIG ===
GITHUB_TOKEN = "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"  # Add your GitHub token here
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
TOPICS = ["latex","machine-learning","algorithm","web development"]
OUT_PATH = "github_md_dataset.jsonl"
NUM_REPOS = 4

def search_repos(topic, per_page=50):
    repos = []
    for page in range(1, 4):
        url = (
            f"https://api.github.com/search/repositories?q=topic:{quote(topic)}"
            f"&sort=stars&order=desc&per_page={per_page}&page={page}"
        )
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print(f"❌ GitHub API error ({resp.status_code}): {resp.text}")
            continue
        data = resp.json()
        for item in data.get("items", []):
            repos.append((item["full_name"], item["default_branch"]))
    return repos

def fetch_readme(repo_full_name, branch="main"):
    url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch}/README.md"
    resp = requests.get(url)
    return resp.text if resp.status_code == 200 else ""

def extract_sentences_and_code(text):
    pattern = r"```"
    parts = re.split(pattern, text)
    flattened = []

    for i in range(0, len(parts), 2):
        normal_text = parts[i]
        sentences = sent_tokenize(normal_text)
        for sent in sentences:
            tokens = word_tokenize(sent)
            if tokens:
                flattened.extend(zip(tokens, ['O'] * len(tokens)))

        if i + 1 < len(parts):
            code = parts[i + 1]
            code_tokens = word_tokenize(code)
            if code_tokens:
                labels = ['B-CODE'] + ['I-CODE'] * (len(code_tokens) - 1)
                flattened.extend(zip(code_tokens, labels))

    if not flattened:
        return None

    # Create valid chunks
    chunks = []
    i = 0
    while i < len(flattened):
        chunk_len = random.randint(32, 512)
        chunk = flattened[i:i + chunk_len]
        i += chunk_len

        label_counts = {"O": 0, "B-CODE": 0, "I-CODE": 0}
        for _, label in chunk:
            if label in label_counts:
                label_counts[label] += 1

        code_total = label_counts["B-CODE"] + label_counts["I-CODE"]
        if code_total > 0 and label_counts["O"] <= 40 * code_total:
            tokens, labels = zip(*chunk)
            chunks.append({"tokens": list(tokens), "labels": list(labels)})

    return chunks if chunks else None

# === Main Scraping ===
all_data = []
repos = []
for topic in TOPICS:
    repos.extend(search_repos(topic))

repos = repos[:NUM_REPOS]
print(f"🔍 Found {len(repos)} repos.")
print(repos)

for repo_full_name, branch in tqdm(repos, desc="🔽 Scraping repos"):
    try:
        md = fetch_readme(repo_full_name, branch)
        if len(md) > 500:
            examples = extract_sentences_and_code(md)
            if examples:
                all_data.extend(examples)
    except Exception as e:
        print(f"⚠️ Error fetching {repo_full_name}: {e}")

# === Save to JSONL ===
with open(OUT_PATH, "w", encoding="utf-8") as f:
    for example in all_data:
        json.dump(example, f)
        f.write("\n")

print(f"✅ Saved {len(all_data)} filtered examples to {OUT_PATH}")

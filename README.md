# LaTeXGenie

**High-fidelity PDF → LaTeX conversion for academic papers.**

LaTeXGenie converts scientific PDFs into clean, editable LaTeX — preserving equations, tables, figures, section hierarchy, footnotes, captions, and citations. Unlike most converters, it doesn't stop at the text: it generates a real `.bib` file, rewrites in-text citations as `\cite{}` / `\parencite{}` commands, and can emit output in IEEE or Elsevier journal formats.

---

## Why

Commercial tools like Mathpix produce accurate math OCR but leave the rest of the document flat — references become plain text, captions lose their `\caption{}` tags, footnotes get inlined, and there's no support for journal templates or double-column layouts. Open-source alternatives generally struggle with complex tables and document structure.

LaTeXGenie targets the parts other tools skip, at a price point that works for students and independent researchers.

### Feature comparison

| Feature | LaTeXGenie | Mathpix |
|---|:---:|:---:|
| Bibliography (`.bib`) generation | ✅ | ❌ |
| In-text citations (IEEE, APA, MLA, Harvard, Chicago) | ✅ | ❌ |
| One / two column layout option | ✅ | ❌ |
| IEEE / Elsevier journal templates | ✅ | ❌ |
| Caption & footnote detection and placement | ✅ | ❌ |
| Title, author, affiliation detection | Better | Fair |
| Table parsing | Comparable | Comparable |
| Algorithm / pseudocode detection | ❌ | ✅ |
| List detection | ❌ | ✅ |
| Text formatting (bold, italic, underline) | ❌ | ✅ |

The last three rows are honest gaps — see [Roadmap](#roadmap).

---

## How it works

### Architecture

```
                  ┌───────────┐
   PDF ──────────▶│  Frontend │──── upload ────▶ ┌───────────┐
                  └─────┬─────┘                  │ S3 Bucket │
                        │ job request            └─────┬─────┘
                        ▼                              │
                  ┌───────────┐   job    ┌──────────┐  │ get_pdf
                  │  Backend  │─────────▶│  Redis   │  │
                  └─────┬─────┘          │  Queue   │  │
                        │                └────┬─────┘  │
                  ┌─────▼─────┐               │        │
                  │ PostgreSQL│          ┌────▼────────▼────┐
                  └───────────┘          │  Worker pool     │
                        ▲                │  (stateless)     │
                        │  pub/sub ──────┴──────────────────┘
                  Socket.IO → frontend            │ upload_zip
                                                  ▼
                                            output.zip (.tex,
                                            images, .bib)
```

- **Frontend** — upload, auth, credit usage, live job status.
- **Backend** — issues `job_id`, writes metadata, pushes to the queue, listens for completion over pub/sub and pushes updates to the client via Socket.IO.
- **Redis queue** — load balancing, retry-on-failure, FIFO ordering, visibility timeouts, priority jobs.
- **Workers** — stateless and idempotent, so they scale horizontally. Each pulls a job, runs the full pipeline, and uploads a ZIP.
- **PostgreSQL** — user activity, credits, job status, durations, errors.

Because workers are stateless and compute is isolated per document, the system parallelizes at the document level and the frontend never blocks on processing.

### Processing pipeline

1. **Layout detection** — a custom-trained DocLayout-YOLO model segments each page into headings, paragraphs, tables, figures, equations, and metadata regions. Reading order is inferred from bounding boxes using document flow, indentation, and column structure.
2. **OCR & glyph recovery** — PaddleOCR handles scanned and image-based PDFs, with a curated set of 3,400+ special and diacritical characters for normalization. Character-level boxes and confidence scores are aligned back to the layout blocks.
3. **Specialized extraction** — equations go to **EquationGenie** (neural math OCR → LaTeX math syntax, inline and display); tables go to **StructEq-Table** / **RapidTable** (rule-based cell detection + neural classification → HTML); figures are cropped and exported as assets.
4. **Metadata & bibliography** — **GROBID** parses front matter into TEI XML; **Anystyle** parses the bibliography into structured entries.
5. **Citation linking** — the bibliography becomes a `.bib` file, a citation map is rendered with pandoc, and a hybrid strategy (regex for citation patterns + fuzzy author/title matching) injects `\cite{}` / `\parencite{}` into the text.
6. **Heading hierarchy** — an LLM-aided classifier assigns `\section` / `\subsection` / `\paragraph` from content, font size, position, and layout proximity.
7. **JSON assembly** — everything is unified into a document-level JSON that captures reading order plus semantic annotations. This is the source of truth.
8. **LaTeX generation** — the JSON is traversed and rendered into the right environments (`equation`, `align`, `tabular` with `\multirow` / `\multicolumn`, `figure`, `table`), then adapted to the chosen journal style and column count.

---

## Requirements

| | Recommended | Minimum |
|---|---|---|
| GPU | 6 GB+ VRAM (RTX 3060 or better) | None — CPU-only works |
| RAM | 16 GB | 16 GB |
| CPU | Modern multi-core | Modern multi-core |

CPU-only mode is fully functional; only speed degrades. Runs on Linux, macOS, and Windows.

---

## Roadmap

- **Code & algorithm detection** — sequence tagging and layout-aware models to segment prose from pseudocode and source, rendered as `algorithm` / `lstlisting`.
- **List identification** — reconstruct itemized and enumerated lists with correct indentation and markers.
- **Citation disambiguation** — stronger in-text ↔ bibliography linkage for ambiguous or unconventional reference formats.
- **Text formatting** — font-style recognition for bold, italic, and underline.
- **Diacritical coverage** — extend beyond the current 3,400+ characters, especially for non-English text and specialized notation.
- **Table parsing** — nested tables, rotated headers, multi-line cells, irregular spans.
- **Resource optimization** — GPU batching, model pruning, parallel job handling.
- **Beyond papers** — scanned books, forms, technical manuals.

---

## Known limitations

- No dedicated handling for algorithm/code environments or lists.
- Inline text formatting (bold, italic, underline) is not preserved.
- Handwritten and heavily noisy scans are not well supported.
- Roughly 5% of references need manual verification; BibTeX coverage is around 95%.

---

## Acknowledgements

Built as a B.Tech final-year project at Netaji Subhas University of Technology, Delhi, under the supervision of Dr. Vijay Kumar Bohat.

**Team:** Aryan Garg · Piyush · Aakshat Malhotra

Evaluated against [Im2LaTeX-100K](https://zenodo.org/record/56198) and real-world arXiv papers. Built on the work of [GROBID](https://github.com/kermitt2/grobid), [Anystyle](https://anystyle.io/), [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), [StructEqTable](https://huggingface.co/U4R/StructTable-base), and [DocLayout-YOLO](https://arxiv.org/abs/2204.08387).


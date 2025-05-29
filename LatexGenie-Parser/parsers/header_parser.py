# docker run -d --rm -p 8070:8070 lfoppiano/grobid:latest-crf
# curl -v --form input=@path http://localhost:8070/api/processFulltextDocument > structure_output.xml

from lxml import etree
import subprocess
import requests
import os
import time
import shutil
import json
from src.logger import Logger

log = Logger.get_logger()

CONTAINER_NAME = "grobid-server"

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

    for key, value in replacements.items():
        text = text.replace(key, value)
    return text
def extract_paper_metadata(xml_file_path):
    result = {
        'title': None,
        'abstract': None,
        'keywords': None,
        'authors': []
    }

    try:
        tree = etree.parse(xml_file_path)
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
    except Exception as e:
        print(f"[XML Parse Error] {e}")
        return result

    # Title extraction
    try:
        title_paths = [
            '//tei:teiHeader//tei:title[@type="main"]/text()',
            '//tei:title[1]/text()',
            '//tei:title/text()'
        ]
        for path in title_paths:
            title_text = tree.xpath(path, namespaces=ns)
            if title_text:
                result['title'] = title_text[0].strip()
                break
    except Exception as e:
        print(f"[Title Extraction Error] {e}")

    # Abstract extraction
    try:
        abstract_paths = [
            '//tei:teiHeader//tei:profileDesc/tei:abstract//text()',
            '//tei:abstract//text()',
            '//tei:div[@type="abstract"]//text()',
        ]
        for path in abstract_paths:
            abstract_text = tree.xpath(path, namespaces=ns)
            if abstract_text:
                result['abstract'] = ' '.join([escape_latex(t.strip()) for t in abstract_text if t.strip()])
                break
    except Exception as e:
        print(f"[Abstract Extraction Error] {e}")

    # Keyword extraction
    try:
        keyword_paths = [
            '//tei:teiHeader//tei:profileDesc/tei:textClass/tei:keywords/tei:term/text()',
            '//tei:keywords/tei:term/text()',
            '//tei:term/text()',
            '//tei:div[@type="keywords"]//tei:item/text()'
        ]
        for path in keyword_paths:
            keyword_text = tree.xpath(path, namespaces=ns)
            if keyword_text:
                result['keywords'] = [escape_latex(kw.strip()) for kw in keyword_text if kw.strip()]
                break
    except Exception as e:
        print(f"[Keyword Extraction Error] {e}")

    # Author extraction
    try:
        author_paths = [
            '//tei:teiHeader//tei:sourceDesc/tei:biblStruct/tei:analytic/tei:author',
            '//tei:respStmt/tei:name'
        ]
        for path in author_paths:
            author_elems = tree.xpath(path, namespaces=ns)
            if author_elems:
                for author_elem in author_elems:
                    try:
                        # Name extraction
                        name_parts = []
                        name_paths = [
                            './/tei:persName//tei:forename/text() | .//tei:persName//tei:surname/text()',
                            './/tei:name//text()',
                            './text()'
                        ]
                        for name_path in name_paths:
                            parts = author_elem.xpath(name_path, namespaces=ns)
                            if parts:
                                name_parts = [p.strip() for p in parts]
                                break
                        name = ' '.join(name_parts) if name_parts else None

                        # Email extraction
                        email = None
                        email_paths = [
                            './/tei:email/text()',
                            './/tei:addrLine[@type="email"]/text()',
                            './/tei:note[@type="email"]/text()'
                        ]
                        for email_path in email_paths:
                            email_text = author_elem.xpath(email_path, namespaces=ns)
                            if email_text:
                                email = email_text[0].strip()
                                break

                        # Affiliation extraction
                        affiliations = []
                        aff_paths = [
                            './/tei:affiliation',
                            './/tei:note[@type="affiliation"]',
                            './/tei:orgName/..'
                        ]
                        for aff_path in aff_paths:
                            aff_elems = author_elem.xpath(aff_path, namespaces=ns)
                            if aff_elems:
                                for aff_elem in aff_elems:
                                    aff_text = [escape_latex(t.strip()) for t in aff_elem.xpath('.//text()') if t.strip()]
                                    if aff_text:
                                        affiliations.append(' '.join(aff_text))
                                break

                        if name:
                            author_data = {
                                'name': escape_latex(name),
                                'email': escape_latex(email) if email else None,
                                'affiliations': affiliations if affiliations else None
                            }
                            result['authors'].append({k: v for k, v in author_data.items() if v is not None})
                    except Exception as e:
                        print(f"[Author Element Extraction Error] {e}")
                break
    except Exception as e:
        print(f"[Author Block Extraction Error] {e}")

    return result
def generate_elsevier_latex_header(metadata):
    latex_lines = []
    
    # Begin frontmatter
    latex_lines.append(r"\begin{frontmatter}")
    latex_lines.append("")
    
    # Add title
    if metadata.get('title'):
        latex_lines.append(r"\title{" + metadata['title'] + "}")
        latex_lines.append("")
    
    # Process authors and affiliations
    if metadata.get('authors'):
        aff_mapping = {}  # To map affiliations to numbers
        current_aff_num = 1
        
        # First pass to collect all unique affiliations
        all_affiliations = []
        for author in metadata['authors']:
            if 'affiliations' in author:
                for aff in author['affiliations']:
                    if aff not in all_affiliations:
                        all_affiliations.append(aff)
        
        # Create affiliation mapping
        aff_mapping = {aff: i+1 for i, aff in enumerate(all_affiliations)}
        
        # Add authors with their affiliation numbers
        for author in metadata['authors']:
            name = author.get('name', '')
            email = author.get('email', '')
            
            if 'affiliations' in author:
                aff_numbers = sorted(list(set([aff_mapping[aff] for aff in author['affiliations']])))
                aff_str = f"[{','.join(map(str, aff_numbers))}]"
            else:
                aff_str = ""
            
            email_part = rf"\textit{{{email}}}" if email else ""
            latex_lines.append(rf"\author{aff_str}{{\\ {name} {email_part}}}")
        
        latex_lines.append("")
        
        # Add address commands
        for aff, num in aff_mapping.items():
            latex_lines.append(rf"\address[{num}]{{{aff}}}")
        
        latex_lines.append("")
    
    # Add abstract
    if metadata.get('abstract'):
        latex_lines.append(r"\begin{abstract}")
        latex_lines.append(metadata['abstract'])
        latex_lines.append(r"\end{abstract}")
        latex_lines.append("")
    
    # Add keywords
    if metadata.get('keywords'):
        latex_lines.append(r"\begin{keyword}")
        latex_lines.append("    " + ", ".join(metadata['keywords']) + ".")
        latex_lines.append(r"\end{keyword}")
        latex_lines.append("")
    
    # End frontmatter
    latex_lines.append(r"\end{frontmatter}")
    
    return "\n".join(latex_lines)

def generate_ieee_latex_header(metadata):
    latex_lines = []
    
    # Add title with IEEE-specific formatting
    if metadata.get('title'):
        title = metadata['title']
        latex_lines.append(r"\title{" + title + r"}")
        latex_lines.append("")
    
    # Process authors and affiliations
    if metadata.get('authors'):
        # First pass: assign unique numbers to affiliations and collect author info
        aff_counter = 1
        aff_mapping = {}  # {affiliation_text: ref_number}
        author_entries = []
        aff_entries = {}
        
        for author in metadata['authors']:
            name = author.get('name', '')
            email = author.get('email', '')
            affiliations = author.get('affiliations', [])
            
            # Assign reference numbers to affiliations
            ref_numbers = []
            for aff in affiliations:
                if aff not in aff_mapping:
                    aff_mapping[aff] = aff_counter
                    aff_counter += 1
                ref_numbers.append(str(aff_mapping[aff]))
                
                # Collect affiliation entries
                if aff_mapping[aff] not in aff_entries:
                    aff_entries[aff_mapping[aff]] = {
                        'text': aff,
                        'emails': []
                    }
                if email:
                    aff_entries[aff_mapping[aff]]['emails'].append(email)
            
            # Create author entry with refmarks
            author_entry = name
            if ref_numbers:
                author_entry += ''.join([r'\IEEEauthorrefmark{' + n + '}' for n in ref_numbers])
            author_entries.append(author_entry)
        
        # Build author block
        latex_lines.append(r"\author{")
        latex_lines.append(r"\IEEEauthorblockN{")
        latex_lines.append(",\n".join(author_entries))
        latex_lines.append("}")
        latex_lines.append("")
        
        # Build affiliation blocks
        for ref_num, data in sorted(aff_entries.items()):
            aff_text = data['text']
            emails = data['emails']
            
            latex_lines.append(r"\IEEEauthorblockA{\IEEEauthorrefmark{" + str(ref_num) + "}" + aff_text)
            if emails:
                latex_lines.append(r"\\Email: " + ", ".join(emails))
            latex_lines.append("}")
            latex_lines.append("")
        
        latex_lines.append("}")
        latex_lines.append("")
    
    # Add \maketitle command
    latex_lines.append(r"\maketitle")
    latex_lines.append("")
    
    # Add abstract
    if metadata.get('abstract'):
        latex_lines.append(r"\begin{abstract}")
        latex_lines.append(metadata['abstract'])
        latex_lines.append(r"\end{abstract}")
        latex_lines.append("")
    
    # Add keywords
    if metadata.get('keywords'):
        latex_lines.append(r"\begin{IEEEkeywords}")
        latex_lines.append(', '.join(metadata['keywords']))
        latex_lines.append(r"\end{IEEEkeywords}")
        latex_lines.append("")
    
    return "\n".join(latex_lines)

def generate_ieee_latex_header_thanks_journal(metadata):
    latex_lines = []
    
    # Add title with IEEE-specific formatting
    if metadata.get('title'):
        title = metadata['title']
        latex_lines.append(r"\title{" + title + r"}")
        latex_lines.append("")
    
    # Process authors in the requested format
    if metadata.get('authors'):
        # Create author list
        author_names = []
        for author in metadata['authors']:
            name = author.get('name', '')
            if name:
                author_names.append(name)
        
        # Format author list with "and" before last author
        if len(author_names) > 1:
            author_list = ", ".join(author_names[:-1]) + ",\n        and " + author_names[-1]
        else:
            author_list = author_names[0] if author_names else ""
        
        latex_lines.append(r"\author{" + author_list)
        
        # Create thanks notes for each author
        for author in metadata['authors']:
            name = author.get('name', '')
            email = author.get('email', '')
            affiliations = author.get('affiliations', [])
            
            if name and affiliations:
                # Format affiliation text
                aff_text = affiliations[0]  # Use first affiliation
                
                # Handle "also affiliated with" cases
                if len(affiliations) > 1:
                    aff_text += " and also affiliated with " + ", ".join(affiliations[1:])
                
                # Build thanks note
                thanks_note = f"{name} is with {aff_text}"
                if email:
                    thanks_note += f" (email: {email})"
                thanks_note += "."
                
                latex_lines.append(r"\thanks{" + thanks_note + "}%")
        
        latex_lines.append("}")
        latex_lines.append("")
    
    # Add \maketitle command
    latex_lines.append(r"\maketitle")
    latex_lines.append("")
    
    # Add abstract
    if metadata.get('abstract'):
        latex_lines.append(r"\begin{abstract}")
        latex_lines.append(metadata['abstract'])
        latex_lines.append(r"\end{abstract}")
        latex_lines.append("")
    
    # Add keywords
    if metadata.get('keywords'):
        latex_lines.append(r"\begin{IEEEkeywords}")
        latex_lines.append(', '.join(metadata['keywords']))
        latex_lines.append(r"\end{IEEEkeywords}")
        latex_lines.append("")
    
    return "\n".join(latex_lines)

def is_grobid_running():
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
            stdout=subprocess.PIPE, text=True
        )
        return CONTAINER_NAME in result.stdout.strip()
    except Exception:
        return False

def start_grobid_server():
    if not shutil.which("docker"):
        raise EnvironmentError("Docker is not installed or not in PATH.")
    if not is_grobid_running():
        try:
            subprocess.run([
                "docker", "run", "-d", "--rm",
                "--name", CONTAINER_NAME,
                "-p", "8070:8070",
                "lfoppiano/grobid:latest-crf",
            ], check=True)
            log.info("✅ GROBID container started in background (port 8070)")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to start GROBID via Docker.\nError: {e}")
        except FileNotFoundError:
            raise EnvironmentError("Docker is not installed or not found in your PATH.")
    else:
        log.info("🚀 GROBID is already up!")

def wait_for_grobid_ready(timeout=20):
    for _ in range(timeout):
        try:
            r = requests.get("http://localhost:8070")
            if r.ok :
                log.info("✅ GROBID is ready.")
                return
        except Exception:
            pass
        log.info("⌛ Waiting for GROBID to be ready...")
        time.sleep(3)
    raise TimeoutError("GROBID did not become ready in time.")


def extract_references(xml_file_path):
    # Parse the XML content
    try:
        tree = etree.parse(xml_file_path)
    except etree.XMLSyntaxError:
        return []
    
    ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
    references = []
    
    # Process each biblStruct element
    for i, bibl in enumerate(tree.xpath('//tei:listBibl//tei:biblStruct', namespaces=ns), 1):
        # Extract authors with improved name handling
        authors = []
        for author in bibl.xpath('.//tei:author', namespaces=ns):
            # Handle all name components
            pers_name = author.xpath('.//tei:persName', namespaces=ns)
            if pers_name:
                # Get all name parts in order
                name_parts = []
                for name_part in pers_name[0].xpath('./*'):
                    if name_part.tag.endswith('forename'):
                        # Handle both first and middle names
                        name_parts.append(name_part.text)
                    elif name_part.tag.endswith('surname'):
                        name_parts.append(name_part.text)
                author_name = ' '.join(filter(None, name_parts))
                if author_name:
                    authors.append(author_name)
        
        # Format author string
        author_str = ''
        if authors:
            if len(authors) > 3:
                author_str = ', '.join(authors[:3]) + ' et al'
            else:
                author_str = ', '.join(authors)
        
        # Extract title with more robust XPath
        title = ''
        title_nodes = bibl.xpath('.//tei:analytic/tei:title[@type="main"]/text()', namespaces=ns)
        if not title_nodes:
            title_nodes = bibl.xpath('.//tei:title[1]/text()', namespaces=ns)
        if title_nodes:
            title = title_nodes[0].strip()
        
        # Extract publication info with fallbacks
        monogr_title = ''
        monogr_nodes = bibl.xpath('.//tei:monogr/tei:title/text()', namespaces=ns)
        if monogr_nodes:
            monogr_title = monogr_nodes[0].strip()
        
        # Extract year with multiple possible locations
        year = ''
        year_nodes = bibl.xpath('.//tei:date[@type="published"]/@when', namespaces=ns)
        if not year_nodes:
            year_nodes = bibl.xpath('.//tei:date/text()', namespaces=ns)
        if year_nodes:
            year = year_nodes[0][:4]  # Take first 4 digits
        
        # Extract volume, issue, and pages with robust handling
        volume = ''
        vol_nodes = bibl.xpath('.//tei:biblScope[@unit="volume"]/text()', namespaces=ns)
        if vol_nodes:
            volume = vol_nodes[0].strip()
        
        issue = ''
        issue_nodes = bibl.xpath('.//tei:biblScope[@unit="issue"]/text()', namespaces=ns)
        if issue_nodes:
            issue = f"({issue_nodes[0].strip()})"
        
        pages = ''
        pages_from = bibl.xpath('.//tei:biblScope[@unit="page"]/@from', namespaces=ns)
        pages_to = bibl.xpath('.//tei:biblScope[@unit="page"]/@to', namespaces=ns)
        if pages_from and pages_to:
            pages = f"{pages_from[0].strip()}–{pages_to[0].strip()}"
        else:
            page_nodes = bibl.xpath('.//tei:biblScope[@unit="page"]/text()', namespaces=ns)
            if page_nodes:
                pages = page_nodes[0].strip()
        
        # Determine reference format
        is_conference = any(x in monogr_title for x in ['Proc.', 'Conf', 'Proceedings'])
        
        if is_conference:
            # Conference paper format
            ref_parts = [
                f"[{i}] {author_str}",
                title,
                f"in: {monogr_title}" if monogr_title else '',
                f"Vol. {volume}" if volume else '',
                year if year else '',
                f"pp. {pages}" if pages else ''
            ]
            ref = ', '.join(filter(None, ref_parts)) + ','
        else:
            # Journal article format
            ref_parts = [
                f"[{i}] {author_str} ({year}) {title}.",
                monogr_title,
                f"{volume}{issue}" if volume or issue else '',
                f"{pages}" if pages else ''
            ]
            ref = ' '.join(filter(None, ref_parts)) + ','
        
        references.append(escape_latex(ref))
    
    return references


def generate_header_and_references(journal_type, pdf_path, title):
    """
    Generates LaTeX header from a PDF using GROBID and journal type.
    
    Parameters:
    - journal_type: 'ieee', 'ieee_thanks_journal', or 'elsevier'
    - pdf_path: path to the input PDF file
    """
    try:
        # Step 1: spin up grobid container
        start_grobid_server()
        wait_for_grobid_ready(20)
        # Step 2: Run curl to get structured XML from GROBID
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        xml_output_path = f"parsers/data/{pdf_name}_structure_xml.xml"
        with open(xml_output_path, 'w') as output_file:
            subprocess.run(
                ["curl", "-s", "--form", f"input=@{pdf_path}", "http://localhost:8070/api/processFulltextDocument"],
                check=True,
                stdout=output_file
            )
            
        metadata=""
        # 1. Extract metadata (returns dictionary)
        metadata = extract_paper_metadata(xml_output_path)
        metadata['title'] = title

        # 2. Extract references (returns array list)
        references = extract_references(xml_output_path)
     
        # 2. Generate LaTeX header
        header = ""
        if journal_type == 'elsevier':
            header = generate_elsevier_latex_header(metadata)
        elif journal_type == 'ieee':
            header = generate_ieee_latex_header(metadata)
        elif journal_type == 'ieee_thanks_journal':
            header = generate_ieee_latex_header_thanks_journal(metadata)
        else:
            raise ValueError("Invalid journal type. Use 'elsevier', 'ieee', or 'ieee_thanks_journal'.")
        
        return header, references
    except Exception as e:
        log.error(f"Error generating header: {e}")

    finally:
        
        if os.path.exists(xml_output_path):
            os.remove(xml_output_path)
            log.info(f"'{xml_output_path}' File deleted.")
        else:
            log.info(f"'{xml_output_path}' File not found.")
        

# generate_header('ieee', 'input/test3/test3.pdf')


# sample output:
# [
# [1] Zhou D, Huang J, Schölkopf B (2006) Learning with hypergraphs: clustering, classification, and embedding. Adv Neural Inf Process Syst 19:1–8,
# [2] Zhang Y, Nie R, Cao J et al (2023) SS-SSAN: a self-supervised subspace attentional network for multi-modal medical image fusion. Artif Intell Rev 56(Suppl 1):421–443,
# [3] Yang Z, Tan Y (2024) The methods for improving large-scale multi-view clustering efficiency: a survey. Artif Intell Rev 57(6):153,
# [4] S. Lee, S. Im, S. Lin, I.S. Kweon, Learning monocular depth in dynamic scenes via instance-aware projection consistency, in: Proc. AAAI Conf. Artif. Intell., Vol. 35, 2021, pp. 1863–1872,
# [5] C. Saharia, J. Ho, W. Chan, T. Salimans, D.J. Fleet, M. Norouzi, Image super-resolution via iterative refinement, IEEE Trans. Pattern Anal. Mach. Intell. 45 (4) (2022) 4713–4726,
# ]
# docker run -d --rm -p 8070:8070 lfoppiano/grobid:latest-crf
# curl -v --form input=@path http://localhost:8070/api/processFulltextDocument > structure_output.xml

from lxml import etree
import subprocess
import requests
import os
import time
import shutil
import json
from latexgenie_parser.utils.logger import Logger
from config import XML_OUTPUT, CONTAINER_NAME, GROBID_BASE_URL
import re
from latexgenie_parser.utils.broken_char import escape_latex
log = Logger.get_logger()



# ------------------- Header Parsing ---------------
class PaperMetadataExtractor:
    """
    A class for extracting paper metadata from TEI XML files produced by GROBID.
    """
    
    def __init__(self):
        self.log = Logger.get_logger()
    
    def _parse_xml_file(self, xml_file_path):
        """Parse XML file and return tree with namespaces."""
        try:
            tree = etree.parse(xml_file_path)
            namespaces = {'tei': 'http://www.tei-c.org/ns/1.0'}
            return tree, namespaces
        except etree.XMLSyntaxError as e:
            self.log.error(f"XML syntax error in {xml_file_path}: {e}")
            return None, None
        except FileNotFoundError:
            self.log.error(f"XML file not found: {xml_file_path}")
            return None, None
        except Exception as e:
            self.log.error(f"Unexpected error parsing XML file {xml_file_path}: {e}")
            return None, None

    def _extract_title(self, tree, namespaces):
        """Extract paper title from XML tree."""
        title_paths = [
            '//tei:teiHeader//tei:title[@type="main"]/text()',
            '//tei:title[1]/text()',
            '//tei:title/text()'
        ]
        
        for path in title_paths:
            try:
                title_elements = tree.xpath(path, namespaces=namespaces)
                if title_elements and title_elements[0].strip():
                    return title_elements[0].strip()
            except Exception as e:
                self.log.warning(f"Error extracting title with path {path}: {e}")
                continue
        
        self.log.warning("No title found in XML")
        return None

    def _extract_abstract(self, tree, namespaces):
        """Extract paper abstract from XML tree."""
        abstract_paths = [
            '//tei:teiHeader//tei:profileDesc/tei:abstract//text()',
            '//tei:abstract//text()',
            '//tei:div[@type="abstract"]//text()',
        ]
        
        for path in abstract_paths:
            try:
                abstract_elements = tree.xpath(path, namespaces=namespaces)
                if abstract_elements:
                    clean_text = [escape_latex(t.strip()) for t in abstract_elements if t.strip()]
                    if clean_text:
                        return ' '.join(clean_text)
            except Exception as e:
                self.log.warning(f"Error extracting abstract with path {path}: {e}")
                continue
        
        self.log.warning("No abstract found in XML")
        return None

    def _extract_keywords(self, tree, namespaces):
        """Extract keywords from XML tree."""
        keyword_paths = [
            '//tei:teiHeader//tei:profileDesc/tei:textClass/tei:keywords/tei:term/text()',
            '//tei:keywords/tei:term/text()',
            '//tei:term/text()',
            '//tei:div[@type="keywords"]//tei:item/text()'
        ]
        
        for path in keyword_paths:
            try:
                keyword_elements = tree.xpath(path, namespaces=namespaces)
                if keyword_elements:
                    keywords = [escape_latex(kw.strip()) for kw in keyword_elements if kw.strip()]
                    if keywords:
                        return keywords
            except Exception as e:
                self.log.warning(f"Error extracting keywords with path {path}: {e}")
                continue
        
        self.log.warning("No keywords found in XML")
        return None

    def _extract_authors(self, tree, namespaces):
        """Extract author information from XML tree."""
        author_paths = [
            '//tei:teiHeader//tei:sourceDesc/tei:biblStruct/tei:analytic/tei:author',
            '//tei:respStmt/tei:name'
        ]
        
        authors = []
        for path in author_paths:
            try:
                author_elements = tree.xpath(path, namespaces=namespaces)
                if author_elements:
                    for author_elem in author_elements:
                        author_data = self._extract_single_author(author_elem, namespaces)
                        if author_data:
                            authors.append(author_data)
                    break  # Use first successful path
            except Exception as e:
                self.log.warning(f"Error extracting authors with path {path}: {e}")
                continue
        
        if not authors:
            self.log.warning("No authors found in XML")
        
        return authors

    def _extract_single_author(self, author_elem, namespaces):
        """Extract information for a single author element."""
        try:
            name = self._extract_author_name(author_elem, namespaces)
            email = self._extract_author_email(author_elem, namespaces)
            affiliations = self._extract_author_affiliations(author_elem, namespaces)
            
            if not name:
                return None
                
            author_data = {'name': escape_latex(name)}
            
            if email:
                author_data['email'] = escape_latex(email)
            
            if affiliations:
                author_data['affiliations'] = affiliations
                
            return author_data
            
        except Exception as e:
            self.log.warning(f"Error extracting single author: {e}")
            return None

    def _extract_author_name(self, author_elem, namespaces):
        """Extract author name from author element."""
        name_paths = [
            './/tei:persName//tei:forename/text() | .//tei:persName//tei:surname/text()',
            './/tei:name//text()',
            './text()'
        ]
        
        for name_path in name_paths:
            try:
                name_parts = author_elem.xpath(name_path, namespaces=namespaces)
                if name_parts:
                    clean_parts = [part.strip() for part in name_parts if part.strip()]
                    if clean_parts:
                        return ' '.join(clean_parts)
            except Exception as e:
                self.log.warning(f"Error extracting author name with path {name_path}: {e}")
                continue
        
        return None

    def _extract_author_email(self, author_elem, namespaces):
        """Extract author email from author element."""
        email_paths = [
            './/tei:email/text()',
            './/tei:addrLine[@type="email"]/text()',
            './/tei:note[@type="email"]/text()'
        ]
        
        for email_path in email_paths:
            try:
                email_elements = author_elem.xpath(email_path, namespaces=namespaces)
                if email_elements and email_elements[0].strip():
                    return email_elements[0].strip()
            except Exception as e:
                self.log.warning(f"Error extracting author email with path {email_path}: {e}")
                continue
        
        return None

    def _extract_author_affiliations(self, author_elem, namespaces):
        """Extract author affiliations from author element."""
        affiliation_paths = [
            './/tei:affiliation',
            './/tei:note[@type="affiliation"]',
            './/tei:orgName/..'
        ]
        
        for aff_path in affiliation_paths:
            try:
                aff_elements = author_elem.xpath(aff_path, namespaces=namespaces)
                if aff_elements:
                    affiliations = []
                    for aff_elem in aff_elements:
                        aff_text_parts = [
                            escape_latex(text.strip()) 
                            for text in aff_elem.xpath('.//text()') 
                            if text.strip()
                        ]
                        if aff_text_parts:
                            affiliations.append(' '.join(aff_text_parts))
                    
                    if affiliations:
                        return affiliations
            except Exception as e:
                self.log.warning(f"Error extracting author affiliations with path {aff_path}: {e}")
                continue
        
        return None

    def extract_paper_metadata(self, xml_file_path):
        """
        Extract paper metadata from a TEI XML file produced by GROBID.
        
        Args:
            xml_file_path (str): Path to the XML file
            
        Returns:
            dict: Dictionary containing title, abstract, keywords, and authors
        """
        result = {
            'title': None,
            'abstract': None,
            'keywords': None,
            'authors': []
        }

        tree, namespaces = self._parse_xml_file(xml_file_path)
        if not tree:
            return result

        result['title'] = self._extract_title(tree, namespaces)
        result['abstract'] = self._extract_abstract(tree, namespaces)
        result['keywords'] = self._extract_keywords(tree, namespaces)
        result['authors'] = self._extract_authors(tree, namespaces)

        print(result)

        return result



    def extract_paper_metadata_as_text(self,xml_file_path):
        """Extract paper metadata as a single text string using existing functions."""
        tree, namespaces = self._parse_xml_file(xml_file_path)
        if not tree:
            return ""
        
        parts = []
        
        # Extract title
        title = self._extract_title(tree, namespaces)
        if title:
            parts.append(title)
        
        # Extract abstract
        abstract = self._extract_abstract(tree, namespaces)
        if abstract:
            parts.append(abstract)
        
        # Extract keywords
        keywords = self._extract_keywords(tree, namespaces)
        if keywords:
            parts.append(', '.join(keywords))
        
        # Extract authors
        authors = self._extract_authors(tree, namespaces)
        if authors:
            for author in authors:
                if author.get('name'):
                    parts.append(author['name'])
                if author.get('email'):
                    parts.append(author['email'])
                if author.get('affiliations'):
                    parts.extend(author['affiliations'])
        
        return ' '.join(parts)





# -------------- Header Latex --------------
class LaTeXHeaderGenerator:
    """
    A class for generating LaTeX headers from paper metadata for different journal types.
    """

    def __init__(self):
        self.log = Logger.get_logger()

    def generate_elsevier_latex_header(self, metadata):
        latex_lines = [r"\begin{frontmatter}", ""]
        
        if metadata.get('title'):
            latex_lines.append(rf"\title{{{metadata['title']}}}")
            latex_lines.append("")

        if metadata.get('authors'):
            latex_lines.extend(self._generate_elsevier_authors_section(metadata['authors']))
        
        if metadata.get('abstract'):
            latex_lines.extend([
                r"\begin{abstract}",
                metadata['abstract'],
                r"\end{abstract}",
                ""
            ])

        if metadata.get('keywords'):
            latex_lines.extend([
                r"\begin{keyword}",
                "    " + ", ".join(metadata['keywords']) + ".",
                r"\end{keyword}",
                ""
            ])

        latex_lines.append(r"\end{frontmatter}")
        return "\n".join(latex_lines)

    def generate_ieee_latex_header(self, metadata):
        latex_lines = []

        if metadata.get('title'):
            latex_lines.append(rf"\title{{{metadata['title']}}}")
            latex_lines.append("")

        if metadata.get('authors'):
            latex_lines.extend(self._generate_ieee_authors_section(metadata['authors']))

        latex_lines.append(r"\maketitle")
        latex_lines.append("")

        if metadata.get('abstract'):
            latex_lines.extend([
                r"\begin{abstract}",
                metadata['abstract'],
                r"\end{abstract}",
                ""
            ])

        if metadata.get('keywords'):
            latex_lines.extend([
                r"\begin{IEEEkeywords}",
                ', '.join(metadata['keywords']),
                r"\end{IEEEkeywords}",
                ""
            ])

        return "\n".join(latex_lines)

    def generate_ieee_latex_header_thanks_journal(self, metadata):
        latex_lines = []

        if metadata.get('title'):
            latex_lines.append(rf"\title{{{metadata['title']}}}")
            latex_lines.append("")

        if metadata.get('authors'):
            latex_lines.extend(self._generate_ieee_thanks_authors_section(metadata['authors']))

        latex_lines.append(r"\maketitle")
        latex_lines.append("")

        if metadata.get('abstract'):
            latex_lines.extend([
                r"\begin{abstract}",
                metadata['abstract'],
                r"\end{abstract}",
                ""
            ])

        if metadata.get('keywords'):
            latex_lines.extend([
                r"\begin{IEEEkeywords}",
                ', '.join(metadata['keywords']),
                r"\end{IEEEkeywords}",
                ""
            ])

        return "\n".join(latex_lines)

    def _generate_elsevier_authors_section(self, authors):
        latex_lines = []
        all_affiliations = []
        for author in authors:
            for aff in author.get('affiliations', []):
                if aff not in all_affiliations:
                    all_affiliations.append(aff)
        aff_mapping = {aff: f"{i+1}" for i, aff in enumerate(all_affiliations)}

        for author in authors:
            name = author.get('name', '')
            email = author.get('email', '')
            aff_indices = [aff_mapping[aff] for aff in author.get('affiliations', [])]
            aff_str = f"[{','.join(aff_indices)}]" if aff_indices else ""
            email_str = rf"\textit{{{email}}}" if email else ""
            latex_lines.append(rf"\author{aff_str}{{{name} {email_str}}}")

        latex_lines.append("")
        for aff, idx in aff_mapping.items():
            latex_lines.append(rf"\address[{idx}]{{{aff}}}")

        latex_lines.append("")
        return latex_lines

    def _generate_ieee_authors_section(self, authors):
        latex_lines = []
        aff_counter = 1
        aff_mapping = {}
        author_entries = []
        emails = []

        for author in authors:
            name = author.get('name', '')
            email = author.get('email', '')
            affiliations = author.get('affiliations', [])

            ref_numbers = []
            for aff in affiliations:
                if aff not in aff_mapping:
                    aff_mapping[aff] = aff_counter
                    aff_counter += 1
                ref_numbers.append(str(aff_mapping[aff]))

            author_entry = name + ''.join([rf'\IEEEauthorrefmark{{{n}}}' for n in ref_numbers])
            author_entries.append(author_entry)

            if email:
                emails.append(email)

        latex_lines.extend([
            r"\author{",
            r"\IEEEauthorblockN{",
            ",\n".join(author_entries),
            "}",
            ""
        ])

        for aff_text, ref_num in sorted(aff_mapping.items(), key=lambda x: x[1]):
            latex_lines.append(
                rf"\IEEEauthorblockA{{\IEEEauthorrefmark{{{ref_num}}}{aff_text}}}"
            )

        if emails:
            latex_lines.append(
                r"\IEEEauthorblockA{Emails: " + ", ".join(emails) + "}"
            )

        latex_lines.append("}")
        return latex_lines

    def _generate_ieee_thanks_authors_section(self, authors):
        latex_lines = []
        author_entries = []
        footnote_map = {}
        
        for author in authors:
            name = author.get("name", "").strip()
            email = author.get("email", "").strip()
            affiliations = author.get("affiliations", [])

            if not name:
                continue

            aff_text = ", ".join(affiliations)
            footnote_text = f"{name} is with {aff_text}"
            if email:
                footnote_text += f" (email: {email})"

            # IEEE prefers one \thanks per author
            entry = rf"{name}\thanks{{{footnote_text}}}"
            author_entries.append(entry)

        latex_lines.append(r"\author{" + " \\and ".join(author_entries) + "}")
        latex_lines.append("")
        return latex_lines





# -------------------- Grobid ---------------
class GrobidManager:
    """
    A class for managing GROBID Docker container operations.
    """
    
    def __init__(self):
        self.log = Logger.get_logger()
    
    def is_grobid_running(self):
        """
        Check if the GROBID Docker container is currently running.
        
        Returns:
            bool: True if GROBID container is running, False otherwise
        """
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
                stdout=subprocess.PIPE, 
                text=True,
                check=True
            )
            return CONTAINER_NAME in result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def start_grobid_server(self):
        """
        Start the GROBID Docker container if it's not already running.
        
        Raises:
            EnvironmentError: If Docker is not installed or not in PATH
            RuntimeError: If failed to start GROBID container
        """
        if not shutil.which("docker"):
            raise EnvironmentError("Docker is not installed or not in PATH.")
        
        if not self.is_grobid_running():
            try:
                subprocess.run([
                    "docker", "run", "-d", "--rm",
                    "--name", CONTAINER_NAME,
                    "-p", "8070:8070",
                    "lfoppiano/grobid:latest-crf",
                ], check=True)
                self.log.info("✅ GROBID container started in background (port 8070)")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to start GROBID via Docker.\nError: {e}")
            except FileNotFoundError:
                raise EnvironmentError("Docker is not installed or not found in your PATH.")
        else:
            self.log.info("🚀 GROBID is already up!")

    def wait_for_grobid_ready(self, timeout=20):
        """
        Wait for GROBID server to become ready and responsive.
        
        Args:
            timeout (int): Maximum time to wait in seconds (default: 20)
            
        Raises:
            TimeoutError: If GROBID doesn't become ready within timeout period
        """
        for _ in range(timeout):
            try:
                response = requests.get(GROBID_BASE_URL, timeout=5)
                if response.ok:
                    self.log.info("✅ GROBID is ready.")
                    return
            except requests.RequestException:
                pass
            
            self.log.info("⌛ Waiting for GROBID to be ready...")
            time.sleep(3)
        
        raise TimeoutError("GROBID did not become ready in time.")





# -------------- references ------------------
class ReferenceExtractor:
    """
    A class for extracting and formatting bibliographic references from TEI XML files produced by GROBID.
    """
    
    def __init__(self):
        self.log = Logger.get_logger()
    
    def _parse_xml_file(self, xml_file_path):
        """Parse XML file and return tree with namespaces."""
        try:
            tree = etree.parse(xml_file_path)
            namespaces = {'tei': 'http://www.tei-c.org/ns/1.0'}
            return tree, namespaces
        except etree.XMLSyntaxError as e:
            self.log.error(f"XML syntax error in {xml_file_path}: {e}")
            return None, None
        except FileNotFoundError:
            self.log.error(f"XML file not found: {xml_file_path}")
            return None, None
        except Exception as e:
            self.log.error(f"Unexpected error parsing XML file {xml_file_path}: {e}")
            return None, None
    
    def extract_references(self, xml_file_path):
        """
        Extract bibliographic references from a TEI XML file produced by GROBID.
        
        Args:
            xml_file_path (str): Path to the XML file containing references
            
        Returns:
            list: List of formatted reference strings with LaTeX escaping applied
        """
        tree, namespaces = self._parse_xml_file(xml_file_path)
        if not tree:
            return []
        
        references = []
        bibl_elements = tree.xpath('//tei:listBibl//tei:biblStruct', namespaces=namespaces)
        
        for i, bibl in enumerate(bibl_elements, 1):
            try:
                reference = self._format_single_reference(bibl, i, namespaces)
                if reference:
                    references.append(escape_latex(reference))
            except Exception as e:
                self.log.warning(f"Error processing reference {i}: {e}")
                continue
        
        return references

    def _format_single_reference(self, bibl_elem, ref_number, namespaces):
        """
        Format a single bibliographic reference from a biblStruct element.
        
        Args:
            bibl_elem: XML element containing bibliographic data
            ref_number (int): Reference number for citation
            namespaces (dict): XML namespaces
            
        Returns:
            str: Formatted reference string or None if extraction fails
        """
        try:
            authors = self._extract_reference_authors(bibl_elem, namespaces)
            title = self._extract_reference_title(bibl_elem, namespaces)
            year = self._extract_reference_year(bibl_elem, namespaces)
            publication_info = self._extract_publication_info(bibl_elem, namespaces)
            
            if not authors and not title:
                return None
            
            # Determine if this is a conference or journal paper
            is_conference = self._is_conference_paper(publication_info.get('venue', ''))
            
            if is_conference:
                return self._format_conference_reference(ref_number, authors, title, year, publication_info)
            else:
                return self._format_journal_reference(ref_number, authors, title, year, publication_info)
                
        except Exception as e:
            self.log.warning(f"Error formatting reference {ref_number}: {e}")
            return None

    def _extract_reference_authors(self, bibl_elem, namespaces):
        """Extract and format author names from a reference."""
        authors = []
        
        for author in bibl_elem.xpath('.//tei:author', namespaces=namespaces):
            author_name = self._extract_reference_author_name(author, namespaces)
            if author_name:
                authors.append(author_name)
        
        return self._format_author_list(authors)

    def _extract_reference_author_name(self, author_elem, namespaces):
        """Extract a single author name from an author element."""
        pers_name = author_elem.xpath('.//tei:persName', namespaces=namespaces)
        if not pers_name:
            return None
        
        name_parts = []
        for name_part in pers_name[0].xpath('./*'):
            if name_part.tag.endswith(('forename', 'surname')) and name_part.text:
                name_parts.append(name_part.text.strip())
        
        return ' '.join(name_parts) if name_parts else None

    def _format_author_list(self, authors):
        """Format a list of authors according to citation style."""
        if not authors:
            return ''
        
        if len(authors) > 3:
            return ', '.join(authors[:3]) + ' et al'
        else:
            return ', '.join(authors)

    def _extract_reference_title(self, bibl_elem, namespaces):
        """Extract the title from a reference."""
        title_paths = [
            './/tei:analytic/tei:title[@type="main"]/text()',
            './/tei:title[1]/text()'
        ]
        
        for path in title_paths:
            title_nodes = bibl_elem.xpath(path, namespaces=namespaces)
            if title_nodes and title_nodes[0].strip():
                return title_nodes[0].strip()
        
        return ''

    def _extract_reference_year(self, bibl_elem, namespaces):
        """Extract the publication year from a reference."""
        year_paths = [
            './/tei:date[@type="published"]/@when',
            './/tei:date/text()'
        ]
        
        for path in year_paths:
            year_nodes = bibl_elem.xpath(path, namespaces=namespaces)
            if year_nodes:
                year_text = str(year_nodes[0])
                # Extract first 4 consecutive digits as year
                year_match = re.search(r'\d{4}', year_text)
                if year_match:
                    return year_match.group()
        
        return ''

    def _extract_publication_info(self, bibl_elem, namespaces):
        """Extract publication venue, volume, issue, and page information."""
        info = {}
        
        # Extract venue (journal/conference name)
        venue_nodes = bibl_elem.xpath('.//tei:monogr/tei:title/text()', namespaces=namespaces)
        info['venue'] = venue_nodes[0].strip() if venue_nodes else ''
        
        # Extract volume
        volume_nodes = bibl_elem.xpath('.//tei:biblScope[@unit="volume"]/text()', namespaces=namespaces)
        info['volume'] = volume_nodes[0].strip() if volume_nodes else ''
        
        # Extract issue
        issue_nodes = bibl_elem.xpath('.//tei:biblScope[@unit="issue"]/text()', namespaces=namespaces)
        info['issue'] = issue_nodes[0].strip() if issue_nodes else ''
        
        # Extract pages
        info['pages'] = self._extract_reference_pages(bibl_elem, namespaces)
        
        return info

    def _extract_reference_pages(self, bibl_elem, namespaces):
        """Extract page range from a reference."""
        pages_from = bibl_elem.xpath('.//tei:biblScope[@unit="page"]/@from', namespaces=namespaces)
        pages_to = bibl_elem.xpath('.//tei:biblScope[@unit="page"]/@to', namespaces=namespaces)
        
        if pages_from and pages_to:
            return f"{pages_from[0].strip()}–{pages_to[0].strip()}"
        
        page_nodes = bibl_elem.xpath('.//tei:biblScope[@unit="page"]/text()', namespaces=namespaces)
        return page_nodes[0].strip() if page_nodes else ''

    def _is_conference_paper(self, venue):
        """Determine if a publication is a conference paper based on venue name."""
        conference_indicators = ['Proc.', 'Conf', 'Proceedings', 'Workshop', 'Symposium']
        return any(indicator in venue for indicator in conference_indicators)

    def _format_conference_reference(self, ref_number, authors, title, year, pub_info):
        """Format a conference paper reference."""
        ref_parts = [f"[{ref_number}] {authors}"]
        
        if title:
            ref_parts.append(title)
        
        if pub_info['venue']:
            ref_parts.append(f"in: {pub_info['venue']}")
        
        if pub_info['volume']:
            ref_parts.append(f"Vol. {pub_info['volume']}")
        
        if year:
            ref_parts.append(year)
        
        if pub_info['pages']:
            ref_parts.append(f"pp. {pub_info['pages']}")
        
        return ', '.join(filter(None, ref_parts)) + ','

    def _format_journal_reference(self, ref_number, authors, title, year, pub_info):
        """Format a journal article reference."""
        # Main citation part
        main_part = f"[{ref_number}] {authors}"
        if year:
            main_part += f" ({year})"
        if title:
            main_part += f" {title}."
        
        # Publication details
        pub_parts = []
        if pub_info['venue']:
            pub_parts.append(pub_info['venue'])
        
        # Volume and issue
        vol_issue = pub_info['volume']
        if pub_info['issue']:
            vol_issue += f"({pub_info['issue']})"
        if vol_issue:
            pub_parts.append(vol_issue)
        
        if pub_info['pages']:
            pub_parts.append(pub_info['pages'])
        
        return ' '.join([main_part] + pub_parts) + ','





@DeprecationWarning
def generate_header_and_references(journal_type, pdf_path):
    """
    Generates LaTeX header from a PDF using GROBID and journal type.
    
    Parameters:
    - journal_type: 'ieee', 'ieee_thanks_journal', or 'elsevier'
    - pdf_path: path to the input PDF file
    """
    try:
        # Initialize class instances
        grobid_manager = GrobidManager()
        metadata_extractor = PaperMetadataExtractor()
        header_generator = LaTeXHeaderGenerator()
        reference_extractor = ReferenceExtractor()
        
        # Step 1: spin up grobid container
        # grobid_manager.start_grobid_server()
        # grobid_manager.wait_for_grobid_ready(60)
        
        # Step 2: Run curl to get structured XML from GROBID
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        xml_output_path = XML_OUTPUT
        with open(xml_output_path, 'w') as output_file:
            subprocess.run(
                ["curl", "-s", "--form", f"input=@{pdf_path}", f"{GROBID_BASE_URL}/api/processFulltextDocument"],
                check=True,
                stdout=output_file
            )
            
        metadata = ""
        # 1. Extract metadata (returns dictionary)
        metadata = metadata_extractor.extract_paper_metadata(xml_output_path)

        # 2. Extract references (returns array list)
        references = reference_extractor.extract_references(xml_output_path)
        print(metadata_extractor.extract_paper_metadata_as_text(xml_output_path))
        
        # 2. Generate LaTeX header
        header = ""
        
        if journal_type == 'elsevier':
            header = header_generator.generate_elsevier_latex_header(metadata)
        elif journal_type == 'ieee':
            header = header_generator.generate_ieee_latex_header(metadata)
        elif journal_type == 'ieee_thanks_journal':
            header = header_generator.generate_ieee_latex_header_thanks_journal(metadata)
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


def get_latex_header(metadata,journal_type='ieee'):
    metadata['abstract'] = escape_latex(metadata['abstract'])
    header_generator = LaTeXHeaderGenerator()
    header = ""
    
    if journal_type == 'elsevier':
        header = header_generator.generate_elsevier_latex_header(metadata)
    elif journal_type == 'ieee':
        header = header_generator.generate_ieee_latex_header(metadata)
    elif journal_type == 'ieee_thanks_journal':
        header = header_generator.generate_ieee_latex_header_thanks_journal(metadata)
    else:
        raise ValueError("Invalid journal type. Use 'elsevier', 'ieee', or 'ieee_thanks_journal'.")

    return header


def get_header_text(pdf_path):
    """
    Generates header text from a PDF using GROBID.

    Parameters:
    - pdf_path: path to the input PDF file
    """
    try:
        # Initialize class instances
        grobid_manager = GrobidManager()
        metadata_extractor = PaperMetadataExtractor()
        
        # Step 1: spin up grobid container
        # grobid_manager.start_grobid_server()
        # grobid_manager.wait_for_grobid_ready(60)
        
        # Step 2: Run curl to get structured XML from GROBID
        xml_output_path = XML_OUTPUT
        with open(xml_output_path, 'w') as output_file:
            subprocess.run(
                ["curl", "-s", "--form", f"input=@{pdf_path}", f"{GROBID_BASE_URL}/api/processFulltextDocument"],
                check=True,
                stdout=output_file
            )
            
        
        header_text = metadata_extractor.extract_paper_metadata_as_text(xml_output_path)
 

        return header_text
    except Exception as e:
        log.error(f"Error generating header: {e}")

    finally:
        if os.path.exists(xml_output_path):
            os.remove(xml_output_path)
            log.info(f"'{xml_output_path}' File deleted.")
        else:
            log.info(f"'{xml_output_path}' File not found.")

def get_reference_list(pdf_path):
    """
    Extracts bibliographic references from a PDF using GROBID.
    
    Parameters:
    - pdf_path: path to the input PDF file
    
    Returns:
    - list: List of formatted reference strings
    """
    try:
        # Initialize class instances
        grobid_manager = GrobidManager()
        reference_extractor = ReferenceExtractor()
        
        # Step 1: spin up grobid container
        # grobid_manager.start_grobid_server()
        # grobid_manager.wait_for_grobid_ready(60)
        
        # Step 2: Run curl to get structured XML from GROBID
        xml_output_path = XML_OUTPUT
        with open(xml_output_path, 'w') as output_file:
            subprocess.run(
                ["curl", "-s", "--form", f"input=@{pdf_path}", f"{GROBID_BASE_URL}/api/processFulltextDocument"],
                check=True,
                stdout=output_file
            )
        
        # Step 3: Extract references
        references = reference_extractor.extract_references(xml_output_path)
        
        return references
        
    except Exception as e:
        log.error(f"Error extracting references: {e}")
        return []
    
    finally:
        if os.path.exists(xml_output_path):
            os.remove(xml_output_path)
            log.info(f"'{xml_output_path}' File deleted.")
        else:
            log.info(f"'{xml_output_path}' File not found.")


# not being used
def get_header_text_reference_list(pdf_path):
    """
    Extracts both header text and reference list from a PDF using GROBID.
    
    Parameters:
    - pdf_path: path to the input PDF file
    
    Returns:
    - tuple: (header_text, reference_list) where header_text is a string 
                and reference_list is a list of formatted reference strings
    """
    try:
        # Initialize class instances
        grobid_manager = GrobidManager()
        metadata_extractor = PaperMetadataExtractor()
        reference_extractor = ReferenceExtractor()
        
        # Step 1: spin up grobid container
        # grobid_manager.start_grobid_server()
        # grobid_manager.wait_for_grobid_ready(60)
        
        # Step 2: Run curl to get structured XML from GROBID
        xml_output_path = XML_OUTPUT
        with open(xml_output_path, 'w') as output_file:
            subprocess.run(
                ["curl", "-s", "--form", f"input=@{pdf_path}", f"{GROBID_BASE_URL}/api/processFulltextDocument"],
                check=True,
                stdout=output_file
            )
        
        # Step 3: Extract header text and references
        header_text = metadata_extractor.extract_paper_metadata_as_text(xml_output_path)
        references = reference_extractor.extract_references(xml_output_path)
        
        return header_text, references
        
    except Exception as e:
        log.error(f"Error extracting header text and references: {e}")
        return "", []
    
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


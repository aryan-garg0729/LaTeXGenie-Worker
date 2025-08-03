import re
from rapidfuzz import process, fuzz
from latexgenie_parser.utils.logger import Logger
log = Logger.get_logger()

def normalize(text):
    text = text.replace('(','')
    text = text.replace(')','')
    text = text.replace('.','')
    text = text.replace(r'$\&$', 'and')
    text = text.replace(r'\&', 'and')
    text = text.replace(r'&', 'and')
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()

def expand_year_variants(part):
    part = part.strip()

    # Match patterns like 'Smith (2001; 2003)' or 'Smith 2001; 2003'
    m = re.match(r'^(.*?)(?:\(([^()]*)\)|\s+((?:\d{4}[a-z]?(?:\s*[;,]\s*\d{4}[a-z]?)*)))$', part)
    if not m:
        return [part]

    author_part = m.group(1).strip()
    years_part = m.group(2) if m.group(2) is not None else m.group(3)
    if not years_part:
        return [part]

    tokens = []
    # Split years_part by commas or semicolons
    for y in re.split(r'[,;]', years_part):
        y = y.strip()
        if re.fullmatch(r'\d{4}[a-z]?', y):
            tokens.append(f"{author_part}, {y}")
        elif re.fullmatch(r'\d{4}', y[:-1]) and y[-1] in ['a', 'b', 'c']:
            tokens.append(f"{author_part}, {y}")
        elif re.fullmatch(r'\d{4}', y):
            tokens.append(f"{author_part}, {y}")
        elif re.fullmatch(r'\d{4}[a-z](?:,[a-z])?', y):
            base = y[:4]
            suffixes = y[4:].split(',')
            tokens.extend([f"{author_part}, {base}{s}" for s in suffixes])
    return tokens

def parse_ieee_citation_block(block):
    block = block.strip("[]")
    refs = []
    parts = re.split(r',(?![^\[]*\])', block)  # split on commas not inside brackets

    for part in parts:
        part = part.strip()

        # Handle "[2]-[4]" style
        m = re.match(r'\[(\d+)\]\s*[-–]\s*\[(\d+)\]', f"[{part}]")
        if m:
            start, end = map(int, m.groups())
            refs.extend([f"[{i}]" for i in range(start, end + 1)])
            continue

        # Handle "2–4" or "2-4"
        if re.match(r'^\d+\s*[-–]\s*\d+$', part):
            start, end = re.split(r'\s*[-–]\s*', part)
            refs.extend([f"[{i}]" for i in range(int(start), int(end) + 1)])
            continue

        # Handle plain number
        if part.isdigit():
            refs.append(f"[{part}]")
    return refs

def fuzzy_match_citations(latex_text, rendered_map,bib_count, threshold=76):
    citation_style = 'ieee'

    normalized_map = {normalize(k): v for k, v in rendered_map.items()}

    regex_patterns = [
            [
                # author, optional author, and author year cases
                r'([A-Z][a-zA-Z\'\-]+(?:\s*)(?:[,]+\s*[A-Z][a-zA-Z\'\-]*)?(?:[.,]?\s*(?:\$?\\?&\$?|and)\s*[A-Z][a-zA-Z\'\-]+[.,]?))\s*[.,]?\s*\(?\s*((?:\d{4}[a-z]?(?:\s*[,;]\s*\d{4}[a-z]?)*))\s*\)?',

                # et al. cases (e.g., Smith et al. 2015 or Smith et al. (2015))
                r'((?:[A-Z][a-zA-Z\'\-]+[\s]?[.,]?[\s]?){1,2}et\s+al[.,]?)\s*[.,]?\s*\(?\s*((?:\d{4}[a-z]?(?:\s*[,;]\s*\d{4}[a-z]?)*))\s*\)?',

                # Single author cases (e.g., Smith 2012, or Smith (2012))   
                r'([A-Z][a-zA-Z\'\-]+)\s*(?:[.,]\s*)?\(?\s*((?:\d{4}[a-z]?(?:\s*[,;]\s*\d{4}[a-z]?)*))\s*\)?',

                # finally just check for brackets
                r'\(((?:[^()]|\([^()]*\))*)\)',
            ],

            [
                # IEEE-style references (e.g., [1], [1-3], [1,2],[7]-[9])
                r'\[\s*\d+\s*\](?:\s*[\-–]\s*\[\s*\d+\s*\])?|\[\s*\d+(?:\s*[\-–]\s*\d+)?(?:\s*,\s*\d+(?:\s*[\-–]\s*\d+)?)*\s*\]',
            ]
        ]

    apa_unique_keys = set()
    for index,batch in enumerate(regex_patterns):
        if index==1 and (len(apa_unique_keys)*5)>bib_count:
            citation_style='apa'
            break
        
        for combined_pattern in batch:
            for match in re.finditer(combined_pattern, latex_text):
                original_span = match.group()
                if len(original_span) > 200:
                    continue
                #log.info(f"\nMatched: {original_span}")
                
                keys = []

                if original_span.startswith('['):
                    # IEEE-style
                    refs = parse_ieee_citation_block(original_span)
                    for ref in refs:
                        #log.info(f"Ref: {ref}")
                        norm = normalize(ref)
                        best = process.extractOne(norm, normalized_map.keys(), scorer=fuzz.ratio)
                        
                        if best and best[1] >= 95:
                            #log.info(f"Ref: {ref}")
                            #log.info(f"Best match: {best}")
                            keys.append(normalized_map[best[0]])
                else:
                    # Author-year-style
                    parts = [part.strip() for part in re.split(r';(?=\s*[A-Z])', original_span)]
                    for part in parts:
                        
                        part = normalize(part)
                        candidates = expand_year_variants(part)
                        
                        for cand in candidates:
                            #log.info(f"Candidate: {cand}")
                            norm = normalize(cand)
                            best = process.extractOne(norm, normalized_map.keys(), scorer=fuzz.ratio)
                            
                            if best and best[1] >= threshold:
                                
                                #log.info(f"Best match: {best}")
                                keys.append(normalized_map[best[0]])

                if keys:
                    if index==0:
                        apa_unique_keys.update(keys)
                    citation = f"\\parencite{{{','.join(sorted(set(keys)))}}}"
                    latex_text = latex_text.replace(original_span, citation)


    log.info(f"apa_unique_keys = {len(apa_unique_keys)}, total bib= {bib_count}")
    return latex_text,citation_style

# latex_text = """
# [19, 28, 48, 57, 72, 100, 104, 121, 131, 153, 159, 176, 178, 180–182, 191]
# [1,2,3]
# [3],[1-2],[23]
# [9]-[12]
# """
# Alberdi et al. (2016,2024j,2024u)
# Alberdi et al. (2016;2024j;2024u)
# Alberdi et al. 2016,2024j,2024u
# Alberdi et al. 2016;2024j,2024u
# Alberdi et al. 2016
# Colligan & Higgins., (2006,1234)
# Colligan and Higgins., (2006;1234)
# Colligan and Higgins., 2006,1234
# Colligan & Higgins., 2006;1234
# Selye 1956
# Selye 1956, 1234, 2012u
# Selye 1956; 1234;2012u
# Selye (1956, 1234;2012u)
# Selye (1956; 1234;2012u)
# (Colligan & Higgins., (2006,1234);Selye (1956; 1234;2012u);Alberdi et al. 2016; Colligan , Higgins et al, (2006,1234))
# Colligan , Higgins et al, (2006,1234)
# Allen, Lu, & Cordiner, 2024; Guo, Li, & Shen, 2024; Zhang et al., 2023
# (Wang), Xu, & Tian, 2023
# (Aandom;Ajk;Akjh78)


# rendered_map ={
#     "(Abbott, \n2012)": "abott2012a",
#     "(Hadi et al.,\n2018)": "hadi2018a",
#     "(Wedyan,\n2014)": "wedyan2014a",
#     "(Padillo et al.,\n2019b)": "padillo2019a",
#     "(Abdelhamid &\nThabtah, 2014)": "abdelhamid2014a",
#   "(Acharya et al.,\n2015)": "acharya2015a",
#   "(Abdelhamid \& Thabtah, (2014))": "al2000a",
#   "(Al-Shargie et\nal., 2015)": "al-shargie2015a",
#   "(Ala’M et al.,\n2021)": "ala2021a",
#   "(Alberdi et al.,\n2016)": "alberdi2016a",
#   "(Alberdi et al.,\n2017)": "alberdi2017a",
#   "(Aljarah et al.,\n2018)": "aljarah2018a",
#   "(Andersson,\n2017)": "andersson2017a",
#   "(Bohat & Arya,\n2018)": "bohat2018a",
#   "(Bohat & Arya,\n2019)": "bohat2019a",
#   "(Boser et al.,\n1992)": "boser1992a",
#   "(Cheema & Singh,\n2019)": "cheema2019a",
#   "(Colligan &\nHiggins, 2006)": "colligan2006a",
#   "(Dahan et al.,\n2014)": "dahan2014a",
#   "(Dedovic et al.,\n2005)": "dedovic2005a",
#   "(Dehzangi et al.,\n2019)": "dehzangi2019a",
#   "(Descheˆnes et al.,\n2015)": "desche2015a",
#   "(Duman,\n2014)": "duman2014a",
#   "(Elgendi &\nMenon, 2020)": "elgendi2020a",
#   "(Espinosa-Garcia et al.,\n2017)": "espinosa-garcia2017a",
#   "(Faris et al.,\n2018)": "faris2018a",
#   "(“Symbolic\nAnalysis of Brain Dynamics Detects Negative Stress,”2017)": "garc2017a",
#   "(“Application of\nEntropy-Based Metrics to Identify Emotional Distress from\nElectroencephalographic Recordings,”2016)": "garc2016a",
#   "(Gaur, McCreadie, et\nal., 2019)": "gaur2019a",
#   "(Gaur et al.,\n2015)": "gaur2015a",
#   "(Gaur et al.,\n2018)": "gaur2018a",
#   "(Gaur, Pachori, et al.,\n2019)": "gaur2019b",
#   "(Gowrisankaran\net al., 2012)": "gowrisankaran2012a",
#   "(Han et al.,\n2011)": "han2011a",
#   "(Hasan & Kim,\n2019)": "hasan2019a",
#   "(H. He et al.,\n2008)": "he2008a",
#   "(J. He et al.,\n2019)": "he2019a",
#   "(Healey & Picard,\n2005)": "healey2005a",
#   "(Hou et al.,\n2015)": "hou2015a",
#   "(Huang et al.,\n2018)": "huang2018a",
#   "(Jebelli et al.,\n2018)": "jebelli2018a",
#   "(Jie et al.,\n2014)": "jie2014a",
#   "(Kannathal et al.,\n2005)": "kannathal2005a",
#   "(Kurniawan et al.,\n2013)": "kurniawan2013a",
#   "(LaValle et al.,\n2004)": "lavalle2004a",
#   "(Lay-Ekuakille\net al., 2013)": "lay-ekuakille2013a",
#   "(Lin et al.,\n2017)": "lin2017a",
#   "(Lu et al.,\n2020)": "lu2020a",
#   "(Mirjalili &\nLewis, 2016)": "mirjalili2016a",
#   "(Munla et al.,\n2015)": "munla2015a",
#   "(Ni et al.,\n2013)": "ni2013a",
#   "(Obiedat et al.,\n2021)": "obiedat2021a",
#   "(“A Hybrid\nArima–Svm Model for the Study of the Remaining Useful Life of Aircraft\nEngines,”2019)": "ord2019a",
#   "(Paiva et al.,\n2016)": "paiva2016a",
#   "(Phan et al.,\n2017)": "phan2017a",
#   "(Ranabir &\nReetu, 2011)": "ranabir2011a",
#   "(Regula et al.,\n2014)": "regula2014a",
#   "(Rizal & Hadiyoso,\n2018)": "rizal2018a",
#   "(Selye,\n1956)": "selye1956a",
#   "(L. Sharma &\nSunkaria, 2019)": "sharma2019a",
#   "(L. D. Sharma &\nBhattacharyya, 2021)": "sharma2021a",
#   "(L. D. Sharma,\nChhabra, et al., 2021)": "sharma2021b",
#   "(L. D. Sharma,\nSaraswat, et al., 2021)": "sharma2021c",
#   "(L. D. Sharma &\nSunkaria, 2018a)": "sharma2018a",
#   "(L. D. Sharma &\nSunkaria, 2018b)": "sharma2018b",
#   "(N. Sharma &\nGedeon, 2012)": "sharma2012a",
#   "(Subhani et al.,\n2017)": "subhani2017a",
#   "(Vanitha &\nKrishnan, 2016)": "vanitha2016a",
#   "(Villarejo et al.,\n2012)": "villarejo2012a",
#   "(Wielgosz et al.,\n2016)": "wielgosz2016a",
#   "(Xin et al.,\n2016)": "xin2016a",
#   "(Yaribeygi et al.,\n2017)": "yaribeygi2017a",
#   "( Guan and Zhang 2020)": "guzang2020a",
# }
# output = fuzzy_match_citations(latex_text, rendered_map,bib_count=100, threshold=80)
# log.info(output)




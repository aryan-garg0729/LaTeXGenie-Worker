# Define diacritics and dotless/special base character cases
import unicodedata
import re
from latexgenie_parser.utils.logger import Logger
log = Logger.get_logger()

# Common diacritical marks
diacritics = [
    '´',
    '`',
    '¨',
    '^',
    'ˆ',
    '~',
    '˜',
    'ˇ',
    '˘',
    '°',
    '¯',
    '˛',
    '¸',
    '˙', 
    '˝',
    '\u0300',  # grave `
    '\u0301',  # acute ´
    '\u0302',  # circumflex ^
    '\u0303',  # tilde ~
    '\u0304',  # macron ¯
    '\u0306',  # breve ˘
    '\u0307',  # dot above ˙
    '\u0308',  # diaeresis ¨
    '\u030A',  # ring above °
    '\u030B',  # double acute ˝
    '\u030C',  # caron ˇ
    '\u0327',  # cedilla ¸
    '\u0328',  # ogonek
    '\u0335',  # short stroke overlay
]

# Base characters to test against
base_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZıȷſ"

# Include special base character cases
special_cases = {
    'ı': 'i',   # dotless i to i
    'ȷ': 'j',   # dotless j to j
    'ſ': 's',   # long s to s
}

def generate_broken_combinations():
    # Generate all broken combinations with mapping to normalized base
    broken_combinations = {
        # Lowercase letters
        'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a', 'ā': 'a', 'ą': 'a', 'ă': 'a',
        'ç': 'c', 'ć': 'c', 'č': 'c', 'ĉ': 'c', 'ċ': 'c',
        'ď': 'd', 'đ': 'd',
        'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e', 'ē': 'e', 'ė': 'e', 'ę': 'e', 'ě': 'e',
        'ƒ': 'f',
        'ğ': 'g', 'ĝ': 'g', 'ġ': 'g', 'ģ': 'g',
        'ĥ': 'h', 'ħ': 'h',
        'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i', 'ī': 'i', 'į': 'i', 'ı': 'i',
        'ĵ': 'j',
        'ķ': 'k',
        'ĺ': 'l', 'ļ': 'l', 'ľ': 'l', 'ł': 'l', 'ŀ': 'l',
        'ñ': 'n', 'ń': 'n', 'ņ': 'n', 'ň': 'n', 'ŋ': 'n',
        'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o', 'ø': 'o', 'ō': 'o', 'ő': 'o', 'ŏ': 'o',
        'ŕ': 'r', 'ř': 'r', 'ŗ': 'r',
        'ś': 's', 'ş': 's', 'š': 's', 'ŝ': 's', 'ș': 's',
        'ť': 't', 'ţ': 't', 'ŧ': 't', 'ț': 't',
        'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u', 'ū': 'u', 'ů': 'u', 'ű': 'u', 'ŭ': 'u', 'ų': 'u',
        'ŵ': 'w',
        'ý': 'y', 'ÿ': 'y', 'ŷ': 'y',
        'ž': 'z', 'ź': 'z', 'ż': 'z',

        # Uppercase letters
        'À': 'A', 'Á': 'A', 'Â': 'A', 'Ã': 'A', 'Ä': 'A', 'Å': 'A', 'Ā': 'A', 'Ą': 'A', 'Ă': 'A',
        'Ç': 'C', 'Ć': 'C', 'Č': 'C', 'Ĉ': 'C', 'Ċ': 'C',
        'Ď': 'D', 'Đ': 'D',
        'È': 'E', 'É': 'E', 'Ê': 'E', 'Ë': 'E', 'Ē': 'E', 'Ė': 'E', 'Ę': 'E', 'Ě': 'E','Ẽ': 'E',
        'Ĝ': 'G', 'Ğ': 'G', 'Ġ': 'G', 'Ģ': 'G',
        'Ĥ': 'H', 'Ħ': 'H',
        'Ì': 'I', 'Í': 'I', 'Î': 'I', 'Ï': 'I', 'Ī': 'I', 'Į': 'I', 'İ': 'I',
        'Ĵ': 'J',
        'Ķ': 'K',
        'Ĺ': 'L', 'Ļ': 'L', 'Ľ': 'L', 'Ł': 'L', 'Ŀ': 'L',
        'Ñ': 'N', 'Ń': 'N', 'Ņ': 'N', 'Ň': 'N', 'Ŋ': 'N',
        'Ò': 'O', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ö': 'O', 'Ø': 'O', 'Ō': 'O', 'Ő': 'O', 'Ŏ': 'O',
        'Ŕ': 'R', 'Ř': 'R', 'Ŗ': 'R',
        'Ś': 'S', 'Ş': 'S', 'Š': 'S', 'Ŝ': 'S', 'Ș': 'S',
        'Ţ': 'T', 'Ť': 'T', 'Ŧ': 'T', 'Ț': 'T',
        'Ù': 'U', 'Ú': 'U', 'Û': 'U', 'Ü': 'U', 'Ū': 'U', 'Ů': 'U', 'Ű': 'U', 'Ŭ': 'U', 'Ų': 'U',
        'Ŵ': 'W',
        'Ý': 'Y', 'Ÿ': 'Y', 'Ŷ': 'Y',
        'Ž': 'Z', 'Ź': 'Z', 'Ż': 'Z'}
    # Generate broken combos: diacritic + base and base + diacritic
    for base in base_chars:
        for mark in diacritics:
            combo1 = mark + base
            combo2 = base + mark
            broken_combinations[combo1] = base if base not in special_cases else special_cases[base]
            broken_combinations[combo2] = base if base not in special_cases else special_cases[base]

    log.info(f"Broken combinations: {len(broken_combinations)}")
    return broken_combinations

def replace_broken(text, diacritics_map):
    """
    Replace diacritic characters in text, but skip:
    - Content between $...$ (e.g., $formula$)
    - Escaped dollars (\$)
    Preserves $ delimiters in output.
    """
    # Split into segments, keeping $...$ blocks intact
    segments = re.split(r'(<!>.*?<!>)', text)
    
    processed_segments = []
    for i, segment in enumerate(segments):
        # Skip processing for $...$ blocks (odd indices)
        if i % 2 == 1:
            processed_segments.append(segment)  # Keep $...$ as-is
        else:
            # Replace diacritics in non-$ segments
            for diacritic, replacement in diacritics_map.items():
                segment = segment.replace(diacritic, replacement)
            processed_segments.append(segment)
    
    return ''.join(processed_segments)

def escape_latex(text) -> str:
    if not isinstance(text, str):
        return ""
    
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

    def replacer(part: str) -> str:
        if part.startswith('<!>') and part.endswith('<!>'):
            return part  # preserve inline LaTeX
        return ''.join(replacements.get(c, c) for c in part)

    parts = re.split(r'(<!>.*?<!>)', text)
    escaped = ''.join(replacer(part) for part in parts)
    return escaped.replace('<!>', '$')

BROKEN_COMBINATIONS = generate_broken_combinations()

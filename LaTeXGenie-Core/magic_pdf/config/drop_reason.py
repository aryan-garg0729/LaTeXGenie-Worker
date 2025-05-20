class DropReason:
    TEXT_BLCOK_HOR_OVERLAP = 'text_block_horizontal_overlap'  # Text blocks have horizontal overlap, making it impossible to accurately determine text order
    USEFUL_BLOCK_HOR_OVERLAP = (
        'useful_block_horizontal_overlap'  # Blocks that need to be retained have horizontal overlap
    )
    COMPLICATED_LAYOUT = 'complicated_layout'  # Complex layout, currently not supported
    TOO_MANY_LAYOUT_COLUMNS = 'too_many_layout_columns'  # Currently does not support layouts with more than 2 columns
    COLOR_BACKGROUND_TEXT_BOX = 'color_background_text_box'  # Contains colored blocks in the PDF, which change the reading order; currently does not support PDFs with colored text blocks
    HIGH_COMPUTATIONAL_lOAD_BY_IMGS = (
        'high_computational_load_by_imgs'  # Contains special images, resulting in excessive computational load, thus discarded
    )
    HIGH_COMPUTATIONAL_lOAD_BY_SVGS = (
        'high_computational_load_by_svgs'  # Special SVG images, resulting in excessive computational load, thus discarded
    )
    HIGH_COMPUTATIONAL_lOAD_BY_TOTAL_PAGES = 'high_computational_load_by_total_pages'  # Computational load exceeds capacity; current method consumes too much computational resources
    MISS_DOC_LAYOUT_RESULT = 'missing doc_layout_result'  # Layout analysis failed
    Exception = '_exception'  # Exception occurred during parsing
    ENCRYPTED = 'encrypted'  # PDF is encrypted
    EMPTY_PDF = 'total_page=0'  # Total number of PDF pages is 0
    NOT_IS_TEXT_PDF = 'not_is_text_pdf'  # Not a text-based PDF, cannot be directly parsed
    DENSE_SINGLE_LINE_BLOCK = 'dense_single_line_block'  # Cannot clearly segment paragraphs
    TITLE_DETECTION_FAILED = 'title_detection_failed'  # Failed to detect title
    TITLE_LEVEL_FAILED = (
        'title_level_failed'  # Failed to analyze title levels (e.g., level 1, level 2, level 3 titles)
    )
    PARA_SPLIT_FAILED = 'para_split_failed'  # Failed to recognize paragraphs
    PARA_MERGE_FAILED = 'para_merge_failed'  # Failed to merge paragraphs
    NOT_ALLOW_LANGUAGE = 'not_allow_language'  # Unsupported language
    SPECIAL_PDF = 'special_pdf'
    PSEUDO_SINGLE_COLUMN = 'pseudo_single_column'  # Unable to accurately determine text column layout
    CAN_NOT_DETECT_PAGE_LAYOUT = 'can_not_detect_page_layout'  # Unable to analyze page layout
    NEGATIVE_BBOX_AREA = 'negative_bbox_area'  # Scaling caused bbox area to be negative
    OVERLAP_BLOCKS_CAN_NOT_SEPARATION = (
        'overlap_blocks_can_t_separation'  # Unable to separate overlapping blocks
    )

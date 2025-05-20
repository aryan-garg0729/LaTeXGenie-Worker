"""Custom fields for span dimension."""
# Whether the span is merged across pages
CROSS_PAGE = 'cross_page'

"""
Custom fields for block dimension
"""
# Whether lines in the block are deleted
LINES_DELETED = 'lines_deleted'

# Default value for table recognition max time
TABLE_MAX_TIME_VALUE = 400

# Maximum length for pp_table_result
TABLE_MAX_LEN = 480

# Table master structure dictionary
TABLE_MASTER_DICT = 'table_master_structure_dict.txt'

# Table master directory
TABLE_MASTER_DIR = 'table_structure_tablemaster_infer/'

# PP detect model directory
DETECT_MODEL_DIR = 'ch_PP-OCRv4_det_infer'

# PP recognition model directory
REC_MODEL_DIR = 'ch_PP-OCRv4_rec_infer'

# PP recognition character dictionary path
REC_CHAR_DICT = 'ppocr_keys_v1.txt'

# PP recognition copy recognition directory
PP_REC_DIRECTORY = '.paddleocr/whl/rec/ch/ch_PP-OCRv4_rec_infer'

# PP recognition copy detection directory
PP_DET_DIRECTORY = '.paddleocr/whl/det/ch/ch_PP-OCRv4_det_infer'


class MODEL_NAME:
    # PP table structure algorithm
    TABLE_MASTER = 'tablemaster'
    # Struct eqtable
    STRUCT_EQTABLE = 'struct_eqtable'

    DocLayout_YOLO = 'doclayout_yolo'

    LAYOUTLMv3 = 'layoutlmv3'

    YOLO_V8_MFD = 'yolo_v8_mfd'

    UniMerNet_v2_Small = 'unimernet_small'

    RAPID_TABLE = 'rapid_table'

    YOLO_V11_LangDetect = 'yolo_v11n_langdetect'


PARSE_TYPE_TXT = 'txt'
PARSE_TYPE_OCR = 'ocr'

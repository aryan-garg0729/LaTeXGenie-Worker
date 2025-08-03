import os
import requests
import zipfile
from config import COLAB_URL
from latexgenie_parser.utils.logger import Logger
from latexgenie_parser.utils.file_utils import safe_remove_dir

log = Logger.get_logger()

def knowledge_extractor(args):
    # Replace this with your actual public ngrok URL from Colab
    

    # Local path to your test PDF
    pdf_path = args.pdf_path
    zip_path = 'output.zip'
    unzip_dir = 'unzipped_output'

    # Endpoint to hit
    url = f'{COLAB_URL}/convert'

    # Upload and download
    with open(pdf_path, 'rb') as f:
        files = {'file': (pdf_path, f, 'application/pdf')}
        log.info("Uploading...")
        response = requests.post(url, files=files)

        if response.status_code == 200:
            with open(zip_path, 'wb') as out_file:
                out_file.write(response.content)
            log.info("✅ Downloaded output.zip successfully.")
        else:
            log.error(f"❌ Request failed with status code {response.status_code}")
        

    # remove old unzipped folder
    safe_remove_dir(unzip_dir)
    # Unzip the downloaded file
    os.makedirs(unzip_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(unzip_dir)

    log.info("✅ Unzipped output.zip successfully.")


def convert_pdf():

    input_path = 'data/input.pdf'
    output_dir = 'data/output'

    os.system(f'rm -rf {output_dir}')

    os.system(f'python latexgenie_core/magic_pdf/tools/cli.py -p {input_path} -o {output_dir}')


    return True

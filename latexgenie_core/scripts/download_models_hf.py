import json
import os
import requests
from huggingface_hub import snapshot_download


def download_json(url):
    # Download the JSON file
    response = requests.get(url)
    response.raise_for_status()  # Check if the request was successful
    return response.json()


def download_and_modify_json(json_file, local_filename, modifications):
    if os.path.exists(local_filename):
        data = json.load(open(local_filename))

    else:
      # read json file
      with open(json_file, 'r', encoding='utf-8') as f:
          data = json.load(f)
    
    # Modify content
    for key, value in modifications.items():
        data[key] = value

    # Save the modified content
    with open(local_filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


if __name__ == '__main__':

    mineru_patterns = [
        "models/Layout/YOLO/*",
        "models/MFD/YOLO/*",
        "models/MFR/unimernet_hf_small_2503/*",
        "models/OCR/paddleocr_torch/*",
    ]
    model_dir = snapshot_download('piyush070920/genie-core', allow_patterns=mineru_patterns,token="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")

    layoutreader_pattern = [
        "*.json",
        "*.safetensors",
    ]
    layoutreader_model_dir = snapshot_download('hantian/layoutreader', allow_patterns=layoutreader_pattern)

    model_dir = model_dir + '/models'
    print(f'model_dir is: {model_dir}')
    print(f'layoutreader_model_dir is: {layoutreader_model_dir}')

    json_path = 'latexgenie_core/magic-pdf.template.json'
    config_file_name = 'magic-pdf.json'
    home_dir = os.path.expanduser('~')
    config_file = os.path.join(home_dir, config_file_name)

    json_mods = {
        'models-dir': model_dir,
        'layoutreader-model-dir': layoutreader_model_dir,
        "llm-aided-config":{
                'title_aided': {
                "api_key": "AIzaSyDBttYA_FjK0sadAxuLjiYO_oNbO7LzmTk",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "model": "gemini-2.0-flash",
                "enable":True
            }
        },
        "device-mode": "cuda"
    }

    download_and_modify_json(json_path, config_file, json_mods)
    print(f'The configuration file has been configured successfully, the path is: {config_file}')

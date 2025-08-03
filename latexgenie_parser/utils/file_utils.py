import os
import shutil
import zipfile
from typing import List

def safe_remove_dir(path: str) -> str:
    if not os.path.exists(path):
        return f"Path does not exist: {path}"
    if not os.path.isdir(path):
        return f"Path is not a directory: {path}"
    try:
        shutil.rmtree(path)
        return f"Successfully removed directory and all contents: {path}"
    except Exception as e:
        return f"Error removing directory: {e}"

def copy_images(src_dir: str, dest_dir: str):
    safe_remove_dir(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    if os.path.exists(src_dir):
        for file in os.listdir(src_dir):
            if file.endswith((".png", ".jpg")):
                src_path = os.path.join(src_dir, file)
                dest_path = os.path.join(dest_dir, file)
                with open(src_path, "rb") as src_file:
                    with open(dest_path, "wb") as dest_file:
                        dest_file.write(src_file.read())

def zip_output(output_dir: str, zip_path: str):
    safe_remove_dir(os.path.dirname(zip_path))
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, output_dir))

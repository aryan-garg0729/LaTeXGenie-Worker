from pathlib import Path
from setuptools import setup, find_packages
from magic_pdf.libs.version import __version__


def parse_requirements(filename):
    with open(filename) as f:
        lines = f.read().splitlines()

    requires = []

    for line in lines:
        if "http" in line:
            pkg_name_without_url = line.split('@')[0].strip()
            requires.append(pkg_name_without_url)
        else:
            requires.append(line)

    return requires


if __name__ == '__main__':
    with Path(Path(__file__).parent,
              'README.md').open(encoding='utf-8') as file:
        long_description = file.read()
    setup(
        name="latexgenie_core",  # Project name
        version=__version__,  # Automatically fetch version number from tag
        license="AGPL-3.0",
        packages=find_packages() + ["magic_pdf.resources"] + ["magic_pdf.model.sub_modules.ocr.paddleocr2pytorch.pytorchocr.utils.resources"],  # Include all packages
        package_data={
            "magic_pdf.resources": ["**"],  # Include all files under magic_pdf.resources directory
            "magic_pdf.model.sub_modules.ocr.paddleocr2pytorch.pytorchocr.utils.resources": ["**"],  # Include all files under pytorchocr.resources directory
        },
        install_requires=parse_requirements('requirements.txt'),  # Third-party libraries required by the project
        extras_require={
            "lite": [
                    "paddleocr==2.7.3",
                    "paddlepaddle==3.0.0b1;platform_system=='Linux'",
                    "paddlepaddle==2.6.1;platform_system=='Windows' or platform_system=='Darwin'",
            ],
            "full": [
                     "matplotlib>=3.10,<4",
                     "ultralytics>=8.3.48,<9",  # yolov8, formula detection
                     "doclayout_yolo==0.0.2b1",  # doclayout_yolo
                     "dill>=0.3.8,<1",  # doclayout_yolo
                     "rapid_table>=1.0.5,<2.0.0",  # rapid_table
                     "PyYAML>=6.0.2,<7",  # yaml
                     "ftfy>=6.3.1,<7",  # unimernet_hf
                     "shapely>=2.0.7,<3",  # imgaug-paddleocr2pytorch
                     "pyclipper>=1.3.0,<2",  # paddleocr2pytorch
                     "omegaconf>=2.3.0,<3",  # paddleocr2pytorch
            ],
            "full_old_linux": [
                    "matplotlib>=3.10,<=3.10.1",
                    "ultralytics>=8.3.48,<=8.3.104",  # yolov8, formula detection
                    "doclayout_yolo==0.0.2b1",  # doclayout_yolo
                    "dill==0.3.8",  # doclayout_yolo
                    "PyYAML==6.0.2",  # yaml
                    "ftfy==6.3.1",  # unimernet_hf
                    "shapely==2.1.0",  # imgaug-paddleocr2pytorch
                    "pyclipper==1.3.0.post6",  # paddleocr2pytorch
                    "omegaconf==2.3.0",  # paddleocr2pytorch
                    "albumentations==1.4.20", # 1.4.21 introduced simsimd which doesn't support Linux systems from 2019 or earlier
                    "rapid_table==1.0.3",  # rapid_table's new version depends on onnxruntime which doesn't support Linux systems from 2019 or earlier
            ],
        },
        description="A practical tool for converting PDF to Markdown",  # Short description
        long_description=long_description,  # Detailed description
        long_description_content_type="text/markdown",  # If README is in Markdown format
        project_urls={
            "Home": "https://mineru.net/",
            "Repository": "https://github.com/opendatalab/MinerU",
        },
        keywords=["magic-pdf, mineru, MinerU, convert, pdf, markdown"],
        classifiers=[
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
            "Programming Language :: Python :: 3.13",
        ],
        python_requires=">=3.10,<4",  # Python version required by the project
        entry_points={
            "console_scripts": [
                "magic-pdf = magic_pdf.tools.cli:cli",
                "magic-pdf-dev = magic_pdf.tools.cli_dev:cli" 
            ],
        },  # Executable commands provided by the project
        include_package_data=True,  # Whether to include non-code files such as data files, configuration files, etc.
        zip_safe=False,  # Whether to use zip file format for packaging, generally set to False
    )
